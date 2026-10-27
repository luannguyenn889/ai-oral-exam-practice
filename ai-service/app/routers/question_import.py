"""Router tiếp nhận tài liệu Word/Excel chứa ngân hàng câu hỏi để AI phân tích và bóc tách."""

from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.schemas.question_import_schema import QuestionExtractResponse
from app.services import question_extractor_service

router = APIRouter(prefix="/ai/questions", tags=["Question Batch Extraction"])


@router.post(
    "/extract-document",
    response_model=QuestionExtractResponse,
    status_code=status.HTTP_200_OK,
    summary="Bóc tách câu hỏi, đáp án mẫu và Rubric từ file Word (.docx) hoặc Excel (.xlsx)",
)
async def extract_questions_from_document(
    file: UploadFile = File(..., description="File tài liệu .docx, .xlsx hoặc .txt"),
    course_id: Optional[str] = Form(None, description="Mã học phần liên kết"),
) -> QuestionExtractResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Tên file không hợp lệ.")

    lower_name = file.filename.lower()
    if not (lower_name.endswith(".xlsx") or lower_name.endswith(".xls") or lower_name.endswith(".docx") or lower_name.endswith(".txt")):
        raise HTTPException(
            status_code=400,
            detail="Hệ thống chỉ hỗ trợ định dạng Excel (.xlsx, .xls) hoặc Word (.docx) hoặc Text (.txt).",
        )

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="File tải lên rỗng.")

    return question_extractor_service.extract_questions_from_file(
        file_bytes=file_bytes,
        file_name=file.filename,
        course_id=course_id,
    )

