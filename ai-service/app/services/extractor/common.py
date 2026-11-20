"""Module tiện ích dùng chung cho phân hệ bóc tách ngân hàng câu hỏi & Rubric.

Nhiệm vụ:
- Làm sạch văn bản chứa thẻ HTML (`_clean_html_to_text`): chuyển `<ul>/<li>`, `<p>`, `<br>`, `&nbsp;` sang văn bản thuần có gạch đầu dòng mà vẫn giữ nguyên các biểu thức toán học (`n < 10`).
- Trích xuất và chuẩn hóa thang điểm (`_extract_score`, `_strip_score`, `_make_criterion`): hỗ trợ điểm số (`3đ`, `2.5 điểm`), phần trăm (`30%` quy đổi thang 10) và tiêu chí cha-con (`_reconcile_parent_child_criteria`, `_normalize_criteria`).
- Sinh dữ liệu mặc định học thuật khi tài liệu gốc thiếu (`_generate_tailored_criteria`, `_generate_tailored_sample_answer`, `_build_answer_from_criteria`, `_make_title`, `_guess_difficulty`).
- Chuyển đổi danh sách mục thô sang schema đầu ra `ExtractedQuestionItem` (`_items_to_questions`).
"""

import html
import re
from typing import Any, List, Optional

from app.schemas.question_import_schema import (
    ExtractedQuestionItem,
    RubricCriterionItem,
)

_HTML_TAG_CHECK_RE = re.compile(r"</?[a-zA-Z][a-zA-Z0-9:-]*(?:\s+[^>]*)?/?>")
_HTML_LI_OPEN_RE = re.compile(r"<li\b[^>]*>", re.IGNORECASE)
_HTML_BLOCK_BREAK_RE = re.compile(
    r"</?(?:ul|ol|p|div|section|article|blockquote|tr|h[1-6])\b[^>]*>|<br\s*/?>",
    re.IGNORECASE,
)
_HTML_TD_CLOSE_RE = re.compile(r"</t[dh]\s*>", re.IGNORECASE)

_BULLET_RE = re.compile(r"^\s*(?:[-–—•●○◦▪■□+*➢➤►✓✔]|\(?[a-zA-Zđ]\)|[a-zA-Zđ][\.\)](?=\s))\s*")
_ENUM_PREFIX_RE = re.compile(r"^\s*(?:\(?\d{1,2}[\.\)]|\(?[a-zA-Zđ][\.\)]|[-–—•●○◦▪■□+*➢➤►✓✔])\s*")
_SUB_NUMBERED_RE = re.compile(r"^(\d{1,3}(?:\.\d{1,3})+)\s*[\.\)]?\s+(.+)$")

_SCORE_RE = re.compile(
    r"(?<![\w.,])(\d{1,2}(?:[.,]\d{1,2})?)\s*(?:điểm|diem|đ|pts?|points?|/10\b)(?!\w)",
    re.IGNORECASE,
)
_PERCENT_SCORE_RE = re.compile(r"(?<![\w.,])(\d{1,3}(?:[.,]\d{1,2})?)\s*%")
_TRAILING_SCORE_RE = re.compile(r"[:\-–|]\s*(\d{1,2}(?:[.,]\d{1,2})?)\s*$")


def _clean_html_to_text(raw: Any) -> str:
    """Chuyển chuỗi có thẻ HTML (<ul>, <li>, <p>, <br>...) thành văn bản thuần có xuống dòng."""
    if raw is None:
        return ""
    text = html.unescape(str(raw)).replace("\xa0", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if _HTML_TAG_CHECK_RE.search(text):
        text = _HTML_LI_OPEN_RE.sub("\n- ", text)
        text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)
        text = _HTML_BLOCK_BREAK_RE.sub("\n", text)
        text = _HTML_TD_CLOSE_RE.sub(" ", text)
        text = _HTML_TAG_CHECK_RE.sub("", text)
        text = re.sub(r"\n{2,}", "\n", text)

    cleaned_lines: list[str] = []
    prev_blank = False
    for line in text.split("\n"):
        line_norm = re.sub(r"[ \t]{2,}", " ", line).strip()
        line_norm = re.sub(r"^-\s*[-•●◦▪➢➤►]+\s*", "- ", line_norm)
        if line_norm == "-":
            continue
        if not line_norm:
            if cleaned_lines and not prev_blank:
                cleaned_lines.append("")
                prev_blank = True
            continue
        cleaned_lines.append(line_norm)
        prev_blank = False

    return "\n".join(cleaned_lines).strip()


def _to_float(raw: str) -> float:
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        return 0.0


def _normalize_difficulty(val: Any) -> str:
    s = str(val or "").strip().lower()
    if any(k in s for k in ["dễ", "de", "easy", "cơ bản", "co ban", "1"]):
        return "easy"
    if any(k in s for k in ["khó", "kho", "hard", "nâng cao", "nang cao", "3"]):
        return "hard"
    return "medium"


def _extract_score(text: str) -> Optional[float]:
    matches = list(_SCORE_RE.finditer(text))
    if matches:
        return _to_float(matches[-1].group(1))
    pct_matches = list(_PERCENT_SCORE_RE.finditer(text))
    if pct_matches:
        pct = _to_float(pct_matches[-1].group(1))
        if 0 < pct <= 100:
            return round(pct / 10.0, 2)
    m = _TRAILING_SCORE_RE.search(text)
    if m:
        return _to_float(m.group(1))
    return None


def _strip_score(text: str) -> str:
    cleaned = _SCORE_RE.sub("", text)
    cleaned = _PERCENT_SCORE_RE.sub("", cleaned)
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


def _reconcile_parent_child_criteria(raw_criteria: list[dict]) -> list[dict]:
    """Làm phẳng tiêu chí cha - con và tự động phát hiện tiêu chí cha khi tổng điểm các ý con kế tiếp bằng điểm cha."""
    flattened: list[dict] = []
    for c in raw_criteria:
        if c.get("children"):
            flattened.extend(c["children"])
        else:
            flattened.append(dict(c))

    scored = [c.get("max_score") for c in flattened]
    total = sum(s for s in scored if s is not None and s > 0)
    if total <= 10.05 or len(flattened) < 3:
        return flattened

    reconciled: list[dict] = []
    i = 0
    n = len(flattened)
    while i < n:
        parent = flattened[i]
        p_score = parent.get("max_score")
        if p_score and p_score > 0 and not str(parent.get("name", "")).startswith("["):
            sub_sum = 0.0
            j = i + 1
            matched_end = -1
            while j < n:
                s_j = flattened[j].get("max_score")
                if not s_j or s_j <= 0 or s_j >= p_score:
                    break
                sub_sum = round(sub_sum + float(s_j), 2)
                if abs(sub_sum - float(p_score)) <= 0.05 and (j - i) >= 2:
                    matched_end = j
                    break
                if sub_sum > float(p_score) + 0.05:
                    break
                j += 1
            if matched_end != -1:
                p_name = parent["name"]
                for k in range(i + 1, matched_end + 1):
                    child = dict(flattened[k])
                    if not str(child.get("name", "")).startswith("["):
                        child["name"] = f"[{p_name}] {child['name']}"
                    reconciled.append(child)
                i = matched_end + 1
                continue
        reconciled.append(parent)
        i += 1
    return reconciled


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
        c_name = _clean_html_to_text(c.get("name") or "Tiêu chí") or "Tiêu chí"
        c_desc = _clean_html_to_text(c.get("description") or c_name) or c_name
        result.append(
            RubricCriterionItem(
                name=c_name[:150],
                description=c_desc,
                max_score=round(sc, 2),
            )
        )
    return result


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
    if "quy trình" in q_lower or "mô hình" in q_lower or "giai đoạn" in q_lower or "hoạt động" in q_lower:
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
    if "ví dụ" in q_lower or "tái cấu trúc" in q_lower or "bài tập" in q_lower or "thiết kế" in q_lower:
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
        content = _clean_html_to_text(it["content"])
        has_file_criteria = bool(it["criteria"]) and not it.get("rubric_by_ai")
        criteria = _normalize_criteria(it["criteria"]) or _generate_tailored_criteria(content)
        sample_answer = _clean_html_to_text(it.get("sample_answer") or "")
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
