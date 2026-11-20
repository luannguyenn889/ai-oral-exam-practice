"""Module tích hợp Gemini AI hỗ trợ hoàn thiện và dự phòng bóc tách đề thi vấn đáp.

Nhiệm vụ:
- Định nghĩa JSON Schema chuẩn đầu ra (`EXTRACTION_JSON_SCHEMA`) để ép Gemini trả về dữ liệu có cấu trúc.
- Bổ sung phần còn thiếu theo lô (`_enrich_missing_with_gemini`):
    + Chỉ gọi Gemini để tóm tắt tiêu đề, soạn đáp án mẫu hoặc gợi ý Rubric thang 10.0đ cho những câu mà file gốc chưa có; tuyệt đối không sửa nội dung câu hỏi hay ghi đè đáp án/rubric có sẵn.
    + Bắt buộc trả về văn bản thuần (không dùng thẻ HTML) và lọc lại bằng `_clean_html_to_text`.
- Phương án dự phòng toàn văn (`_parse_word_with_gemini`): khi bộ đọc cấu trúc không nhận diện được câu hỏi nào từ tài liệu tự do, nhờ Gemini bóc tách toàn bộ văn bản.
"""

import json
import os
from typing import List, Optional

from google import genai
from google.genai import types

from app.config import settings
from app.schemas.question_import_schema import ExtractedQuestionItem
from app.services.extractor.common import _clean_html_to_text, _items_to_questions
from app.services.extractor.word_parser import _blocks_to_text

EXTRACTION_JSON_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "questions": {
            "type": "ARRAY",
            "description": "Danh sách TẤT CẢ các câu hỏi có trong văn bản được trích xuất nguyên văn, không bỏ sót bất kỳ câu nào",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "code": {"type": "STRING", "description": "Mã câu hỏi (VD: Q1, Q2, Q2.1)"},
                    "topic": {"type": "STRING", "description": "Chủ đề / chương kiến thức được ghi trong tài liệu"},
                    "title": {"type": "STRING", "description": "Tiêu đề tóm tắt ngắn gọn từ chính câu hỏi"},
                    "content": {"type": "STRING", "description": "NGUYÊN VĂN câu hỏi phát vấn trích từ tài liệu gốc"},
                    "sample_answer": {"type": "STRING", "description": "Câu trả lời tham chiếu chi tiết và chuẩn xác cho câu hỏi này"},
                    "difficulty": {"type": "STRING", "description": "Độ khó: easy, medium hoặc hard"},
                    "time_limit_seconds": {"type": "INTEGER", "description": "Thời gian trả lời tối đa (giây, thường 120-300)"},
                    "parent_code": {
                        "type": "STRING",
                        "description": "Mã câu hỏi cha nếu đây là câu hỏi phụ / nhánh hỏi tiếp theo sau câu trước (hoặc null)",
                    },
                    "is_followup": {"type": "BOOLEAN", "description": "True nếu đây là câu hỏi phụ hỏi tiếp"},
                    "tags": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"},
                        "description": "Danh sách từ khóa phân loại",
                    },
                    "criteria": {
                        "type": "ARRAY",
                        "description": "Danh sách 3-4 tiêu chí Rubric chấm điểm chi tiết. Tổng max_score phải đúng bằng 10.0",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "name": {"type": "STRING", "description": "Tên tiêu chí (bám sát nội dung câu hỏi)"},
                                "description": {"type": "STRING", "description": "Mô tả cụ thể ý cần đạt để AI chấm điểm"},
                                "max_score": {"type": "NUMBER", "description": "Điểm tối đa của tiêu chí"},
                            },
                            "required": ["name", "description", "max_score"],
                        },
                    },
                },
                "required": ["code", "topic", "title", "content", "sample_answer", "difficulty", "criteria"],
            },
        }
    },
    "required": ["questions"],
}


def _enrich_missing_with_gemini(items: list[dict]) -> None:
    """Gọi Gemini CHỈ để bổ sung tiêu đề tóm tắt, đáp án, rubric mà file gốc không có."""
    api_key = (settings.gemini_api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
    if not api_key or not items:
        return

    schema = {
        "type": "OBJECT",
        "properties": {
            "items": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "code": {"type": "STRING"},
                        "title": {"type": "STRING"},
                        "sample_answer": {"type": "STRING"},
                        "criteria": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "name": {"type": "STRING"},
                                    "description": {"type": "STRING"},
                                    "max_score": {"type": "NUMBER"},
                                },
                                "required": ["name", "description", "max_score"],
                            },
                        },
                    },
                    "required": ["code", "title"],
                },
            }
        },
        "required": ["items"],
    }

    try:
        client = genai.Client(api_key=api_key)
    except Exception as exc:  # pragma: no cover
        print(f"[AI-SERVICE] Khong khoi tao duoc Gemini: {exc}", flush=True)
        return

    by_code = {it["code"]: it for it in items}
    batch_size = 8
    for start_idx in range(0, len(items), batch_size):
        batch = items[start_idx : start_idx + batch_size]
        payload = [
            {
                "code": it["code"],
                "topic": it["topic"],
                "question": it["content"],
                "existing_answer": it["sample_answer"] or None,
                "need_answer": not it["sample_answer"],
                "need_rubric": not it["criteria"],
            }
            for it in batch
        ]
        prompt = (
            "Bạn là giảng viên CNTT soạn tài liệu chấm thi vấn đáp. Với MỖI câu hỏi dưới đây (giữ đúng `code`):\n"
            "1. `title`: tóm tắt chủ đề câu hỏi thành cụm danh từ 3-8 từ (KHÔNG chép lại nguyên câu hỏi).\n"
            "2. Nếu `need_answer` = true: viết `sample_answer` là đáp án tham chiếu chuyên môn, chính xác, "
            "trả lời ĐÚNG và ĐỦ các ý mà câu hỏi yêu cầu (dùng văn bản thuần, xuống dòng bằng `- ` cho từng ý, 80-200 từ). "
            "TUYỆT ĐỐI KHÔNG dùng thẻ HTML như `<ul>`, `<li>`, `<p>`, `<br>`, `<b>`.\n"
            "Nếu `need_answer` = false: để `sample_answer` rỗng.\n"
            "3. Nếu `need_rubric` = true: tạo `criteria` gồm 3-4 tiêu chí bám sát các ý trong câu hỏi "
            "(dựa trên existing_answer nếu có), dùng văn bản thuần không chứa thẻ HTML, tổng `max_score` ĐÚNG 10.0. Nếu false: để `criteria` rỗng.\n"
            "Không được thay đổi hay bịa thêm câu hỏi. Trả về JSON theo schema.\n\n"
            f"DANH SÁCH CÂU HỎI:\n{json.dumps(payload, ensure_ascii=False, indent=1)}"
        )
        try:
            response = client.models.generate_content(
                model=settings.default_llm_model or "gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0.2,
                ),
            )
            parsed = json.loads((response.text or "").strip() or "{}")
        except Exception as exc:
            print(f"[AI-SERVICE] Gemini bo sung that bai (batch {start_idx}): {exc}", flush=True)
            continue

        for out in parsed.get("items", []):
            it = by_code.get(str(out.get("code", "")).strip())
            if it is None:
                continue
            title = _clean_html_to_text(out.get("title") or "")
            if title:
                it["ai_title"] = title[:120]
            if not it["sample_answer"]:
                ans = _clean_html_to_text(out.get("sample_answer") or "")
                if ans:
                    it["sample_answer"] = ans
                    it["answer_by_ai"] = True
            if not it["criteria"] and out.get("criteria"):
                crits = [
                    {
                        "name": _clean_html_to_text(c.get("name")),
                        "description": _clean_html_to_text(c.get("description") or ""),
                        "max_score": float(c.get("max_score") or 0),
                    }
                    for c in out["criteria"]
                    if _clean_html_to_text(c.get("name"))
                ]
                total = sum(c["max_score"] for c in crits)
                if crits and total > 0 and abs(total - 10.0) > 0.05:
                    for c in crits:
                        c["max_score"] = round(c["max_score"] * 10.0 / total, 1)
                    crits[-1]["max_score"] = round(10.0 - sum(c["max_score"] for c in crits[:-1]), 1)
                if crits:
                    it["criteria"] = crits
                    it["rubric_by_ai"] = True


def _parse_word_with_gemini(blocks: list[dict]) -> Optional[List[ExtractedQuestionItem]]:
    """Phương án dự phòng: khi parser cấu trúc không nhận ra câu hỏi nào, nhờ Gemini bóc tách toàn bộ."""
    api_key = (settings.gemini_api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
    full_text = _blocks_to_text(blocks)
    if not api_key or not full_text.strip():
        return None

    system_prompt = """
BẠN LÀ CHUYÊN GIA BÓC TÁCH ĐỀ THI VẤN ĐÁP. QUY TẮC BẮT BUỘC:
1. Mỗi câu hỏi gồm 3 vùng tách biệt:
   - `content`: CHỈ nguyên văn câu hỏi phát vấn (kể cả các ý a, b, c / gạch đầu dòng thuộc câu hỏi).
   - `sample_answer`: phần "Đáp án / Gợi ý / Trả lời / Hướng dẫn giải" trong tài liệu (nguyên văn).
     Nếu tài liệu không có, tự soạn đáp án chuyên môn chính xác bằng văn bản thuần (xuống dòng với `- ` cho từng ý).
   - `criteria`: phần "Tiêu chí chấm điểm / Rubric / Thang điểm / Biểu điểm" trong tài liệu (giữ nguyên tên và điểm).
     Nếu tài liệu không có, tự tạo 3-4 tiêu chí, tổng đúng 10.0.
2. Dòng tiêu đề như "Tiêu chí chấm điểm (Rubric)", "Đáp án:" KHÔNG thuộc `content`.
3. Các dòng đánh số 1., 2., 3. nằm dưới "Tiêu chí chấm điểm" là TIÊU CHÍ, KHÔNG phải câu hỏi mới.
4. Dòng "PHẦN ...", "CHƯƠNG ..." là `topic`, không phải câu hỏi.
5. Không bịa câu hỏi không có trong tài liệu. `title` là cụm tóm tắt 3-8 từ.
6. Mọi trường chuỗi chỉ xuất VĂN BẢN THUẦN (plain text), TUYỆT ĐỐI KHÔNG dùng thẻ HTML như `<ul>`, `<li>`, `<p>`, `<br>`, `<b>`.
"""
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=settings.default_llm_model or "gemini-2.5-flash",
            contents=f"{system_prompt}\n\nTÀI LIỆU:\n===================\n{full_text[:40000]}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=EXTRACTION_JSON_SCHEMA,
                temperature=0.1,
            ),
        )
        parsed = json.loads((response.text or "").strip())
    except Exception as e:
        print(f"[AI-SERVICE] Loi khi goi Gemini (fallback): {e}", flush=True)
        return None

    items: list[dict] = []
    for i, q in enumerate(parsed.get("questions", [])):
        content = _clean_html_to_text(q.get("content") or "")
        if not content:
            continue
        items.append({
            "code": str(q.get("code") or f"Q{i + 1}"),
            "topic": _clean_html_to_text(q.get("topic") or "Kiến thức chuyên ngành") or "Kiến thức chuyên ngành",
            "content": content,
            "sample_answer": _clean_html_to_text(q.get("sample_answer") or ""),
            "criteria": [
                {
                    "name": _clean_html_to_text(c.get("name")),
                    "description": _clean_html_to_text(c.get("description", "")),
                    "max_score": float(c.get("max_score") or 0),
                }
                for c in q.get("criteria", [])
                if _clean_html_to_text(c.get("name"))
            ],
            "parent_code": q.get("parent_code") or None,
            "is_followup": bool(q.get("is_followup", False)),
            "ai_title": _clean_html_to_text(q.get("title") or "") or None,
        })
    return _items_to_questions(items) if items else None
