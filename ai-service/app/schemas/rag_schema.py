"""Các mô hình dữ liệu (Pydantic Schemas) cho phân hệ Quản lý & Truy xuất Giáo trình (RAG).

Nhiệm vụ:
- RagIndexRequest & RagIndexResponse: Khuôn dữ liệu gửi vào và kết quả trả về khi thực hiện quét/lập chỉ mục tài liệu giáo trình của môn học.
- RagSearchRequest: Dữ liệu gửi vào khi tìm kiếm đoạn trích giáo trình (mã môn, câu truy vấn, chế độ hybrid/dense/bm25, top_k, rerank).
- RagChunkResult: Cấu trúc chi tiết của từng đoạn văn bản tìm được (chunk_id, nguồn file, điểm tương đồng Cosine, BM25, RRF).
- RagSearchResponse: Kết quả tìm kiếm tổng hợp kèm chuỗi ngữ cảnh chuẩn bị sẵn cho LLM prompt (formatted_context).
- RagStatusResponse: Báo cáo trạng thái kho tài liệu môn học (số lượng file, số chunk, tình trạng BM25).
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


ChunkingStrategy = Literal["recursive", "semantic", "legacy"]


class RagIndexRequest(BaseModel):
    course_id: str = Field(default="default", description="Mã học phần (ví dụ: IT2030)")
    force_reindex: bool = Field(default=False, description="Bắt buộc tạo lại chỉ mục toàn bộ file trong học phần")
    embedding_provider: Optional[Literal["local", "e5-small", "gemini"]] = Field(
        default=None, description="Ghi đè embedding provider ('local', 'e5-small', hoặc 'gemini')"
    )
    chunking_strategy: Optional[ChunkingStrategy] = Field(
        default=None,
        description="Chiến lược chia đoạn: 'recursive' (mặc định), 'semantic', hoặc 'legacy' (cách cũ 600 ký tự)",
    )


class RagIndexResponse(BaseModel):
    course_id: str
    status: str
    total_files: int
    added_or_updated_chunks: int
    removed_chunks: int = 0
    total_chunks: int
    embedding_model: str
    chunking_strategy: str = "recursive"


class RagIndexJobResponse(BaseModel):
    job_id: str
    course_id: str
    status: Literal["queued", "running", "completed", "failed"]
    phase: str = "queued"
    percent: int = Field(default=0, ge=0, le=100)
    message: str = ""
    current_file: Optional[str] = None
    processed_files: int = 0
    total_files: int = 0
    processed_chunks: int = 0
    total_chunks: int = 0
    embedding_provider: str = "local"
    chunking_strategy: str = "recursive"
    elapsed_seconds: int = 0
    result: Optional[RagIndexResponse] = None
    error: Optional[str] = None


class RagSearchRequest(BaseModel):
    course_id: str = Field(default="default", description="Mã học phần cần tra cứu")
    query_text: str = Field(..., min_length=1, description="Câu hỏi hoặc câu trả lời sinh viên cần tra cứu")
    top_k: int = Field(default=3, ge=1, le=20, description="Số đoạn giáo trình trả về")
    search_mode: Literal["hybrid", "dense", "bm25"] = Field(
        default="hybrid", description="Chế độ tìm kiếm: hybrid (Dense + BM25 + RRF), dense, hoặc bm25"
    )
    score_threshold: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Ngưỡng Cosine Similarity tối thiểu (0..1)"
    )
    use_rerank: bool = Field(default=False, description="Bật tầng Cross-Encoder Reranker")
    embedding_provider: Optional[Literal["local", "e5-small", "gemini"]] = Field(
        default=None, description="Ghi đè embedding provider ('local', 'e5-small', hoặc 'gemini')"
    )


class RagChunkResult(BaseModel):
    chunk_id: str
    source: str
    course_id: str
    index: int
    text: str
    retrieved_by: str
    dense_sim: Optional[float] = None
    bm25_score: Optional[float] = None
    rrf_score: float = 0.0
    rerank_score: Optional[float] = None
    method: str = "Hybrid RRF"


class RagSearchResponse(BaseModel):
    course_id: str
    query_text: str
    cleaned_query: str
    search_mode: str
    top_k: int
    results: list[RagChunkResult]
    formatted_context: str


class RagStatusResponse(BaseModel):
    course_id: str
    status: str
    total_chunks: int
    total_files: int
    files: list[str]
    embedding_model: str
    reranker_model: str
    chunking_strategy: str = "recursive"
    hybrid_bm25_active: bool
    reranker_enabled_by_default: bool = False
    search_modes_available: list[str]
    features: list[str]
    error: Optional[str] = None


class SuggestedRubricCriterion(BaseModel):
    name: str = Field(..., description="Tên tiêu chí Rubric đề xuất")
    description: str = Field(default="", description="Hướng dẫn chấm chi tiết cho AI")
    max_score: float = Field(..., gt=0, le=10.0, description="Điểm tối đa của tiêu chí")


class RagSuggestAnswerRequest(BaseModel):
    course_id: str = Field(default="default", description="Mã học phần dùng để truy xuất giáo trình RAG")
    question: str = Field(..., min_length=3, description="Nội dung câu hỏi phát vấn")
    topic: Optional[str] = Field(default=None, description="Chủ đề / chương kiến thức của câu hỏi")
    reference_answer: Optional[str] = Field(
        default=None,
        description="Đáp án mẫu giảng viên đã soạn (nếu có) để AI bám sát khi đề xuất tiêu chí Rubric",
    )
    top_k: int = Field(default=4, ge=1, le=10, description="Số đoạn giáo trình RAG cần truy xuất")
    search_mode: Literal["hybrid", "dense", "bm25"] = Field(
        default="hybrid", description="Chế độ truy xuất RAG"
    )
    include_rubric: bool = Field(
        default=False, description="Bật để AI gợi ý thêm danh sách tiêu chí Rubric thang 10.0đ"
    )
    selected_chunk_ids: Optional[list[str]] = Field(
        default=None,
        description="Danh sách chunk_id được giảng viên chọn giữ lại (Human-in-the-loop lọc nhiễu RAG)",
    )
    llm_model: Optional[str] = Field(
        default=None, description="Ghi đè mô hình LLM (hỗ trợ 'mock' khi kiểm thử)"
    )


class RagSuggestAnswerResponse(BaseModel):
    course_id: str
    sample_answer: str
    suggested_criteria: list[SuggestedRubricCriterion] = Field(default_factory=list)
    rag_references: list[RagChunkResult] = Field(default_factory=list)
    used_chunk_ids: list[str] = Field(default_factory=list)
    llm_model: str
    status: Literal["ai_draft"] = "ai_draft"
    notice: str


