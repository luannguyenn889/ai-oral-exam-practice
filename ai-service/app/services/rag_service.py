"""Facade tương thích ngược cho phân hệ RAG (tổng hợp và re-export từ gói `app.services.rag`).

Nhiệm vụ:
- Giữ nguyên giao diện import cũ (`from app.services import rag_service`) cho toàn bộ Router (`routers/rag.py`), dịch vụ chấm điểm (`grading_service.py`), `main.py` và bộ kiểm thử.
- Gom các hàm công khai và helper kiểm thử từ 5 module chuyên biệt:
    + `rag.embeddings`: Embedding models, Reranker, tiền xử lý truy vấn.
    + `rag.extractors`: Đọc tài liệu .docx, .pdf (kèm lọc header/footer & OCR), .txt.
    + `rag.chunking`: Các chiến lược chia đoạn `recursive`, `semantic`, `legacy`.
    + `rag.store`: ChromaDB, BM25, lập chỉ mục và truy vấn Hybrid RAG.
    + `rag.folders`: Quản lý thư mục tài liệu theo mã học phần.
"""

from app.services.rag.chunking import (
    CHUNKING_STRATEGIES,
    CHUNKING_STRATEGY_LABELS,
    DEFAULT_CHUNKING_STRATEGY,
    _cosine_similarity,
    _detect_heading_level,
    _format_breadcrumb,
    _is_heading_line,
    _merge_units_recursively,
    _recursive_split_piece,
    _reflow_wrapped_lines,
    _sentence_overlap,
    _split_into_sections,
    _split_sentences,
    _split_table_with_header,
    chunk_text,
    chunk_text_legacy,
    chunk_text_recursive,
    chunk_text_semantic,
    get_chunking_strategy_label,
    get_clean_overlap,
    normalize_chunking_strategy,
)
from app.services.rag.embeddings import (
    EMBEDDING_PROVIDERS,
    FILLER_PATTERNS,
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
    _clean_pdf_pages,
    _detect_docx_heading_level,
    _normalize_pdf_margin_line,
    extract_text_from_docx,
    extract_text_from_pdf,
    extract_text_from_txt,
)
from app.services.rag.folders import (
    _migrate_folder_contents,
    _normalize_folder_code,
    _purge_course_vectors,
    delete_course_folder,
    ensure_course_folder,
    rename_course_folder,
)
from app.services.rag.store import (
    format_rag_context,
    get_bm25_index,
    get_chroma_collection,
    get_collection_name,
    get_rag_status,
    index_documents,
    invalidate_bm25_cache,
    list_course_files,
    query_relevant_chunks,
    warmup_rag_background,
)

__all__ = [
    "CHUNKING_STRATEGIES",
    "CHUNKING_STRATEGY_LABELS",
    "DEFAULT_CHUNKING_STRATEGY",
    "EMBEDDING_PROVIDERS",
    "FILLER_PATTERNS",
    "chunk_text",
    "chunk_text_legacy",
    "chunk_text_recursive",
    "chunk_text_semantic",
    "clean_oral_query",
    "delete_course_folder",
    "embed_texts",
    "ensure_course_folder",
    "extract_text_from_docx",
    "extract_text_from_pdf",
    "extract_text_from_txt",
    "format_rag_context",
    "get_active_embedding_name",
    "get_bm25_index",
    "get_chroma_collection",
    "get_chunking_strategy_label",
    "get_clean_overlap",
    "get_collection_name",
    "get_embedding_model",
    "get_rag_status",
    "get_reranker_model",
    "index_documents",
    "invalidate_bm25_cache",
    "list_course_files",
    "normalize_chunking_strategy",
    "normalize_course_id",
    "normalize_embedding_provider",
    "query_relevant_chunks",
    "rename_course_folder",
    "tokenize_text",
    "warmup_rag_background",
]
