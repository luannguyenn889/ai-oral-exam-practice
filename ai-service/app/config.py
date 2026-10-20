import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_FILE_PATH, override=False)


class Settings(BaseSettings):
    gemini_api_key: str = ""
    groq_api_key: str = ""

    default_stt_provider: str = "groq"
    default_llm_model: str = "gemini-2.5-flash"
    embedding_provider: str = "local"
    embedding_model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"
    gemini_embedding_model_name: str = "gemini-embedding-2"
    gemini_embedding_dimensions: int = 768
    reranker_model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    ollama_base_url: str = "http://localhost:11434"

    data_dir: str = "data"
    documents_dir: str = "data/documents"
    chroma_db_dir: str = "data/chroma_db"
    collection_prefix: str = "qnu_viva_documents"

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

    def course_documents_dir(self, course_id: str) -> Path:
        safe_course = "".join(c for c in (course_id or "default").strip() if c.isalnum() or c in ("-", "_")) or "default"
        path = self.resolved_documents_dir / safe_course
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()

