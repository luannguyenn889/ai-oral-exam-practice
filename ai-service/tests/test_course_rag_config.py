"""Kiểm thử cấu hình RAG theo từng học phần (embedding_provider & chunking_strategy) đồng bộ xuyên suốt."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

AI_SERVICE_DIR = Path(__file__).resolve().parent.parent
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

from app.config import settings
from app.routers import rag
from app.schemas.eval_schema import EvaluationRequest, RagConfig, RubricCriterionInput
from app.schemas.rag_schema import CourseRagConfigUpdateRequest, RagSuggestAnswerRequest
from app.services import grading_service, rag_service
from app.services.rag import folders as rag_folders
from app.services.rag import store as rag_store
from app.services.rag import suggest as rag_suggest


class _EmptyChromaCollection:
    def get(self, where=None, include=None):
        result = {"ids": []}
        if include and "documents" in include:
            result["documents"] = []
        if include and "metadatas" in include:
            result["metadatas"] = []
        return result

    def delete(self, ids=None, where=None) -> None:
        return None


def run_course_rag_config_sync_test() -> None:
    orig_docs = settings.documents_dir
    fake_collection = _EmptyChromaCollection()

    with tempfile.TemporaryDirectory(
        prefix="course_rag_config_test_", ignore_cleanup_errors=True
    ) as tmp_dir:
        docs_root = Path(tmp_dir) / "documents"
        docs_root.mkdir(parents=True, exist_ok=True)
        settings.documents_dir = str(docs_root)

        try:
            # 1. Cập nhật cấu hình RAG cho học phần SOFTWARE IT (giống trang Quản lý kho tài liệu)
            updated = rag.update_course_rag_config_endpoint(
                "SOFTWARE IT",
                CourseRagConfigUpdateRequest(
                    embedding_provider="e5-small",
                    chunking_strategy="semantic",
                ),
            )
            assert updated.course_id == "SOFTWAREIT"
            assert updated.embedding_provider == "e5-small"
            assert updated.chunking_strategy == "semantic"
            assert "e5-small" in updated.embedding_model

            fetched = rag.get_course_rag_config_endpoint("SOFTWARE IT")
            assert fetched.embedding_provider == "e5-small"
            assert fetched.chunking_strategy == "semantic"

            # 2. GET /ai/rag/status không truyền embedding_provider vẫn trả đúng e5-small & semantic đã lưu
            with patch.object(rag_store, "get_chroma_collection", return_value=fake_collection):
                status_resp = rag.get_course_rag_status(course_id="SOFTWARE IT", embedding_provider=None)
                assert status_resp.embedding_provider == "e5-small"
                assert status_resp.chunking_strategy == "semantic"
                assert "e5-small" in status_resp.embedding_model

            # 3. POST /ai/rag/suggest-answer (Soạn câu hỏi & Soạn Rubric) tự động dùng e5-small của học phần
            captured_suggest_calls: list[dict[str, object]] = []

            def _fake_query_suggest(**kwargs):
                captured_suggest_calls.append(kwargs)
                return [
                    {
                        "id": "SOFTWARE IT::sommerville.pdf::0",
                        "text": "Waterfall model gồm các giai đoạn phân tích yêu cầu, thiết kế, triển khai và kiểm thử.",
                        "source": "sommerville.pdf",
                        "course_id": "SOFTWARE IT",
                        "index": 0,
                        "retrieved_by": "hybrid",
                        "dense_sim": 0.82,
                        "bm25_score": 4.5,
                        "rrf_score": 0.032,
                    }
                ]

            with (
                patch.object(rag_suggest, "query_relevant_chunks", side_effect=_fake_query_suggest),
                patch.object(rag_suggest, "has_gemini_api_key", return_value=False),
            ):
                suggest_resp = rag.suggest_reference_answer_endpoint(
                    RagSuggestAnswerRequest(
                        course_id="SOFTWARE IT",
                        question="Trình bày mô hình thác nước Waterfall?",
                        include_rubric=True,
                    )
                )
                assert len(captured_suggest_calls) == 1
                assert captured_suggest_calls[0]["embedding_provider"] == "e5-small"
                assert captured_suggest_calls[0]["use_rerank"] is True
                assert suggest_resp.embedding_provider == "e5-small"
                assert "e5-small" in suggest_resp.embedding_model
                assert len(suggest_resp.suggested_criteria) > 0

            # 4. Chấm bài (/ai/evaluations) tự động dùng e5-small của học phần khi không truyền embedding_provider
            captured_eval_calls: list[dict[str, object]] = []

            def _fake_query_eval(**kwargs):
                captured_eval_calls.append(kwargs)
                return [
                    {
                        "id": "SOFTWARE IT::sommerville.pdf::0",
                        "text": "Waterfall model gồm đặc tả yêu cầu, thiết kế, cài đặt, kiểm thử và bảo trì.",
                        "source": "sommerville.pdf",
                        "retrieved_by": "hybrid",
                        "dense_sim": 0.79,
                        "rrf_score": 0.031,
                    }
                ]

            with patch.object(rag_service, "query_relevant_chunks", side_effect=_fake_query_eval):
                eval_resp = grading_service.evaluate_oral_answer(
                    EvaluationRequest(
                        session_id="sess-001",
                        course_id="SOFTWARE IT",
                        question="Trình bày mô hình thác nước Waterfall?",
                        reference_answer="Mô hình Waterfall gồm các pha tuần tự rõ ràng.",
                        transcript="Em thưa thầy mô hình thác nước gồm phân tích yêu cầu, thiết kế, lập trình và kiểm thử.",
                        rubric=[
                            RubricCriterionInput(
                                criterion_id="c1",
                                name="Các giai đoạn chính",
                                description="Nêu đủ các pha của Waterfall",
                                max_score=10.0,
                            )
                        ],
                        rag_config=RagConfig(enabled=True, search_mode="hybrid", top_k=3),
                        llm_model="mock",
                    )
                )
                assert len(captured_eval_calls) == 1
                assert captured_eval_calls[0]["embedding_provider"] == "e5-small"
                assert "e5-small" in eval_resp.metadata.embedding_model

            # 5. Đổi mã học phần & xóa học phần tự động di chuyển / dọn dẹp cấu hình
            with patch.object(rag_folders, "get_chroma_collection", return_value=fake_collection):
                rag_service.ensure_course_folder("SOFTWARE IT")
                rag_service.rename_course_folder("SOFTWARE IT", "SE2026")
                migrated = rag.get_course_rag_config_endpoint("SE2026")
                assert migrated.embedding_provider == "e5-small"
                assert migrated.chunking_strategy == "semantic"

                rag_service.delete_course_folder("SE2026")
                after_delete = rag.get_course_rag_config_endpoint("SE2026")
                assert after_delete.embedding_provider == (settings.embedding_provider or "local").strip().lower()

        finally:
            settings.documents_dir = orig_docs


if __name__ == "__main__":
    run_course_rag_config_sync_test()
    print("OK: Course RAG config persistence & cross-feature sync tests passed.")
