"""Router định tuyến các API quản lý giáo trình và tìm kiếm RAG (Retrieval-Augmented Generation).

Nhiệm vụ:
- POST /ai/rag/index:
    + Quét và lập chỉ mục (index) toàn bộ tài liệu giáo trình (.docx, .pdf, .txt) của một môn học vào ChromaDB (Dense) và BM25 (Sparse).
- POST /ai/rag/upload:
    + Cho phép Giảng viên tải file giáo trình mới lên kho tài liệu của môn học và tự động cập nhật chỉ mục.
- POST /ai/rag/search:
    + Tìm kiếm các đoạn giáo trình liên quan nhất theo câu hỏi/bài làm với các chế độ: 'hybrid' (Dense + BM25 + RRF), 'dense', hoặc 'bm25'. Hỗ trợ tái xếp hạng Cross-Encoder.
- GET /ai/rag/status:
    + Kiểm tra trạng thái kho giáo trình của môn học (số file, tổng số chunks, model embedding, tình trạng BM25).
- DELETE /ai/rag/documents/{course_id}/{filename}:
    + Xóa tài liệu khỏi kho giáo trình và loại bỏ các chunk tương ứng khỏi chỉ mục ChromaDB & BM25.
- GET /ai/rag/presets:
    + Cung cấp dữ liệu đề thi và Rubric mẫu từ file data/BỘ ĐỀ THI.txt (phục vụ tham khảo và khởi tạo nhanh).
"""

import os
import urllib.parse
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.schemas.rag_schema import (
    CourseRagConfigResponse,
    CourseRagConfigUpdateRequest,
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

ALLOWED_EXTENSIONS = {".docx", ".pdf", ".txt"}
_DOCUMENT_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain; charset=utf-8",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _resolve_course_document(course_id: str, filename: str) -> tuple[Path, str]:
    """Trả về đường dẫn tệp hợp lệ trong kho tài liệu của học phần hoặc báo lỗi 404."""
    course_dir = settings.course_documents_dir(course_id)
    safe_name = Path(filename).name
    target_path = course_dir / safe_name
    if not target_path.is_file():
        raise HTTPException(status_code=404, detail=f"Không tìm thấy tài liệu: {safe_name}")
    return target_path, safe_name


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


@router.post("/upload", response_model=RagIndexResponse)
async def upload_and_index_document(
    course_id: str = Form(default="default"),
    force_reindex: bool = Form(default=False),
    embedding_provider: Optional[str] = Form(default=None),
    chunking_strategy: Optional[str] = Form(default=None),
    file: UploadFile = File(...),
) -> RagIndexResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Tên file không hợp lệ.")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Chỉ hỗ trợ định dạng {', '.join(sorted(ALLOWED_EXTENSIONS))}.",
        )

    course_dir = settings.course_documents_dir(course_id)
    safe_name = Path(file.filename).name
    target_path = course_dir / safe_name

    try:
        content = await file.read()
        with open(target_path, "wb") as out_file:
            out_file.write(content)
        resolved_provider = embedding_provider if isinstance(embedding_provider, str) else None
        resolved_strategy = chunking_strategy if isinstance(chunking_strategy, str) else None
        result = rag_service.index_documents(
            course_id=course_id,
            force_reindex=force_reindex,
            embedding_provider=resolved_provider,
            chunking_strategy=resolved_strategy,
        )
        return RagIndexResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Lỗi khi tải lên và lập chỉ mục tài liệu: {exc}"
        ) from exc


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
        )
        formatted = rag_service.format_rag_context(chunks)
        results = [
            RagChunkResult(
                chunk_id=str(c.get("id", "")),
                source=str(c.get("source", "Không rõ")),
                course_id=str(c.get("course_id", request.course_id)),
                index=int(c.get("index", 0)),
                text=str(c.get("text", "")),
                retrieved_by=str(c.get("retrieved_by", "hybrid")),
                dense_sim=c.get("dense_sim"),
                bm25_score=c.get("bm25_score"),
                rrf_score=float(c.get("rrf_score", 0.0)),
                rerank_score=c.get("rerank_score"),
                method=str(c.get("method", "Hybrid RRF")),
            )
            for c in chunks
        ]
        return RagSearchResponse(
            course_id=rag_service.normalize_course_id(request.course_id),
            query_text=request.query_text,
            cleaned_query=rag_service.clean_oral_query(request.query_text),
            search_mode=request.search_mode,
            top_k=request.top_k,
            results=results,
            formatted_context=formatted,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve)) from ve
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi khi tìm kiếm RAG: {exc}") from exc


@router.post("/suggest-answer", response_model=RagSuggestAnswerResponse)
def suggest_reference_answer_endpoint(
    request: RagSuggestAnswerRequest,
) -> RagSuggestAnswerResponse:
    """Human-in-the-loop: AI truy xuất Hybrid RAG và khởi tạo bản nháp Đáp án mẫu (+ Rubric) để giảng viên chỉnh sửa và duyệt."""
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
            llm_model=request.llm_model,
        )
        rag_refs = [
            RagChunkResult(
                chunk_id=str(c.get("id", "")),
                source=str(c.get("source", "Không rõ")),
                course_id=str(c.get("course_id", result["course_id"])),
                index=int(c.get("index", 0)),
                text=str(c.get("text", "")),
                retrieved_by=str(c.get("retrieved_by", "hybrid")),
                dense_sim=c.get("dense_sim"),
                bm25_score=c.get("bm25_score"),
                rrf_score=float(c.get("rrf_score", 0.0)),
                rerank_score=c.get("rerank_score"),
                method=str(c.get("method", "Hybrid RRF")),
            )
            for c in result.get("rag_references", [])
        ]
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
            rag_references=rag_refs,
            used_chunk_ids=result.get("used_chunk_ids", []),
            embedding_provider=result.get("embedding_provider", "local"),
            embedding_model=result.get("embedding_model", ""),
            llm_model=result["llm_model"],
            status="ai_draft",
            notice=result["notice"],
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve)) from ve
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Lỗi khi AI khởi tạo bản nháp đáp án từ RAG: {exc}"
        ) from exc


@router.get("/courses/{course_id}/config", response_model=CourseRagConfigResponse)
def get_course_rag_config_endpoint(course_id: str) -> CourseRagConfigResponse:
    cfg = rag_service.get_course_rag_config(course_id)
    return CourseRagConfigResponse(
        course_id=cfg["course_id"],
        embedding_provider=cfg["embedding_provider"],
        chunking_strategy=cfg["chunking_strategy"],
        embedding_model=rag_service.get_active_embedding_name(cfg["embedding_provider"]),
    )


@router.put("/courses/{course_id}/config", response_model=CourseRagConfigResponse)
def update_course_rag_config_endpoint(
    course_id: str,
    request: CourseRagConfigUpdateRequest,
) -> CourseRagConfigResponse:
    cfg = rag_service.set_course_rag_config(
        course_id=course_id,
        embedding_provider=request.embedding_provider,
        chunking_strategy=request.chunking_strategy,
    )
    return CourseRagConfigResponse(
        course_id=cfg["course_id"],
        embedding_provider=cfg["embedding_provider"],
        chunking_strategy=cfg["chunking_strategy"],
        embedding_model=rag_service.get_active_embedding_name(cfg["embedding_provider"]),
    )


@router.get("/status", response_model=RagStatusResponse)
def get_course_rag_status(
    course_id: str = Query(default="default", description="Mã học phần cần kiểm tra"),
    embedding_provider: Optional[str] = Query(default=None),
) -> RagStatusResponse:
    status_dict = rag_service.get_rag_status(
        course_id=course_id, embedding_provider=embedding_provider
    )
    return RagStatusResponse(**status_dict)


@router.get("/documents/{course_id}/{filename}/preview")
def preview_course_document(course_id: str, filename: str) -> dict[str, object]:
    target_path, safe_name = _resolve_course_document(course_id, filename)
    ext = target_path.suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng {ext or 'không rõ'} chưa hỗ trợ đọc trực tiếp.",
        )
    try:
        if ext == ".docx":
            content = rag_service.extract_text_from_docx(str(target_path))
        elif ext == ".pdf":
            content = rag_service.extract_text_from_pdf(str(target_path))
        else:
            content = rag_service.extract_text_from_txt(str(target_path))
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Lỗi khi đọc nội dung tài liệu: {exc}"
        ) from exc

    return {
        "course_id": rag_service.normalize_course_id(course_id),
        "filename": safe_name,
        "size_bytes": target_path.stat().st_size,
        "total_chars": len(content),
        "content": content,
    }


@router.get("/documents/{course_id}/{filename}")
def download_or_open_course_document(course_id: str, filename: str) -> FileResponse:
    target_path, safe_name = _resolve_course_document(course_id, filename)
    media_type = _DOCUMENT_MEDIA_TYPES.get(
        target_path.suffix.lower(), "application/octet-stream"
    )
    encoded_name = urllib.parse.quote(safe_name)
    return FileResponse(
        path=str(target_path),
        media_type=media_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{encoded_name}"
        },
    )


class CourseFolderSyncRequest(BaseModel):
    course_code: str = Field(..., min_length=1, description="Mã học phần chuẩn hóa (VD: IT2030)")
    old_code: Optional[str] = Field(default=None, description="Mã học phần cũ nếu đang đổi mã")
    legacy_id: Optional[str] = Field(default=None, description="UUID cũ nếu cần gom tài liệu về mã học phần")


@router.post("/courses/sync-folder")
def sync_course_folder(request: CourseFolderSyncRequest) -> dict[str, object]:
    """Tạo, đổi tên hoặc di chuyển thư mục lưu trữ tài liệu RAG theo mã học phần."""
    try:
        if request.old_code and request.old_code.strip().upper() != request.course_code.strip().upper():
            return rag_service.rename_course_folder(
                old_code=request.old_code,
                new_code=request.course_code,
                legacy_id=request.legacy_id,
            )
        return rag_service.ensure_course_folder(
            course_code=request.course_code,
            legacy_id=request.legacy_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Lỗi khi đồng bộ thư mục học phần: {exc}"
        ) from exc


@router.delete("/courses/{course_code}")
def delete_course_rag_folder(
    course_code: str,
    legacy_id: Optional[str] = Query(default=None, description="UUID cũ của học phần nếu có"),
) -> dict[str, object]:
    """Xóa thư mục tài liệu và toàn bộ dữ liệu RAG của học phần."""
    try:
        return rag_service.delete_course_folder(course_code=course_code, legacy_id=legacy_id)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Lỗi khi xóa kho tài liệu học phần: {exc}"
        ) from exc


@router.delete("/documents/{course_id}/{filename}", response_model=RagIndexResponse)
def delete_course_document(course_id: str, filename: str) -> RagIndexResponse:
    target_path, _ = _resolve_course_document(course_id, filename)
    try:
        target_path.unlink()
        result = rag_service.index_documents(course_id=course_id, force_reindex=False)
        return RagIndexResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi khi xóa tài liệu: {exc}") from exc


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


