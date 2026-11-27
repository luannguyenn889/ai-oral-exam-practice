"""Quản lý cấu hình tập trung của AI Service.

Nhiệm vụ:
- Tải các biến môi trường từ file .env (khóa API Gemini, Groq, cấu hình model STT/LLM/Embedding).
- Định nghĩa lớp Settings (Pydantic Settings) với các giá trị mặc định an toàn cho hệ thống.
- Cung cấp các đường dẫn thư mục chuẩn hóa:
    + resolved_documents_dir: Thư mục chứa tài liệu/giáo trình môn học theo từng course_id.
    + resolved_chroma_db_dir: Thư mục cơ sở dữ liệu vector ChromaDB.
    + get_course_documents_dir(course_id): Hàm tiện ích lấy thư mục tài liệu riêng của từng môn.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_FILE_PATH, override=False)


class Settings(BaseSettings):
    gemini_api_key: str = ""
    gemini_api_keys: str = ""
    groq_api_key: str = ""

    default_stt_provider: str = "groq"
    default_llm_model: str = "gemini-2.5-flash"
    embedding_provider: str = "e5-small"
    embedding_backend: str = "auto"  # "auto" (onnx tren CPU / cuda FP16 tren GPU), "onnx", hoac "torch"
    embedding_batch_size: int = 64
    embedding_model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"
    e5_embedding_model_name: str = "intfloat/multilingual-e5-small"
    gemini_embedding_model_name: str = "gemini-embedding-2"
    gemini_embedding_dimensions: int = 768
    gemini_embedding_batch_size: int = 50
    gemini_embedding_max_workers: int = 2
    reranker_provider: str = "bge-m3"
    reranker_model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    bge_reranker_model_name: str = "BAAI/bge-reranker-v2-m3"
    warmup_reranker: bool = True
    max_upload_size_mb: int = 50
    rag_min_relevance_enabled: bool = True
    rag_min_rerank_score: float = 0.03
    rag_min_minilm_rerank_score: float = -4.5
    rag_min_dense_sim_local: float = 0.35
    rag_min_dense_sim_e5: float = 0.76
    rag_min_dense_sim_gemini: float = 0.52
    ollama_base_url: str = "http://localhost:11434"

    data_dir: str = "data"
    documents_dir: str = "data/documents"
    chroma_db_dir: str = "data/chroma_db"
    collection_prefix: str = "qnu_viva_documents"
    rag_noise_drop_threshold: float = 0.70
    rag_noise_penalty_threshold: float = 0.40

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def resolved_documents_dir(self) -> Path:
        p = Path(self.documents_dir)
        return p if p.is_absolute() else (BASE_DIR / p).resolve()

    @property
    def resolved_chroma_db_dir(self) -> Path:
        p = Path(self.chroma_db_dir)
        return p if p.is_absolute() else (BASE_DIR / p).resolve()

    def resolve_course_documents_dir(self, course_id: str) -> Path:
        safe_course = "".join(c for c in (course_id or "default").strip() if c.isalnum() or c in ("-", "_")) or "default"
        return self.resolved_documents_dir / safe_course

    def course_documents_dir(self, course_id: str) -> Path:
        path = self.resolve_course_documents_dir(course_id)
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()

