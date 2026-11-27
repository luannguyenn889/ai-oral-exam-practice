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
    compute_noise_profile,
    get_chunking_strategy_label,
    get_clean_overlap,
    is_low_value_rag_chunk,
    normalize_chunking_strategy,
)
from app.services.rag.course_config import (
    delete_course_rag_config,
    get_course_rag_config,
    rename_course_rag_config,
    resolve_course_chunking_strategy,
    resolve_course_embedding_provider,
    resolve_course_reranker_provider,
    set_course_rag_config,
)
from app.services.rag.embeddings import (
    EMBEDDING_PROVIDERS,
    FILLER_PATTERNS,
    RERANKER_PROVIDERS,
    clean_oral_query,
    embed_texts,
    get_active_embedding_name,
    get_active_reranker_name,
    get_embedding_model,
    get_reranker_model,
    normalize_course_id,
    normalize_embedding_provider,
    normalize_reranker_provider,
    tokenize_text,
)
from app.services.rag.extractors import (
    _clean_pdf_pages,
    _detect_docx_heading_level,
    _normalize_pdf_margin_line,
    extract_document_with_pages,
    extract_text_from_docx,
    extract_text_from_pdf,
    extract_text_from_pptx,
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
    _bm25_cache,
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
from app.services.rag.jobs import (
    cancel_index_job,
    get_active_index_job,
    get_index_job,
    start_index_job,
)
from app.services.rag.suggest import HITL_NOTICE, suggest_reference_answer

__all__ = [
    "_bm25_cache",
    "CHUNKING_STRATEGIES",
    "CHUNKING_STRATEGY_LABELS",
    "DEFAULT_CHUNKING_STRATEGY",
    "EMBEDDING_PROVIDERS",
    "FILLER_PATTERNS",
    "cancel_index_job",
    "chunk_text",
    "chunk_text_legacy",
    "chunk_text_recursive",
    "chunk_text_semantic",
    "clean_oral_query",
    "delete_course_folder",
    "delete_course_rag_config",
    "embed_texts",
    "ensure_course_folder",
    "extract_document_with_pages",
    "extract_text_from_docx",
    "extract_text_from_pdf",
    "extract_text_from_pptx",
    "extract_text_from_txt",
    "format_rag_context",
    "get_active_embedding_name",
    "get_active_index_job",
    "get_bm25_index",
    "get_chroma_collection",
    "get_chunking_strategy_label",
    "get_clean_overlap",
    "get_collection_name",
    "get_course_rag_config",
    "get_embedding_model",
    "get_index_job",
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
    "rename_course_rag_config",
    "resolve_course_chunking_strategy",
    "resolve_course_embedding_provider",
    "set_course_rag_config",
    "start_index_job",
    "suggest_reference_answer",
    "HITL_NOTICE",
    "tokenize_text",
    "warmup_rag_background",
]
