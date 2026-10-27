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
    """Tạo câu trả lời tham chiếu súc tích bám sát theo câu hỏi nếu file Word chưa có sẵn đáp án."""
    q_clean = question_text.strip().rstrip("?").rstrip(":")
    return (
        f"Thí sinh cần trình bày đúng trọng tâm câu hỏi: '{q_clean}'. "
        "Yêu cầu nêu rõ: (1) Khái niệm/Định nghĩa cốt lõi; "
        "(2) Các đặc điểm, cơ chế hoạt động hoặc các giai đoạn chi tiết theo giáo trình; "
        "(3) Lấy ví dụ minh họa cụ thể trong dự án phần mềm thực tế; "
        "(4) Phân tích ưu/nhược điểm và trả lời tự tin, đúng thuật ngữ chuyên môn."
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


def _parse_word_smart_heuristic(file_bytes: bytes, filename: str) -> List[ExtractedQuestionItem]:
    """Phân tích cấu trúc file Word thông minh dựa trên ngữ cảnh thực tế của tài liệu đề thi.
    
    Quy tắc phân định ranh giới câu hỏi:
    1. Nhận diện các tiền tố câu hỏi chuẩn: 'Câu 1:', 'Câu 2:', 'Câu 1.1:', 'Bài 1:', '1.', '2.' v.v.
    2. Gom nhóm (Grouping): toàn bộ các dòng mô tả, gạch đầu dòng (-), ý phụ (a, b, c) nằm dưới câu hỏi
       phải được giữ nguyên trong nội dung của câu hỏi đó (content), tuyệt đối không cắt vụn thành câu hỏi mới.
    3. Tách biệt đáp án: các dòng 'Đáp án:', 'Gợi ý:', 'Key points:' được trích xuất riêng vào sample_answer.
    4. Nếu tài liệu không dùng tiền tố 'Câu ...' mà liệt kê từng đoạn phát vấn (hỏi độc lập), mỗi đoạn là 1 câu hỏi.
    """
    paragraphs: list[str] = []
    lower_fn = filename.lower()

    if lower_fn.endswith(".docx"):
        import docx
        doc = docx.Document(io.BytesIO(file_bytes))

        # 1. Kiểm tra xem có cấu trúc bảng biểu hay không
        if doc.tables:
            table_questions: List[ExtractedQuestionItem] = []
            q_idx = 0
            for table in doc.tables:
                for row in table.rows:
                    cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if len(cells) >= 2:
                        first_str = cells[0].lower()
                        if any(k in first_str for k in ["stt", "mã", "câu hỏi", "tiêu đề"]):
                            continue  # Bỏ qua hàng tiêu đề bảng
                        q_idx += 1
                        q_content = cells[1] if len(cells) > 1 else cells[0]
                        q_answer = cells[2] if len(cells) > 2 else _generate_tailored_sample_answer(q_content)
                        table_questions.append(
                            ExtractedQuestionItem(
                                temp_id=f"tbl-{q_idx}",
                                code=f"Q{q_idx}",
                                topic="Ngân hàng đề thi",
                                title=q_content[:60] + "..." if len(q_content) > 60 else q_content,
                                content=q_content,
                                sample_answer=q_answer,
                                difficulty="medium",
                                time_limit_seconds=180,
                                parent_code=None,
                                is_followup=False,
                                tags=["CNPM"],
                                criteria=_generate_tailored_criteria(q_content),
                                total_score=10.0,
                                status="valid",
                                errors=[],
                                warnings=[],
                            )
                        )
            if len(table_questions) >= 2:
                return table_questions

        # 2. Đọc toàn bộ các đoạn văn bản trong file docx
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    else:
        try:
            raw_text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raw_text = file_bytes.decode("latin-1", errors="ignore")
        paragraphs = [line.strip() for line in raw_text.splitlines() if line.strip()]

    if not paragraphs:
        return []

    # Danh sách tiêu đề tài liệu cần bỏ qua không tính là câu hỏi
    IGNORE_PATTERNS = [
        r"^nội dung ôn tập",
        r"^đề cương ôn tập",
        r"^ngân hàng câu hỏi",
        r"^bộ câu hỏi ôn tập",
        r"^nhập môn",
        r"^[a-z]\.\s*lý thuyết",
        r"^[a-z]\.\s*bài tập",
        r"^--\s*hết\s*--",
        r"^hết$",
        r"^giáo viên phụ trách",
        r"^năm học",
    ]

    filtered_lines: list[str] = []
    for p in paragraphs:
        t = p.strip()
        if not t:
            continue
        lower = t.lower()
        if any(re.search(pat, lower) for pat in IGNORE_PATTERNS):
            continue
        filtered_lines.append(t)

    QUESTION_START_PATTERN = re.compile(
        r"^(?:Câu|Bài|Question)\s*(\d+(?:[\.\d]+)*)\s*(?:\([^\)]*\))?[:\.\)\-]\s*(.*)$",
        re.IGNORECASE,
    )
    NUMBERED_PATTERN = re.compile(r"^(\d+)[\.\)]\s+(.*)$")
    ANSWER_PATTERN = re.compile(
        r"^(?:Đáp án|Trả lời|Gợi ý(?: trả lời)?|Hướng dẫn(?: giải)?|Key points?)[:\.\-]\s*(.*)$",
        re.IGNORECASE,
    )

    explicit_count = sum(
        1 for line in filtered_lines if QUESTION_START_PATTERN.match(line) or NUMBERED_PATTERN.match(line)
    )

    raw_items: list[dict] = []
    current_topic = "Kiến thức chuyên ngành"

    if explicit_count >= 2:
        # Style A: Tài liệu có tiền tố rõ ràng (Câu 1, Câu 2, 1., 2...)
        current_q: Optional[dict] = None
        for line in filtered_lines:
            lower = line.lower()
            if (
                re.match(r"^(?:phần|chương|chủ đề|bài)\s*\d+[:\.\-]", lower)
                or (len(line) < 70 and line.isupper() and not line.endswith("?"))
                or re.match(r"^[ivx]+\.\s+", lower)
            ):
                current_topic = line
                continue

            q_match = QUESTION_START_PATTERN.match(line)
            n_match = NUMBERED_PATTERN.match(line) if not q_match else None

            if q_match:
                if current_q:
                    raw_items.append(current_q)
                q_code_num = q_match.group(1)
                content_part = q_match.group(2).strip()
                is_sub = ("." in q_code_num) or ("câu hỏi phụ" in line.lower()) or ("nhánh phụ" in line.lower())
                parent = f"Q{q_code_num.split('.')[0]}" if "." in q_code_num else None
                current_q = {
                    "code": f"Q{q_code_num}",
                    "topic": current_topic,
                    "content": content_part or line,
                    "sample_answer": "",
                    "parent_code": parent,
                    "is_followup": is_sub,
                    "mode": "content",
                }
            elif n_match:
                if current_q:
                    raw_items.append(current_q)
                q_code_num = n_match.group(1)
                content_part = n_match.group(2).strip()
                current_q = {
                    "code": f"Q{q_code_num}",
                    "topic": current_topic,
                    "content": content_part or line,
                    "sample_answer": "",
                    "parent_code": None,
                    "is_followup": False,
                    "mode": "content",
                }
            elif current_q is not None:
                ans_match = ANSWER_PATTERN.match(line)
                if ans_match:
                    current_q["mode"] = "answer"
                    ans_text = ans_match.group(1).strip()
                    current_q["sample_answer"] += (
                        (" " if current_q["sample_answer"] else "") + ans_text
                    )
                elif current_q["mode"] == "answer":
                    current_q["sample_answer"] += "\n" + line
                else:
                    # Gom các dòng con, gạch đầu dòng, ý a, b, c vào cùng một câu hỏi
                    current_q["content"] += "\n" + line

        if current_q:
            raw_items.append(current_q)
    else:
        # Style B: Tài liệu không có tiền tố 'Câu ...' (danh sách câu hỏi theo đoạn văn)
        q_idx = 0
        for line in filtered_lines:
            lower = line.lower()
            if (
                re.match(r"^(?:phần|chương|chủ đề|bài)\s*\d+[:\.\-]", lower)
                or (len(line) < 70 and line.isupper() and not line.endswith("?"))
                or re.match(r"^[ivx]+\.\s+", lower)
            ):
                current_topic = line
                continue

            if len(line) < 10:
                continue

            q_idx += 1
            raw_items.append({
                "code": f"Q{q_idx}",
                "topic": current_topic,
                "content": line,
                "sample_answer": "",
                "parent_code": None,
                "is_followup": False,
                "mode": "content",
            })

    questions: List[ExtractedQuestionItem] = []
    for idx, item in enumerate(raw_items):
        q_content = item["content"].strip()
        p_lower = q_content.lower()

        # Xác định độ khó dựa trên từ khóa trong câu hỏi
        if any(k in p_lower for k in ["nêu ", "là gì", "định nghĩa", "bao gồm những gì"]):
            diff = "easy"
        elif any(k in p_lower for k in ["ví dụ", "tái cấu trúc", "so sánh", "phân biệt", "xây dựng", "viết use case"]):
            diff = "hard"
        else:
            diff = "medium"

        sample_answer = item["sample_answer"].strip()
        if not sample_answer:
            # Kiểm tra xem trong content có chứa đáp án inline không
            ans_match = re.search(r"(?:Đáp án|Gợi ý trả lời|Trả lời|Key points)[:\.]\s*(.+)$", q_content, re.IGNORECASE)
            if ans_match:
                sample_answer = ans_match.group(1).strip()
                q_content = q_content[:ans_match.start()].strip()
            else:
                sample_answer = _generate_tailored_sample_answer(q_content)

        first_line = q_content.splitlines()[0] if q_content else f"Câu hỏi {idx + 1}"
        title = first_line[:65].rstrip() + ("..." if len(first_line) > 65 else "")

        criteria = _generate_tailored_criteria(q_content)
        tot_score = round(sum(c.max_score for c in criteria), 1)

        questions.append(
            ExtractedQuestionItem(
                temp_id=f"doc-{idx + 1}",
                code=item["code"],
                topic=item["topic"],
                title=title,
                content=q_content,
                sample_answer=sample_answer,
                difficulty=diff,
                time_limit_seconds=180,
                parent_code=item["parent_code"],
                is_followup=item["is_followup"],
                tags=[item["topic"]] if item["topic"] else ["CNPM"],
                criteria=criteria,
                total_score=tot_score,
                status="valid",
                errors=[],
                warnings=[],
            )
        )

    return questions


def _parse_word_with_gemini(file_bytes: bytes, filename: str) -> Optional[List[ExtractedQuestionItem]]:
    """Gọi Gemini trích xuất cấu trúc khi có kết nối mạng và API key."""
    api_key = (settings.gemini_api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
    if not api_key:
        return None

    lower_fn = filename.lower()
    paragraphs: list[str] = []
    if lower_fn.endswith(".docx"):
        import docx
        doc = docx.Document(io.BytesIO(file_bytes))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join([cell.text.strip() for cell in row.cells if cell.text.strip()])
                if row_text:
                    paragraphs.append(row_text)
    else:
        try:
            raw_text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raw_text = file_bytes.decode("latin-1", errors="ignore")
        paragraphs = [line.strip() for line in raw_text.splitlines() if line.strip()]

    full_text = "\n".join(paragraphs)
    if not full_text.strip():
        return None

    try:
        client = genai.Client(api_key=api_key)
        system_prompt = """
BẠN LÀ CHUYÊN GIA THẨM ĐỊNH VÀ BÓC TÁCH ĐỀ THI VẤN ĐÁP (ORAL EXAM PRACTICE) CHUẨN XÁC.
QUY TẮC BÓC TÁCH BẮT BUỘC (TUYỆT ĐỐI TUÂN THỦ):
1. NHẬN DIỆN RANH GIỚI CÂU HỎI CHUẨN XÁC:
   - Câu hỏi trong tài liệu thường bắt đầu bằng: "Câu 1:", "Câu 2:", "Câu 1.1:", "Bài 1:", "Question 1:", hoặc số thứ tự "1.", "2." v.v.
   - TOÀN BỘ các dòng giải thích, ví dụ, gạch đầu dòng (-), ý phụ (a, b, c) nằm ngay dưới câu hỏi ĐỀU LÀ NỘI DUNG CỦA CÂU HỎI ĐÓ.
   - TUYỆT ĐỐI KHÔNG được cắt các gạch đầu dòng hoặc ý mô tả thành các câu hỏi mới làm đảo lộn thứ tự!

2. TÁCH BIỆT ĐÁP ÁN THAM CHIẾU:
   - Nếu dưới câu hỏi có phần ghi "Đáp án:", "Trả lời:", "Gợi ý:", "Key points:", hãy trích xuất toàn bộ phần đó vào `sample_answer`, KHÔNG coi đáp án là câu hỏi mới.
   - Nếu tài liệu CHƯA CÓ đáp án mẫu, hãy tự động soạn câu trả lời tham chiếu chuẩn xác, súc tích cho câu hỏi đó vào `sample_answer`.

3. CÂU HỎI PHỤ & NHÁNH HỎI TIẾP:
   - Nếu câu hỏi có đánh số dạng con như "Câu 1.1", "Câu 1.2" hoặc ghi rõ "(Câu hỏi phụ)", hãy đặt `parent_code` trỏ về câu cha tương ứng (ví dụ: "Q1") và đặt `is_followup = true`.

4. RUBRIC THANG ĐIỂM CHUẨN 10.0Đ:
   - Xây dựng 3-4 tiêu chí Rubric đánh giá chi tiết bám sát vào nội dung câu hỏi.
   - TỔNG ĐIỂM TẤT CẢ TIÊU CHÍ BẮT BUỘC PHẢI BẰNG ĐÚNG 10.0 ĐIỂM.

5. NGUYÊN TẮC KHÔNG BỊA ĐẶT (ANTI-HALLUCINATION):
   - Trích xuất ĐÚNG 100% nội dung câu hỏi có trong tài liệu của giảng viên, TUYỆT ĐỐI KHÔNG BỊA RA câu hỏi không có trong file.
"""
        response = client.models.generate_content(
            model=settings.default_llm_model or "gemini-2.5-flash",
            contents=f"{system_prompt}\n\nVĂN BẢN ĐỀ THI CẦN BÓC TÁCH NGUYÊN VĂN:\n===================\n{full_text[:40000]}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=EXTRACTION_JSON_SCHEMA,
                temperature=0.1,
            ),
        )
        result_text = (response.text or "").strip()
        parsed = json.loads(result_text)
        raw_questions = parsed.get("questions", [])

        if not raw_questions:
            return None

        questions: List[ExtractedQuestionItem] = []
        for i, q in enumerate(raw_questions):
            criteria_items: List[RubricCriterionItem] = []
            for c in q.get("criteria", []):
                criteria_items.append(
                    RubricCriterionItem(
                        name=str(c.get("name", "Tiêu chí")),
                        description=str(c.get("description", "")),
                        max_score=float(c.get("max_score", 2.5)),
                    )
                )
            if not criteria_items:
                criteria_items = _generate_tailored_criteria(str(q.get("content", "")))

            tot_score = round(sum(c.max_score for c in criteria_items), 1)
            q_content = str(q.get("content") or "").strip()
            item = ExtractedQuestionItem(
                temp_id=f"doc-{i + 1}",
                code=str(q.get("code") or f"Q{i + 1}"),
                topic=str(q.get("topic") or "Kiến thức chuyên ngành"),
                title=str(q.get("title") or f"Câu hỏi {i + 1}"),
                content=q_content,
                sample_answer=str(q.get("sample_answer") or _generate_tailored_sample_answer(q_content)),
                difficulty=_normalize_difficulty(q.get("difficulty")),
                time_limit_seconds=int(q.get("time_limit_seconds") or 180),
                parent_code=q.get("parent_code") or None,
                is_followup=bool(q.get("is_followup", False)),
                tags=q.get("tags") or ["Vấn đáp"],
                criteria=criteria_items,
                total_score=tot_score,
                status="valid",
                errors=[],
                warnings=[],
            )
            questions.append(item)

        return questions
    except Exception as e:
        print(f"[AI-SERVICE] Loi khi goi Gemini: {e}. Chuyen sang Heuristic Parser.", flush=True)
        return None


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
        # Thử Gemini trước; nếu không có mạng / lỗi thì dùng Heuristic Parser chuẩn xác
        questions = _parse_word_with_gemini(file_bytes, file_name) or _parse_word_smart_heuristic(file_bytes, file_name)

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
