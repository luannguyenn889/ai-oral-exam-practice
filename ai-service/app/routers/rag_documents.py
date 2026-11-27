"""Router quản lý tệp giáo trình (upload, preview, tải xuống, xóa) và vòng đời thư mục học phần RAG."""

from __future__ import annotations

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
    RagIndexResponse,
)
from app.services import rag_service

router = APIRouter()

ALLOWED_EXTENSIONS = {".docx", ".pdf", ".txt", ".pptx"}
_DOCUMENT_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain; charset=utf-8",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def _resolve_course_document(course_id: str, filename: str) -> tuple[Path, str]:
    """Trả về đường dẫn tệp hợp lệ (hỗ trợ cả thư mục con, chống path traversal) hoặc báo lỗi 404."""
    course_dir = settings.course_documents_dir(course_id).resolve()
    raw_rel = (filename or "").replace("\\", "/").lstrip("/")
    rel_parts = [p for p in Path(raw_rel).parts if p not in ("", ".")]
    if not rel_parts or any(p == ".." for p in rel_parts):
        raise HTTPException(status_code=400, detail="Đường dẫn tài liệu không hợp lệ.")

    target_path = (course_dir / Path(*rel_parts)).resolve()
    try:
        target_path.relative_to(course_dir)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Đường dẫn tài liệu vượt ra ngoài phạm vi học phần.") from exc

    if not target_path.is_file():
        raise HTTPException(status_code=404, detail=f"Không tìm thấy tài liệu: {raw_rel}")
    return target_path, raw_rel


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
    max_bytes = max(1, int(getattr(settings, "max_upload_size_mb", 50) or 50)) * 1024 * 1024

    try:
        content = await file.read()
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Kích thước file vượt quá giới hạn cho phép ({settings.max_upload_size_mb} MB).",
            )
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
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Lỗi khi tải lên và lập chỉ mục tài liệu: {exc}"
        ) from exc


@router.get("/courses/{course_id}/config", response_model=CourseRagConfigResponse)
def get_course_rag_config_endpoint(course_id: str) -> CourseRagConfigResponse:
    cfg = rag_service.get_course_rag_config(course_id)
    return CourseRagConfigResponse(
        course_id=cfg["course_id"],
        embedding_provider=cfg["embedding_provider"],
        chunking_strategy=cfg["chunking_strategy"],
        embedding_model=rag_service.get_active_embedding_name(cfg["embedding_provider"]),
        reranker_provider=cfg["reranker_provider"],
        reranker_model=rag_service.get_active_reranker_name(cfg["reranker_provider"]),
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
        reranker_provider=request.reranker_provider,
    )
    return CourseRagConfigResponse(
        course_id=cfg["course_id"],
        embedding_provider=cfg["embedding_provider"],
        chunking_strategy=cfg["chunking_strategy"],
        embedding_model=rag_service.get_active_embedding_name(cfg["embedding_provider"]),
        reranker_provider=cfg["reranker_provider"],
        reranker_model=rag_service.get_active_reranker_name(cfg["reranker_provider"]),
    )


@router.get("/documents/{course_id}/{filename:path}/preview")
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
            content = rag_service.extract_text_from_docx(str(target_path), raise_on_error=True)
        elif ext == ".pdf":
            content = rag_service.extract_text_from_pdf(str(target_path))
        elif ext == ".pptx":
            content = rag_service.extract_text_from_pptx(str(target_path), raise_on_error=True)
        else:
            content = rag_service.extract_text_from_txt(str(target_path), raise_on_error=True)
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


@router.get("/documents/{course_id}/{filename:path}")
def download_or_open_course_document(course_id: str, filename: str) -> FileResponse:
    target_path, safe_name = _resolve_course_document(course_id, filename)
    media_type = _DOCUMENT_MEDIA_TYPES.get(
        target_path.suffix.lower(), "application/octet-stream"
    )
    encoded_name = urllib.parse.quote(Path(safe_name).name)
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


@router.delete("/documents/{course_id}/{filename:path}", response_model=RagIndexResponse)
def delete_course_document(course_id: str, filename: str) -> RagIndexResponse:
    target_path, _ = _resolve_course_document(course_id, filename)
    try:
        target_path.unlink()
        result = rag_service.index_documents(course_id=course_id, force_reindex=False)
        return RagIndexResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi khi xóa tài liệu: {exc}") from exc
