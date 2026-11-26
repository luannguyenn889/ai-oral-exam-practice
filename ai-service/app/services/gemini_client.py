"""Quản lý đa khóa Gemini API (Round-Robin + Failover tự động khi chạm hạn mức/lỗi).

Nhiệm vụ:
- Đọc danh sách khóa từ `GEMINI_API_KEYS` (phân tách bằng dấu phẩy) và `GEMINI_API_KEY`.
- Phân phối request lần lượt qua các khóa (Round-Robin) để giảm tải RPM.
- Khi một khóa gặp lỗi quota/rate-limit (429, RESOURCE_EXHAUSTED) hoặc lỗi xác thực/tạm thời,
  tự động đưa vào cooldown ngắn và chuyển sang khóa dự phòng tiếp theo.
"""

from __future__ import annotations

import os
import re
import threading
import time
from typing import Callable, Optional, TypeVar

from google import genai

from app.config import settings

T = TypeVar("T")

_lock = threading.Lock()
_rr_index = 0
_cooldown_until: dict[str, float] = {}

_QUOTA_COOLDOWN_SECONDS = 60.0
_AUTH_COOLDOWN_SECONDS = 300.0


def _split_keys(raw: str) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in re.split(r"[,;\s]+", raw) if part and part.strip()]


def get_gemini_api_keys(explicit_key: Optional[str] = None) -> list[str]:
    """Trả về danh sách Gemini API key hợp lệ (đã khử trùng lặp, giữ nguyên thứ tự)."""
    candidates: list[str] = []
    if explicit_key and explicit_key.strip():
        candidates.extend(_split_keys(explicit_key))

    candidates.extend(_split_keys(settings.gemini_api_keys))
    candidates.extend(_split_keys(os.environ.get("GEMINI_API_KEYS", "")))
    candidates.extend(_split_keys(settings.gemini_api_key))
    candidates.extend(_split_keys(os.environ.get("GEMINI_API_KEY", "")))

    unique: list[str] = []
    seen: set[str] = set()
    for key in candidates:
        if key not in seen:
            seen.add(key)
            unique.append(key)
    return unique


def has_gemini_api_key() -> bool:
    return len(get_gemini_api_keys()) > 0


def _classify_error_cooldown(exc: Exception) -> Optional[float]:
    """Trả về số giây cooldown nếu lỗi đáng để chuyển sang key khác, ngược lại None."""
    msg = str(exc).lower()
    if any(
        token in msg
        for token in (
            "429",
            "resource_exhausted",
            "quota",
            "rate limit",
            "too many requests",
            "503",
            "unavailable",
            "overloaded",
        )
    ):
        return _QUOTA_COOLDOWN_SECONDS
    if any(
        token in msg
        for token in (
            "api_key_invalid",
            "api key not valid",
            "permission_denied",
            "unauthenticated",
            "401",
            "403",
        )
    ):
        return _AUTH_COOLDOWN_SECONDS
    return None


def _ordered_keys_for_attempt(keys: list[str]) -> list[str]:
    """Sắp xếp key theo Round-Robin, đẩy các key đang cooldown xuống cuối."""
    global _rr_index
    now = time.monotonic()
    with _lock:
        start = _rr_index % len(keys)
        _rr_index = (_rr_index + 1) % len(keys)
        rotated = keys[start:] + keys[:start]
        ready = [k for k in rotated if _cooldown_until.get(k, 0.0) <= now]
        cooling = [k for k in rotated if _cooldown_until.get(k, 0.0) > now]
        return ready + cooling


def run_with_gemini_client(
    fn: Callable[[genai.Client], T],
    explicit_key: Optional[str] = None,
    missing_key_message: str = "Chưa cấu hình GEMINI_API_KEY / GEMINI_API_KEYS trong file .env.",
) -> T:
    """Thực thi callback với `genai.Client`, tự động xoay vòng và failover qua các key khả dụng."""
    keys = get_gemini_api_keys(explicit_key)
    if not keys:
        raise ValueError(missing_key_message)

    ordered_keys = _ordered_keys_for_attempt(keys)
    last_exc: Optional[Exception] = None

    for idx, key in enumerate(ordered_keys):
        try:
            client = genai.Client(api_key=key)
            return fn(client)
        except Exception as exc:
            last_exc = exc
            cooldown = _classify_error_cooldown(exc)
            if cooldown is None or idx == len(ordered_keys) - 1:
                raise
            with _lock:
                _cooldown_until[key] = time.monotonic() + cooldown
            masked = f"...{key[-6:]}" if len(key) > 6 else "***"
            detail = " ".join(str(exc).split())[:140]
            print(
                f"[AI-SERVICE] Gemini key {masked} gap loi ({type(exc).__name__}: {detail}), chuyen sang key du phong tiep theo.",
                flush=True,
            )

    if last_exc is not None:  # pragma: no cover
        raise last_exc
    raise RuntimeError("Không thể thực thi yêu cầu Gemini API.")  # pragma: no cover


def reset_gemini_key_state() -> None:
    """Dùng cho unit test: reset bộ đếm Round-Robin và cooldown."""
    global _rr_index
    with _lock:
        _rr_index = 0
        _cooldown_until.clear()
