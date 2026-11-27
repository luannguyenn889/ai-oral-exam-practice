"""Quản lý tác vụ chạy nền (Background Indexing Jobs) cho phân hệ RAG.

Nhiệm vụ:
- Khởi chạy lập chỉ mục tài liệu trên luồng nền để tránh timeout/treo HTTP khi tài liệu PDF dày.
- Ngăn chạy trùng nhiều job đồng thời trên cùng một học phần và cùng nhà cung cấp embedding.
- Theo dõi tiến độ thời gian thực (% hoàn thành, file đang xử lý, số đoạn đã embedding) cho UI polling.
- Cho phép UI tự khôi phục thanh tiến trình khi người dùng tải lại trang (F5).
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Optional

from app.services.rag.chunking import normalize_chunking_strategy
from app.services.rag.course_config import (
    resolve_course_chunking_strategy,
    resolve_course_embedding_provider,
    set_course_rag_config,
)
from app.services.rag.embeddings import (
    IndexingCancelledError,
    normalize_course_id,
    normalize_embedding_provider,
)
from app.services.rag.store import index_documents

_jobs_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}
_MAX_RETAINED_JOBS = 50


def _prune_old_jobs_locked() -> None:
    if len(_jobs) <= _MAX_RETAINED_JOBS:
        return
    completed_ids = [
        jid
        for jid, job in sorted(_jobs.items(), key=lambda item: item[1].get("started_ts", 0.0))
        if job.get("status") in ("completed", "failed", "cancelled")
    ]
    while len(_jobs) > _MAX_RETAINED_JOBS and completed_ids:
        _jobs.pop(completed_ids.pop(0), None)


def _snapshot_job(job: dict[str, Any]) -> dict[str, Any]:
    started_ts = float(job.get("started_ts", time.monotonic()))
    finished_ts = job.get("finished_ts")
    end_ts = float(finished_ts) if finished_ts is not None else time.monotonic()
    elapsed = max(0, int(round(end_ts - started_ts)))
    return {
        "job_id": job["job_id"],
        "course_id": job["course_id"],
        "status": job["status"],
        "phase": job.get("phase", "queued"),
        "percent": int(job.get("percent", 0)),
        "message": str(job.get("message", "")),
        "current_file": job.get("current_file"),
        "processed_files": int(job.get("processed_files", 0)),
        "total_files": int(job.get("total_files", 0)),
        "processed_chunks": int(job.get("processed_chunks", 0)),
        "total_chunks": int(job.get("total_chunks", 0)),
        "embedding_provider": job["embedding_provider"],
        "chunking_strategy": job["chunking_strategy"],
        "elapsed_seconds": elapsed,
        "result": job.get("result"),
        "error": job.get("error"),
    }


def get_active_index_job(
    course_id: str,
    embedding_provider: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Trả về job lập chỉ mục đang chạy cho học phần (nếu có)."""
    norm_course = normalize_course_id(course_id)
    target_provider = (
        normalize_embedding_provider(embedding_provider) if embedding_provider else None
    )
    with _jobs_lock:
        for job in reversed(list(_jobs.values())):
            if job.get("course_id") != norm_course:
                continue
            if job.get("status") not in ("queued", "running"):
                continue
            if target_provider and job.get("embedding_provider") != target_provider:
                continue
            return _snapshot_job(job)
    return None


def get_index_job(job_id: str) -> Optional[dict[str, Any]]:
    with _jobs_lock:
        job = _jobs.get(job_id)
        return _snapshot_job(job) if job else None


def start_index_job(
    course_id: str = "default",
    force_reindex: bool = False,
    embedding_provider: Optional[str] = None,
    chunking_strategy: Optional[str] = None,
) -> dict[str, Any]:
    """Khởi chạy tác vụ lập chỉ mục ở luồng nền và trả về job_id ngay lập tức."""
    norm_course = normalize_course_id(course_id)
    if (isinstance(embedding_provider, str) and embedding_provider.strip()) or (
        isinstance(chunking_strategy, str) and chunking_strategy.strip()
    ):
        set_course_rag_config(
            norm_course,
            embedding_provider=embedding_provider,
            chunking_strategy=chunking_strategy,
        )
    norm_provider = resolve_course_embedding_provider(norm_course, embedding_provider)
    norm_strategy = resolve_course_chunking_strategy(norm_course, chunking_strategy)

    with _jobs_lock:
        # Nếu cùng học phần & provider đang chạy nền, tái sử dụng job đó để tránh chạy chồng
        for existing in reversed(list(_jobs.values())):
            if (
                existing.get("course_id") == norm_course
                and existing.get("embedding_provider") == norm_provider
                and existing.get("status") in ("queued", "running")
            ):
                return _snapshot_job(existing)

        cancel_event = threading.Event()
        job_id = f"rag-job-{uuid.uuid4().hex[:10]}"
        now_ts = time.monotonic()
        job: dict[str, Any] = {
            "job_id": job_id,
            "course_id": norm_course,
            "status": "running",
            "phase": "queued",
            "percent": 1,
            "message": f"Đã đưa tác vụ lập chỉ mục học phần {norm_course} vào hàng đợi...",
            "current_file": None,
            "processed_files": 0,
            "total_files": 0,
            "processed_chunks": 0,
            "total_chunks": 0,
            "embedding_provider": norm_provider,
            "chunking_strategy": norm_strategy,
            "started_ts": now_ts,
            "finished_ts": None,
            "result": None,
            "error": None,
            "cancel_event": cancel_event,
        }
        _jobs[job_id] = job
        _prune_old_jobs_locked()
        initial_snapshot = _snapshot_job(job)

    def _on_progress(update: dict[str, Any]) -> None:
        with _jobs_lock:
            current = _jobs.get(job_id)
            if not current or current.get("status") in ("completed", "failed", "cancelled"):
                return
            if current.get("phase") == "cancelling":
                return
            for key in (
                "phase",
                "percent",
                "message",
                "current_file",
                "processed_files",
                "total_files",
                "processed_chunks",
                "total_chunks",
            ):
                if key in update:
                    current[key] = update[key]

    def _worker() -> None:
        try:
            res = index_documents(
                course_id=norm_course,
                force_reindex=force_reindex,
                embedding_provider=norm_provider,
                chunking_strategy=norm_strategy,
                progress_callback=_on_progress,
                cancel_event=cancel_event,
            )
            with _jobs_lock:
                current = _jobs.get(job_id)
                if current:
                    current["status"] = "completed"
                    current["phase"] = "completed"
                    current["percent"] = 100
                    current["result"] = res
                    current["finished_ts"] = time.monotonic()
                    current["message"] = (
                        f"Đã hoàn tất đồng bộ {res.get('total_chunks', 0)} đoạn từ "
                        f"{res.get('total_files', 0)} tài liệu."
                    )
        except IndexingCancelledError:
            with _jobs_lock:
                current = _jobs.get(job_id)
                if current:
                    current["status"] = "cancelled"
                    current["phase"] = "cancelled"
                    current["finished_ts"] = time.monotonic()
                    current["message"] = "Đã hủy tác vụ lập chỉ mục theo yêu cầu."
        except Exception as exc:
            with _jobs_lock:
                current = _jobs.get(job_id)
                if current:
                    current["status"] = "failed"
                    current["phase"] = "failed"
                    current["error"] = str(exc)
                    current["finished_ts"] = time.monotonic()
                    current["message"] = f"Lập chỉ mục thất bại: {exc}"

    worker = threading.Thread(target=_worker, name=f"rag-index-{job_id}", daemon=True)
    worker.start()
    return initial_snapshot


def cancel_index_job(job_id: str) -> Optional[dict[str, Any]]:
    """Gửi tín hiệu hủy mềm cho job lập chỉ mục đang chạy."""
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return None
        if job.get("status") in ("completed", "failed", "cancelled"):
            return _snapshot_job(job)
        ev = job.get("cancel_event")
        if isinstance(ev, threading.Event):
            ev.set()
        job["phase"] = "cancelling"
        job["message"] = "Đang hủy tác vụ lập chỉ mục..."
        return _snapshot_job(job)
