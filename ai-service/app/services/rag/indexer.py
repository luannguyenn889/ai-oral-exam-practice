"""Pipeline đồng bộ và lập chỉ mục tài liệu giáo trình vào ChromaDB."""

from __future__ import annotations

import hashlib
import os
import threading
from typing import Any, Callable, Optional

from app.config import settings
from app.services.rag.bm25_index import (
    _empty_file_hashes,
    _get_course_stats,
    invalidate_bm25_cache,
)
from app.services.rag.chroma_client import (
    _batched_collection_delete,
    _batched_collection_upsert,
    _get_course_index_lock,
    _resolve_store_dep,
    get_chroma_collection,
    get_collection_name,
    list_course_files,
)
from app.services.rag.chunking import CHUNKING_VERSION, chunk_text
from app.services.rag.course_config import (
    resolve_course_chunking_strategy,
    resolve_course_embedding_provider,
    set_course_rag_config,
)
from app.services.rag.embeddings import (
    IndexingCancelledError,
    embed_texts,
    get_active_embedding_name,
    normalize_course_id,
)
from app.services.rag.extractors import extract_document_with_pages


def _build_chunk_metadatas(
    file_chunks: list[dict[str, Any]],
    source: str,
    norm_course: str,
    content_hash: str,
    active_embedding_name: str,
    active_strategy: str,
) -> list[dict[str, Any]]:
    metadatas: list[dict[str, Any]] = []
    for chunk in file_chunks:
        meta: dict[str, Any] = {
            "source": source,
            "course_id": norm_course,
            "index": chunk["index"],
            "content_hash": content_hash,
            "embedding_model": active_embedding_name,
            "chunking_strategy": active_strategy,
            "chunking_version": CHUNKING_VERSION,
            "section_title": chunk.get("section_title", ""),
            "noise_score": float(chunk.get("noise_score", 0.0)),
            "noise_type": str(chunk.get("noise_type", "clean")),
        }
        if chunk.get("page_start") is not None:
            meta["page_start"] = int(chunk["page_start"])
        if chunk.get("page_end") is not None:
            meta["page_end"] = int(chunk["page_end"])
        metadatas.append(meta)
    return metadatas


def _collect_existing_by_source(collection: Any, norm_course: str) -> dict[str, dict[str, Any]]:
    try:
        existing = collection.get(where={"course_id": norm_course}, include=["metadatas"])
    except Exception:
        existing = {"ids": [], "metadatas": []}

    existing_by_source: dict[str, dict[str, Any]] = {}
    for chunk_id, meta in zip(existing.get("ids", []), existing.get("metadatas", [])):
        meta = meta or {}
        source = meta.get("source")
        if source:
            item = existing_by_source.setdefault(
                source,
                {
                    "ids": [],
                    "content_hash": meta.get("content_hash"),
                    "embedding_model": meta.get("embedding_model"),
                    "chunking_strategy": meta.get("chunking_strategy") or "legacy",
                    "chunking_version": meta.get("chunking_version") or "v1",
                },
            )
            item["ids"].append(chunk_id)
    return existing_by_source


def index_documents(
    course_id: str = "default",
    force_reindex: bool = False,
    embedding_provider: Optional[str] = None,
    chunking_strategy: Optional[str] = None,
    progress_callback: Optional[Callable[[dict[str, Any]], None]] = None,
    cancel_event: Optional[threading.Event] = None,
) -> dict[str, Any]:
    """Đồng bộ tài liệu trong data/documents/{course_id}/ với ChromaDB (khóa theo học phần, cô lập lỗi từng file)."""

    def _report(**payload: Any) -> None:
        if progress_callback is not None:
            try:
                progress_callback(payload)
            except Exception:
                pass

    norm_course = normalize_course_id(course_id)
    if (isinstance(embedding_provider, str) and embedding_provider.strip()) or (
        isinstance(chunking_strategy, str) and chunking_strategy.strip()
    ):
        set_course_rag_config(
            norm_course,
            embedding_provider=embedding_provider,
            chunking_strategy=chunking_strategy,
        )
    effective_provider = resolve_course_embedding_provider(norm_course, embedding_provider)
    effective_strategy = resolve_course_chunking_strategy(norm_course, chunking_strategy)

    course_dir = str(settings.course_documents_dir(norm_course))
    get_coll = _resolve_store_dep("get_chroma_collection", get_chroma_collection)
    embed_fn = _resolve_store_dep("embed_texts", embed_texts)
    collection = get_coll(effective_provider)
    coll_name = get_collection_name(effective_provider)
    active_embedding_name = get_active_embedding_name(effective_provider)
    course_lock = _get_course_index_lock(norm_course, coll_name)

    with course_lock:
        if force_reindex:
            invalidate_bm25_cache(norm_course, clear_empty_cache=True)

        all_files = list_course_files(norm_course)
        total_files = len(all_files)
        _report(
            phase="scanning",
            percent=3,
            total_files=total_files,
            processed_files=0,
            message=f"Đang kiểm tra {total_files} tài liệu trong kho học phần {norm_course}...",
        )

        existing_by_source = _collect_existing_by_source(collection, norm_course)
        current_sources: set[str] = set()
        added_or_updated = 0
        removed = 0
        warnings: list[str] = []

        for file_idx, file_path in enumerate(all_files):
            if cancel_event is not None and cancel_event.is_set():
                raise IndexingCancelledError("Tác vụ lập chỉ mục đã bị hủy.")
            source = os.path.relpath(file_path, course_dir).replace("\\", "/")
            current_sources.add(source)
            file_start_pct = 5 + int((file_idx / max(1, total_files)) * 88)
            file_span_pct = max(1, int(88 / max(1, total_files)))

            try:
                with open(file_path, "rb") as source_file:
                    content_hash = hashlib.sha256(source_file.read()).hexdigest()
            except OSError as exc:
                warnings.append(f"Không đọc được file {source}: {exc}")
                continue

            previous = existing_by_source.get(source)
            empty_key = (norm_course, coll_name, source)
            if not force_reindex and _empty_file_hashes.get(empty_key) == content_hash and not previous:
                _report(
                    phase="scanning",
                    percent=min(94, file_start_pct + file_span_pct),
                    processed_files=file_idx + 1,
                    total_files=total_files,
                    current_file=source,
                    message=f"Bỏ qua file rỗng đã kiểm tra ({file_idx + 1}/{total_files}): {source}",
                )
                continue

            if (
                not force_reindex
                and previous
                and previous["content_hash"] == content_hash
                and previous.get("embedding_model") == active_embedding_name
                and previous.get("chunking_strategy") == effective_strategy
                and previous.get("chunking_version") == CHUNKING_VERSION
            ):
                _report(
                    phase="scanning",
                    percent=min(94, file_start_pct + file_span_pct),
                    processed_files=file_idx + 1,
                    total_files=total_files,
                    current_file=source,
                    message=f"Giữ nguyên chỉ mục đã có ({file_idx + 1}/{total_files}): {source}",
                )
                continue

            _report(
                phase="extracting",
                percent=min(94, file_start_pct + max(1, file_span_pct // 10)),
                processed_files=file_idx,
                total_files=total_files,
                current_file=source,
                processed_chunks=0,
                total_chunks=0,
                message=f"Đang đọc & cắt đoạn tài liệu ({file_idx + 1}/{total_files}): {source}",
            )

            try:
                raw_text, page_entries = extract_document_with_pages(file_path, raise_on_error=True)
                file_chunks = chunk_text(
                    raw_text,
                    source_name=source,
                    course_id=norm_course,
                    strategy=effective_strategy,
                    embedding_provider=effective_provider,
                    page_entries=page_entries or None,
                )
                old_ids = previous["ids"] if previous else []
                if file_chunks:
                    _empty_file_hashes.pop(empty_key, None)
                    texts = [chunk["text"] for chunk in file_chunks]
                    chunk_total = len(texts)

                    _report(
                        phase="embedding",
                        percent=min(94, file_start_pct + max(2, file_span_pct // 6)),
                        processed_files=file_idx,
                        total_files=total_files,
                        current_file=source,
                        processed_chunks=0,
                        total_chunks=chunk_total,
                        message=f"Đang tạo vector (0/{chunk_total} đoạn) — {source}",
                    )

                    def _on_embed_progress(done: int, total: int) -> None:
                        ratio = done / max(1, total)
                        embed_pct = file_start_pct + int(file_span_pct * (0.15 + 0.75 * ratio))
                        _report(
                            phase="embedding",
                            percent=min(94, embed_pct),
                            processed_files=file_idx,
                            total_files=total_files,
                            current_file=source,
                            processed_chunks=done,
                            total_chunks=total,
                            message=f"Đang tạo vector ({done}/{total} đoạn) — {source}",
                        )

                    embed_kwargs: dict[str, Any] = {
                        "task": "document",
                        "provider": effective_provider,
                    }
                    if progress_callback is not None:
                        embed_kwargs["progress_callback"] = _on_embed_progress
                    if cancel_event is not None:
                        embed_kwargs["cancel_event"] = cancel_event
                    embeddings = embed_fn(texts, **embed_kwargs)

                    _report(
                        phase="storing",
                        percent=min(95, file_start_pct + int(file_span_pct * 0.95)),
                        processed_files=file_idx,
                        total_files=total_files,
                        current_file=source,
                        processed_chunks=chunk_total,
                        total_chunks=chunk_total,
                        message=f"Đang lưu {chunk_total} đoạn vào ChromaDB — {source}",
                    )

                    metadatas = _build_chunk_metadatas(
                        file_chunks,
                        source,
                        norm_course,
                        content_hash,
                        active_embedding_name,
                        effective_strategy,
                    )
                    _batched_collection_upsert(
                        collection=collection,
                        ids=[chunk["id"] for chunk in file_chunks],
                        documents=texts,
                        metadatas=metadatas,
                        embeddings=embeddings,
                    )
                    stale_ids = list(set(old_ids) - {chunk["id"] for chunk in file_chunks})
                    if stale_ids:
                        _batched_collection_delete(collection, stale_ids)
                        removed += len(stale_ids)
                    added_or_updated += len(file_chunks)
                else:
                    if old_ids:
                        _batched_collection_delete(collection, old_ids)
                        removed += len(old_ids)
                    _empty_file_hashes[empty_key] = content_hash
                    warnings.append(f"Tài liệu '{source}' không trích xuất được đoạn nội dung hợp lệ nào.")
            except IndexingCancelledError:
                raise
            except Exception as exc:
                old_ids = previous["ids"] if previous else []
                if old_ids:
                    try:
                        _batched_collection_delete(collection, old_ids)
                        removed += len(old_ids)
                    except Exception:
                        pass
                warn_msg = f"Lỗi xử lý file '{source}' (đã bỏ qua để tiếp tục các file khác): {exc}"
                warnings.append(warn_msg)
                print(f"[AI-SERVICE] {warn_msg}", flush=True)

            _report(
                phase="storing",
                percent=min(95, file_start_pct + file_span_pct),
                processed_files=file_idx + 1,
                total_files=total_files,
                current_file=source,
                message=f"Hoàn tất tài liệu ({file_idx + 1}/{total_files}): {source}",
            )

        for source, item in existing_by_source.items():
            if source not in current_sources and item["ids"]:
                _batched_collection_delete(collection, item["ids"])
                removed += len(item["ids"])

        _report(
            phase="finalizing",
            percent=97,
            processed_files=total_files,
            total_files=total_files,
            message="Đang làm mới chỉ mục BM25 và kiểm đếm dữ liệu...",
        )
        invalidate_bm25_cache(norm_course)

        stats = _get_course_stats(collection, norm_course, coll_name)
        course_chunk_count = int(stats.get("count", 0))

        result = {
            "course_id": norm_course,
            "status": "ready" if course_chunk_count > 0 else "empty",
            "total_files": len(all_files),
            "added_or_updated_chunks": added_or_updated,
            "removed_chunks": removed,
            "total_chunks": course_chunk_count,
            "embedding_model": active_embedding_name,
            "chunking_strategy": effective_strategy,
            "warnings": warnings,
        }
        _report(
            phase="completed",
            percent=100,
            processed_files=total_files,
            total_files=total_files,
            message=f"Hoàn tất đồng bộ ({course_chunk_count} đoạn từ {total_files} tài liệu).",
        )
        return result
