"""Module quản lý vòng đời thư mục lưu trữ tài liệu của từng học phần trên Server.

Nhiệm vụ:
- Chuẩn hóa tên thư mục theo mã học phần (`_normalize_folder_code`) và dọn sạch toàn bộ vector RAG liên quan trên tất cả collection (`_purge_course_vectors`).
- Di chuyển tệp an toàn giữa các thư mục trên Windows (`_migrate_folder_contents`).
- Đồng bộ thao tác CRUD học phần từ Backend Spring Boot:
    + `ensure_course_folder`: Đảm bảo thư mục mã học phần tồn tại và gom tệp từ thư mục UUID cũ (nếu có).
    + `rename_course_folder`: Di chuyển tài liệu từ mã học phần cũ sang mã mới, xóa vector cũ và lập chỉ mục lại.
    + `delete_course_folder`: Xóa thư mục tài liệu cùng toàn bộ chunk/BM25 của học phần đó.
"""

import os
import shutil
from typing import Any, Optional

from app.config import settings
from app.services.rag.course_config import delete_course_rag_config, rename_course_rag_config
from app.services.rag.embeddings import EMBEDDING_PROVIDERS, normalize_course_id
from app.services.rag.store import (
    get_chroma_collection,
    index_documents,
    invalidate_bm25_cache,
    list_course_files,
)


def _normalize_folder_code(code: Optional[str]) -> str:
    norm = normalize_course_id(code)
    if norm.lower() == "default":
        return "default"
    return norm.upper()


def _purge_course_vectors(course_keys: list[Optional[str]]) -> int:
    """Xóa toàn bộ chunk khỏi ChromaDB & BM25 cache cho các định danh học phần đã cho."""
    cleaned_keys: list[str] = []
    for raw_key in course_keys:
        if raw_key and raw_key.strip():
            for candidate in (raw_key.strip(), normalize_course_id(raw_key)):
                if candidate and candidate not in cleaned_keys:
                    cleaned_keys.append(candidate)

    removed_count = 0
    for key in cleaned_keys:
        invalidate_bm25_cache(key)

    for prov in EMBEDDING_PROVIDERS:
        try:
            collection = get_chroma_collection(provider=prov)
        except Exception:
            continue
        for key in cleaned_keys:
            try:
                existing = collection.get(where={"course_id": key}, include=[])
                ids = existing.get("ids", []) if existing else []
                if ids:
                    for start in range(0, len(ids), 500):
                        collection.delete(ids=ids[start : start + 500])
                    removed_count += len(ids)
            except Exception:
                continue
    return removed_count


def _migrate_folder_contents(source_dir: os.PathLike[str] | Any, target_dir: Any) -> int:
    """Di chuyển tệp từ source_dir sang target_dir và xóa source_dir (an toàn trên Windows)."""
    if not source_dir.exists() or not source_dir.is_dir():
        return 0
    if target_dir.exists():
        try:
            if os.path.samefile(source_dir, target_dir):
                return 0
        except OSError:
            pass

    target_dir.mkdir(parents=True, exist_ok=True)
    moved_files = 0
    for item in list(source_dir.iterdir()):
        dest = target_dir / item.name
        if item.is_file():
            if dest.exists():
                item.unlink(missing_ok=True)
            else:
                shutil.move(str(item), str(dest))
                moved_files += 1
        elif item.is_dir():
            moved_files += _migrate_folder_contents(item, dest)

    try:
        shutil.rmtree(source_dir, ignore_errors=True)
    except Exception:
        pass
    return moved_files


def ensure_course_folder(course_code: str, legacy_id: Optional[str] = None) -> dict[str, Any]:
    """Đảm bảo thư mục lưu tài liệu tồn tại theo mã học phần và gom tệp từ thư mục UUID cũ nếu có."""
    norm_code = _normalize_folder_code(course_code)
    target_dir = settings.course_documents_dir(norm_code)

    migrated_files = 0
    purge_keys: list[Optional[str]] = []

    norm_legacy = normalize_course_id(legacy_id) if legacy_id else None
    if norm_legacy and norm_legacy.lower() != norm_code.lower():
        legacy_dir = settings.resolve_course_documents_dir(norm_legacy)
        if legacy_dir.exists():
            migrated_files += _migrate_folder_contents(legacy_dir, target_dir)
            purge_keys.extend([legacy_id, norm_legacy])

    if purge_keys:
        _purge_course_vectors(purge_keys)

    if migrated_files > 0:
        index_documents(course_id=norm_code, force_reindex=False)

    return {
        "course_code": norm_code,
        "folder_path": str(target_dir),
        "migrated_files": migrated_files,
        "status": "ready",
    }


def rename_course_folder(
    old_code: str, new_code: str, legacy_id: Optional[str] = None
) -> dict[str, Any]:
    """Đổi tên/di chuyển thư mục tài liệu từ mã học phần cũ sang mã mới và đồng bộ chỉ mục RAG."""
    norm_old = _normalize_folder_code(old_code)
    norm_new = _normalize_folder_code(new_code)
    target_dir = settings.course_documents_dir(norm_new)

    migrated_files = 0
    purge_keys: list[Optional[str]] = []

    if norm_old != norm_new:
        old_dir = settings.resolve_course_documents_dir(norm_old)
        if old_dir.exists():
            try:
                same_target = target_dir.exists() and os.path.samefile(old_dir, target_dir)
            except OSError:
                same_target = False
            if not same_target:
                migrated_files += _migrate_folder_contents(old_dir, target_dir)
        purge_keys.extend([old_code, norm_old])

    norm_legacy = normalize_course_id(legacy_id) if legacy_id else None
    if norm_legacy and norm_legacy.lower() not in {norm_old.lower(), norm_new.lower()}:
        legacy_dir = settings.resolve_course_documents_dir(norm_legacy)
        if legacy_dir.exists():
            migrated_files += _migrate_folder_contents(legacy_dir, target_dir)
        purge_keys.extend([legacy_id, norm_legacy])

    if purge_keys:
        _purge_course_vectors(purge_keys)

    rename_course_rag_config(norm_old, norm_new)

    if migrated_files > 0 or (norm_old != norm_new and list_course_files(norm_new)):
        index_documents(course_id=norm_new, force_reindex=False)

    return {
        "course_code": norm_new,
        "old_code": norm_old,
        "folder_path": str(target_dir),
        "migrated_files": migrated_files,
        "status": "renamed",
    }


def delete_course_folder(course_code: str, legacy_id: Optional[str] = None) -> dict[str, Any]:
    """Xóa thư mục tài liệu và toàn bộ chunk RAG của học phần."""
    norm_code = _normalize_folder_code(course_code)
    candidate_dirs = [settings.resolve_course_documents_dir(norm_code)]
    purge_keys: list[Optional[str]] = [course_code, norm_code]

    if course_code and course_code.strip() and course_code.strip() != norm_code:
        candidate_dirs.append(settings.resolve_course_documents_dir(course_code.strip()))

    if legacy_id and legacy_id.strip():
        norm_legacy = normalize_course_id(legacy_id)
        candidate_dirs.append(settings.resolve_course_documents_dir(norm_legacy))
        purge_keys.extend([legacy_id, norm_legacy])

    deleted_dirs = 0
    seen_paths: set[str] = set()
    for folder in candidate_dirs:
        key = os.path.normcase(str(folder.resolve()))
        if key in seen_paths:
            continue
        seen_paths.add(key)
        if folder.exists() and folder.is_dir():
            shutil.rmtree(folder, ignore_errors=True)
            deleted_dirs += 1

    removed_chunks = _purge_course_vectors(purge_keys)
    delete_course_rag_config(norm_code)
    return {
        "course_code": norm_code,
        "deleted_dirs": deleted_dirs,
        "removed_chunks": removed_chunks,
        "status": "deleted",
    }
