"""Module đọc và bóc tách ngân hàng câu hỏi & Rubric từ file Excel (.xlsx).

Nhiệm vụ:
- Đọc sheet chính bằng `openpyxl` (`_parse_excel`), tự nhận diện dòng tiêu đề và ánh xạ linh hoạt các cột (Mã câu, Chương/Chủ đề, Tiêu đề, Nội dung phát vấn, Đáp án tham chiếu, Ý chính/Tiêu chí Rubric, Độ khó, Thời lượng, Mã câu hỏi cha).
- Tự động làm sạch thẻ HTML trong từng ô dữ liệu qua `_clean_html_to_text`.
- Tách danh sách tiêu chí Rubric (theo xuống dòng, `;`, `•`, gạch đầu dòng đầu ý — không cắt nhầm từ ghép như `Client-Server`), làm phẳng tiêu chí cha-con và tự bù đáp án/rubric mẫu nếu dòng bị thiếu.
"""

import io
import re
from typing import List

import openpyxl

from app.schemas.question_import_schema import (
    ExtractedQuestionItem,
    RubricCriterionItem,
)
from app.services.extractor.common import (
    _clean_html_to_text,
    _extract_score,
    _generate_tailored_criteria,
    _generate_tailored_sample_answer,
    _make_criterion,
    _make_title,
    _normalize_criteria,
    _normalize_difficulty,
    _reconcile_parent_child_criteria,
)


def _parse_excel(file_bytes: bytes) -> List[ExtractedQuestionItem]:
    """Phân tích dữ liệu từ file Excel (.xlsx)."""
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    sheet = wb.active
    if sheet is None:
        return []

    rows = list(sheet.iter_rows(values_only=True))
    if not rows or len(rows) < 2:
        return []

    header_idx = 0
    header_map: dict[str, int] = {}
    for r_idx, row in enumerate(rows[:5]):
        row_str = " ".join([str(c or "").lower() for c in row])
        if any(kw in row_str for kw in ["mã", "code", "nội dung", "câu hỏi", "đáp án", "tiêu đề"]):
            header_idx = r_idx
            for c_idx, cell in enumerate(row):
                if cell is not None:
                    header_map[str(cell).strip().lower()] = c_idx
            break

    def get_col_val(row_data: tuple, *aliases: str) -> str:
        for alias in aliases:
            for h_name, col_i in header_map.items():
                if alias in h_name and col_i < len(row_data):
                    val = row_data[col_i]
                    if val is not None:
                        return _clean_html_to_text(val)
        return ""

    questions: List[ExtractedQuestionItem] = []
    row_count = 0

    for r_idx in range(header_idx + 1, len(rows)):
        row_data = rows[r_idx]
        if not row_data or all(c is None or str(c).strip() == "" for c in row_data):
            continue

        row_count += 1
        code = get_col_val(row_data, "mã câu", "ma cau", "code", "mã") or f"Q{row_count}"
        topic = get_col_val(row_data, "chương", "chuong", "chủ đề", "chu de", "topic") or "Chủ đề chung"
        title = get_col_val(row_data, "tiêu đề", "tieu de", "title") or ""
        content = get_col_val(row_data, "nội dung", "noi dung", "câu hỏi", "cau hoi", "prompt") or ""
        sample_answer = get_col_val(row_data, "đáp án", "dap an", "sample", "reference", "trả lời") or ""
        raw_diff = get_col_val(row_data, "độ khó", "do kho", "difficulty", "mức độ")
        difficulty = _normalize_difficulty(raw_diff)
        raw_time = get_col_val(row_data, "thời gian", "thoi gian", "time", "giây")
        time_limit = 180
        if raw_time:
            digits = re.findall(r"\d+", raw_time)
            if digits:
                time_limit = int(digits[0])
                if time_limit < 10:
                    time_limit = time_limit * 60

        parent_code = get_col_val(row_data, "câu hỏi cha", "cau hoi cha", "parent", "mã cha") or None
        is_followup = bool(parent_code)

        key_points = get_col_val(row_data, "ý chính", "y chinh", "key", "rubric", "tiêu chí")
        criteria: List[RubricCriterionItem] = []
        if key_points:
            raw_parts = [
                p.strip()
                for p in re.split(r"(?:\r?\n|;|•)+|(?:^|\s+)(?:[-*+]\s+)", key_points)
                if p and p.strip()
            ]
            raw_crits = []
            for pt in raw_parts:
                c_dict = _make_criterion(pt, _extract_score(pt))
                if c_dict:
                    raw_crits.append(c_dict)
            if raw_crits:
                criteria = _normalize_criteria(_reconcile_parent_child_criteria(raw_crits))
        if not criteria:
            criteria = _generate_tailored_criteria(content)

        total_score = round(sum(c.max_score for c in criteria), 1)
        if not title and content:
            title = _make_title(content)

        if not sample_answer and content:
            sample_answer = _generate_tailored_sample_answer(content)

        questions.append(
            ExtractedQuestionItem(
                temp_id=f"row-{row_count}",
                code=code,
                topic=topic,
                title=title or f"Câu hỏi {row_count}",
                content=content,
                sample_answer=sample_answer,
                difficulty=difficulty,
                time_limit_seconds=time_limit,
                parent_code=parent_code,
                is_followup=is_followup,
                tags=[topic] if topic else ["Chung"],
                criteria=criteria,
                total_score=total_score,
                status="valid",
                errors=[],
                warnings=[],
            )
        )

    return questions
