"""Kiểm thử toàn bộ các nâng cấp RAG (A1-A4, B1-B6, C, D, E) & bộ đo đánh giá."""

import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

AI_SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from app.config import settings  # noqa: E402
from app.routers import rag  # noqa: E402
from app.schemas.eval_schema import EvaluationRequest, RagConfig, RubricCriterionInput  # noqa: E402
from app.services import grading_service, rag_service  # noqa: E402
from app.services.rag import embeddings as rag_embeddings  # noqa: E402
from app.services.rag import eval_metrics, store as rag_store, suggest as rag_suggest  # noqa: E402


class _MemoryCollection:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, object]] = {}

    def get(self, where=None, include=None):
        where = where or {}
        target_course = where.get("course_id")
        ids, docs, metas = [], [], []
        for cid, entry in self.items.items():
            meta = entry["metadata"]
            if target_course is None or meta.get("course_id") == target_course:
                ids.append(cid)
                docs.append(entry["document"])
                metas.append(meta)
        res = {"ids": ids}
        if include and "documents" in include:
            res["documents"] = docs
        if include and "metadatas" in include:
            res["metadatas"] = metas
        return res

    def upsert(self, ids, documents, metadatas, embeddings=None) -> None:
        for cid, doc, meta in zip(ids, documents, metadatas):
            self.items[cid] = {"document": doc, "metadata": dict(meta)}

    def delete(self, ids=None, where=None) -> None:
        for cid in ids or []:
            self.items.pop(cid, None)


def _create_sample_pptx(path: Path) -> None:
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        "</Types>"
    )
    slide1 = (
        '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        "<p:cSld><p:spTree>"
        '<p:sp><p:nvSpPr><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>'
        "<p:txBody><a:p><a:r><a:t>Mô hình Agile và Scrum</a:t></a:r></a:p></p:txBody></p:sp>"
        "<p:sp><p:nvSpPr><p:nvPr/></p:nvSpPr><p:txBody>"
        "<a:p><a:r><a:t>Agile tập trung vào chuyển giao lặp tăng trưởng và phản hồi nhanh với thay đổi yêu cầu khách hàng.</a:t></a:r></a:p>"
        "</p:txBody></p:sp>"
        "</p:spTree></p:cSld></p:sld>"
    )
    rels1 = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide" Target="../notesSlides/notesSlide1.xml"/>'
        "</Relationships>"
    )
    notes1 = (
        '<p:notes xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        "<p:cSld><p:spTree><p:sp><p:txBody>"
        "<a:p><a:r><a:t>Nhấn mạnh sự khác biệt giữa Sprint Planning và Daily Standup.</a:t></a:r></a:p>"
        "</p:txBody></p:sp></p:spTree></p:cSld></p:notes>"
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("ppt/slides/slide1.xml", slide1)
        zf.writestr("ppt/slides/_rels/slide1.xml.rels", rels1)
        zf.writestr("ppt/notesSlides/notesSlide1.xml", notes1)


def test_defaults_and_onnx_safety() -> None:
    assert settings.embedding_provider == "e5-small"
    assert settings.reranker_provider == "bge-m3"
    assert rag_service.normalize_course_id("it2030") == "IT2030"
    assert rag_service.normalize_course_id("default") == "default"

    def _boom_find_spec(name: str):
        raise ModuleNotFoundError("No module named 'optimum'")

    with patch.object(rag_embeddings.importlib.util, "find_spec", side_effect=_boom_find_spec):
        assert rag_embeddings._can_use_onnx_backend() is False


def test_vietnamese_bm25_tokenization_and_provider_chunk_sizing() -> None:
    tokens = rag_service.tokenize_text("Kiểm thử phần mềm Client-Server và micro-services")
    assert "kiểm" in tokens and "kiem" in tokens
    assert "client-server" in tokens and "client" in tokens and "server" in tokens

    long_prose = ("Kiểm thử đơn vị xác minh từng hàm riêng lẻ theo đặc tả chi tiết.\n") * 25
    chunks_local = rag_service.chunk_text(
        long_prose, source_name="unit.txt", course_id="IT2030", embedding_provider="local"
    )
    chunks_e5 = rag_service.chunk_text(
        long_prose, source_name="unit.txt", course_id="IT2030", embedding_provider="e5-small"
    )
    assert max(len(c["text"]) for c in chunks_local) <= 460
    assert max(len(c["text"]) for c in chunks_e5) <= 800
    assert len(chunks_local) > len(chunks_e5)


def test_pptx_subfolder_resolution_and_fault_tolerant_indexing() -> None:
    orig_docs = settings.documents_dir
    fake_coll = _MemoryCollection()
    with tempfile.TemporaryDirectory(prefix="rag_upgrade_test_", ignore_cleanup_errors=True) as tmp:
        docs_root = Path(tmp) / "documents"
        docs_root.mkdir(parents=True, exist_ok=True)
        settings.documents_dir = str(docs_root)
        rag_service.invalidate_bm25_cache(clear_empty_cache=True)

        try:
            course_dir = docs_root / "IT9001"
            sub_dir = course_dir / "chuong1"
            sub_dir.mkdir(parents=True, exist_ok=True)
            pptx_path = sub_dir / "bai1.pptx"
            _create_sample_pptx(pptx_path)

            # File corrupt .docx nằm cùng thư mục vẫn không được làm hỏng việc index bai1.pptx
            corrupt_docx = course_dir / "hong.docx"
            corrupt_docx.write_bytes(b"not-a-valid-zip-docx")

            with (
                patch.object(rag_store, "get_chroma_collection", return_value=fake_coll),
                patch.object(
                    rag_store,
                    "embed_texts",
                    side_effect=lambda texts, task="document", provider=None, progress_callback=None: [
                        [0.25] * 8 for _ in texts
                    ],
                ),
            ):
                res = rag_store.index_documents(course_id="it9001", force_reindex=True)
                assert res["total_files"] == 2
                assert res["total_chunks"] >= 1
                assert len(res["warnings"]) == 1 and "hong.docx" in res["warnings"][0]

                # Xác nhận subfolder preview/download/path traversal guard
                prev = rag.preview_course_document("IT9001", "chuong1/bai1.pptx")
                assert "Agile tập trung" in str(prev["content"])
                assert "Sprint Planning" in str(prev["content"])

                try:
                    rag.preview_course_document("IT9001", "../../etc/passwd")
                    raise AssertionError("Expected HTTPException on path traversal")
                except HTTPException as exc:
                    assert exc.status_code == 400

                # Ghi đè bai1.pptx thành rỗng -> chunk cũ bị xóa khỏi fake_coll (B2)
                empty_txt = sub_dir / "note.txt"
                empty_txt.write_text("Nội dung hợp lệ đủ dài để tạo ít nhất một chunk kiểm thử lưu trữ RAG môn học phần mềm.", encoding="utf-8")
                rag_store.index_documents(course_id="IT9001")
                assert any("chuong1/note.txt" in cid for cid in fake_coll.items)

                empty_txt.write_text("", encoding="utf-8")
                res_after_empty = rag_store.index_documents(course_id="IT9001")
                assert not any("chuong1/note.txt" in cid for cid in fake_coll.items)
                assert res_after_empty["removed_chunks"] >= 1
        finally:
            rag_service.invalidate_bm25_cache(clear_empty_cache=True)
            settings.documents_dir = orig_docs


def test_secondary_query_grading_suggest_warnings_and_eval_metrics() -> None:
    captured: list[dict[str, object]] = []

    def _fake_query(**kwargs):
        captured.append(kwargs)
        return [
            {
                "id": "IT2030::doc.pdf_chunk_1",
                "text": "Waterfall gồm 5 giai đoạn tuần tự.",
                "expanded_text": "Chương 2 > 2.1 Waterfall\nWaterfall gồm 5 giai đoạn tuần tự.",
                "source": "doc.pdf",
                "page_start": 14,
                "page_end": 15,
                "retrieved_by": "hybrid",
                "dense_sim": 0.85,
                "rrf_score": 0.032,
            }
        ]

    with patch.object(rag_service, "query_relevant_chunks", side_effect=_fake_query):
        grading_service.evaluate_oral_answer(
            EvaluationRequest(
                session_id="s1",
                course_id="IT2030",
                question="Trình bày mô hình Waterfall?",
                reference_answer="Gồm 5 giai đoạn tuần tự.",
                transcript="À dạ thưa thầy theo em nhớ Waterfall có năm bước...",
                rubric=[
                    RubricCriterionInput(criterion_id="c1", name="Nội dung", max_score=10.0)
                ],
                rag_config=RagConfig(enabled=True),
                llm_model="mock",
            )
        )
        assert len(captured) == 1
        assert captured[0]["query_text"] == "Trình bày mô hình Waterfall?"
        assert "năm bước" in str(captured[0]["secondary_query"])
        assert captured[0]["expand_neighbors"] is True

    # format_rag_context không chứa rác điểm Cosine/RRF nội bộ, có Trang/Slide
    formatted = rag_store.format_rag_context(
        [
            {
                "source": "doc.pdf",
                "page_start": 14,
                "page_end": 15,
                "text": "Waterfall gồm 5 giai đoạn tuần tự.",
                "dense_sim": 0.85,
                "rrf_score": 0.032,
            }
        ]
    )
    assert "Trang/Slide: 14-15" in formatted
    assert "Cosine:" not in formatted and "RRF:" not in formatted

    # suggest.py bề mặt cảnh báo khi query_relevant_chunks lỗi (B6)
    with (
        patch.object(rag_suggest, "query_relevant_chunks", side_effect=RuntimeError("Chroma lock error")),
        patch.object(rag_suggest, "has_gemini_api_key", return_value=False),
    ):
        sug = rag_suggest.suggest_reference_answer(
            course_id="IT2030",
            question="Phân biệt hộp đen và hộp trắng?",
            llm_model="mock",
        )
        assert len(sug["warnings"]) == 1
        assert "Chroma lock error" in sug["warnings"][0]

    # Benchmark metrics
    metrics = eval_metrics.evaluate_retrieval_benchmark(
        cases=[{"query": "Waterfall", "expected_terms": ["Waterfall", "tuần tự"]}],
        retriever=lambda q: [] if "phở" in q else [{"text": "Waterfall gồm các pha tuần tự", "noise_score": 0.0}],
        k=3,
        off_topic_queries=["cách nấu phở"],
    )
    assert metrics["recall_at_k"] == 1.0
    assert metrics["mrr_at_k"] == 1.0
    assert metrics["noise_rate_at_k"] == 0.0
    assert metrics["off_topic_rejection_rate"] == 1.0


def test_cooperative_job_cancellation() -> None:
    started = threading.Event()

    def _slow_index(**kwargs):
        cancel_ev = kwargs.get("cancel_event")
        started.set()
        for _ in range(50):
            if cancel_ev is not None and cancel_ev.wait(0.05):
                raise rag_embeddings.IndexingCancelledError("Cancelled in test")
        return {
            "course_id": "IT9999",
            "status": "empty",
            "total_files": 0,
            "added_or_updated_chunks": 0,
            "removed_chunks": 0,
            "total_chunks": 0,
            "embedding_model": "intfloat/multilingual-e5-small",
            "chunking_strategy": "recursive",
            "warnings": [],
        }

    with patch("app.services.rag.jobs.index_documents", side_effect=_slow_index):
        job = rag_service.start_index_job(course_id="IT9999")
        assert started.wait(timeout=2.0)
        cancel_res = rag.cancel_index_job_endpoint(job["job_id"])
        assert cancel_res.job_id == job["job_id"]
        for _ in range(30):
            snap = rag_service.get_index_job(job["job_id"])
            if snap and snap["status"] == "cancelled":
                break
            time.sleep(0.05)
        final_snap = rag_service.get_index_job(job["job_id"])
        assert final_snap is not None and final_snap["status"] == "cancelled"


if __name__ == "__main__":
    test_defaults_and_onnx_safety()
    test_vietnamese_bm25_tokenization_and_provider_chunk_sizing()
    test_pptx_subfolder_resolution_and_fault_tolerant_indexing()
    test_secondary_query_grading_suggest_warnings_and_eval_metrics()
    test_cooperative_job_cancellation()
    print(">>> ALL RAG UPGRADE TESTS PASSED! <<<")
