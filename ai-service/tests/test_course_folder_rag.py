"""Kiểm thử quản lý thư mục giáo trình theo mã học phần và API đồng bộ/xóa kho RAG."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

AI_SERVICE_DIR = Path(__file__).resolve().parent.parent
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

from app.config import settings
from app.routers import rag
from app.services import rag_service


def _run_sync(coro):
    """Chạy coroutine đồng bộ không dùng event loop/socketpair."""
    try:
        coro.send(None)
    except StopIteration as exc:
        return exc.value
    raise RuntimeError("Coroutine suspended unexpectedly in synchronous test runner.")


class _FakeUploadFile:
    def __init__(self, filename: str, data: bytes) -> None:
        self.filename = filename
        self._data = data

    async def read(self) -> bytes:
        return self._data


class _FakeChromaCollection:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, object]] = {}

    def get(self, where=None, include=None):
        where = where or {}
        target_course = where.get("course_id")
        matched_ids = []
        matched_docs = []
        matched_metas = []
        for cid, entry in self.items.items():
            meta = entry["metadata"]
            if target_course is None or meta.get("course_id") == target_course:
                matched_ids.append(cid)
                matched_docs.append(entry["document"])
                matched_metas.append(meta)
        result = {"ids": matched_ids}
        if include and "documents" in include:
            result["documents"] = matched_docs
        if include and "metadatas" in include:
            result["metadatas"] = matched_metas
        return result

    def upsert(self, ids, documents, metadatas, embeddings=None) -> None:
        for cid, doc, meta in zip(ids, documents, metadatas):
            self.items[cid] = {"document": doc, "metadata": dict(meta)}

    def delete(self, ids=None, where=None) -> None:
        for cid in ids or []:
            self.items.pop(cid, None)


def _fake_embed(texts: list[str], task: str = "document", provider=None) -> list[list[float]]:
    return [[float((i % 5) + 1) * 0.1] * 8 for i, _ in enumerate(texts)]


def run_course_folder_lifecycle_test() -> None:
    orig_docs = settings.documents_dir
    orig_bm25 = dict(rag_service._bm25_cache)
    fake_collection = _FakeChromaCollection()

    with tempfile.TemporaryDirectory(
        prefix="rag_course_folder_test_", ignore_cleanup_errors=True
    ) as tmp_dir:
        docs_root = Path(tmp_dir) / "documents"
        docs_root.mkdir(parents=True, exist_ok=True)
        settings.documents_dir = str(docs_root)
        rag_service._bm25_cache.clear()

        try:
            with (
                patch.object(rag_service, "get_chroma_collection", return_value=fake_collection),
                patch.object(rag_service, "embed_texts", side_effect=_fake_embed),
            ):
                # 1. Tạo thư mục học phần mới theo mã môn học (chuẩn hóa uppercase)
                res_create = rag.sync_course_folder(
                    rag.CourseFolderSyncRequest(course_code="it4010")
                )
                assert res_create["course_code"] == "IT4010"
                assert (docs_root / "IT4010").is_dir()

                # 2. Upload tài liệu vào mã IT4010 và lập chỉ mục
                sample_text = (
                    "Kiến trúc hướng dịch vụ và kiểm thử hộp đen giúp đảm bảo chất lượng hệ thống phần mềm.\n"
                    * 3
                ).encode("utf-8")
                res_upload = _run_sync(
                    rag.upload_and_index_document(
                        course_id="IT4010",
                        force_reindex=False,
                        file=_FakeUploadFile("tai_lieu.txt", sample_text),
                    )
                )
                assert res_upload.total_files == 1
                assert res_upload.total_chunks >= 1

                # Kiểm tra đọc nội dung trực tiếp và mở file trực tiếp theo mã IT4010
                res_preview = rag.preview_course_document("IT4010", "tai_lieu.txt")
                assert "Kiến trúc hướng dịch vụ" in str(res_preview["content"])

                res_open = rag.download_or_open_course_document("IT4010", "tai_lieu.txt")
                assert Path(res_open.path) == docs_root / "IT4010" / "tai_lieu.txt"

                # 3. Giả lập di chuyển từ thư mục UUID cũ sang mã học phần IT4010
                legacy_uuid = "84bb8a1a-0e9b-4cf1-ac7e-7b7f74454c44"
                legacy_dir = docs_root / legacy_uuid
                legacy_dir.mkdir(parents=True, exist_ok=True)
                (legacy_dir / "legacy_note.txt").write_text(
                    "Ghi chú ôn tập bổ sung cho môn học phần mềm và bảo trì mã nguồn.\n" * 3,
                    encoding="utf-8",
                )
                res_migrate = rag.sync_course_folder(
                    rag.CourseFolderSyncRequest(course_code="IT4010", legacy_id=legacy_uuid)
                )
                assert res_migrate["migrated_files"] == 1
                assert not legacy_dir.exists()
                assert (docs_root / "IT4010" / "legacy_note.txt").is_file()

                # 4. Đổi mã học phần (Sửa học phần): IT4010 -> IT4099
                res_rename = rag.sync_course_folder(
                    rag.CourseFolderSyncRequest(
                        course_code="IT4099",
                        old_code="IT4010",
                        legacy_id=legacy_uuid,
                    )
                )
                assert res_rename["course_code"] == "IT4099"
                assert not (docs_root / "IT4010").exists()
                assert (docs_root / "IT4099" / "tai_lieu.txt").is_file()
                assert (docs_root / "IT4099" / "legacy_note.txt").is_file()

                status_old = rag.get_course_rag_status(
                    course_id="IT4010", embedding_provider=None
                )
                assert status_old.total_chunks == 0

                status_new = rag.get_course_rag_status(
                    course_id="IT4099", embedding_provider=None
                )
                assert status_new.total_files == 2
                assert status_new.total_chunks >= 2

                # 5. Xóa học phần IT4099 -> xóa thư mục + chunks
                res_delete = rag.delete_course_rag_folder("IT4099", legacy_id=legacy_uuid)
                assert int(res_delete["deleted_dirs"]) >= 1
                assert int(res_delete["removed_chunks"]) >= 2
                assert not (docs_root / "IT4099").exists()
                assert fake_collection.get()["ids"] == []
        finally:
            rag_service._bm25_cache.clear()
            rag_service._bm25_cache.update(orig_bm25)
            settings.documents_dir = orig_docs


if __name__ == "__main__":
    run_course_folder_lifecycle_test()
    print("COURSE FOLDER LIFECYCLE TESTS PASSED!")
