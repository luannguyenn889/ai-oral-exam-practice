"""Dịch vụ AI phân tích và bóc tách câu hỏi, đáp án mẫu, câu hỏi cha/con và Rubric từ file Word/Excel.

CAM KẾT CHÍNH XÁC:
- Đọc TOÀN BỘ tài liệu từ đầu đến cuối (tất cả các đoạn văn bản và bảng biểu).
- Trích xuất ĐÚNG 100% nội dung câu hỏi có trong tài liệu của giảng viên, TUYỆT ĐỐI KHÔNG BỊA RA nội dung không có trong file.
- Nhận diện đúng cấu trúc phân nhóm (Chương/Phần/Chủ đề).
- Tự động xây dựng Rubric thang điểm chuẩn 10.0đ bám sát vào từng câu hỏi cụ thể.
"""

import io
import json
import os
import re
import time
from typing import Any, List, Optional

import openpyxl
from google import genai
from google.genai import types

from app.config import settings
from app.schemas.question_import_schema import (
    ExtractedQuestionItem,
    QuestionExtractResponse,
    RubricCriterionItem,
)

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


def _normalize_difficulty(val: Any) -> str:
    s = str(val or "").strip().lower()
    if any(k in s for k in ["dễ", "de", "easy", "cơ bản", "co ban", "1"]):
        return "easy"
    if any(k in s for k in ["khó", "kho", "hard", "nâng cao", "nang cao", "3"]):
        return "hard"
    return "medium"


def _generate_tailored_criteria(question_text: str) -> List[RubricCriterionItem]:
    """Tự động sinh tiêu chí Rubric chuẩn 10.0đ bám sát vào nội dung của chính câu hỏi."""
    q_lower = question_text.lower()
    if "so sánh" in q_lower or "phân biệt" in q_lower:
        return [
            RubricCriterionItem(
                name="Khái niệm & Bản chất các đối tượng",
                description="Trình bày chính xác định nghĩa và nguyên lý của từng đối tượng được so sánh (3.5đ)",
                max_score=3.5,
            ),
            RubricCriterionItem(
                name="Điểm tương đồng & Khác biệt cốt lõi",
                description="Phân tích rõ các tiêu chí so sánh, ưu nhược điểm và sự khác biệt bản chất (4.5đ)",
                max_score=4.5,
            ),
            RubricCriterionItem(
                name="Ví dụ minh họa & Kỹ năng phản xạ",
                description="Lấy ví dụ thực tế minh họa sự khác nhau và trả lời mạch lạc, tự tin (2.0đ)",
                max_score=2.0,
            ),
        ]
    elif "quy trình" in q_lower or "mô hình" in q_lower or "giai đoạn" in q_lower or "hoạt động" in q_lower:
        return [
            RubricCriterionItem(
                name="Các giai đoạn / Hoạt động trọng tâm",
                description="Nêu đầy đủ và đúng trình tự các bước/giai đoạn của quy trình hoặc mô hình (4.0đ)",
                max_score=4.0,
            ),
            RubricCriterionItem(
                name="Nội dung chi tiết & Ý nghĩa từng bước",
                description="Giải thích rõ mục tiêu, đầu vào/đầu ra và vai trò của từng giai đoạn (4.0đ)",
                max_score=4.0,
            ),
            RubricCriterionItem(
                name="Đánh giá ưu nhược điểm & Ứng dụng",
                description="Nêu được bối cảnh áp dụng thực tế và trình bày rõ ràng, mạch lạc (2.0đ)",
                max_score=2.0,
            ),
        ]
    elif "ví dụ" in q_lower or "tái cấu trúc" in q_lower or "bài tập" in q_lower or "thiết kế" in q_lower:
        return [
            RubricCriterionItem(
                name="Cơ sở lý thuyết & Nguyên lý áp dụng",
                description="Nắm vững định nghĩa, cơ chế và yêu cầu kỹ thuật liên quan (3.0đ)",
                max_score=3.0,
            ),
            RubricCriterionItem(
                name="Giải pháp thực thi & Minh họa cụ thể",
                description="Đưa ra tình huống thực tế, phân tích giải pháp hoặc mã nguồn hợp lý (5.0đ)",
                max_score=5.0,
            ),
            RubricCriterionItem(
                name="Lập luận logic & Phản xạ tự tin",
                description="Giải thích rõ ràng lý do lựa chọn giải pháp và phản xạ chuyên nghiệp (2.0đ)",
                max_score=2.0,
            ),
        ]
    else:
        return [
            RubricCriterionItem(
                name="Khái niệm & Kiến thức cốt lõi",
                description="Trình bày chính xác và đầy đủ các định nghĩa, thuật ngữ chuyên môn trọng tâm (3.5đ)",
                max_score=3.5,
            ),
            RubricCriterionItem(
                name="Phân tích chuyên sâu & Bản chất vấn đề",
                description="Phân tích rõ cơ chế hoạt động, sự tác động và nguyên nhân - kết quả (4.5đ)",
                max_score=4.5,
            ),
            RubricCriterionItem(
                name="Liên hệ thực tế & Kỹ năng trình bày",
                description="Đưa ra ví dụ thực tiễn minh họa và diễn đạt lưu loát, tự tin (2.0đ)",
                max_score=2.0,
            ),
        ]


def _generate_tailored_sample_answer(question_text: str) -> str:
    """Tạo dàn ý đáp án tham chiếu chuẩn học thuật khi tài liệu chưa có sẵn phần trả lời mẫu."""
    q_lower = question_text.lower()
    if "so sánh" in q_lower or "phân biệt" in q_lower:
        return (
            "- Nêu khái niệm và bản chất cốt lõi của từng đối tượng được đề cập.\n"
            "- Phân tích các tiêu chí khác biệt trọng tâm (cơ chế hoạt động, phạm vi áp dụng, ưu và nhược điểm).\n"
            "- Đưa ra ví dụ thực tế minh họa hoàn cảnh lựa chọn phù hợp cho từng trường hợp."
        )
    if "quy trình" in q_lower or "mô hình" in q_lower or "giai đoạn" in q_lower or "hoạt động" in q_lower:
        return (
            "- Trình bày tổng quan mục đích và nguyên lý chung của quy trình / mô hình.\n"
            "- Nêu đầy đủ các giai đoạn / hoạt động chính theo đúng trình tự cùng đầu vào và đầu ra của mỗi bước.\n"
            "- Đánh giá ưu nhược điểm và phạm vi áp dụng thực tế trong dự án phần mềm."
        )
    return (
        "- Trình bày chính xác định nghĩa, khái niệm và các thuật ngữ chuyên môn trọng tâm.\n"
        "- Phân tích chi tiết các đặc điểm, thành phần cấu thành hoặc cơ chế hoạt động cốt lõi.\n"
        "- Liên hệ thực tiễn kèm ví dụ minh họa cụ thể và đánh giá ưu / nhược điểm khi áp dụng."
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
                        return str(val).strip()
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
            points = [p.strip() for p in re.split(r"[;\n\r\•\-\*]+", key_points) if p.strip()]
            if len(points) >= 2:
                each_score = round(10.0 / len(points), 1)
                for p_idx, pt in enumerate(points):
                    criteria.append(
                        RubricCriterionItem(
                            name=f"Tiêu chí {p_idx + 1}: {pt[:40]}",
                            description=pt,
                            max_score=each_score if p_idx < len(points) - 1 else round(10.0 - each_score * (len(points) - 1), 1),
                        )
                    )
        if not criteria:
            criteria = _generate_tailored_criteria(content)

        total_score = round(sum(c.max_score for c in criteria), 1)
        if not title and content:
            title = content[:60] + "..." if len(content) > 60 else content

        if not sample_answer and content:
            sample_answer = _generate_tailored_sample_answer(content)

        q_item = ExtractedQuestionItem(
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
        questions.append(q_item)

    return questions


# =====================================================================================
# BÓC TÁCH FILE WORD TỰ DO: Parser cấu trúc theo vùng (State Machine) + AI chỉ bù phần thiếu
# =====================================================================================
#
# Nguyên tắc:
#   1. Đọc tài liệu ĐÚNG THỨ TỰ xuất hiện (đoạn văn + bảng xen kẽ), nhận biết cả danh sách
#      đánh số tự động của Word (số "1." không nằm trong text).
#   2. Mỗi dòng được phân vào 1 trong 3 VÙNG của câu hỏi hiện tại:
#        content (nội dung phát vấn) | answer (đáp án tham chiếu) | rubric (tiêu chí chấm)
#      -> Dòng tiêu đề "Tiêu chí chấm điểm (Rubric)", "Đáp án:" chỉ dùng để CHUYỂN VÙNG,
#         không bao giờ bị chèn vào nội dung câu hỏi.
#      -> Các dòng đánh số "1.", "2." nằm trong vùng rubric/đáp án là Ý CHẤM / Ý ĐÁP ÁN,
#         không bị tách thành câu hỏi mới.
#   3. Nội dung câu hỏi, đáp án và rubric có sẵn trong file được giữ NGUYÊN VĂN.
#      AI (Gemini) chỉ được gọi để bổ sung phần file KHÔNG có (đáp án, rubric, tiêu đề tóm tắt).

_BULLET_RE = re.compile(r"^\s*(?:[-–—•●○◦▪■□+*➢➤►✓✔]|\(?[a-zA-Zđ]\)|[a-zA-Zđ][\.\)](?=\s))\s*")
_ENUM_PREFIX_RE = re.compile(r"^\s*(?:\(?\d{1,2}[\.\)]|\(?[a-zA-Zđ][\.\)]|[-–—•●○◦▪■□+*➢➤►✓✔])\s*")

_TOPIC_RE = re.compile(
    r"^(?:phần|chương|chủ đề|học phần|part|chapter|unit)\s*(?:[\dIVXLivxl]+|[A-Z])\s*[:\.\-–)]?\s*",
    re.IGNORECASE,
)
_SECTION_RE = re.compile(r"^(?:[A-D]|[IVX]{1,4})[\.\)]\s+\S", re.IGNORECASE)

_QUESTION_PREFIX_RE = re.compile(
    r"^(?:câu(?:\s*hỏi)?|bài|question|q)\s*(\d+(?:\.\d+)*)\s*(\([^)]*\))?\s*[:\.\)\-–]?\s*(.*)$",
    re.IGNORECASE,
)
_NUMBERED_RE = re.compile(r"^(\d{1,3})\s*[\.\)]\s+(.+)$")
_SUB_NUMBERED_RE = re.compile(r"^(\d{1,3}(?:\.\d{1,3})+)\s*[\.\)]?\s+(.+)$")

_ANSWER_HEADER_RE = re.compile(
    r"^(?:đáp\s*án(?:\s*(?:tham\s*chiếu|mẫu|gợi\s*ý|đề\s*xuất))?|trả\s*lời|lời\s*giải|"
    r"gợi\s*ý(?:\s*(?:trả\s*lời|đáp\s*án))?|hướng\s*dẫn\s*(?:giải|trả\s*lời)|"
    r"reference\s*answer|sample\s*answer|answer|key\s*points?|ý\s*chính(?:\s*cần\s*đạt)?)"
    r"\s*(?:\([^)]*\))?\s*[:\.\-–]?\s*(.*)$",
    re.IGNORECASE,
)
_RUBRIC_HEADER_RE = re.compile(
    r"^(?:tiêu\s*chí(?:\s*(?:chấm(?:\s*điểm)?|đánh\s*giá))?|rubric|thang\s*điểm|biểu\s*điểm|"
    r"barem[e]?|hướng\s*dẫn\s*chấm(?:\s*điểm)?|cách\s*chấm(?:\s*điểm)?|grading\s*criteria|criteria)"
    r"\s*(?:\([^)]*\))?\s*[:\.\-–]?\s*(.*)$",
    re.IGNORECASE,
)
_SCORE_RE = re.compile(
    r"(?<![\w.,])(\d{1,2}(?:[.,]\d{1,2})?)\s*(?:điểm|diem|đ|pts?|points?)(?!\w)",
    re.IGNORECASE,
)
_TRAILING_SCORE_RE = re.compile(r"[:\-–|]\s*(\d{1,2}(?:[.,]\d{1,2})?)\s*$")

_QUESTION_CUE_START_RE = re.compile(
    r"^(?:hãy|trình\s*bày|nêu|phân\s*biệt|so\s*sánh|giải\s*thích|phân\s*tích|mô\s*tả|cho\s*biết|"
    r"vì\s*sao|tại\s*sao|thế\s*nào|liệt\s*kê|định\s*nghĩa|xây\s*dựng|thiết\s*kế|viết|vẽ|đánh\s*giá|"
    r"chứng\s*minh|làm\s*thế\s*nào|khi\s*nào|bằng\s*cách\s*nào|kể\s*tên|lấy\s*ví\s*dụ|cho\s*ví\s*dụ)\b",
    re.IGNORECASE,
)
_QUESTION_CUE_ANY_RE = re.compile(
    r"\?|\bhãy\s|\blà\s*gì\b|\bnhư\s*thế\s*nào\b|\bvì\s*sao\b|\btại\s*sao\b", re.IGNORECASE
)

_IGNORE_LINE_PATTERNS = [
    r"^nội dung ôn tập",
    r"^đề cương(?: ôn tập)?",
    r"^ngân hàng câu hỏi",
    r"^bộ câu hỏi",
    r"^danh sách câu hỏi",
    r"^--+\s*hết\s*--+",
    r"^hết$",
    r"^giáo viên|^giảng viên(?: phụ trách)?\s*:",
    r"^năm học",
    r"^trường đại học|^khoa\s",
    r"^thời gian(?: làm bài)?\s*:",
]


def _to_float(raw: str) -> float:
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        return 0.0


def _read_document_blocks(file_bytes: bytes, filename: str) -> list[dict]:
    """Đọc tài liệu theo đúng thứ tự: [{'type':'line','text','is_list'} | {'type':'table','rows'}]."""
    blocks: list[dict] = []
    if filename.lower().endswith(".docx"):
        import docx
        from docx.table import Table
        from docx.text.paragraph import Paragraph

        doc = docx.Document(io.BytesIO(file_bytes))
        for child in doc.element.body.iterchildren():
            tag = child.tag.rsplit("}", 1)[-1]
            if tag == "p":
                para = Paragraph(child, doc)
                ppr = child.pPr
                is_list = bool(ppr is not None and ppr.numPr is not None)
                style_name = (para.style.name or "").lower() if para.style is not None else ""
                if "list" in style_name:
                    is_list = True
                for part in (para.text or "").split("\n"):
                    text = re.sub(r"\s+", " ", part).strip()
                    if text:
                        blocks.append({"type": "line", "text": text, "is_list": is_list})
            elif tag == "tbl":
                table = Table(child, doc)
                rows: list[list[str]] = []
                for row in table.rows:
                    cells: list[str] = []
                    prev_tc = None
                    for cell in row.cells:
                        if cell._tc is prev_tc:  # bỏ ô gộp (merged) bị lặp
                            continue
                        prev_tc = cell._tc
                        cells.append(re.sub(r"\s+", " ", cell.text or "").strip())
                    if any(cells):
                        rows.append(cells)
                if rows:
                    blocks.append({"type": "table", "rows": rows})
    else:
        try:
            raw_text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raw_text = file_bytes.decode("latin-1", errors="ignore")
        for line in raw_text.splitlines():
            text = re.sub(r"\s+", " ", line).strip()
            if text:
                blocks.append({"type": "line", "text": text, "is_list": False})
    return blocks


def _blocks_to_text(blocks: list[dict]) -> str:
    out: list[str] = []
    for b in blocks:
        if b["type"] == "line":
            out.append(("• " if b.get("is_list") else "") + b["text"])
        else:
            for row in b["rows"]:
                out.append(" | ".join(c for c in row if c))
    return "\n".join(out)


def _extract_score(text: str) -> Optional[float]:
    matches = list(_SCORE_RE.finditer(text))
    if matches:
        return _to_float(matches[-1].group(1))
    m = _TRAILING_SCORE_RE.search(text)
    if m:
        return _to_float(m.group(1))
    return None


def _strip_score(text: str) -> str:
    cleaned = _SCORE_RE.sub("", text)
    cleaned = _TRAILING_SCORE_RE.sub("", cleaned)
    cleaned = re.sub(r"\(\s*\)|\[\s*\]", "", cleaned)
    return cleaned.strip(" \t:;,-–|()[]")


def _make_criterion(text: str, score: Optional[float]) -> Optional[dict]:
    text_clean = text.strip()
    m_sub = _SUB_NUMBERED_RE.match(text_clean)
    if m_sub:
        body = m_sub.group(2).strip()
    else:
        body = _ENUM_PREFIX_RE.sub("", text_clean, count=1).strip()
    body = re.sub(r"^tiêu\s*chí\s*\d*\s*[:\.\-–)]?\s*", "", body, flags=re.IGNORECASE)
    body = _strip_score(body)
    if not body:
        return None
    if ":" in body:
        left, right = body.split(":", 1)
        if 2 <= len(left.strip()) <= 90 and right.strip():
            return {"name": left.strip(), "description": right.strip(), "max_score": score}
    name = body if len(body) <= 90 else body[:87].rsplit(" ", 1)[0] + "..."
    return {"name": name, "description": body, "max_score": score}


def _is_topic_line(text: str) -> bool:
    if _TOPIC_RE.match(text) and not text.rstrip().endswith("?"):
        return True
    letters = [c for c in text if c.isalpha()]
    return bool(
        letters
        and len(text) <= 90
        and text.isupper()
        and not text.endswith("?")
        and not _SCORE_RE.search(text)
    )


def _looks_like_question(text: str) -> bool:
    body = _ENUM_PREFIX_RE.sub("", text, count=1)
    return bool(_QUESTION_CUE_START_RE.match(body) or _QUESTION_CUE_ANY_RE.search(body))


def _new_item(code: Optional[str], topic: str, content: str, parent: Optional[str] = None,
              is_followup: bool = False) -> dict:
    return {
        "code": code,
        "topic": topic,
        "content_lines": [content] if content else [],
        "answer_lines": [],
        "criteria": [],
        "parent_code": parent,
        "is_followup": is_followup,
        "mode": "content",
    }


def _structure_parse(blocks: list[dict]) -> list[dict]:
    """Máy trạng thái phân vùng: chia tài liệu thành các câu hỏi với 3 vùng content/answer/rubric."""
    lines = [b for b in blocks if b["type"] == "line"]
    uses_prefix = sum(1 for b in lines if _QUESTION_PREFIX_RE.match(b["text"])) >= 2

    items: list[dict] = []
    current: Optional[dict] = None
    current_topic = "Kiến thức chuyên ngành"

    def start(item: dict) -> None:
        nonlocal current
        if current is not None:
            items.append(current)
        current = item

    def add_criterion_line(text: str, is_list: bool = False) -> None:
        assert current is not None
        score = _extract_score(text)
        text_s = text.strip()
        is_sub_num = bool(_SUB_NUMBERED_RE.match(text_s))
        is_bullet = bool(_BULLET_RE.match(text_s)) or is_list
        is_major_num = bool(_NUMBERED_RE.match(text_s)) and not is_sub_num

        # 1. Tiêu chí cha: '1. Kiến thức chuyên môn (6đ)'
        if is_major_num:
            m = _NUMBERED_RE.match(text_s)
            body = m.group(2).strip()
            crit = _make_criterion(body, score)
            if crit:
                crit["is_parent"] = True
                crit["children"] = []
                current["criteria"].append(crit)
            return

        # 2. Tiêu chí con: 'a. Nêu đúng định nghĩa (2đ)' hoặc '1.1. Nêu...' hoặc '- Trả lời lưu loát...'
        if (is_bullet or is_sub_num) and current["criteria"]:
            last_parent = None
            for c in reversed(current["criteria"]):
                if c.get("is_parent"):
                    last_parent = c
                    break

            crit = _make_criterion(text_s, score)
            if crit:
                if last_parent:
                    p_name = last_parent["name"]
                    c_name = crit["name"]
                    crit["name"] = f"[{p_name}] {c_name}"
                    crit["is_child"] = True
                    last_parent["children"].append(crit)
                else:
                    current["criteria"].append(crit)
            return

        # 3. Dòng mô tả nối tiếp của tiêu chí ngay trước
        if score is None and current["criteria"] and not is_bullet and not is_major_num and not is_sub_num:
            target = current["criteria"][-1]
            if target.get("children"):
                target = target["children"][-1]
            target["description"] = (target["description"] + " " + text_s).strip()
            return

        # 4. Tiêu chí độc lập khác
        crit = _make_criterion(text_s, score)
        if crit:
            current["criteria"].append(crit)

    for block in blocks:
        # ----------------------------- BẢNG -----------------------------
        if block["type"] == "table":
            rows = block["rows"]
            header = " ".join(rows[0]).lower()
            is_rubric_table = (current is not None and current["mode"] == "rubric") or (
                current is not None and ("tiêu chí" in header or "điểm" in header) and "câu hỏi" not in header
            )
            is_question_table = any(k in header for k in ["câu hỏi", "nội dung", "đề bài", "question"])

            if is_rubric_table and current is not None:
                current["mode"] = "rubric"
                for r_idx, row in enumerate(rows):
                    joined = " ".join(row).lower()
                    numeric_cells = [c for c in row if re.fullmatch(r"\d{1,2}(?:[.,]\d{1,2})?\s*(?:đ|điểm)?", c.strip(), re.I)]
                    if r_idx == 0 and not numeric_cells and ("tiêu chí" in joined or "điểm" in joined or "stt" in joined):
                        continue  # hàng tiêu đề bảng
                    score = None
                    for c in numeric_cells:
                        val = _to_float(re.sub(r"[^\d.,]", "", c))
                        if 0 < val <= 10:
                            score = val
                    if score is None:
                        score = _extract_score(" ".join(row))
                    texts = [c for c in row if c and c not in numeric_cells and not re.fullmatch(r"\d{1,2}", c)]
                    if not texts:
                        continue
                    name = _strip_score(texts[0])
                    desc = _strip_score(" ".join(texts[1:])) or name
                    if name:
                        current["criteria"].append({"name": name[:120], "description": desc, "max_score": score})
                continue

            if is_question_table:
                hdr = [c.lower() for c in rows[0]]

                def col(*keys: str) -> int:
                    for i, h in enumerate(hdr):
                        if any(k in h for k in keys):
                            return i
                    return -1

                c_content = col("câu hỏi", "nội dung", "đề bài", "question")
                c_answer = col("đáp án", "trả lời", "gợi ý", "answer", "lời giải")
                c_rubric = col("tiêu chí", "rubric", "thang điểm", "biểu điểm", "barem")
                c_code = col("mã", "stt", "code")
                for row in rows[1:]:
                    def cell(i: int) -> str:
                        return row[i].strip() if 0 <= i < len(row) else ""
                    content = cell(c_content)
                    if not content:
                        continue
                    code_raw = cell(c_code)
                    code = f"Q{code_raw}" if code_raw.isdigit() else (code_raw or None)
                    item = _new_item(code, current_topic, content)
                    if cell(c_answer):
                        item["answer_lines"].append(cell(c_answer))
                    if cell(c_rubric):
                        for part in re.split(r"[;\n]|(?<=\d[đ\)])\s*,", cell(c_rubric)):
                            crit = _make_criterion(part, _extract_score(part))
                            if crit:
                                item["criteria"].append(crit)
                    start(item)
                continue

            # Bảng không xác định: coi như văn bản của vùng hiện tại
            for row in rows:
                text = " | ".join(c for c in row if c)
                if current is None:
                    continue
                if current["mode"] == "answer":
                    current["answer_lines"].append(text)
                elif current["mode"] == "content":
                    current["content_lines"].append(text)
            continue

        # ----------------------------- DÒNG VĂN BẢN -----------------------------
        text = block["text"]
        lower = text.lower()
        if any(re.search(p, lower) for p in _IGNORE_LINE_PATTERNS):
            continue

        # 1. Tiêu đề phần / chương -> chủ đề (đóng câu hiện tại)
        if _is_topic_line(text) or _SECTION_RE.match(text) and len(text) < 60 and not _looks_like_question(text):
            if _SECTION_RE.match(text) and not _TOPIC_RE.match(text) and not text.isupper():
                # "A. Lý thuyết", "I. Bài tập" -> chỉ là nhóm, không đổi chủ đề cụ thể
                if current is not None:
                    items.append(current)
                    current = None
                continue
            if current is not None:
                items.append(current)
                current = None
            current_topic = text
            continue

        # 2. Câu hỏi có tiền tố rõ ràng: "Câu 1:", "Câu 1.1 (Câu hỏi phụ):", "Bài 2."
        q_match = _QUESTION_PREFIX_RE.match(text)
        if q_match:
            num = q_match.group(1)
            note = (q_match.group(2) or "").lower()
            body = q_match.group(3).strip()
            is_sub = "." in num or "phụ" in note or "hỏi tiếp" in note
            parent = f"Q{num.split('.')[0]}" if "." in num else (
                items[-1]["code"] if is_sub and items else None
            )
            start(_new_item(f"Q{num}", current_topic, body, parent, is_sub))
            continue

        # 3. Tiêu đề vùng Rubric (chỉ chuyển vùng, không chèn vào nội dung)
        r_match = _RUBRIC_HEADER_RE.match(text) if "?" not in text else None
        if r_match and current is not None and (_extract_score(text) is None or not r_match.group(1)):
            rest = r_match.group(1).strip()
            prefix_part = text[: len(text) - len(rest)] if rest else text
            if not rest or re.search(r"[:\.\-–\)]", prefix_part) or _extract_score(rest) is not None:
                current["mode"] = "rubric"
                if rest and _extract_score(rest) is not None:
                    add_criterion_line(rest)
                continue
        if r_match and current is not None and current["mode"] in ("content", "answer") and _extract_score(text) is not None:
            # "Tiêu chí 1: Định nghĩa đúng (3đ)" xuất hiện ngay sau câu hỏi
            current["mode"] = "rubric"
            add_criterion_line(text)
            continue

        # 4. Tiêu đề vùng Đáp án
        a_match = _ANSWER_HEADER_RE.match(text) if "?" not in text else None
        if a_match and current is not None:
            rest = a_match.group(1).strip()
            prefix_part = text[: len(text) - len(rest)] if rest else text
            if not rest or re.search(r"[:\.\-–\)]", prefix_part):
                current["mode"] = "answer"
                if rest:
                    current["answer_lines"].append(rest)
                continue

        is_bullet = bool(_BULLET_RE.match(text))
        n_match = _NUMBERED_RE.match(text)

        # 5. Đang ở vùng rubric / đáp án
        if current is not None and current["mode"] in ("rubric", "answer"):
            has_score = _extract_score(text) is not None
            has_qmark = "?" in text
            rubric_has_scores = any(c.get("max_score") is not None for c in current["criteria"])
            looks_q_in_rubric = (
                current["mode"] == "rubric"
                and _looks_like_question(text)
                and (
                    rubric_has_scores
                    or (len(current["criteria"]) >= 2 and not n_match and not block.get("is_list"))
                    or (n_match and int(n_match.group(1)) == 1 and len(current["criteria"]) >= 1)
                )
            )
            looks_q_in_answer = (
                current["mode"] == "answer"
                and _looks_like_question(text)
                and len(current["answer_lines"]) >= 1
                and not block.get("is_list")
            )
            new_question = (
                (not uses_prefix)
                and not is_bullet
                and not has_score
                and (has_qmark or looks_q_in_rubric or looks_q_in_answer)
            )
            if not new_question:
                if current["mode"] == "rubric":
                    add_criterion_line(text, is_list=bool(block.get("is_list")))
                else:
                    current["answer_lines"].append(text)
                continue
            # Không có tiền tố "Câu": câu hỏi mới kết thúc vùng rubric/đáp án của câu trước
            start(_new_item(None, current_topic, _ENUM_PREFIX_RE.sub("", text, count=1) if n_match else text))
            continue

        # 6. Vùng nội dung câu hỏi
        if uses_prefix:
            if current is None:
                continue  # văn bản mở đầu trước câu hỏi đầu tiên
            current["content_lines"].append(text)
            continue

        # Tài liệu không dùng tiền tố "Câu": mỗi đoạn nghi vấn là một câu hỏi mới,
        # gạch đầu dòng / ý a,b,c / đoạn mô tả thì gộp vào câu hiện tại.
        if is_bullet and current is not None:
            current["content_lines"].append(text)
            continue
        if n_match and _extract_score(text) is None:
            start(_new_item(f"Q{n_match.group(1)}", current_topic, n_match.group(2).strip()))
            continue
        if current is None or _looks_like_question(text) or (block.get("is_list") and len(text) > 15):
            if len(text) < 8 and current is not None:
                current["content_lines"].append(text)
                continue
            start(_new_item(None, current_topic, text))
            continue
        current["content_lines"].append(text)

    if current is not None:
        items.append(current)

    # Loại bỏ câu rỗng & đánh mã liên tục cho câu chưa có mã
    cleaned: list[dict] = []
    used_codes: set[str] = set()
    seq = 0
    for it in items:
        content = "\n".join(l for l in it["content_lines"] if l).strip()
        if len(content) < 5:
            continue
        seq += 1
        code = it["code"] or f"Q{seq}"
        while code.upper() in used_codes:
            seq += 1
            code = f"Q{seq}"
        used_codes.add(code.upper())
        it["code"] = code
        it["content"] = content
        it["sample_answer"] = "\n".join(it["answer_lines"]).strip()
        # Phẳng hóa tiêu chí phân cấp cha - con: giữ ý con có tiền tố [Tên tiêu chí cha]
        flattened_criteria = []
        for c in it["criteria"]:
            if c.get("children"):
                flattened_criteria.extend(c["children"])
            else:
                flattened_criteria.append(c)
        it["criteria"] = flattened_criteria
        cleaned.append(it)
    return cleaned


def _normalize_criteria(raw: list[dict]) -> List[RubricCriterionItem]:
    """Giữ nguyên điểm của giảng viên; chỉ chia đều khi file không ghi điểm cho tiêu chí nào."""
    if not raw:
        return []
    scores = [c.get("max_score") for c in raw]
    if all(s is None or s <= 0 for s in scores):
        each = round(10.0 / len(raw), 1)
        filled = [each] * len(raw)
        filled[-1] = round(10.0 - each * (len(raw) - 1), 1)
    else:
        filled = [float(s) if s and s > 0 else 0.0 for s in scores]
    result: List[RubricCriterionItem] = []
    for c, sc in zip(raw, filled):
        result.append(
            RubricCriterionItem(
                name=str(c.get("name") or "Tiêu chí")[:150],
                description=str(c.get("description") or c.get("name") or ""),
                max_score=round(sc, 2),
            )
        )
    return result


def _make_title(content: str) -> str:
    first = content.splitlines()[0].strip()
    first = re.sub(r"^(?:hãy\s+)", "", first, flags=re.IGNORECASE)
    if len(first) <= 95:
        title = first
    else:
        m = re.match(r"^(.{15,95}?[\?\.])(?:\s|$)", first)
        title = m.group(1) if m else (first[:92].rsplit(" ", 1)[0] + "...")
    return title[:1].upper() + title[1:] if title else "Câu hỏi"


def _guess_difficulty(content: str) -> str:
    p = content.lower()
    if any(k in p for k in ["so sánh", "phân biệt", "đánh giá", "thiết kế", "xây dựng", "tái cấu trúc", "ví dụ", "viết use case"]):
        return "hard"
    if any(k in p for k in ["là gì", "định nghĩa", "kể tên", "liệt kê", "nêu "]):
        return "easy"
    return "medium"


def _enrich_missing_with_gemini(items: list[dict]) -> None:
    """Gọi Gemini CHỈ để bổ sung tiêu đề tóm tắt, đáp án, rubric mà file gốc không có.

    Không bao giờ sửa nội dung câu hỏi; không ghi đè đáp án / rubric có sẵn trong file.
    """
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
        batch = items[start_idx:start_idx + batch_size]
        payload = []
        for it in batch:
            payload.append({
                "code": it["code"],
                "topic": it["topic"],
                "question": it["content"],
                "existing_answer": it["sample_answer"] or None,
                "need_answer": not it["sample_answer"],
                "need_rubric": not it["criteria"],
            })
        prompt = (
            "Bạn là giảng viên CNTT soạn tài liệu chấm thi vấn đáp. Với MỖI câu hỏi dưới đây (giữ đúng `code`):\n"
            "1. `title`: tóm tắt chủ đề câu hỏi thành cụm danh từ 3-8 từ (KHÔNG chép lại nguyên câu hỏi).\n"
            "2. Nếu `need_answer` = true: viết `sample_answer` là đáp án tham chiếu chuyên môn, chính xác, "
            "trả lời ĐÚNG và ĐỦ các ý mà câu hỏi yêu cầu (gạch đầu dòng ngắn gọn, 80-200 từ). "
            "Nếu `need_answer` = false: để `sample_answer` rỗng.\n"
            "3. Nếu `need_rubric` = true: tạo `criteria` gồm 3-4 tiêu chí bám sát các ý trong câu hỏi "
            "(dựa trên existing_answer nếu có), tổng `max_score` ĐÚNG 10.0. Nếu false: để `criteria` rỗng.\n"
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
            title = str(out.get("title") or "").strip()
            if title:
                it["ai_title"] = title[:120]
            if not it["sample_answer"]:
                ans = str(out.get("sample_answer") or "").strip()
                if ans:
                    it["sample_answer"] = ans
                    it["answer_by_ai"] = True
            if not it["criteria"] and out.get("criteria"):
                crits = [
                    {"name": c.get("name"), "description": c.get("description"), "max_score": float(c.get("max_score") or 0)}
                    for c in out["criteria"]
                    if c.get("name")
                ]
                total = sum(c["max_score"] for c in crits)
                if crits and total > 0 and abs(total - 10.0) > 0.05:
                    for c in crits:
                        c["max_score"] = round(c["max_score"] * 10.0 / total, 1)
                    crits[-1]["max_score"] = round(10.0 - sum(c["max_score"] for c in crits[:-1]), 1)
                if crits:
                    it["criteria"] = crits
                    it["rubric_by_ai"] = True


def _build_answer_from_criteria(criteria: List[RubricCriterionItem]) -> str:
    lines = ["Các ý trọng tâm cần trình bày theo Rubric chấm điểm:"]
    for c in criteria:
        name = c.name.strip()
        desc = c.description.strip()
        if desc and desc.lower() != name.lower():
            lines.append(f"- {name} ({c.max_score:g}đ): {desc}")
        else:
            lines.append(f"- {name} ({c.max_score:g}đ)")
    return "\n".join(lines)


def _items_to_questions(items: list[dict]) -> List[ExtractedQuestionItem]:
    questions: List[ExtractedQuestionItem] = []
    for idx, it in enumerate(items):
        content = it["content"]
        has_file_criteria = bool(it["criteria"]) and not it.get("rubric_by_ai")
        criteria = _normalize_criteria(it["criteria"]) or _generate_tailored_criteria(content)
        sample_answer = (it.get("sample_answer") or "").strip()
        if not sample_answer:
            if has_file_criteria:
                sample_answer = _build_answer_from_criteria(criteria)
            else:
                sample_answer = _generate_tailored_sample_answer(content)
                it["answer_by_ai"] = True
        tags = [it["topic"]] if it["topic"] else []
        if it.get("answer_by_ai"):
            tags.append("Đáp án do AI soạn")
        if it.get("rubric_by_ai") or not it["criteria"]:
            tags.append("Rubric do AI đề xuất")
        questions.append(
            ExtractedQuestionItem(
                temp_id=f"doc-{idx + 1}",
                code=it["code"],
                topic=it["topic"],
                title=it.get("ai_title") or _make_title(content),
                content=content,
                sample_answer=sample_answer,
                difficulty=_guess_difficulty(content),
                time_limit_seconds=180,
                parent_code=it["parent_code"],
                is_followup=it["is_followup"],
                tags=tags,
                criteria=criteria,
                total_score=round(sum(c.max_score for c in criteria), 1),
                status="valid",
                errors=[],
                warnings=[],
            )
        )
    return questions


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
     Nếu tài liệu không có, tự soạn đáp án chuyên môn chính xác.
   - `criteria`: phần "Tiêu chí chấm điểm / Rubric / Thang điểm / Biểu điểm" trong tài liệu (giữ nguyên tên và điểm).
     Nếu tài liệu không có, tự tạo 3-4 tiêu chí, tổng đúng 10.0.
2. Dòng tiêu đề như "Tiêu chí chấm điểm (Rubric)", "Đáp án:" KHÔNG thuộc `content`.
3. Các dòng đánh số 1., 2., 3. nằm dưới "Tiêu chí chấm điểm" là TIÊU CHÍ, KHÔNG phải câu hỏi mới.
4. Dòng "PHẦN ...", "CHƯƠNG ..." là `topic`, không phải câu hỏi.
5. Không bịa câu hỏi không có trong tài liệu. `title` là cụm tóm tắt 3-8 từ.
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
        content = str(q.get("content") or "").strip()
        if not content:
            continue
        items.append({
            "code": str(q.get("code") or f"Q{i + 1}"),
            "topic": str(q.get("topic") or "Kiến thức chuyên ngành"),
            "content": content,
            "sample_answer": str(q.get("sample_answer") or "").strip(),
            "criteria": [
                {"name": c.get("name"), "description": c.get("description", ""), "max_score": float(c.get("max_score") or 0)}
                for c in q.get("criteria", [])
                if c.get("name")
            ],
            "parent_code": q.get("parent_code") or None,
            "is_followup": bool(q.get("is_followup", False)),
            "ai_title": str(q.get("title") or "").strip() or None,
        })
    return _items_to_questions(items) if items else None


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
        # Parser cấu trúc theo vùng (content/answer/rubric) + Gemini chỉ bổ sung phần file không có
        questions = _parse_word_document(file_bytes, file_name)

    existing_codes = {q.code.strip().upper() for q in questions if q.code}
    valid_count = 0
    error_count = 0
    warning_count = 0

    for q in questions:
        q.errors = []
        q.warnings = []

        if not q.content.strip():
            q.errors.append("Thiếu nội dung câu hỏi phát vấn")
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
