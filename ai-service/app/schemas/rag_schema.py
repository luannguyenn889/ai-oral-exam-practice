from typing import Literal, Optional
from pydantic import BaseModel, Field


class RagIndexRequest(BaseModel):
    course_id: str = Field(default="default", description="Mã học phần (ví dụ: IT2030)")
    force_reindex: bool = Field(default=False, description="Bắt buộc tạo lại chỉ mục toàn bộ file trong học phần")
    embedding_provider: Optional[Literal["local", "gemini"]] = Field(
        default=None, description="Ghi đè embedding provider ('local' hoặc 'gemini')"
    )


class RagIndexResponse(BaseModel):
    course_id: str
    status: str
    total_files: int
    added_or_updated_chunks: int
    removed_chunks: int = 0
    total_chunks: int
    embedding_model: str


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
    hybrid_bm25_active: bool
    reranker_enabled_by_default: bool = False
    search_modes_available: list[str]
    features: list[str]
    error: Optional[str] = None

