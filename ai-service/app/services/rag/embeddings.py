"""Module quản lý Embedding, Reranker và tiền xử lý truy vấn vấn đáp cho phân hệ RAG.

Nhiệm vụ:
- Chuẩn hóa định danh học phần (`normalize_course_id`) và nhà cung cấp embedding (`normalize_embedding_provider`):
    + Hỗ trợ 3 lựa chọn: 'local' (MiniLM-L12-v2), 'e5-small' (multilingual-e5-small 512 tokens), và 'gemini' (Gemini Embedding).
- Nạp model theo cơ chế Lazy Load an toàn đa luồng (`get_embedding_model`, `get_reranker_model`):
    + Ưu tiên tải từ cache cục bộ (`local_files_only=True`) để khởi động nhanh và chạy ổn định.
- Tạo vector nhúng chuẩn hóa (`embed_texts`):
    + Tự gắn tiền tố `query:` / `passage:` đối với họ model E5.
    + Gọi Google Gemini Embedding theo lô (batch 32) kèm giới hạn tốc độ và tự thử lại khi gặp lỗi 429 (`_gemini_embed_content`).
- Tiền xử lý truy vấn giọng nói (`clean_oral_query`) và tách từ (`tokenize_text`) phục vụ BM25.
"""

import os
import re
import threading
import time
import warnings
from typing import Any, Optional

from app.config import settings

warnings.filterwarnings("ignore", message=".*unauthenticated requests.*")
warnings.filterwarnings("ignore", message=".*HF Hub.*")
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

GEMINI_MIN_REQUEST_INTERVAL_SECONDS = 0.7
GEMINI_EMBED_MAX_RETRIES = 3

EMBEDDING_PROVIDERS = ("local", "e5-small", "gemini")

_embedding_models: dict[str, Any] = {}
_embedding_lock = threading.Lock()
_reranker_model: Any = None

_gemini_client: Any = None
_gemini_client_api_key: Optional[str] = None
_gemini_request_lock = threading.Lock()
_gemini_last_request_at = 0.0

FILLER_PATTERNS = [
    r"\bdạ\b",
    r"\bthưa thầy\b",
    r"\bthưa cô\b",
    r"\bem xin phép\b",
    r"\btheo em nghĩ\b",
    r"\btheo em nhớ\b",
    r"\bem nghĩ là\b",
    r"\bừm\b",
    r"\bà\b",
    r"\bthì là mà\b",
    r"\bạ\b",
]


def normalize_course_id(course_id: Optional[str]) -> str:
    cleaned = "".join(c for c in (course_id or "default").strip() if c.isalnum() or c in ("-", "_"))
    return cleaned or "default"


def normalize_embedding_provider(provider: Optional[str] = None) -> str:
    raw = provider if isinstance(provider, str) else None
    prov = (raw or settings.embedding_provider or "local").strip().lower()
    if prov == "gemini":
        return "gemini"
    if prov in ("e5-small", "e5", "multilingual-e5-small", "intfloat/multilingual-e5-small"):
        return "e5-small"
    return "local"


def get_active_embedding_name(provider: Optional[str] = None) -> str:
    prov = normalize_embedding_provider(provider)
    if prov == "gemini":
        return settings.gemini_embedding_model_name
    if prov == "e5-small":
        return settings.e5_embedding_model_name
    return settings.embedding_model_name


def clean_oral_query(text: str) -> str:
    """Lọc bỏ các từ đệm, ngập ngừng hội thoại để làm sắc nét véc-tơ truy vấn."""
    if not text:
        return ""
    cleaned = text
    for pat in FILLER_PATTERNS:
        cleaned = re.sub(pat, " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned if len(cleaned) > 5 else text.strip()


def tokenize_text(text: str) -> list[str]:
    """Tách từ đơn giản cho BM25 (hỗ trợ cả tiếng Việt và thuật ngữ CNTT)."""
    if not text:
        return []
    return re.findall(r"\b\w+\b", text.lower())


def get_embedding_model(model_name: Optional[str] = None) -> Any:
    """Tải embedding model theo cơ chế Lazy load từ cache máy tính (thread-safe)."""
    target_name = (model_name or settings.embedding_model_name).strip()
    if target_name in _embedding_models:
        return _embedding_models[target_name]

    with _embedding_lock:
        if target_name not in _embedding_models:
            from sentence_transformers import SentenceTransformer

            try:
                _embedding_models[target_name] = SentenceTransformer(
                    target_name, local_files_only=True
                )
            except Exception:
                _embedding_models[target_name] = SentenceTransformer(target_name)
    return _embedding_models[target_name]


def _gemini_embed_content(contents: list[Any]) -> Any:
    """Call Gemini embeddings with gentle pacing and bounded 429 retries."""
    global _gemini_last_request_at
    from google.genai import types

    for attempt in range(GEMINI_EMBED_MAX_RETRIES + 1):
        try:
            with _gemini_request_lock:
                elapsed = time.monotonic() - _gemini_last_request_at
                if elapsed < GEMINI_MIN_REQUEST_INTERVAL_SECONDS:
                    time.sleep(GEMINI_MIN_REQUEST_INTERVAL_SECONDS - elapsed)
                _gemini_last_request_at = time.monotonic()
                return _gemini_client.models.embed_content(
                    model=settings.gemini_embedding_model_name,
                    contents=contents,
                    config=types.EmbedContentConfig(
                        output_dimensionality=settings.gemini_embedding_dimensions
                    ),
                )
        except Exception as exc:
            status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            message = str(exc)
            is_rate_limit = (
                status_code == 429 or "429" in message or "RESOURCE_EXHAUSTED" in message
            )
            if not is_rate_limit or attempt >= GEMINI_EMBED_MAX_RETRIES:
                raise

            retry_match = re.search(
                r"retryDelay['\"]?\s*:\s*['\"]?(\d+(?:\.\d+)?)\s*(ms|s)", message, re.I
            )
            if not retry_match:
                retry_match = re.search(
                    r"retry in\s+(\d+(?:\.\d+)?)\s*(?:seconds?|s)\b", message, re.I
                )
            if retry_match:
                delay = float(retry_match.group(1))
                if len(retry_match.groups()) > 1 and retry_match.group(2).lower() == "ms":
                    delay /= 1000
            else:
                delay = min(5 * (2**attempt), 30)
            delay = min(max(delay, 1.0), 120.0)
            time.sleep(delay)


def embed_texts(
    texts: list[str], task: str = "document", provider: Optional[str] = None
) -> list[list[float]]:
    """Create normalized vectors locally or through Google Gemini embeddings."""
    if not texts:
        return []
    prov = normalize_embedding_provider(provider)
    if prov in ("local", "e5-small"):
        model_name = get_active_embedding_name(prov)
        model = get_embedding_model(model_name)
        inputs = texts
        if "e5" in model_name.lower():
            prefix = "query: " if task == "query" else "passage: "
            inputs = [f"{prefix}{t}" for t in texts]
        return model.encode(
            inputs, batch_size=32, show_progress_bar=False, normalize_embeddings=True
        ).tolist()

    api_key = (settings.gemini_api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
    if not api_key:
        raise ValueError("Chưa cấu hình GEMINI_API_KEY trong .env để dùng Gemini Embedding.")

    global _gemini_client, _gemini_client_api_key
    if _gemini_client is None or _gemini_client_api_key != api_key:
        from google import genai

        _gemini_client = genai.Client(api_key=api_key)
        _gemini_client_api_key = api_key

    from google.genai import types

    prefix = "task: search result | query: " if task == "query" else "title: none | text: "
    vectors: list[list[float]] = []
    for start in range(0, len(texts), 32):
        contents = [
            types.Content(parts=[types.Part.from_text(text=f"{prefix}{text}")])
            for text in texts[start : start + 32]
        ]
        response = _gemini_embed_content(contents)
        vectors.extend(embedding.values for embedding in (response.embeddings or []))
    if len(vectors) != len(texts):
        raise RuntimeError(f"Gemini trả về {len(vectors)} vector cho {len(texts)} đoạn văn bản.")
    return vectors


def get_reranker_model() -> Any:
    """Tải Cross-Encoder Reranker model để tái xếp hạng Top-K ứng viên."""
    global _reranker_model
    if _reranker_model is None:
        try:
            from sentence_transformers import CrossEncoder

            try:
                _reranker_model = CrossEncoder(
                    settings.reranker_model_name, local_files_only=True
                )
            except Exception:
                _reranker_model = CrossEncoder(settings.reranker_model_name)
        except Exception:
            _reranker_model = None
    return _reranker_model
