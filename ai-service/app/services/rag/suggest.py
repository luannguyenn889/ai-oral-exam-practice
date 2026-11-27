"""Dịch vụ AI hỗ trợ soạn thảo Đáp án mẫu & Rubric từ giáo trình RAG (Human-in-the-loop).

Nhiệm vụ:
- Truy xuất ngữ cảnh giáo trình bằng Hybrid RAG (Dense + BM25 + RRF) theo học phần và nội dung câu hỏi.
- Hỗ trợ giảng viên chọn lọc/loại bỏ các đoạn RAG nhiễu thông qua `selected_chunk_ids`.
- Gọi Gemini sinh bản nháp Đáp án mẫu (và tùy chọn tiêu chí Rubric thang 10.0đ) dạng văn bản thuần.
- Luôn trả về trạng thái `ai_draft` kèm danh sách đoạn trích dẫn giáo trình để giảng viên kiểm tra, chỉnh sửa và duyệt cuối cùng.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from google import genai
from google.genai import types

from app.config import settings
from app.services.extractor.common import (
    _clean_html_to_text,
    _generate_tailored_criteria,
    _generate_tailored_sample_answer,
)
from app.services.gemini_client import has_gemini_api_key, run_with_gemini_client
from app.services.rag.course_config import (
    resolve_course_embedding_provider,
    resolve_course_reranker_provider,
)
from app.services.rag.embeddings import (
    get_active_embedding_name,
    get_active_reranker_name,
    normalize_course_id,
)
from app.services.rag.store import format_rag_context, query_relevant_chunks

HITL_NOTICE = (
    "Bản nháp do AI khởi tạo dựa trên giáo trình môn học (Hybrid RAG). "
    "Giảng viên giữ toàn quyền rà soát, loại bỏ đoạn RAG nhiễu, chỉnh sửa nội dung "
    "và phê duyệt cuối cùng trước khi dùng làm nguồn đối chiếu chấm thi."
)


def _normalize_suggested_criteria(raw_criteria: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for item in raw_criteria:
        name = _clean_html_to_text(item.get("name") or "")
        desc = _clean_html_to_text(item.get("description") or "")
        try:
            score = round(float(item.get("max_score") or 0.0), 1)
        except (TypeError, ValueError):
            score = 0.0
        if name and score > 0:
            cleaned.append({"name": name, "description": desc, "max_score": score})

    if not cleaned:
        return []

    total = round(sum(c["max_score"] for c in cleaned), 1)
    if total > 0 and abs(total - 10.0) > 0.05:
        for c in cleaned:
            c["max_score"] = round(c["max_score"] * 10.0 / total, 1)
        cleaned[-1]["max_score"] = round(
            max(0.5, 10.0 - sum(c["max_score"] for c in cleaned[:-1])), 1
        )
    return cleaned


def _build_fallback_draft(
    question: str,
    active_chunks: list[dict[str, Any]],
    include_rubric: bool,
) -> tuple[str, list[dict[str, Any]]]:
    """Tạo bản nháp đáp án mẫu từ đoạn RAG hoặc dàn ý học thuật khi chạy mock/thiếu API key."""
    if active_chunks:
        lines = ["Gợi ý các luận điểm chính tổng hợp từ giáo trình môn học (chờ giảng viên hiệu đính):"]
        for idx, chunk in enumerate(active_chunks[:4], start=1):
            source = str(chunk.get("source", "Giáo trình"))
            text = _clean_html_to_text(str(chunk.get("text", ""))).strip()
            snippet = " ".join(text.split())
            if len(snippet) > 260:
                snippet = snippet[:257].rsplit(" ", 1)[0] + "..."
            if snippet:
                lines.append(f"- Ý {idx} (theo {source}): {snippet}")
        lines.append("- Liên hệ thực tiễn và lấy ví dụ minh họa phù hợp với ngữ cảnh bài toán.")
        sample_answer = "\n".join(lines)
    else:
        sample_answer = _generate_tailored_sample_answer(question)

    suggested_criteria: list[dict[str, Any]] = []
    if include_rubric:
        suggested_criteria = [
            {
                "name": c.name,
                "description": c.description,
                "max_score": c.max_score,
            }
            for c in _generate_tailored_criteria(question)
        ]
    return sample_answer, suggested_criteria


def suggest_reference_answer(
    course_id: str,
    question: str,
    topic: Optional[str] = None,
    reference_answer: Optional[str] = None,
    top_k: int = 4,
    search_mode: str = "hybrid",
    include_rubric: bool = False,
    selected_chunk_ids: Optional[list[str]] = None,
    embedding_provider: Optional[str] = None,
    reranker_provider: Optional[str] = None,
    llm_model: Optional[str] = None,
) -> dict[str, Any]:
    """Truy xuất RAG và nhờ AI khởi tạo bản nháp Đáp án mẫu (+ tùy chọn Rubric) cho giảng viên duyệt."""
    normalized_course = normalize_course_id(course_id)
    effective_provider = resolve_course_embedding_provider(normalized_course, embedding_provider)
    effective_reranker = resolve_course_reranker_provider(normalized_course, reranker_provider)
    active_embedding_model = get_active_embedding_name(effective_provider)
    active_reranker_model = get_active_reranker_name(effective_reranker)
    query_parts = [p.strip() for p in [topic or "", question] if p and p.strip()]
    search_query = " — ".join(query_parts) if query_parts else question
    secondary_ref_query = (
        reference_answer.strip()[:260]
        if isinstance(reference_answer, str) and reference_answer.strip()
        else None
    )

    warnings: list[str] = []
    # 1. Truy xuất các đoạn giáo trình liên quan bằng Hybrid RAG theo đúng embedding & reranker của học phần
    try:
        retrieved_chunks = query_relevant_chunks(
            query_text=search_query,
            course_id=normalized_course,
            top_k=top_k,
            search_mode=search_mode,
            use_rerank=True,
            embedding_provider=effective_provider,
            reranker_provider=effective_reranker,
            secondary_query=secondary_ref_query,
            expand_neighbors=True,
        )
    except Exception as exc:
        retrieved_chunks = []
        warn_msg = f"Không truy xuất được giáo trình RAG ({exc}); AI chuyển sang biên soạn không có ngữ cảnh giáo trình."
        warnings.append(warn_msg)
        print(f"[AI-SERVICE] {warn_msg}", flush=True)

    # 2. Lọc theo lựa chọn của giảng viên (Human-in-the-loop: bỏ các đoạn RAG nhiễu)
    if selected_chunk_ids is not None:
        allowed_ids = {cid.strip() for cid in selected_chunk_ids if cid and cid.strip()}
        active_chunks = [c for c in retrieved_chunks if str(c.get("id", "")) in allowed_ids]
    else:
        active_chunks = list(retrieved_chunks)

    used_chunk_ids = [str(c.get("id", "")) for c in active_chunks if c.get("id")]
    rag_context_str = format_rag_context(active_chunks)

    target_model = (llm_model or settings.default_llm_model or "gemini-2.5-flash").strip()

    # Chế độ mock hoặc thiếu API key -> dùng fallback an toàn
    if target_model.lower() == "mock" or not has_gemini_api_key():
        sample_answer, suggested_criteria = _build_fallback_draft(
            question=question,
            active_chunks=active_chunks,
            include_rubric=include_rubric,
        )
        return {
            "course_id": normalized_course,
            "sample_answer": sample_answer,
            "suggested_criteria": suggested_criteria,
            "rag_references": retrieved_chunks,
            "used_chunk_ids": used_chunk_ids,
            "embedding_provider": effective_provider,
            "embedding_model": active_embedding_model,
            "reranker_provider": effective_reranker,
            "reranker_model": active_reranker_model,
            "llm_model": "mock-fallback" if target_model.lower() != "mock" else "mock",
            "status": "ai_draft",
            "notice": HITL_NOTICE,
            "warnings": warnings,
        }

    # 3. Gọi Gemini Structured Output sinh bản nháp Đáp án mẫu (+ Rubric nếu bật)
    schema_properties: dict[str, Any] = {
        "sample_answer": {
            "type": "STRING",
            "description": (
                "Đáp án mẫu chuẩn học thuật bằng văn bản thuần (gạch đầu dòng '- ' cho từng ý chính, "
                "120-260 từ, bám sát giáo trình được cung cấp, tuyệt đối không chứa thẻ HTML)"
            ),
        }
    }
    required_fields = ["sample_answer"]
    if include_rubric:
        schema_properties["suggested_criteria"] = {
            "type": "ARRAY",
            "description": "3-4 tiêu chí Rubric bám sát đáp án mẫu, tổng max_score đúng bằng 10.0",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING"},
                    "description": {"type": "STRING"},
                    "max_score": {"type": "NUMBER"},
                },
                "required": ["name", "description", "max_score"],
            },
        }
        required_fields.append("suggested_criteria")

    response_schema = {
        "type": "OBJECT",
        "properties": schema_properties,
        "required": required_fields,
    }

    rag_block = (
        f"NGỮ CẢNH GIÁO TRÌNH ĐƯỢC GIẢNG VIÊN CHỌN (RAG CONTEXT):\n{rag_context_str}\n\n"
        if rag_context_str
        else "(Chưa có đoạn giáo trình RAG nào được chọn; hãy biên soạn đáp án theo chuẩn học thuật CNTT.)\n\n"
    )
    ref_block = (
        f"ĐÁP ÁN MẪU CỦA GIẢNG VIÊN (NGUỒN CHÍNH — BẮT BUỘC BÁM SÁT KHI CHIA TIÊU CHÍ RUBRIC):\n{reference_answer.strip()}\n\n"
        if reference_answer and reference_answer.strip()
        else ""
    )
    rubric_instruction = (
        "3. Kèm `suggested_criteria` gồm 3-4 tiêu chí chấm điểm rõ ràng bám sát Đáp án mẫu (nếu có) "
        "và ngữ cảnh giáo trình, mỗi tiêu chí nêu rõ các ý bắt buộc phải có và cách chia điểm, tổng `max_score` ĐÚNG BẰNG 10.0.\n"
        if include_rubric
        else ""
    )

    prompt = (
        "Bạn là trợ lý học thuật AI hỗ trợ Giảng viên đại học biên soạn đề thi vấn đáp (mô hình Human-in-the-loop).\n"
        f"Học phần: {normalized_course}\n"
        f"Chủ đề: {topic or 'Chưa ghi rõ'}\n"
        f"Câu hỏi phát vấn:\n{question}\n\n"
        f"{ref_block}"
        f"{rag_block}"
        "YÊU CẦU:\n"
        "1. Soạn bản nháp `sample_answer` đầy đủ, chính xác, mạch lạc, bám sát các đoạn giáo trình ở trên nếu có.\n"
        "2. Trình bày bằng VĂN BẢN THUẦN (xuống dòng bằng `- ` cho từng luận điểm/ý chính), "
        "TUYỆT ĐỐI KHÔNG dùng thẻ HTML (`<ul>`, `<li>`, `<p>`, `<br>`, `<b>`).\n"
        f"{rubric_instruction}"
        "4. Chỉ trả về JSON đúng theo schema."
    )

    try:
        response = run_with_gemini_client(
            lambda client: client.models.generate_content(
                model=target_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    temperature=0.2,
                ),
            )
        )
        parsed = json.loads((response.text or "").strip() or "{}")
        sample_answer = _clean_html_to_text(parsed.get("sample_answer") or "")
        suggested_criteria = (
            _normalize_suggested_criteria(parsed.get("suggested_criteria") or [])
            if include_rubric
            else []
        )
        if not sample_answer:
            sample_answer, fallback_criteria = _build_fallback_draft(
                question=question,
                active_chunks=active_chunks,
                include_rubric=include_rubric,
            )
            if include_rubric and not suggested_criteria:
                suggested_criteria = fallback_criteria

        return {
            "course_id": normalized_course,
            "sample_answer": sample_answer,
            "suggested_criteria": suggested_criteria,
            "rag_references": retrieved_chunks,
            "used_chunk_ids": used_chunk_ids,
            "embedding_provider": effective_provider,
            "embedding_model": active_embedding_model,
            "reranker_provider": effective_reranker,
            "reranker_model": active_reranker_model,
            "llm_model": target_model,
            "status": "ai_draft",
            "notice": HITL_NOTICE,
            "warnings": warnings,
        }
    except Exception as exc:
        print(f"[AI-SERVICE] Loi suggest_reference_answer ({target_model}): {exc}", flush=True)
        warnings.append(f"LLM gặp sự cố ({exc}), đã chuyển sang bản nháp tổng hợp cục bộ.")
        sample_answer, suggested_criteria = _build_fallback_draft(
            question=question,
            active_chunks=active_chunks,
            include_rubric=include_rubric,
        )
        return {
            "course_id": normalized_course,
            "sample_answer": sample_answer,
            "suggested_criteria": suggested_criteria,
            "rag_references": retrieved_chunks,
            "used_chunk_ids": used_chunk_ids,
            "embedding_provider": effective_provider,
            "embedding_model": active_embedding_model,
            "reranker_provider": effective_reranker,
            "reranker_model": active_reranker_model,
            "llm_model": f"{target_model} (fallback)",
            "status": "ai_draft",
            "notice": HITL_NOTICE,
            "warnings": warnings,
        }
