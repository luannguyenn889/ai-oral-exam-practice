"""Router chính cho phân hệ RAG: lập chỉ mục, tìm kiếm ngữ nghĩa, gợi ý HITL, trạng thái và bộ đề mẫu."""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.routers.rag_documents import (
    ALLOWED_EXTENSIONS,
    CourseFolderSyncRequest,
    _DOCUMENT_MEDIA_TYPES,
    _resolve_course_document,
    delete_course_document,
    delete_course_rag_folder,
    download_or_open_course_document,
    get_course_rag_config_endpoint,
    preview_course_document,
    router as documents_router,
    sync_course_folder,
    update_course_rag_config_endpoint,
    upload_and_index_document,
)
from app.schemas.rag_schema import (
    RagChunkResult,
    RagIndexJobResponse,
    RagIndexRequest,
    RagIndexResponse,
    RagSearchRequest,
    RagSearchResponse,
    RagStatusResponse,
    RagSuggestAnswerRequest,
    RagSuggestAnswerResponse,
    SuggestedRubricCriterion,
)
from app.services import rag_service

router = APIRouter(prefix="/ai/rag", tags=["rag"])
router.include_router(documents_router)


@router.post("/index", response_model=RagIndexResponse)
def index_course_documents(request: RagIndexRequest) -> RagIndexResponse:
    try:
        result = rag_service.index_documents(
            course_id=request.course_id,
            force_reindex=request.force_reindex,
            embedding_provider=request.embedding_provider,
            chunking_strategy=request.chunking_strategy,
        )
        return RagIndexResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lập chỉ mục RAG: {exc}") from exc


@router.post("/index/start", response_model=RagIndexJobResponse)
def start_index_course_documents(request: RagIndexRequest) -> RagIndexJobResponse:
    """Khởi chạy tác vụ đồng bộ & lập chỉ mục ở luồng nền, trả job_id ngay lập tức để UI theo dõi % tiến độ."""
    try:
        job = rag_service.start_index_job(
            course_id=request.course_id,
            force_reindex=request.force_reindex,
            embedding_provider=request.embedding_provider,
            chunking_strategy=request.chunking_strategy,
        )
        return RagIndexJobResponse(**job)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi khi khởi chạy tác vụ lập chỉ mục RAG: {exc}") from exc


@router.get("/index/jobs/{job_id}", response_model=RagIndexJobResponse)
def get_index_job_status(job_id: str) -> RagIndexJobResponse:
    job = rag_service.get_index_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy tác vụ lập chỉ mục: {job_id}")
    return RagIndexJobResponse(**job)


@router.post("/index/jobs/{job_id}/cancel", response_model=RagIndexJobResponse)
def cancel_index_job_endpoint(job_id: str) -> RagIndexJobResponse:
    job = rag_service.cancel_index_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy tác vụ lập chỉ mục: {job_id}")
    return RagIndexJobResponse(**job)


@router.get("/index/active", response_model=Optional[RagIndexJobResponse])
def get_active_index_job_status(
    course_id: str = Query(default="default", description="Mã học phần cần kiểm tra job đang chạy"),
    embedding_provider: Optional[str] = Query(default=None),
) -> Optional[RagIndexJobResponse]:
    job = rag_service.get_active_index_job(
        course_id=course_id,
        embedding_provider=embedding_provider,
    )
    return RagIndexJobResponse(**job) if job else None


def _to_chunk_results(chunks: list[dict], fallback_course_id: str) -> list[RagChunkResult]:
    return [
        RagChunkResult(
            chunk_id=str(c.get("id", "")),
            source=str(c.get("source", "Không rõ")),
            course_id=str(c.get("course_id", fallback_course_id)),
            index=int(c.get("index", 0)),
            text=str(c.get("text", "")),
            retrieved_by=str(c.get("retrieved_by", "hybrid")),
            dense_sim=c.get("dense_sim"),
            bm25_score=c.get("bm25_score"),
            rrf_score=float(c.get("rrf_score", 0.0)),
            rerank_score=c.get("rerank_score"),
            method=str(c.get("method", "Hybrid RRF")),
            page_start=c.get("page_start"),
            page_end=c.get("page_end"),
        )
        for c in chunks
    ]


@router.post("/search", response_model=RagSearchResponse)
def search_course_documents(request: RagSearchRequest) -> RagSearchResponse:
    try:
        chunks = rag_service.query_relevant_chunks(
            query_text=request.query_text,
            course_id=request.course_id,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
            search_mode=request.search_mode,
            use_rerank=request.use_rerank,
            embedding_provider=request.embedding_provider,
            reranker_provider=request.reranker_provider,
            expand_neighbors=request.expand_neighbors,
        )
        return RagSearchResponse(
            course_id=rag_service.normalize_course_id(request.course_id),
            query_text=request.query_text,
            cleaned_query=rag_service.clean_oral_query(request.query_text),
            search_mode=request.search_mode,
            top_k=request.top_k,
            results=_to_chunk_results(chunks, request.course_id),
            formatted_context=rag_service.format_rag_context(chunks),
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve)) from ve
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi khi tìm kiếm RAG: {exc}") from exc


@router.post("/suggest-answer", response_model=RagSuggestAnswerResponse)
def suggest_reference_answer_endpoint(
    request: RagSuggestAnswerRequest,
) -> RagSuggestAnswerResponse:
    """Human-in-the-loop: AI truy xuất Hybrid RAG và khởi tạo bản nháp Đáp án mẫu (+ Rubric) để giảng viên duyệt."""
    try:
        result = rag_service.suggest_reference_answer(
            course_id=request.course_id,
            question=request.question,
            topic=request.topic,
            reference_answer=request.reference_answer,
            top_k=request.top_k,
            search_mode=request.search_mode,
            include_rubric=request.include_rubric,
            selected_chunk_ids=request.selected_chunk_ids,
            embedding_provider=request.embedding_provider,
            reranker_provider=request.reranker_provider,
            llm_model=request.llm_model,
        )
        criteria = [
            SuggestedRubricCriterion(
                name=str(item["name"]),
                description=str(item.get("description", "")),
                max_score=float(item["max_score"]),
            )
            for item in result.get("suggested_criteria", [])
        ]
        return RagSuggestAnswerResponse(
            course_id=result["course_id"],
            sample_answer=result["sample_answer"],
            suggested_criteria=criteria,
            rag_references=_to_chunk_results(result.get("rag_references", []), result["course_id"]),
            used_chunk_ids=result.get("used_chunk_ids", []),
            embedding_provider=result.get("embedding_provider", "e5-small"),
            embedding_model=result.get("embedding_model", ""),
            reranker_provider=result.get("reranker_provider", "bge-m3"),
            reranker_model=result.get("reranker_model", ""),
            llm_model=result["llm_model"],
            status="ai_draft",
            notice=result["notice"],
            warnings=result.get("warnings", []),
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve)) from ve
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Lỗi khi AI khởi tạo bản nháp đáp án từ RAG: {exc}"
        ) from exc


@router.get("/status", response_model=RagStatusResponse)
def get_course_rag_status(
    course_id: str = Query(default="default", description="Mã học phần cần kiểm tra"),
    embedding_provider: Optional[str] = Query(default=None),
) -> RagStatusResponse:
    status_dict = rag_service.get_rag_status(
        course_id=course_id, embedding_provider=embedding_provider
    )
    return RagStatusResponse(**status_dict)


@router.get("/presets")
def get_preset_questions() -> dict[str, dict[str, str]]:
    """Đọc bộ câu hỏi và Rubric mẫu từ file data/BỘ ĐỀ THI.txt (từ speed-to-text-demo)."""
    preset_path = Path(settings.data_dir)
    if not preset_path.is_absolute():
        preset_path = Path(__file__).resolve().parent.parent.parent / settings.data_dir
    file_path = preset_path / "BỘ ĐỀ THI.txt"
    if not file_path.exists():
        return {}
    try:
        content = file_path.read_text(encoding="utf-8")
        parts = content.split("---")
        presets: dict[str, dict[str, str]] = {}
        for part in parts:
            if "CÂU HỎI" not in part:
                continue
            title_line = ""
            for line in part.split("\n"):
                if "## 📑 CÂU HỎI" in line:
                    title_line = line.replace("## 📑", "").strip()
                    break
            q_start = part.find('> "')
            q_end = part.find('"', q_start + 3)
            question = part[q_start + 3 : q_end].strip() if (q_start != -1 and q_end != -1) else ""
            r_marker = "### 📋 Rubric chấm điểm chi tiết (Thang điểm 10)"
            r_start = part.find(r_marker)
            rubric = part[r_start + len(r_marker) :].strip() if r_start != -1 else ""
            if title_line and question and rubric:
                presets[title_line] = {"question": question, "rubric": rubric}
        return presets
    except Exception:
        return {}


__all__ = [
    "ALLOWED_EXTENSIONS",
    "CourseFolderSyncRequest",
    "_DOCUMENT_MEDIA_TYPES",
    "_resolve_course_document",
    "delete_course_document",
    "delete_course_rag_folder",
    "download_or_open_course_document",
    "get_course_rag_config_endpoint",
    "preview_course_document",
    "router",
    "sync_course_folder",
    "update_course_rag_config_endpoint",
    "upload_and_index_document",
]
