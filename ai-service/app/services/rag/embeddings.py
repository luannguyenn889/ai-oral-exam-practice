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
import time
import unicodedata
import warnings
from typing import Any, Callable, Optional

from app.config import settings

warnings.filterwarnings("ignore", message=".*unauthenticated requests.*")
warnings.filterwarnings("ignore", message=".*HF Hub.*")
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ.setdefault("OMP_NUM_THREADS", str(max(1, os.cpu_count() or 4)))

EMBEDDING_PROVIDERS = ("local", "e5-small", "gemini")
RERANKER_PROVIDERS = ("minilm", "bge-m3")


class IndexingCancelledError(Exception):
    """Ngoại lệ báo hiệu tác vụ lập chỉ mục đã được người dùng hủy an toàn."""

_embedding_models: dict[str, Any] = {}
_embedding_lock = threading.Lock()
_reranker_models: dict[str, Any] = {}
_reranker_lock = threading.Lock()

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
    if not cleaned or cleaned.lower() == "default":
        return "default"
    return cleaned.upper()


def _strip_vietnamese_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return stripped.replace("đ", "d").replace("Đ", "D")


def is_rerank_score_relevant(score: float, provider: Optional[str] = None) -> bool:
    """Kiểm tra điểm Cross-Encoder có vượt ngưỡng liên quan theo từng họ reranker."""
    prov = normalize_reranker_provider(provider)
    if prov == "bge-m3":
        thr = float(getattr(settings, "rag_min_rerank_score", 0.03))
        return score >= thr
    thr = float(getattr(settings, "rag_min_minilm_rerank_score", -4.5))
    return score >= thr


def get_min_dense_similarity(provider: Optional[str] = None) -> float:
    """Ngưỡng Cosine Similarity tối thiểu tham chiếu theo đặc trưng từng không gian embedding."""
    prov = normalize_embedding_provider(provider)
    if prov == "e5-small":
        return float(getattr(settings, "rag_min_dense_sim_e5", 0.76))
    if prov == "gemini":
        return float(getattr(settings, "rag_min_dense_sim_gemini", 0.52))
    return float(getattr(settings, "rag_min_dense_sim_local", 0.35))


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


def normalize_reranker_provider(provider: Optional[str] = None) -> str:
    raw = provider if isinstance(provider, str) else None
    prov = (raw or settings.reranker_provider or "minilm").strip().lower()
    if prov in ("bge-m3", "bge", "bge_m3", "baai/bge-reranker-v2-m3", "bge-reranker-v2-m3"):
        return "bge-m3"
    return "minilm"


def get_active_reranker_name(provider: Optional[str] = None) -> str:
    prov = normalize_reranker_provider(provider)
    if prov == "bge-m3":
        return settings.bge_reranker_model_name
    return settings.reranker_model_name


def clean_oral_query(text: str) -> str:
    """Lọc bỏ các từ đệm, ngập ngừng hội thoại để làm sắc nét véc-tơ truy vấn."""
    if not text:
        return ""
    cleaned = text
    for pat in FILLER_PATTERNS:
        cleaned = re.sub(pat, " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned if len(cleaned) > 5 else text.strip()


_BM25_STOPWORDS = frozenset(
    {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "of", "to", "in", "for", "on", "with", "that", "this", "these", "those",
        "as", "by", "from", "which", "and", "or", "not", "if", "when", "where",
        "là", "của", "và", "các", "những", "trong", "cho", "được", "có", "một",
        "để", "với", "khi", "này", "đó", "về", "từ", "theo", "như", "tại",
        "thì", "mà", "nhưng", "nên", "nếu", "vì", "do", "bởi", "nào", "thế",
        "sao", "vậy", "gì", "cách", "làm", "nói", "rằng", "hãy", "trên", "dưới",
    }
)


def tokenize_text(text: str) -> list[str]:
    """Tách từ cho BM25: lọc hư từ phổ biến, giữ có dấu + bản không dấu tiếng Việt và tách từ ghép '-'/'_'."""
    if not text:
        return []
    raw_tokens = re.findall(r"[A-Za-zÀ-ỹ0-9]+(?:[-_][A-Za-zÀ-ỹ0-9]+)*", text.lower())
    tokens: list[str] = []
    for tok in raw_tokens:
        if not tok or tok in _BM25_STOPWORDS:
            continue
        tokens.append(tok)
        if "-" in tok or "_" in tok:
            for part in re.split(r"[-_]+", tok):
                if len(part) >= 2 and part not in _BM25_STOPWORDS:
                    tokens.append(part)
                    folded_part = _strip_vietnamese_accents(part)
                    if folded_part and folded_part != part:
                        tokens.append(folded_part)
        folded = _strip_vietnamese_accents(tok)
        if folded and folded != tok:
            tokens.append(folded)
    return tokens


def _can_use_onnx_backend() -> bool:
    try:
        return (
            importlib.util.find_spec("onnxruntime") is not None
            and importlib.util.find_spec("optimum.onnxruntime") is not None
        )
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


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
    cancel_event: Optional[threading.Event] = None,
) -> list[list[float]]:
    """Create normalized vectors locally (ONNX/CUDA, batch 64) or via parallel multi-key Gemini embeddings."""
    if not texts:
        return []
    if cancel_event is not None and cancel_event.is_set():
        raise IndexingCancelledError("Tác vụ lập chỉ mục đã bị hủy.")
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
            if cancel_event is not None and cancel_event.is_set():
                raise IndexingCancelledError("Tác vụ lập chỉ mục đã bị hủy.")
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
    batch_size = min(100, max(1, int(settings.gemini_embedding_batch_size or 50)))
    batches = [texts[start : start + batch_size] for start in range(0, total_texts, batch_size)]

    def _embed_batch(batch_texts: list[str]) -> list[list[float]]:
        if cancel_event is not None and cancel_event.is_set():
            raise IndexingCancelledError("Tác vụ lập chỉ mục đã bị hủy.")
        contents = [
            types.Content(parts=[types.Part.from_text(text=f"{prefix}{text}")])
            for text in batch_texts
        ]
        max_retries = 3
        for attempt in range(max_retries + 1):
            if cancel_event is not None and cancel_event.is_set():
                raise IndexingCancelledError("Tác vụ lập chỉ mục đã bị hủy.")
            try:
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
                if len(batches) > 1:
                    if cancel_event is not None:
                        if cancel_event.wait(0.25):
                            raise IndexingCancelledError("Tác vụ lập chỉ mục đã bị hủy.")
                    else:
                        time.sleep(0.25)
                return [list(embedding.values) for embedding in (response.embeddings or [])]
            except IndexingCancelledError:
                raise
            except Exception as exc:
                msg = str(exc).lower()
                is_rate_limit = any(
                    tok in msg
                    for tok in ("429", "resource_exhausted", "rate limit", "too many requests", "503")
                )
                if not is_rate_limit or attempt >= max_retries:
                    raise
                wait_sec = 15 * (attempt + 1)
                print(
                    f"[AI-SERVICE] Gemini Embedding cham han muc tam thoi, cho {wait_sec}s roi thu lai ({attempt + 1}/{max_retries})...",
                    flush=True,
                )
                if cancel_event is not None:
                    if cancel_event.wait(wait_sec):
                        raise IndexingCancelledError("Tác vụ lập chỉ mục đã bị hủy trong lúc chờ hạn mức.")
                else:
                    time.sleep(wait_sec)
        raise RuntimeError("Không thể tạo vector Gemini Embedding sau nhiều lần thử lại.")

    vectors = []
    done_count = 0
    available_keys = max(1, len(get_gemini_api_keys()))
    max_workers = min(len(batches), available_keys, max(1, int(settings.gemini_embedding_max_workers or 3)))

    if max_workers > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for batch_vectors in executor.map(_embed_batch, batches):
                if cancel_event is not None and cancel_event.is_set():
                    raise IndexingCancelledError("Tác vụ lập chỉ mục đã bị hủy.")
                vectors.extend(batch_vectors)
                done_count += len(batch_vectors)
                if progress_callback is not None:
                    progress_callback(min(done_count, total_texts), total_texts)
    else:
        for batch in batches:
            if cancel_event is not None and cancel_event.is_set():
                raise IndexingCancelledError("Tác vụ lập chỉ mục đã bị hủy.")
            batch_vectors = _embed_batch(batch)
            vectors.extend(batch_vectors)
            done_count += len(batch_vectors)
            if progress_callback is not None:
                progress_callback(min(done_count, total_texts), total_texts)

    if len(vectors) != total_texts:
        raise RuntimeError(f"Gemini trả về {len(vectors)} vector cho {total_texts} đoạn văn bản.")
    return vectors


def get_reranker_model(
    model_name: Optional[str] = None,
    provider: Optional[str] = None,
) -> Any:
    """Tải Cross-Encoder Reranker model (MiniLM hoặc BAAI/bge-reranker-v2-m3) để tái xếp hạng Top-K ứng viên."""
    target_name = (model_name or get_active_reranker_name(provider)).strip()
    if target_name in _reranker_models:
        return _reranker_models[target_name]

    with _reranker_lock:
        if target_name not in _reranker_models:
            try:
                from sentence_transformers import CrossEncoder

                device = "cpu"
                kwargs: dict[str, Any] = {}
                try:
                    import torch

                    if torch.cuda.is_available():
                        device = "cuda"
                        kwargs["model_kwargs"] = {"torch_dtype": torch.float16}
                except Exception:
                    device = "cpu"
                kwargs["device"] = device

                try:
                    loaded = CrossEncoder(target_name, local_files_only=True, **kwargs)
                except Exception:
                    loaded = CrossEncoder(target_name, **kwargs)

                _reranker_models[target_name] = loaded
                print(
                    f"[AI-SERVICE] Reranker model '{target_name}' ready (device={device}).",
                    flush=True,
                )
            except Exception as exc:
                print(
                    f"[AI-SERVICE] Khong nap duoc Reranker '{target_name}' ({exc}), fallback ve RRF.",
                    flush=True,
                )
                return None
    return _reranker_models.get(target_name)
