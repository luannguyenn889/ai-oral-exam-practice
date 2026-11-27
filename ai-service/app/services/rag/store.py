"""Facade tương thích cho kho lưu trữ & truy vấn RAG (`chroma_client`, `bm25_index`, `indexer`, `retriever`, `status`)."""

from app.services.rag.bm25_index import (
    _bm25_cache,
    _bm25_lock,
    _course_stats_cache,
    _empty_file_hashes,
    _get_course_stats,
    get_bm25_index,
    invalidate_bm25_cache,
)
from app.services.rag.chroma_client import (
    _batched_collection_delete,
    _batched_collection_upsert,
    _get_course_index_lock,
    get_chroma_collection,
    get_collection_name,
    list_course_files,
    warmup_rag_background,
)
from app.services.rag.embeddings import embed_texts, get_reranker_model
from app.services.rag.indexer import index_documents
from app.services.rag.retriever import format_rag_context, query_relevant_chunks
from app.services.rag.status import get_rag_status

__all__ = [
    "_bm25_cache",
    "_bm25_lock",
    "_course_stats_cache",
    "_empty_file_hashes",
    "_batched_collection_delete",
    "_batched_collection_upsert",
    "_get_course_index_lock",
    "_get_course_stats",
    "embed_texts",
    "format_rag_context",
    "get_bm25_index",
    "get_chroma_collection",
    "get_collection_name",
    "get_rag_status",
    "get_reranker_model",
    "index_documents",
    "invalidate_bm25_cache",
    "list_course_files",
    "query_relevant_chunks",
    "warmup_rag_background",
]
