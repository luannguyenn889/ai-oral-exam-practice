"""Quản lý kết nối ChromaDB, warmup nền, quét tệp học phần và khóa đồng bộ theo học phần."""

from __future__ import annotations

import glob
import os
import sys
import threading
from typing import Any, Optional

import chromadb

from app.config import settings
from app.services.rag.embeddings import (
    get_active_embedding_name,
    get_embedding_model,
    get_reranker_model,
    normalize_course_id,
    normalize_embedding_provider,
)

_CHROMA_BATCH_SIZE = 500

_chroma_client: Optional[chromadb.ClientAPI] = None
_collections: dict[str, Any] = {}
_course_index_locks: dict[str, threading.Lock] = {}
_course_locks_guard = threading.Lock()


def _resolve_store_dep(name: str, default: Any) -> Any:
    """Ưu tiên lấy dependency đã được monkey-patch qua facade `rag.store` khi chạy kiểm thử."""
    store_mod = sys.modules.get("app.services.rag.store")
    if store_mod is not None and hasattr(store_mod, name):
        return getattr(store_mod, name)
    return default


def _get_course_index_lock(course_id: str, collection_name: str) -> threading.Lock:
    key = f"{normalize_course_id(course_id)}::{collection_name}"
    with _course_locks_guard:
        if key not in _course_index_locks:
            _course_index_locks[key] = threading.Lock()
        return _course_index_locks[key]


def _batched_collection_upsert(
    collection: Any,
    ids: list[str],
    documents: list[str],
    metadatas: list[dict[str, Any]],
    embeddings: list[list[float]],
    batch_size: int = _CHROMA_BATCH_SIZE,
) -> None:
    for start in range(0, len(ids), batch_size):
        end = start + batch_size
        collection.upsert(
            ids=ids[start:end],
            documents=documents[start:end],
            metadatas=metadatas[start:end],
            embeddings=embeddings[start:end],
        )


def _batched_collection_delete(
    collection: Any,
    ids: list[str],
    batch_size: int = _CHROMA_BATCH_SIZE,
) -> None:
    for start in range(0, len(ids), batch_size):
        collection.delete(ids=ids[start : start + batch_size])


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
    """Nạp trước ChromaDB, embedding mặc định và reranker mặc định trong nền."""
    try:
        provider = normalize_embedding_provider(settings.embedding_provider)
        get_chroma_collection(provider)
        if provider in ("local", "e5-small"):
            target_name = get_active_embedding_name(provider)
            get_embedding_model(target_name)
        if getattr(settings, "warmup_reranker", True):
            get_reranker_model(provider=settings.reranker_provider)
        print("[AI-SERVICE] Warmup RAG model & reranker nen hoan tat.", flush=True)
    except Exception as exc:
        print(f"[AI-SERVICE] Bo qua warmup nen (se nap khi dung): {exc}", flush=True)


def list_course_files(course_id: str = "default") -> list[str]:
    course_dir = str(settings.course_documents_dir(course_id))
    all_files: list[str] = []
    for pattern in ("**/*.docx", "**/*.txt", "**/*.pdf", "**/*.pptx"):
        for path in glob.glob(os.path.join(course_dir, pattern), recursive=True):
            if not os.path.basename(path).startswith("~$"):
                all_files.append(path)
    return sorted(set(all_files))
