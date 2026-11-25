"""Lưu trữ cấu hình RAG (embedding_provider & chunking_strategy) bền vững theo từng học phần.

Nhiệm vụ:
- Lưu cấu hình lựa chọn của Giảng viên tại `course_rag_configs.json` (cùng cấp thư mục `documents`).
- Khi bất kỳ luồng nào (Tìm kiếm RAG, AI gợi ý Đáp án/Rubric, Chấm điểm bài thi) không truyền cứng
  `embedding_provider`, hệ thống tự động tra cứu cấu hình đã lưu của học phần đó (fallback về `.env`).
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.config import settings
from app.services.rag.chunking import DEFAULT_CHUNKING_STRATEGY, normalize_chunking_strategy
from app.services.rag.embeddings import normalize_course_id, normalize_embedding_provider

_config_lock = threading.Lock()


def _config_file_path() -> Path:
    return settings.resolved_documents_dir.parent / "course_rag_configs.json"


def _load_all_locked() -> dict[str, dict[str, Any]]:
    path = _config_file_path()
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8") or "{}")
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _save_all_locked(data: dict[str, dict[str, Any]]) -> None:
    path = _config_file_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"[AI-SERVICE] Khong luu duoc course_rag_configs.json: {exc}", flush=True)


def get_course_rag_config(course_id: str) -> dict[str, str]:
    """Lấy cấu hình RAG hiện tại của học phần (fallback về cấu hình mặc định của hệ thống)."""
    norm_course = normalize_course_id(course_id).upper()
    default_provider = normalize_embedding_provider(None)
    default_strategy = DEFAULT_CHUNKING_STRATEGY

    with _config_lock:
        all_cfg = _load_all_locked()
        entry = all_cfg.get(norm_course) or all_cfg.get(normalize_course_id(course_id)) or {}

    provider = (
        normalize_embedding_provider(entry.get("embedding_provider"))
        if entry.get("embedding_provider")
        else default_provider
    )
    strategy = (
        normalize_chunking_strategy(entry.get("chunking_strategy"))
        if entry.get("chunking_strategy")
        else default_strategy
    )
    return {
        "course_id": norm_course,
        "embedding_provider": provider,
        "chunking_strategy": strategy,
    }


def set_course_rag_config(
    course_id: str,
    embedding_provider: Optional[str] = None,
    chunking_strategy: Optional[str] = None,
) -> dict[str, str]:
    """Lưu cập nhật cấu hình embedding_provider và/hoặc chunking_strategy cho học phần."""
    norm_course = normalize_course_id(course_id).upper()
    with _config_lock:
        all_cfg = _load_all_locked()
        current = dict(all_cfg.get(norm_course) or {})
        resolved_provider = (
            normalize_embedding_provider(embedding_provider)
            if isinstance(embedding_provider, str) and embedding_provider.strip()
            else normalize_embedding_provider(current.get("embedding_provider"))
        )
        resolved_strategy = (
            normalize_chunking_strategy(chunking_strategy)
            if isinstance(chunking_strategy, str) and chunking_strategy.strip()
            else normalize_chunking_strategy(
                current.get("chunking_strategy") or DEFAULT_CHUNKING_STRATEGY
            )
        )
        all_cfg[norm_course] = {
            "embedding_provider": resolved_provider,
            "chunking_strategy": resolved_strategy,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        _save_all_locked(all_cfg)

    return {
        "course_id": norm_course,
        "embedding_provider": resolved_provider,
        "chunking_strategy": resolved_strategy,
    }


def resolve_course_embedding_provider(
    course_id: str,
    explicit_provider: Optional[str] = None,
) -> str:
    """Ưu tiên provider truyền trực tiếp; nếu không có thì lấy theo cấu hình đã lưu của học phần."""
    if isinstance(explicit_provider, str) and explicit_provider.strip():
        return normalize_embedding_provider(explicit_provider)
    return get_course_rag_config(course_id)["embedding_provider"]


def resolve_course_chunking_strategy(
    course_id: str,
    explicit_strategy: Optional[str] = None,
) -> str:
    """Ưu tiên strategy truyền trực tiếp; nếu không có thì lấy theo cấu hình đã lưu của học phần."""
    if isinstance(explicit_strategy, str) and explicit_strategy.strip():
        return normalize_chunking_strategy(explicit_strategy)
    return get_course_rag_config(course_id)["chunking_strategy"]


def rename_course_rag_config(old_code: str, new_code: str) -> None:
    norm_old = normalize_course_id(old_code).upper()
    norm_new = normalize_course_id(new_code).upper()
    if norm_old == norm_new:
        return
    with _config_lock:
        all_cfg = _load_all_locked()
        if norm_old in all_cfg:
            entry = all_cfg.pop(norm_old)
            if norm_new not in all_cfg:
                all_cfg[norm_new] = entry
            _save_all_locked(all_cfg)


def delete_course_rag_config(course_code: str) -> None:
    norm_code = normalize_course_id(course_code).upper()
    with _config_lock:
        all_cfg = _load_all_locked()
        if norm_code in all_cfg:
            all_cfg.pop(norm_code, None)
            _save_all_locked(all_cfg)
