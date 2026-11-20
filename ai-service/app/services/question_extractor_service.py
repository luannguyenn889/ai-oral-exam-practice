"""Service điều phối bóc tách & kiểm duyệt ngân hàng câu hỏi/Rubric từ Word/Excel.

Nhiệm vụ:
- Đóng vai trò điểm vào chính (`extract_questions_from_file`) và facade tương thích ngược cho gói `app.services.extractor` (`common`, `excel_parser`, `word_parser`, `gemini_enricher`).
- Điều tuyến theo định dạng file: `.xlsx`/`.xls` -> `_parse_excel`; `.docx`/`.txt` -> `_parse_word_document` (State Machine + bổ sung phần thiếu bằng Gemini).
- Kiểm duyệt tính hợp lệ cho từng câu hỏi trước khi trả lên bảng Preview của Giảng viên:
    + Phát hiện thiếu nội dung/đáp án, câu hỏi trùng lặp, câu hỏi lẫn tiêu đề Rubric/Đáp án, câu hỏi cha không tồn tại, hoặc tổng điểm Rubric lệch 10.0đ.
"""

import re
from typing import List, Optional

from app.schemas.question_import_schema import (
    ExtractedQuestionItem,
    QuestionExtractResponse,
)
from app.services.extractor.common import (
    _build_answer_from_criteria,
    _clean_html_to_text,
    _extract_score,
    _generate_tailored_criteria,
    _generate_tailored_sample_answer,
    _guess_difficulty,
    _items_to_questions,
    _make_criterion,
    _make_title,
    _normalize_criteria,
    _normalize_difficulty,
    _reconcile_parent_child_criteria,
    _strip_score,
    _to_float,
)
from app.services.extractor.excel_parser import _parse_excel
from app.services.extractor.gemini_enricher import (
    EXTRACTION_JSON_SCHEMA,
    _enrich_missing_with_gemini,
    _parse_word_with_gemini,
)
from app.services.extractor.word_parser import (
    _blocks_to_text,
    _detect_word_list_info,
    _read_document_blocks,
    _structure_parse,
)


def _parse_word_document(file_bytes: bytes, filename: str) -> List[ExtractedQuestionItem]:
    blocks = _read_document_blocks(file_bytes, filename)
    items = _structure_parse(blocks)
    if not items:
        return _parse_word_with_gemini(blocks) or []
    _enrich_missing_with_gemini(items)
    return _items_to_questions(items)


def extract_questions_from_file(
    file_bytes: bytes,
    file_name: str,
    course_id: Optional[str] = None,
) -> QuestionExtractResponse:
    """Hàm điều phối phân tích file Word/Excel và trả về bảng Preview có kiểm duyệt tính hợp lệ."""
    lower_fn = file_name.lower()
    if lower_fn.endswith((".xlsx", ".xls")):
        questions = _parse_excel(file_bytes)
    else:
        questions = _parse_word_document(file_bytes, file_name)

    existing_codes = {q.code.strip().upper() for q in questions if q.code}
    valid_count = 0
    error_count = 0
    warning_count = 0

    seen_contents: dict[str, str] = {}
    leaked_header_re = re.compile(
        r"(?:tiêu\s*chí\s*chấm\s*điểm|thang\s*điểm|biểu\s*điểm|đáp\s*án\s*tham\s*chiếu|hướng\s*dẫn\s*chấm)",
        re.IGNORECASE,
    )

    for q in questions:
        q.errors = []
        q.warnings = []

        content_clean = q.content.strip()
        if not content_clean:
            q.errors.append("Thiếu nội dung câu hỏi phát vấn")
        else:
            norm_key = re.sub(r"\W+", " ", content_clean.lower()).strip()
            if norm_key in seen_contents:
                q.warnings.append(f"Nội dung câu hỏi trùng lặp với câu {seen_contents[norm_key]}")
            else:
                seen_contents[norm_key] = q.code

            if leaked_header_re.search(content_clean):
                q.warnings.append("Nội dung câu hỏi có dấu hiệu lẫn tiêu đề Rubric/Đáp án, vui lòng kiểm tra lại")
            if len(content_clean) > 650:
                q.warnings.append("Nội dung câu hỏi dài bất thường (>650 ký tự), có thể đang gộp nhiều câu")

        if not q.sample_answer.strip():
            q.errors.append("Thiếu đáp án tham chiếu (AI cần đáp án mẫu để đối chiếu chấm)")

        if q.parent_code:
            parent_clean = q.parent_code.strip().upper()
            if parent_clean == q.code.strip().upper():
                q.errors.append("Câu hỏi cha không được trùng với chính câu hỏi này")
            elif parent_clean not in existing_codes:
                q.warnings.append(f"Không tìm thấy câu hỏi cha mang mã '{q.parent_code}' trong file")

        total_sc = round(sum(c.max_score for c in q.criteria), 1)
        q.total_score = total_sc
        if abs(total_sc - 10.0) > 0.05:
            q.warnings.append(f"Tổng điểm Rubric là {total_sc}đ (Cần cân bằng về đúng 10.0đ)")

        if q.errors:
            q.status = "error"
            error_count += 1
        elif q.warnings:
            q.status = "warning"
            warning_count += 1
        else:
            q.status = "valid"
            valid_count += 1

    return QuestionExtractResponse(
        file_name=file_name,
        total_detected=len(questions),
        valid_count=valid_count,
        error_count=error_count,
        warning_count=warning_count,
        questions=questions,
    )
