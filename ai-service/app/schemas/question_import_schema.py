"""Schema mô hình dữ liệu cho tính năng Bóc tách & Nhập câu hỏi thi vấn đáp hàng loạt."""

from typing import List, Optional
from pydantic import BaseModel, Field


class RubricCriterionItem(BaseModel):
    name: str = Field(..., description="Tên tiêu chí chấm điểm")
    description: str = Field(..., description="Mô tả hướng dẫn chấm chi tiết cho AI")
    max_score: float = Field(..., description="Điểm tối đa của tiêu chí")


class ExtractedQuestionItem(BaseModel):
    temp_id: str = Field(..., description="Mã định danh tạm thời ở client")
    code: str = Field(..., description="Mã câu hỏi (VD: Q1, Q1.1)")
    topic: str = Field(default="Chung", description="Chủ đề / Chương kiến thức")
    title: str = Field(..., description="Tiêu đề tóm tắt câu hỏi")
    content: str = Field(..., description="Nội dung câu hỏi phát vấn cho thí sinh")
    sample_answer: str = Field(default="", description="Đáp án mẫu / Reference Answer")
    difficulty: str = Field(default="medium", description="Độ khó: easy, medium, hard")
    time_limit_seconds: int = Field(default=180, description="Thời gian trả lời tối đa (giây)")
    parent_code: Optional[str] = Field(
        default=None,
        description="Mã câu hỏi cha nếu đây là câu hỏi phụ / nhánh hỏi tiếp trong ca thi vấn đáp",
    )
    is_followup: bool = Field(
        default=False,
        description="Đánh dấu câu này là câu hỏi phụ hỏi tiếp theo sau câu cha",
    )
    tags: List[str] = Field(default_factory=list, description="Thẻ phân loại")
    criteria: List[RubricCriterionItem] = Field(
        default_factory=list,
        description="Danh sách tiêu chí Rubric chấm điểm",
    )
    total_score: float = Field(default=10.0, description="Tổng điểm của các tiêu chí Rubric")
    status: str = Field(
        default="valid",
        description="Trạng thái kiểm tra dữ liệu: valid (hợp lệ), warning (cảnh báo), error (lỗi)",
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Danh sách lỗi bắt buộc phải sửa (màu đỏ)",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Danh sách cảnh báo cần lưu ý (màu vàng)",
    )


class QuestionExtractResponse(BaseModel):
    file_name: str
    total_detected: int
    valid_count: int
    error_count: int
    warning_count: int
    questions: List[ExtractedQuestionItem]

