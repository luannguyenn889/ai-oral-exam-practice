"""Báo cáo trạng thái kho tri thức RAG của từng học phần cho giao diện quản lý."""

from __future__ import annotations

import os
from typing import Any, Optional

from app.config import settings
from app.services.rag.bm25_index import _get_course_stats, get_bm25_index
from app.services.rag.chroma_client import (
    _resolve_store_dep,
    get_chroma_collection,
    get_collection_name,
    list_course_files,
)
from app.services.rag.chunking import (
    CHUNKING_VERSION,
    DEFAULT_CHUNKING_STRATEGY,
    get_chunking_strategy_label,
)
from app.services.rag.course_config import (
    get_course_rag_config,
    resolve_course_embedding_provider,
)
from app.services.rag.embeddings import (
    get_active_embedding_name,
    get_active_reranker_name,
    normalize_course_id,
)


def get_rag_status(
    course_id: str = "default", embedding_provider: Optional[str] = None
) -> dict[str, Any]:
    """Lấy thông tin trạng thái kho tri thức RAG của một học phần."""
    norm_course = normalize_course_id(course_id)
    saved_cfg = get_course_rag_config(norm_course)
    effective_provider = resolve_course_embedding_provider(norm_course, embedding_provider)
    course_dir = str(settings.course_documents_dir(norm_course))
    try:
        get_coll = _resolve_store_dep("get_chroma_collection", get_chroma_collection)
        bm25_fn = _resolve_store_dep("get_bm25_index", get_bm25_index)
        collection = get_coll(effective_provider)
        coll_name = get_collection_name(effective_provider)
        stats = _get_course_stats(collection, norm_course, coll_name)
        count = int(stats.get("count", 0))
        outdated_chunks = int(stats.get("outdated_chunks", 0))
        found_strategies = stats.get("found_strategies", [])
        sources_in_db = set(stats.get("sources", []))

        indexed_strategy = saved_cfg.get("chunking_strategy") or DEFAULT_CHUNKING_STRATEGY
        if count > 0 and found_strategies:
            indexed_strategy = found_strategies[0]

        all_paths = list_course_files(norm_course)
        files = [os.path.relpath(p, course_dir).replace("\\", "/") for p in all_paths]
        unindexed_files = [f for f in files if f not in sources_in_db]

        bm25, _ = bm25_fn(norm_course, provider=effective_provider) if count else (None, [])
        has_bm25 = bm25 is not None

        warnings: list[str] = []
        if outdated_chunks > 0:
            warnings.append(
                f"Có {outdated_chunks}/{count} đoạn được lập chỉ mục theo phiên bản cũ (chưa đạt {CHUNKING_VERSION}). Nên bấm lập chỉ mục lại."
            )
        if unindexed_files and count > 0:
            warnings.append(f"Có {len(unindexed_files)} tài liệu mới trên ổ đĩa chưa được đồng bộ vào chỉ mục.")
        needs_reindex = outdated_chunks > 0 or (len(files) > 0 and count == 0) or bool(unindexed_files)

        return {
            "course_id": norm_course,
            "status": "ready" if count > 0 else "empty",
            "total_chunks": count,
            "total_files": len(files),
            "files": files,
            "embedding_provider": effective_provider,
            "embedding_model": get_active_embedding_name(effective_provider),
            "reranker_provider": saved_cfg.get("reranker_provider", "bge-m3"),
            "reranker_model": get_active_reranker_name(saved_cfg.get("reranker_provider")),
            "chunking_strategy": indexed_strategy,
            "hybrid_bm25_active": has_bm25,
            "reranker_enabled_by_default": False,
            "needs_reindex": needs_reindex,
            "outdated_chunks": outdated_chunks,
            "warnings": warnings,
            "search_modes_available": ["dense"] + (["bm25", "hybrid"] if has_bm25 else []),
            "features": [
                get_chunking_strategy_label(indexed_strategy),
                "Course-level Isolation (course_id metadata filter)",
                "ChromaDB HNSW Dense Cosine Search",
                *(["BM25 Okapi Sparse Keyword Search", "Reciprocal Rank Fusion (RRF)"] if has_bm25 else []),
                f"Cross-Encoder Reranker ({saved_cfg.get('reranker_provider', 'bge-m3')})",
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
            "reranker_provider": saved_cfg.get("reranker_provider", "bge-m3"),
            "reranker_model": get_active_reranker_name(saved_cfg.get("reranker_provider")),
            "chunking_strategy": saved_cfg.get("chunking_strategy") or DEFAULT_CHUNKING_STRATEGY,
            "hybrid_bm25_active": False,
            "reranker_enabled_by_default": False,
            "needs_reindex": False,
            "outdated_chunks": 0,
            "warnings": [],
            "search_modes_available": [],
            "features": [],
            "error": str(e),
        }
