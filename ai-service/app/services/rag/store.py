"""Module lưu trữ vector ChromaDB, chỉ mục từ khóa BM25 và truy vấn Hybrid RAG theo từng học phần.

Nhiệm vụ:
- Quản lý kết nối ChromaDB theo từng nhà cung cấp embedding (`get_collection_name`, `get_chroma_collection`) và nạp sẵn nền (`warmup_rag_background`).
- Quản lý bộ nhớ đệm chỉ mục từ khóa thưa BM25Okapi (`get_bm25_index`, `invalidate_bm25_cache`) cô lập theo `course_id`.
- Đồng bộ & lập chỉ mục tài liệu (`index_documents`, `list_course_files`):
    + Quét toàn bộ file (.docx, .pdf, .txt) trong thư mục của học phần; tính SHA-256 `content_hash` để chỉ lập chỉ mục lại khi nội dung, model embedding hoặc chiến lược chunking thay đổi.
    + Lưu metadata (`source`, `course_id`, `index`, `content_hash`, `embedding_model`, `chunking_strategy`, `section_title`) và dọn sạch các chunk thừa.
- Truy vấn lai kép (`query_relevant_chunks`) & định dạng ngữ cảnh (`format_rag_context`):
    + Kết hợp Dense Cosine Search (ChromaDB) + Sparse Keyword Search (BM25) bằng Reciprocal Rank Fusion (RRF, k=60), hỗ trợ tùy chọn Cross-Encoder Rerank.
- Báo cáo trạng thái kho tri thức (`get_rag_status`) cho giao diện Quản lý tài liệu.
"""

import glob
import hashlib
import os
from typing import Any, Callable, Optional

import chromadb

from app.config import settings
from app.services.rag.course_config import (
    get_course_rag_config,
    resolve_course_chunking_strategy,
    resolve_course_embedding_provider,
    set_course_rag_config,
)
from app.services.rag.chunking import (
    CHUNKING_VERSION,
    DEFAULT_CHUNKING_STRATEGY,
    chunk_text,
    get_chunking_strategy_label,
    is_low_value_rag_chunk,
    normalize_chunking_strategy,
)
from app.services.rag.embeddings import (
    clean_oral_query,
    embed_texts,
    get_active_embedding_name,
    get_embedding_model,
    get_reranker_model,
    normalize_course_id,
    normalize_embedding_provider,
    tokenize_text,
)
from app.services.rag.extractors import (
    extract_text_from_docx,
    extract_text_from_pdf,
    extract_text_from_txt,
)

_chroma_client: Optional[chromadb.ClientAPI] = None
_collections: dict[str, Any] = {}
_bm25_cache: dict[str, tuple[Any, list[dict[str, Any]]]] = {}


def get_collection_name(provider: Optional[str] = None) -> str:
    prov = normalize_embedding_provider(provider)
    if prov == "gemini":
        return f"{settings.collection_prefix}_gemini"
    if prov == "e5-small":
        return f"{settings.collection_prefix}_e5_small"
    return settings.collection_prefix


def get_chroma_collection(provider: Optional[str] = None) -> Any:
    """Khởi tạo ChromaDB client và collection."""
    global _chroma_client
    db_dir = str(settings.resolved_chroma_db_dir)
    os.makedirs(db_dir, exist_ok=True)
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=db_dir)
    coll_name = get_collection_name(provider)
    if coll_name not in _collections:
        _collections[coll_name] = _chroma_client.get_or_create_collection(
            name=coll_name,
            metadata={"hnsw:space": "cosine"},
        )
    return _collections[coll_name]


def warmup_rag_background() -> None:
    """Nạp trước ChromaDB và model embedding mặc định trong nền để không làm chậm lúc khởi động."""
    try:
        provider = normalize_embedding_provider(settings.embedding_provider)
        get_chroma_collection(provider)
        if provider in ("local", "e5-small"):
            target_name = get_active_embedding_name(provider)
            get_embedding_model(target_name)
        print("[AI-SERVICE] Warmup RAG model nen hoan tat.", flush=True)
    except Exception as exc:
        print(f"[AI-SERVICE] Bo qua warmup nen (se nap khi dung): {exc}", flush=True)


def invalidate_bm25_cache(course_id: Optional[str] = None) -> None:
    if course_id:
        norm = normalize_course_id(course_id)
        for k in list(_bm25_cache.keys()):
            if k == norm or k.startswith(f"{norm}::"):
                _bm25_cache.pop(k, None)
    else:
        _bm25_cache.clear()


def get_bm25_index(
    course_id: str = "default", provider: Optional[str] = None
) -> tuple[Any, list[dict[str, Any]]]:
    """Khởi tạo hoặc lấy chỉ mục BM25 của một học phần (course_id) từ ChromaDB."""
    norm_course = normalize_course_id(course_id)
    cache_key = f"{norm_course}::{get_collection_name(provider)}"
    if cache_key in _bm25_cache:
        return _bm25_cache[cache_key]

    collection = get_chroma_collection(provider)
    try:
        course_data = collection.get(
            where={"course_id": norm_course},
            include=["documents", "metadatas"],
        )
    except Exception:
        course_data = {"ids": [], "documents": [], "metadatas": []}

    bm25_docs: list[dict[str, Any]] = []
    if course_data and course_data.get("documents"):
        for chunk_id, doc, meta in zip(
            course_data["ids"], course_data["documents"], course_data["metadatas"]
        ):
            meta = meta or {}
            bm25_docs.append(
                {
                    "text": doc,
                    "id": chunk_id,
                    "source": meta.get("source", "Không rõ"),
                    "course_id": meta.get("course_id", norm_course),
                    "index": meta.get("index", 0),
                    "section_title": meta.get("section_title", ""),
                }
            )

    try:
        from rank_bm25 import BM25Okapi

        indexed_docs = []
        tokenized_corpus = []
        for item in bm25_docs:
            tokens = tokenize_text(item["text"])
            if tokens:
                indexed_docs.append(item)
                tokenized_corpus.append(tokens)
        bm25_index = BM25Okapi(tokenized_corpus) if tokenized_corpus else None
        _bm25_cache[cache_key] = (bm25_index, indexed_docs)
        return bm25_index, indexed_docs
    except Exception:
        return None, []


def list_course_files(course_id: str = "default") -> list[str]:
    course_dir = str(settings.course_documents_dir(course_id))
    all_files: list[str] = []
    for pattern in ("**/*.docx", "**/*.txt", "**/*.pdf"):
        for path in glob.glob(os.path.join(course_dir, pattern), recursive=True):
            if not os.path.basename(path).startswith("~$"):
                all_files.append(path)
    return sorted(set(all_files))


def index_documents(
    course_id: str = "default",
    force_reindex: bool = False,
    embedding_provider: Optional[str] = None,
    chunking_strategy: Optional[str] = None,
    progress_callback: Optional[Callable[[dict[str, Any]], None]] = None,
) -> dict[str, Any]:
    """Đồng bộ tài liệu trong data/documents/{course_id}/ với ChromaDB (hỗ trợ báo tiến độ theo từng bước)."""

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
    collection = get_chroma_collection(effective_provider)
    active_embedding_name = get_active_embedding_name(effective_provider)
    active_strategy = effective_strategy

    if force_reindex:
        invalidate_bm25_cache(norm_course)

    all_files = list_course_files(norm_course)
    total_files = len(all_files)
    _report(
        phase="scanning",
        percent=3,
        total_files=total_files,
        processed_files=0,
        message=f"Đang kiểm tra {total_files} tài liệu trong kho học phần {norm_course}...",
    )

    try:
        existing = collection.get(
            where={"course_id": norm_course},
            include=["metadatas"],
        )
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

    current_sources: set[str] = set()
    added_or_updated = 0
    removed = 0

    for file_idx, file_path in enumerate(all_files):
        source = os.path.relpath(file_path, course_dir).replace("\\", "/")
        current_sources.add(source)
        file_start_pct = 5 + int((file_idx / max(1, total_files)) * 88)
        file_span_pct = max(1, int(88 / max(1, total_files)))

        try:
            with open(file_path, "rb") as source_file:
                content_hash = hashlib.sha256(source_file.read()).hexdigest()
        except OSError:
            continue

        previous = existing_by_source.get(source)
        if (
            not force_reindex
            and previous
            and previous["content_hash"] == content_hash
            and previous.get("embedding_model") == active_embedding_name
            and previous.get("chunking_strategy") == active_strategy
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

        extension = os.path.splitext(file_path)[1].lower()
        if extension == ".docx":
            raw_text = extract_text_from_docx(file_path)
        elif extension == ".pdf":
            raw_text = extract_text_from_pdf(file_path)
        else:
            raw_text = extract_text_from_txt(file_path)

        file_chunks = chunk_text(
            raw_text,
            source_name=source,
            course_id=norm_course,
            strategy=active_strategy,
            embedding_provider=effective_provider,
        )
        if file_chunks:
            old_ids = previous["ids"] if previous else []
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

            if progress_callback is not None:
                embeddings = embed_texts(
                    texts,
                    task="document",
                    provider=effective_provider,
                    progress_callback=_on_embed_progress,
                )
            else:
                embeddings = embed_texts(texts, task="document", provider=effective_provider)

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

            collection.upsert(
                ids=[chunk["id"] for chunk in file_chunks],
                documents=texts,
                metadatas=[
                    {
                        "source": source,
                        "course_id": norm_course,
                        "index": chunk["index"],
                        "content_hash": content_hash,
                        "embedding_model": active_embedding_name,
                        "chunking_strategy": active_strategy,
                        "chunking_version": CHUNKING_VERSION,
                        "section_title": chunk.get("section_title", ""),
                    }
                    for chunk in file_chunks
                ],
                embeddings=embeddings,
            )
            stale_ids = set(old_ids) - {chunk["id"] for chunk in file_chunks}
            if stale_ids:
                collection.delete(ids=list(stale_ids))
            added_or_updated += len(file_chunks)

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
            collection.delete(ids=item["ids"])
            removed += len(item["ids"])

    _report(
        phase="finalizing",
        percent=97,
        processed_files=total_files,
        total_files=total_files,
        message="Đang làm mới chỉ mục BM25 và kiểm đếm dữ liệu...",
    )
    invalidate_bm25_cache(norm_course)

    try:
        after_course = collection.get(where={"course_id": norm_course}, include=[])
        course_chunk_count = len(after_course.get("ids", []))
    except Exception:
        course_chunk_count = 0

    result = {
        "course_id": norm_course,
        "status": "ready" if course_chunk_count > 0 else "empty",
        "total_files": len(all_files),
        "added_or_updated_chunks": added_or_updated,
        "removed_chunks": removed,
        "total_chunks": course_chunk_count,
        "embedding_model": active_embedding_name,
        "chunking_strategy": active_strategy,
    }
    _report(
        phase="completed",
        percent=100,
        processed_files=total_files,
        total_files=total_files,
        message=f"Hoàn tất đồng bộ ({course_chunk_count} đoạn từ {total_files} tài liệu).",
    )
    return result


def query_relevant_chunks(
    query_text: str,
    course_id: str = "default",
    top_k: int = 3,
    score_threshold: Optional[float] = None,
    search_mode: str = "hybrid",
    use_rerank: bool = False,
    embedding_provider: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Truy vấn nâng cao các đoạn giáo trình liên quan nhất (Hybrid Dense + BM25 + RRF + Optional Reranker)."""
    if not query_text or not query_text.strip():
        return []
    if search_mode not in {"dense", "bm25", "hybrid"}:
        raise ValueError("search_mode phải là 'dense', 'bm25' hoặc 'hybrid'.")
    if top_k < 1:
        return []

    norm_course = normalize_course_id(course_id)
    effective_provider = resolve_course_embedding_provider(norm_course, embedding_provider)
    collection = get_chroma_collection(effective_provider)

    try:
        existing_course = collection.get(where={"course_id": norm_course}, include=[])
        course_count = len(existing_course.get("ids", []))
    except Exception:
        course_count = 0

    if course_count == 0:
        index_documents(
            course_id=norm_course,
            force_reindex=False,
            embedding_provider=effective_provider,
        )
        try:
            existing_course = collection.get(where={"course_id": norm_course}, include=[])
            course_count = len(existing_course.get("ids", []))
        except Exception:
            course_count = 0

    if course_count == 0:
        return []

    cleaned_query = clean_oral_query(query_text)
    candidate_pool_size = min(max(top_k * 6, 20), course_count)
    candidates: dict[str, dict[str, Any]] = {}

    if search_mode in ("hybrid", "dense"):
        query_vector = embed_texts([cleaned_query], task="query", provider=effective_provider)
        results = collection.query(
            query_embeddings=query_vector,
            n_results=candidate_pool_size,
            where={"course_id": norm_course},
            include=["documents", "metadatas", "distances"],
        )
        if results and results.get("documents"):
            docs = results["documents"][0]
            metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
            distances = (
                results["distances"][0] if results.get("distances") else [0.0] * len(docs)
            )
            ids = results.get("ids", [[]])[0]
            for rank, (chunk_id, doc, meta, dist) in enumerate(
                zip(ids, docs, metas, distances), 1
            ):
                meta = meta or {}
                sim = round(1.0 - float(dist), 4)
                candidates[chunk_id] = {
                    "id": chunk_id,
                    "text": doc,
                    "source": meta.get("source", "Không rõ"),
                    "course_id": meta.get("course_id", norm_course),
                    "index": meta.get("index", 0),
                    "section_title": meta.get("section_title", ""),
                    "dense_sim": sim,
                    "dense_distance": round(float(dist), 4),
                    "dense_rank": rank,
                    "bm25_score": None,
                    "bm25_rank": 999,
                    "rrf_score": 0.0,
                }

    if search_mode in ("hybrid", "bm25"):
        bm25, bm25_docs = get_bm25_index(norm_course, provider=effective_provider)
        if bm25 and bm25_docs:
            tokenized_q = tokenize_text(cleaned_query)
            if tokenized_q:
                bm25_scores = bm25.get_scores(tokenized_q)
                top_bm25_indices = sorted(
                    range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True
                )[:candidate_pool_size]

                for rank, idx in enumerate(top_bm25_indices, 1):
                    score = float(bm25_scores[idx])
                    if score <= 0:
                        continue
                    b_doc = bm25_docs[idx]
                    chunk_id = b_doc["id"]
                    if chunk_id not in candidates:
                        candidates[chunk_id] = {
                            "id": chunk_id,
                            "text": b_doc["text"],
                            "source": b_doc["source"],
                            "course_id": b_doc.get("course_id", norm_course),
                            "index": b_doc["index"],
                            "section_title": b_doc.get("section_title", ""),
                            "dense_sim": None,
                            "dense_rank": 999,
                            "bm25_score": round(score, 2),
                            "bm25_rank": rank,
                            "rrf_score": 0.0,
                        }
                    else:
                        candidates[chunk_id]["bm25_score"] = round(score, 2)
                        candidates[chunk_id]["bm25_rank"] = rank

    if not candidates:
        return []

    raw_candidates = list(candidates.values())
    filtered_candidates = [
        c
        for c in raw_candidates
        if not is_low_value_rag_chunk(str(c.get("text", "")), str(c.get("section_title", "")))
    ]
    candidate_list = filtered_candidates if filtered_candidates else raw_candidates
    k_constant = 60.0
    for c in candidate_list:
        retrieval_sources = []
        if c.get("dense_rank", 999) != 999:
            retrieval_sources.append("dense")
        if c.get("bm25_rank", 999) != 999:
            retrieval_sources.append("BM25")
        c["retrieved_by"] = " + ".join(retrieval_sources) or "unknown"
        score_dense = (
            1.0 / (k_constant + c["dense_rank"]) if c.get("dense_rank", 999) < 999 else 0.0
        )
        score_bm25 = (
            1.0 / (k_constant + c["bm25_rank"]) if c.get("bm25_rank", 999) < 999 else 0.0
        )
        c["rrf_score"] = round(score_dense + score_bm25, 5)

    candidate_list.sort(key=lambda x: x["rrf_score"], reverse=True)

    if use_rerank and len(candidate_list) > 1:
        reranker = get_reranker_model()
        if reranker is not None:
            pairs = [[cleaned_query, c["text"]] for c in candidate_list]
            try:
                rerank_scores = reranker.predict(pairs)
                for c, r_score in zip(candidate_list, rerank_scores):
                    c["rerank_score"] = round(float(r_score), 4)
                    c["method"] = f"{search_mode.title()} + Cross-Encoder Rerank"
                candidate_list.sort(key=lambda x: x["rerank_score"], reverse=True)
            except Exception:
                for c in candidate_list:
                    c["method"] = f"{search_mode.title()} RRF"
        else:
            for c in candidate_list:
                c["method"] = f"{search_mode.title()} RRF"
    else:
        for c in candidate_list:
            c["method"] = f"{search_mode.title()} RRF"

    if score_threshold is not None:
        candidate_list = [
            c
            for c in candidate_list
            if c.get("dense_rank", 999) == 999
            or (c.get("dense_sim") is not None and c["dense_sim"] >= score_threshold)
        ]

    return candidate_list[:top_k]


def format_rag_context(chunks: list[dict[str, Any]]) -> str:
    """Định dạng danh sách các đoạn trích xuất thành văn bản sạch sẽ để chèn vào Prompt của LLM."""
    if not chunks:
        return ""
    formatted = []
    for i, c in enumerate(chunks, 1):
        method_str = f" | Phương thức: {c.get('method', 'RAG')}" if "method" in c else ""
        sim_str = (
            f" (Cosine: {c.get('dense_sim', 'N/A')}; RRF: {c.get('rrf_score', 'N/A')}; "
            f"Rerank: {c.get('rerank_score', 'N/A')}{method_str})"
        )
        formatted.append(
            f"[Đoạn trích {i} - ID: {c.get('id', 'N/A')} - Nguồn: {c['source']} - "
            f"Chunk: {c.get('index', 'N/A')}{sim_str}]\n{c['text']}"
        )
    return "\n\n---\n\n".join(formatted)


def get_rag_status(
    course_id: str = "default", embedding_provider: Optional[str] = None
) -> dict[str, Any]:
    """Lấy thông tin trạng thái kho tri thức RAG của một học phần."""
    norm_course = normalize_course_id(course_id)
    saved_cfg = get_course_rag_config(norm_course)
    effective_provider = resolve_course_embedding_provider(norm_course, embedding_provider)
    course_dir = str(settings.course_documents_dir(norm_course))
    try:
        collection = get_chroma_collection(effective_provider)
        existing = collection.get(where={"course_id": norm_course}, include=["metadatas"])
        ids = existing.get("ids", [])
        metadatas = existing.get("metadatas", []) or []
        count = len(ids)

        indexed_strategy = saved_cfg.get("chunking_strategy") or DEFAULT_CHUNKING_STRATEGY
        if count > 0:
            found_strategies = {
                (m or {}).get("chunking_strategy") or "legacy" for m in metadatas
            }
            if len(found_strategies) == 1:
                indexed_strategy = next(iter(found_strategies))
            elif found_strategies:
                indexed_strategy = next(iter(sorted(found_strategies)))

        all_paths = list_course_files(norm_course)
        files = [os.path.relpath(p, course_dir).replace("\\", "/") for p in all_paths]

        bm25, _ = get_bm25_index(norm_course, provider=effective_provider) if count else (None, [])
        has_bm25 = bm25 is not None

        return {
            "course_id": norm_course,
            "status": "ready" if count > 0 else "empty",
            "total_chunks": count,
            "total_files": len(files),
            "files": files,
            "embedding_provider": effective_provider,
            "embedding_model": get_active_embedding_name(effective_provider),
            "reranker_model": settings.reranker_model_name,
            "chunking_strategy": indexed_strategy,
            "hybrid_bm25_active": has_bm25,
            "reranker_enabled_by_default": False,
            "search_modes_available": ["dense"] + (["bm25", "hybrid"] if has_bm25 else []),
            "features": [
                get_chunking_strategy_label(indexed_strategy),
                "Course-level Isolation (course_id metadata filter)",
                "ChromaDB HNSW Dense Cosine Search",
                *(["BM25 Okapi Sparse Keyword Search", "Reciprocal Rank Fusion (RRF)"] if has_bm25 else []),
                "Cross-Encoder available (opt-in for experiment)",
            ],
            "error": None,
        }
    except Exception as e:
        return {
            "course_id": norm_course,
            "status": "error",
            "total_chunks": 0,
            "total_files": 0,
            "files": [],
            "embedding_provider": effective_provider,
            "embedding_model": get_active_embedding_name(effective_provider),
            "reranker_model": settings.reranker_model_name,
            "chunking_strategy": saved_cfg.get("chunking_strategy") or DEFAULT_CHUNKING_STRATEGY,
            "hybrid_bm25_active": False,
            "reranker_enabled_by_default": False,
            "search_modes_available": [],
            "features": [],
            "error": str(e),
        }
