"""Chỉ mục từ khóa thưa BM25Okapi và bộ nhớ đệm thống kê kho tri thức theo học phần."""

from __future__ import annotations

import threading
from typing import Any, Optional

from app.services.rag.chroma_client import (
    _resolve_store_dep,
    get_chroma_collection,
    get_collection_name,
)
from app.services.rag.chunking import CHUNKING_VERSION
from app.services.rag.embeddings import normalize_course_id, tokenize_text

_bm25_cache: dict[str, tuple[Any, list[dict[str, Any]]]] = {}
_bm25_lock = threading.Lock()
_course_stats_cache: dict[tuple[str, str, int], dict[str, Any]] = {}
_empty_file_hashes: dict[tuple[str, str, str], str] = {}


def invalidate_bm25_cache(course_id: Optional[str] = None, clear_empty_cache: bool = False) -> None:
    """Làm mới bộ nhớ đệm BM25 và thống kê metadata của một hoặc toàn bộ học phần."""
    with _bm25_lock:
        if course_id:
            norm = normalize_course_id(course_id)
            for k in list(_bm25_cache.keys()):
                if k == norm or k.startswith(f"{norm}::"):
                    _bm25_cache.pop(k, None)
            for k in list(_course_stats_cache.keys()):
                if k[0] == norm:
                    _course_stats_cache.pop(k, None)
            if clear_empty_cache:
                for k in list(_empty_file_hashes.keys()):
                    if k[0] == norm:
                        _empty_file_hashes.pop(k, None)
        else:
            _bm25_cache.clear()
            _course_stats_cache.clear()
            if clear_empty_cache:
                _empty_file_hashes.clear()


def _get_course_stats(
    collection: Any,
    norm_course: str,
    coll_name: str,
) -> dict[str, Any]:
    cache_key = (norm_course, coll_name, id(collection))
    with _bm25_lock:
        cached = _course_stats_cache.get(cache_key)
        if cached is not None:
            return dict(cached)

    try:
        existing = collection.get(where={"course_id": norm_course}, include=["metadatas"])
    except Exception:
        existing = {"ids": [], "metadatas": []}

    ids = existing.get("ids", []) or []
    metadatas = existing.get("metadatas", []) or []
    count = len(ids)
    outdated_chunks = 0
    found_strategies: set[str] = set()
    sources_in_db: set[str] = set()

    for m in metadatas:
        meta = m or {}
        found_strategies.add(meta.get("chunking_strategy") or "legacy")
        if meta.get("chunking_version") != CHUNKING_VERSION:
            outdated_chunks += 1
        if meta.get("source"):
            sources_in_db.add(str(meta["source"]))

    stats = {
        "count": count,
        "outdated_chunks": outdated_chunks,
        "found_strategies": sorted(found_strategies),
        "sources": sorted(sources_in_db),
    }
    with _bm25_lock:
        _course_stats_cache[cache_key] = stats
    return dict(stats)


def get_bm25_index(
    course_id: str = "default", provider: Optional[str] = None
) -> tuple[Any, list[dict[str, Any]]]:
    """Khởi tạo hoặc lấy chỉ mục BM25 của một học phần (course_id) từ ChromaDB."""
    norm_course = normalize_course_id(course_id)
    coll_name = get_collection_name(provider)
    cache_key = f"{norm_course}::{coll_name}"
    with _bm25_lock:
        if cache_key in _bm25_cache:
            return _bm25_cache[cache_key]

    get_coll = _resolve_store_dep("get_chroma_collection", get_chroma_collection)
    collection = get_coll(provider)
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
                    "noise_score": meta.get("noise_score"),
                    "noise_type": meta.get("noise_type"),
                    "page_start": meta.get("page_start"),
                    "page_end": meta.get("page_end"),
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
        with _bm25_lock:
            _bm25_cache[cache_key] = (bm25_index, indexed_docs)
        return bm25_index, indexed_docs
    except Exception:
        return None, []
