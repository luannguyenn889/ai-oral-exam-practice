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

from concurrent.futures import ThreadPoolExecutor
import importlib.util
import os
import re
import threading
import warnings
from typing import Any, Callable, Optional

from app.config import settings

warnings.filterwarnings("ignore", message=".*unauthenticated requests.*")
warnings.filterwarnings("ignore", message=".*HF Hub.*")
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ.setdefault("OMP_NUM_THREADS", str(max(1, os.cpu_count() or 4)))

EMBEDDING_PROVIDERS = ("local", "e5-small", "gemini")

_embedding_models: dict[str, Any] = {}
_embedding_lock = threading.Lock()
_reranker_model: Any = None

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


def _can_use_onnx_backend() -> bool:
    return (
        importlib.util.find_spec("onnxruntime") is not None
        and importlib.util.find_spec("optimum.onnxruntime") is not None
    )


def _load_sentence_transformer(target_name: str, backend: str = "torch", device: str = "cpu") -> Any:
    from sentence_transformers import SentenceTransformer

    kwargs: dict[str, Any] = {"device": device}
    if backend == "onnx":
        kwargs["backend"] = "onnx"
    elif device == "cuda":
        try:
            import torch

            kwargs["model_kwargs"] = {"torch_dtype": torch.float16}
        except Exception:
            pass

    try:
        return SentenceTransformer(target_name, local_files_only=True, **kwargs)
    except Exception:
        return SentenceTransformer(target_name, **kwargs)


def get_embedding_model(model_name: Optional[str] = None) -> Any:
    """Tải embedding model theo cơ chế Lazy load (tự chọn ONNX trên CPU hoặc CUDA FP16 trên GPU)."""
    target_name = (model_name or settings.embedding_model_name).strip()
    if target_name in _embedding_models:
        return _embedding_models[target_name]

    with _embedding_lock:
        if target_name not in _embedding_models:
            device = "cpu"
            try:
                import torch

                if torch.cuda.is_available():
                    device = "cuda"
            except Exception:
                device = "cpu"

            preferred = (settings.embedding_backend or "auto").strip().lower()
            use_onnx = device == "cpu" and preferred in ("auto", "onnx") and _can_use_onnx_backend()

            loaded_backend = "torch"
            if use_onnx:
                try:
                    _embedding_models[target_name] = _load_sentence_transformer(
                        target_name, backend="onnx", device="cpu"
                    )
                    loaded_backend = "onnx"
                except Exception as exc:
                    print(
                        f"[AI-SERVICE] Khong dung duoc ONNX backend cho '{target_name}' ({exc}), chuyen ve PyTorch.",
                        flush=True,
                    )
                    _embedding_models[target_name] = _load_sentence_transformer(
                        target_name, backend="torch", device="cpu"
                    )
            else:
                _embedding_models[target_name] = _load_sentence_transformer(
                    target_name, backend="torch", device=device
                )

            print(
                f"[AI-SERVICE] Embedding model '{target_name}' ready (device={device}, backend={loaded_backend}).",
                flush=True,
            )
    return _embedding_models[target_name]


def embed_texts(
    texts: list[str],
    task: str = "document",
    provider: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> list[list[float]]:
    """Create normalized vectors locally (ONNX/CUDA, batch 64) or via parallel multi-key Gemini embeddings."""
    if not texts:
        return []
    total_texts = len(texts)
    prov = normalize_embedding_provider(provider)
    if prov in ("local", "e5-small"):
        model_name = get_active_embedding_name(prov)
        model = get_embedding_model(model_name)
        inputs = texts
        if "e5" in model_name.lower():
            prefix = "query: " if task == "query" else "passage: "
            inputs = [f"{prefix}{t}" for t in texts]
        batch_size = max(1, int(settings.embedding_batch_size or 64))
        if progress_callback is None or total_texts <= batch_size:
            result = model.encode(
                inputs, batch_size=batch_size, show_progress_bar=False, normalize_embeddings=True
            ).tolist()
            if progress_callback is not None:
                progress_callback(total_texts, total_texts)
            return result

        vectors: list[list[float]] = []
        for start in range(0, total_texts, batch_size):
            batch_inputs = inputs[start : start + batch_size]
            batch_vecs = model.encode(
                batch_inputs,
                batch_size=batch_size,
                show_progress_bar=False,
                normalize_embeddings=True,
            ).tolist()
            vectors.extend(batch_vecs)
            progress_callback(min(start + len(batch_inputs), total_texts), total_texts)
        return vectors

    from app.services.gemini_client import get_gemini_api_keys, run_with_gemini_client
    from google.genai import types

    prefix = "task: search result | query: " if task == "query" else "title: none | text: "
    batch_size = min(100, max(1, int(settings.gemini_embedding_batch_size or 100)))
    batches = [texts[start : start + batch_size] for start in range(0, total_texts, batch_size)]

    def _embed_batch(batch_texts: list[str]) -> list[list[float]]:
        contents = [
            types.Content(parts=[types.Part.from_text(text=f"{prefix}{text}")])
            for text in batch_texts
        ]
        response = run_with_gemini_client(
            lambda client: client.models.embed_content(
                model=settings.gemini_embedding_model_name,
                contents=contents,
                config=types.EmbedContentConfig(
                    output_dimensionality=settings.gemini_embedding_dimensions
                ),
            ),
            missing_key_message="Chưa cấu hình GEMINI_API_KEY / GEMINI_API_KEYS trong file .env để dùng Gemini Embedding.",
        )
        return [list(embedding.values) for embedding in (response.embeddings or [])]

    vectors = []
    done_count = 0
    available_keys = max(1, len(get_gemini_api_keys()))
    max_workers = min(len(batches), available_keys, max(1, int(settings.gemini_embedding_max_workers or 3)))

    if max_workers > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for batch_vectors in executor.map(_embed_batch, batches):
                vectors.extend(batch_vectors)
                done_count += len(batch_vectors)
                if progress_callback is not None:
                    progress_callback(min(done_count, total_texts), total_texts)
    else:
        for batch in batches:
            batch_vectors = _embed_batch(batch)
            vectors.extend(batch_vectors)
            done_count += len(batch_vectors)
            if progress_callback is not None:
                progress_callback(min(done_count, total_texts), total_texts)

    if len(vectors) != total_texts:
        raise RuntimeError(f"Gemini trả về {len(vectors)} vector cho {total_texts} đoạn văn bản.")
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
