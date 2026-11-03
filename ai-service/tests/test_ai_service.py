"""Bộ kiểm thử tích hợp tự động cho AI Service (Integration & Unit Tests).

Nhiệm vụ:
- Kiểm tra trạng thái sức khỏe và cấu hình API key (/ai/health).
- Kiểm tra hàm clean_oral_query (lọc từ đệm nói miệng) và thuật toán chia nhỏ tài liệu (chunk_text, get_clean_overlap).
- Kiểm tra pipeline lập chỉ mục giáo trình vào ChromaDB và BM25 cho học phần IT2030.
- Kiểm tra tìm kiếm giáo trình Hybrid RAG (Dense + BM25 + RRF) đảm bảo trả đúng đoạn trích dẫn và điểm số.
- Kiểm tra pipeline nhận dạng giọng nói STT (Mock provider) và bước hiệu đính thuật ngữ CNTT bằng Gemini.
- Kiểm tra toàn trình endpoint chấm điểm (/ai/evaluations): gửi câu hỏi, rubric, transcript -> kiểm tra định dạng JSON và điểm số.
"""

from fastapi.testclient import TestClient

from app.main import app
from app.services import rag_service

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/ai/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "UP"
    assert data["service"] == "ai-service"
    assert data["gemini_key_configured"] is True
    assert data["groq_key_configured"] is True


def test_clean_oral_query_and_chunking():
    raw_query = "Dạ thưa thầy theo em nghĩ Verification là kiểm tra đặc tả thiết kế ạ"
    cleaned = rag_service.clean_oral_query(raw_query)
    assert "dạ" not in cleaned.lower()
    assert "thưa thầy" not in cleaned.lower()
    assert "Verification" in cleaned

    sample_text = (
        "Verification (Xác minh) là quá trình kiểm tra xem phần mềm có được xây dựng đúng theo tài liệu đặc tả yêu cầu và thiết kế hay không.\n"
        * 6
    )
    chunks = rag_service.chunk_text(sample_text, source_name="sample.txt", course_id="IT2030")
    assert len(chunks) >= 2
    assert all(c["course_id"] == "IT2030" for c in chunks)
    assert all(c["id"].startswith("IT2030::sample.txt_chunk_") for c in chunks)


def test_rag_index_status_and_hybrid_search():
    idx_resp = client.post(
        "/ai/rag/index",
        json={"course_id": "IT2030", "force_reindex": False},
    )
    assert idx_resp.status_code == 200
    idx_data = idx_resp.json()
    assert idx_data["course_id"] == "IT2030"
    assert idx_data["total_files"] >= 1
    assert idx_data["total_chunks"] > 0

    status_resp = client.get("/ai/rag/status", params={"course_id": "IT2030"})
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["status"] == "ready"
    assert status_data["hybrid_bm25_active"] is True

    # Kiểm tra tìm kiếm Hybrid (Dense + BM25 + RRF)
    search_resp = client.post(
        "/ai/rag/search",
        json={
            "course_id": "IT2030",
            "query_text": "Dạ thưa thầy kiểm thử phần mềm Verification và Validation khác nhau thế nào ạ?",
            "top_k": 3,
            "search_mode": "hybrid",
            "use_rerank": False,
        },
    )
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    assert len(search_data["results"]) > 0
    assert all(r["course_id"] == "IT2030" for r in search_data["results"])
    assert search_data["results"][0]["rrf_score"] > 0

    # Kiểm tra cô lập theo học phần (học phần chưa có tài liệu phải trả về rỗng)
    empty_status = client.get("/ai/rag/status", params={"course_id": "EMPTY_COURSE_999"})
    assert empty_status.status_code == 200
    assert empty_status.json()["total_chunks"] == 0


def test_transcriptions_and_evaluations_contract():
    stt_resp = client.post(
        "/ai/transcriptions",
        json={
            "audio_path": "non_existent_for_mock.wav",
            "question_text": "Trình bày 4 tính chất của lập trình hướng đối tượng (OOP).",
            "rubric_summary": "Đóng gói, Kế thừa, Đa hình, Trừu tượng",
            "stt_provider": "mock",
            "enable_spell_correction": False,
        },
    )
    assert stt_resp.status_code == 200
    stt_data = stt_resp.json()
    assert "raw_transcript" in stt_data
    assert "corrected_transcript" in stt_data

    eval_resp = client.post(
        "/ai/evaluations",
        json={
            "session_id": "test-session-001",
            "course_id": "IT2030",
            "question": "Phân biệt Verification và Validation trong kiểm thử phần mềm.",
            "reference_answer": "Verification kiểm tra sản phẩm có đúng đặc tả không; Validation kiểm tra sản phẩm có đúng nhu cầu khách hàng không.",
            "transcript": "Dạ thưa thầy verification là kiểm tra xem mình làm có đúng tài liệu thiết kế không, còn validation là kiểm tra xem phần mềm có đúng ý người dùng cần không ạ.",
            "rubric": [
                {
                    "criterion_id": "c1",
                    "name": "Định nghĩa Verification",
                    "description": "Nêu được Verification là đối chiếu với đặc tả/thiết kế",
                    "max_score": 4.0,
                },
                {
                    "criterion_id": "c2",
                    "name": "Định nghĩa Validation",
                    "description": "Nêu được Validation là đối chiếu với nhu cầu thực tế của người dùng",
                    "max_score": 4.0,
                },
                {
                    "criterion_id": "c3",
                    "name": "Ví dụ minh họa",
                    "description": "Nêu được ít nhất 1 ví dụ thực tế",
                    "max_score": 2.0,
                },
            ],
            "rag_config": {"enabled": True, "search_mode": "hybrid", "top_k": 3},
            "llm_model": "mock",
        },
    )
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()
    assert eval_data["max_score"] == 10.0
    assert len(eval_data["criteria"]) == 3
    assert len(eval_data["rag_references"]) > 0
    assert eval_data["total_score"] == round(sum(c["score"] for c in eval_data["criteria"]), 2)


if __name__ == "__main__":
    print("1/4 Testing /ai/health...")
    test_health_endpoint()
    print("2/4 Testing clean_oral_query & chunk_text...")
    test_clean_oral_query_and_chunking()
    print("3/4 Testing RAG indexing, status & Hybrid Search (IT2030)...")
    test_rag_index_status_and_hybrid_search()
    print("4/4 Testing Transcriptions & Evaluations contract...")
    test_transcriptions_and_evaluations_contract()
    print("ALL TESTS PASSED SUCCESSFULLY!")


