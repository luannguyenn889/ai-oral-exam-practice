import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from app.config import settings
from app.schemas.rag_schema import (
    RagChunkResult,
    RagIndexRequest,
    RagIndexResponse,
    RagSearchRequest,
    RagSearchResponse,
    RagStatusResponse,
)
from app.services import rag_service

router = APIRouter(prefix="/ai/rag", tags=["rag"])

ALLOWED_EXTENSIONS = {".docx", ".pdf", ".txt"}


@router.post("/index", response_model=RagIndexResponse)
def index_course_documents(request: RagIndexRequest) -> RagIndexResponse:
    try:
        result = rag_service.index_documents(
            course_id=request.course_id,
            force_reindex=request.force_reindex,
            embedding_provider=request.embedding_provider,
        )
        return RagIndexResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lập chỉ mục RAG: {exc}") from exc


@router.post("/upload", response_model=RagIndexResponse)
async def upload_and_index_document(
    course_id: str = Form(default="default"),
    force_reindex: bool = Form(default=False),
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
        result = rag_service.index_documents(
            course_id=course_id,
            force_reindex=force_reindex,
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


@router.get("/status", response_model=RagStatusResponse)
def get_course_rag_status(
    course_id: str = Query(default="default", description="Mã học phần cần kiểm tra"),
    embedding_provider: Optional[str] = Query(default=None),
) -> RagStatusResponse:
    status_dict = rag_service.get_rag_status(
        course_id=course_id, embedding_provider=embedding_provider
    )
    return RagStatusResponse(**status_dict)


@router.delete("/documents/{course_id}/{filename}", response_model=RagIndexResponse)
def delete_course_document(course_id: str, filename: str) -> RagIndexResponse:
    course_dir = settings.course_documents_dir(course_id)
    safe_name = Path(filename).name
    target_path = course_dir / safe_name
    if not target_path.exists():
        raise HTTPException(status_code=404, detail=f"Không tìm thấy tài liệu: {safe_name}")
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


