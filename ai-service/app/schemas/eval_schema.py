"""Các mô hình dữ liệu (Pydantic Schemas) cho phân hệ Chấm điểm vấn đáp (Grading & Evaluation).

Nhiệm vụ:
- RubricCriterionInput: Định nghĩa một tiêu chí chấm điểm trong Rubric (mã, tên, mô tả, điểm tối đa).
- RagConfig: Cấu hình cơ chế tra cứu giáo trình hỗ trợ chấm (bật/tắt RAG, chế độ hybrid/dense/bm25, số lượng top_k, rerank).
- EvaluationRequest: Dữ liệu gửi vào khi chấm điểm một bài làm (session_id, course_id, câu hỏi, đáp án mẫu, transcript sinh viên, rubric, rag_config, llm_model).
- CriterionEvaluation: Đánh giá chi tiết cho từng tiêu chí Rubric (điểm đạt được, trích dẫn bằng chứng từ bài làm, thiếu sót/sai sót, nhận xét).
- RagReference: Đoạn trích dẫn tài liệu giáo trình được AI sử dụng làm căn cứ đối chiếu khi chấm.
- EvaluationResponse: Cấu trúc kết quả chấm điểm toàn diện trả về cho Frontend và Backend.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class RubricCriterionInput(BaseModel):
    criterion_id: str = Field(..., description="Mã tiêu chí (ví dụ: c1, c2)")
    name: str = Field(..., description="Tên tiêu chí")
    description: str = Field(default="", description="Mô tả chi tiết yêu cầu của tiêu chí")
    max_score: float = Field(..., gt=0, description="Điểm tối đa của tiêu chí")


class RagConfig(BaseModel):
    enabled: bool = Field(default=True, description="Bật/tắt đối chiếu giáo trình RAG")
    search_mode: Literal["hybrid", "dense", "bm25"] = Field(default="hybrid")
    top_k: int = Field(default=3, ge=1, le=10)
    score_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    use_rerank: bool = Field(default=False)


class EvaluationRequest(BaseModel):
    session_id: Optional[str] = Field(default=None, description="ID phiên luyện tập")
    course_id: str = Field(default="default", description="Mã học phần để lọc đúng giáo trình RAG")
    question: str = Field(..., min_length=1, description="Nội dung câu hỏi")
    reference_answer: str = Field(default="", description="Đáp án mẫu / ý chuẩn của giảng viên")
    transcript: str = Field(..., min_length=1, description="Câu trả lời của sinh viên đã xác nhận")
    rubric: list[RubricCriterionInput] = Field(
        default_factory=list, description="Danh sách tiêu chí chấm điểm theo Rubric"
    )
    rag_config: RagConfig = Field(default_factory=RagConfig)
    llm_model: str = Field(
        default="gemini-2.5-flash",
        description="Model chấm điểm: gemini-2.5-flash, gemini-2.5-pro, gemma3:4b (Local - Ollama), hoặc mock",
    )


class CriterionEvaluation(BaseModel):
    criterion_id: str
    score: float
    max_score: float
    evidence: str = ""
    missing_or_incorrect: list[str] = Field(default_factory=list)
    feedback: str = ""


class RagReference(BaseModel):
    chunk_id: str
    source: str
    retrieved_by: str
    dense_sim: Optional[float] = None
    rrf_score: float = 0.0
    text_preview: str


class EvaluationMetadata(BaseModel):
    llm_model: str
    embedding_model: str
    processing_time_ms: int


class EvaluationResponse(BaseModel):
    total_score: float
    max_score: float
    summary: str
    criteria: list[CriterionEvaluation]
    strengths: list[str]
    weaknesses: list[str] = Field(default_factory=list)
    improvements: list[str]
    uncertainty_notes: list[str] = Field(default_factory=list)
    needs_human_review: bool = False
    rag_references: list[RagReference] = Field(default_factory=list)
    metadata: EvaluationMetadata


