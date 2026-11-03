"""Dịch vụ Chấm điểm bài thi vấn đáp tự động bằng AI kết hợp Rubric và RAG.

Nhiệm vụ:
- build_grading_prompt:
    + Thiết lập System Instruction định hình vai trò Giảng viên đại học ngành CNTT khách quan, công tâm, chuyên nghiệp.
    + Tích hợp kiến thức chuẩn trích xuất từ giáo trình môn học (RAG Context).
    + Truyền danh sách tiêu chí Rubric chi tiết (tên tiêu chí, mô tả yêu cầu, thang điểm con).
    + Truyền transcript câu trả lời đã xác nhận của sinh viên để đối chiếu.
- evaluate_oral_answer:
    + Tự động kích hoạt Hybrid RAG (Dense + BM25 + RRF) lấy Top-K đoạn giáo trình chuẩn sát nhất với câu hỏi.
    + Gọi Gemini (gemini-2.5-flash / gemini-2.5-pro / Ollama gemma3:4b) với Structured Outputs (JSON Schema).
    + Trả về đánh giá từng tiêu chí, bằng chứng trích từ bài nói, điểm mạnh, điểm thiếu sót so với giáo trình, gợi ý cải thiện.
    + Hậu kiểm tra (post-validation): kiểm tra tính hợp lệ của điểm, đảm bảo không vượt quá thang điểm 10 hoặc thang điểm tiêu chí.
"""

import json
import os
import re
import time
from typing import Any

from google import genai
from google.genai import types

from app.config import settings
from app.schemas.eval_schema import (
    CriterionEvaluation,
    EvaluationMetadata,
    EvaluationRequest,
    EvaluationResponse,
    RagReference,
)
from app.services import rag_service, stt_service

# Schema JSON kết hợp giữa bộ prompt gốc của speed-to-text-demo (score, summary, strengths, weaknesses, improvement)
# và bảng điểm chi tiết từng tiêu chí Rubric (criteria) của hệ thống AI Oral Exam Practice.
GEMINI_RUBRIC_EVALUATION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "score": {"type": "NUMBER", "description": "Điểm số đánh giá trên thang 10"},
        "summary": {
            "type": "STRING",
            "description": "Nhận xét chung chi tiết về tính logic, độ chính xác kiến thức và cách diễn đạt",
        },
        "criteria": {
            "type": "ARRAY",
            "description": "Kết quả chấm điểm chi tiết cho từng tiêu chí trong Rubric",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "criterion_id": {
                        "type": "STRING",
                        "description": "Mã tiêu chí (giữ nguyên từ danh sách Rubric đầu vào)",
                    },
                    "score": {
                        "type": "NUMBER",
                        "description": "Điểm đạt được của tiêu chí này (không vượt quá max_score)",
                    },
                    "evidence": {
                        "type": "STRING",
                        "description": "Câu hoặc cụm từ trích nguyên văn từ câu trả lời của sinh viên làm bằng chứng",
                    },
                    "missing_or_incorrect": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"},
                        "description": "Danh sách các ý còn thiếu hoặc trả lời sai ở tiêu chí này",
                    },
                    "feedback": {
                        "type": "STRING",
                        "description": "Nhận xét ngắn gọn cho tiêu chí này",
                    },
                },
                "required": [
                    "criterion_id",
                    "score",
                    "evidence",
                    "missing_or_incorrect",
                    "feedback",
                ],
            },
        },
        "strengths": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "Danh sách 3 điểm mạnh cụ thể",
        },
        "weaknesses": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "Danh sách 3 điểm yếu hoặc thiếu sót cụ thể so với giáo trình/tài liệu chuẩn",
        },
        "improvements": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "Danh sách 2-3 gợi ý cải thiện để sinh viên đạt điểm tốt hơn",
        },
        "uncertainty_notes": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "Ghi chú nếu câu trả lời mơ hồ hoặc cần giảng viên xem lại",
        },
        "needs_human_review": {
            "type": "BOOLEAN",
            "description": "True nếu câu trả lời quá mơ hồ hoặc có mâu thuẫn cần giảng viên chấm lại",
        },
    },
    "required": [
        "score",
        "summary",
        "criteria",
        "strengths",
        "weaknesses",
        "improvements",
        "uncertainty_notes",
        "needs_human_review",
    ],
}


def _build_default_rubric(request: EvaluationRequest) -> list[dict[str, Any]]:
    if request.rubric:
        return [
            {
                "criterion_id": c.criterion_id,
                "name": c.name,
                "description": c.description,
                "max_score": float(c.max_score),
            }
            for c in request.rubric
        ]
    return [
        {
            "criterion_id": "c1",
            "name": "Độ chính xác kiến thức cốt lõi",
            "description": "Trả lời đúng bản chất lý thuyết và thuật ngữ chuyên ngành",
            "max_score": 6.0,
        },
        {
            "criterion_id": "c2",
            "name": "Tính đầy đủ và giải thích logic",
            "description": "Trình bày mạch lạc, đủ ý và có liên hệ/ví dụ minh họa",
            "max_score": 4.0,
        },
    ]


def _evaluate_mock(
    request: EvaluationRequest,
    rubric_items: list[dict[str, Any]],
    rag_refs: list[RagReference],
    start_ts: float,
) -> EvaluationResponse:
    criteria_results: list[CriterionEvaluation] = []
    for item in rubric_items:
        awarded = round(item["max_score"] * 0.8, 2)
        criteria_results.append(
            CriterionEvaluation(
                criterion_id=item["criterion_id"],
                score=awarded,
                max_score=item["max_score"],
                evidence=request.transcript[:120],
                missing_or_incorrect=["Cần bổ sung thêm ví dụ thực tế chi tiết hơn."],
                feedback=f"Đạt yêu cầu cơ bản ở tiêu chí '{item['name']}'.",
            )
        )
    max_total = round(sum(i["max_score"] for i in rubric_items), 2)
    total_score = round(sum(c.score for c in criteria_results), 2)
    elapsed_ms = int((time.perf_counter() - start_ts) * 1000)

    return EvaluationResponse(
        total_score=total_score,
        max_score=max_total,
        summary="Bài trả lời nắm được ý chính của câu hỏi theo giáo trình, diễn đạt rõ ràng nhưng cần bổ sung ví dụ thực tế.",
        criteria=criteria_results,
        strengths=[
            "Nêu đúng khái niệm trọng tâm của câu hỏi.",
            "Sử dụng đúng thuật ngữ chuyên ngành.",
            "Bố cục câu trả lời rõ ràng, dễ theo dõi.",
        ],
        weaknesses=[
            "Chưa đưa ra ví dụ thực tế minh họa cho lý thuyết.",
            "Một số ý giải thích còn ngắn gọn so với tài liệu giáo trình.",
        ],
        improvements=[
            "Luôn kèm theo ít nhất 1 ví dụ thực tế sau khi nêu định nghĩa để đạt điểm tối đa.",
            "Đối chiếu kỹ các ý trong Rubric để không bỏ sót phần liên hệ thực tiễn.",
        ],
        uncertainty_notes=[],
        needs_human_review=False,
        rag_references=rag_refs,
        metadata=EvaluationMetadata(
            llm_model="mock",
            embedding_model=rag_service.get_active_embedding_name(),
            processing_time_ms=elapsed_ms,
        ),
    )


def evaluate_oral_answer(request: EvaluationRequest) -> EvaluationResponse:
    """
    Thực hiện chấm điểm câu trả lời vấn đáp sử dụng bộ Prompt từ speed-to-text-demo
    kết hợp Hybrid RAG (Dense + BM25 + RRF) và chấm chi tiết từng tiêu chí trong Rubric.
    """
    start_ts = time.perf_counter()
    rubric_items = _build_default_rubric(request)
    max_total_score = round(sum(item["max_score"] for item in rubric_items), 2)

    # 1. Truy xuất ngữ cảnh giáo trình bằng Hybrid RAG (nếu bật)
    rag_chunks: list[dict[str, Any]] = []
    rag_context_str = ""
    rag_refs: list[RagReference] = []

    if request.rag_config.enabled:
        combined_query = f"{request.question}\n{request.transcript}"
        rag_chunks = rag_service.query_relevant_chunks(
            query_text=combined_query,
            course_id=request.course_id,
            top_k=request.rag_config.top_k,
            score_threshold=request.rag_config.score_threshold,
            search_mode=request.rag_config.search_mode,
            use_rerank=request.rag_config.use_rerank,
        )
        rag_context_str = rag_service.format_rag_context(rag_chunks)
        for chunk in rag_chunks:
            preview = chunk.get("text", "")
            if len(preview) > 280:
                preview = preview[:277] + "..."
            rag_refs.append(
                RagReference(
                    chunk_id=str(chunk.get("id", "")),
                    source=str(chunk.get("source", "Không rõ")),
                    retrieved_by=str(chunk.get("retrieved_by", "hybrid")),
                    dense_sim=chunk.get("dense_sim"),
                    rrf_score=float(chunk.get("rrf_score", 0.0)),
                    text_preview=preview,
                )
            )

    llm_model = (request.llm_model or settings.default_llm_model or "gemini-2.5-flash").strip()
    if llm_model.lower() == "mock":
        return _evaluate_mock(request, rubric_items, rag_refs, start_ts)

    # 2. Xây dựng Prompt chấm điểm từ bộ prompt chuẩn của speed-to-text-demo + chi tiết từng tiêu chí Rubric
    rubric_json_str = json.dumps(rubric_items, ensure_ascii=False, indent=2)
    rag_section = ""
    if rag_context_str and rag_context_str.strip():
        rag_section = f"""
DƯỚI ĐÂY LÀ KIẾN THỨC CHUẨN ĐƯỢC TRÍCH XUẤT TỪ TÀI LIỆU/GIÁO TRÌNH MÔN HỌC (RAG CONTEXT):
======================================================================
{rag_context_str}
======================================================================
Hãy đối chiếu kỹ lưỡng bài trả lời của sinh viên với tài liệu chuẩn ở trên để đánh giá độ chính xác về mặt học thuật và các thuật ngữ chuyên ngành.
"""

    ref_section = (
        f"\nĐáp án tham chiếu của giảng viên:\n{request.reference_answer}\n"
        if request.reference_answer.strip()
        else ""
    )

    prompt = f"""
Bạn là giảng viên đại học chuyên ngành Công nghệ thông tin. Đánh giá câu trả lời vấn đáp của sinh viên theo thang điểm {max_total_score} dựa trên rubric và tài liệu môn học.

Câu hỏi:
{request.question}
{ref_section}
Tiêu chí chấm điểm (Rubric):
{rubric_json_str}
{rag_section}
Văn bản câu trả lời của sinh viên (được ghi âm và chuyển thành văn bản):
{request.transcript}

Yêu cầu:
- Cho điểm từng tiêu chí trong danh sách `criteria` (giữ nguyên `criterion_id`, điểm `score` không vượt quá `max_score` của tiêu chí đó, chấp nhận điểm lẻ như 0.5, 1.25, 1.5). Trích dẫn nguyên văn câu nói của sinh viên vào `evidence` và liệt kê các ý thiếu/sai vào `missing_or_incorrect`.
- Nhận xét chi tiết (`summary`) về tính logic, độ chính xác kiến thức và cách diễn đạt (đặc biệt đối chiếu với nội dung kiến thức chuẩn từ RAG nếu có).
- Chỉ ra 3 điểm mạnh cụ thể (`strengths`).
- Chỉ ra 3 điểm yếu hoặc điểm thiếu sót cụ thể so với giáo trình/tài liệu chuẩn (`weaknesses`).
- Đề xuất 2–3 gợi ý cải thiện để sinh viên đạt điểm tốt hơn (`improvements`).

BẮT BUỘC TRẢ VỀ DUY NHẤT 1 ĐỐI TƯỢNG JSON (không kèm bất kỳ lời dẫn nào) khớp với schema.
"""

    is_local = "ollama" in llm_model.lower() or llm_model.startswith("gemma3")
    if is_local:
        ollama_model_name = llm_model.split()[0] if " " in llm_model else llm_model
        result_text = stt_service.call_ollama_api(ollama_model_name, prompt, is_json=True)
    else:
        api_key = (settings.gemini_api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
        if not api_key:
            raise ValueError("Chưa cấu hình GEMINI_API_KEY trong file .env để chấm điểm.")
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=llm_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=GEMINI_RUBRIC_EVALUATION_SCHEMA,
                temperature=0.1,
            ),
        )
        result_text = (response.text or "").strip()

    json_match = re.search(r"(\{[\s\S]*\})", result_text)
    if json_match:
        result_text = json_match.group(1)
    result_text = (
        result_text.replace("“", '"')
        .replace("”", '"')
        .replace("’", "'")
        .replace("‘", "'")
    )
    parsed = json.loads(result_text)

    # 3. Hậu kiểm (Post-validation): Khóa biên điểm từng tiêu chí và tự cộng lại total_score
    raw_criteria_map: dict[str, dict[str, Any]] = {}
    for c_obj in parsed.get("criteria", []):
        if isinstance(c_obj, dict) and c_obj.get("criterion_id"):
            raw_criteria_map[str(c_obj["criterion_id"])] = c_obj

    validated_criteria: list[CriterionEvaluation] = []
    for item in rubric_items:
        cid = item["criterion_id"]
        c_max = float(item["max_score"])
        raw_c = raw_criteria_map.get(cid, {})
        raw_score = float(raw_c.get("score", 0.0) or 0.0)
        clamped_score = round(min(max(raw_score, 0.0), c_max), 2)

        validated_criteria.append(
            CriterionEvaluation(
                criterion_id=cid,
                score=clamped_score,
                max_score=c_max,
                evidence=str(raw_c.get("evidence", "") or ""),
                missing_or_incorrect=[
                    str(x) for x in (raw_c.get("missing_or_incorrect") or []) if str(x).strip()
                ],
                feedback=str(raw_c.get("feedback", "") or ""),
            )
        )

    total_score = round(sum(c.score for c in validated_criteria), 2)
    elapsed_ms = int((time.perf_counter() - start_ts) * 1000)

    weaknesses_list = [str(w) for w in (parsed.get("weaknesses") or []) if str(w).strip()]
    improvements_list = [
        str(i)
        for i in (parsed.get("improvements") or parsed.get("improvement") or [])
        if str(i).strip()
    ]

    return EvaluationResponse(
        total_score=total_score,
        max_score=max_total_score,
        summary=str(parsed.get("summary", "") or "Đã hoàn thành đánh giá câu trả lời."),
        criteria=validated_criteria,
        strengths=[str(s) for s in (parsed.get("strengths") or []) if str(s).strip()],
        weaknesses=weaknesses_list,
        improvements=improvements_list,
        uncertainty_notes=[
            str(u) for u in (parsed.get("uncertainty_notes") or []) if str(u).strip()
        ],
        needs_human_review=bool(parsed.get("needs_human_review", False)),
        rag_references=rag_refs,
        metadata=EvaluationMetadata(
            llm_model=llm_model,
            embedding_model=rag_service.get_active_embedding_name(),
            processing_time_ms=elapsed_ms,
        ),
    )
