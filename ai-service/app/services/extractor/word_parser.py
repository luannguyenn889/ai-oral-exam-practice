"""Module bóc tách cấu trúc theo vùng (State Machine) cho đề thi Word (.docx) và Text (.txt)."""

from __future__ import annotations

import re
from typing import Optional

from app.services.extractor.common import (
    _BULLET_RE,
    _ENUM_PREFIX_RE,
    _SCORE_RE,
    _SUB_NUMBERED_RE,
    _extract_score,
    _make_criterion,
    _reconcile_parent_child_criteria,
)
from app.services.extractor.word_blocks import (
    _blocks_to_text,
    _detect_word_list_info,
    _read_document_blocks,
)
from app.services.extractor.word_table_parser import parse_table_block

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


def _new_item(
    code: Optional[str],
    topic: str,
    content: str,
    parent: Optional[str] = None,
    is_followup: bool = False,
) -> dict:
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


def _append_criterion_line(
    current: dict,
    text: str,
    is_list: bool = False,
    list_kind: Optional[str] = None,
    list_level: int = 0,
) -> None:
    score = _extract_score(text)
    text_s = text.strip()
    is_sub_num = bool(_SUB_NUMBERED_RE.match(text_s))
    is_explicit_bullet = bool(_BULLET_RE.match(text_s))
    is_explicit_major = bool(_NUMBERED_RE.match(text_s)) and not is_sub_num

    is_major_num = is_explicit_major or (
        is_list and list_kind == "ordered" and list_level == 0 and not is_explicit_bullet and not is_sub_num
    )
    is_child_item = (
        is_sub_num
        or is_explicit_bullet
        or (is_list and (list_kind == "bullet" or list_level >= 1))
    )

    if is_major_num:
        m = _NUMBERED_RE.match(text_s)
        body = m.group(2).strip() if m else text_s
        crit = _make_criterion(body, score)
        if crit:
            crit["is_parent"] = True
            crit["children"] = []
            current["criteria"].append(crit)
        return

    if is_child_item and current["criteria"]:
        last_parent = next((c for c in reversed(current["criteria"]) if c.get("is_parent")), None)
        crit = _make_criterion(text_s, score)
        if crit:
            if last_parent:
                crit["name"] = f"[{last_parent['name']}] {crit['name']}"
                crit["is_child"] = True
                last_parent["children"].append(crit)
            else:
                current["criteria"].append(crit)
        return

    if score is None and current["criteria"] and not is_child_item and not is_major_num:
        target = current["criteria"][-1]
        if target.get("children"):
            target = target["children"][-1]
        target["description"] = (target["description"] + " " + text_s).strip()
        return

    crit = _make_criterion(text_s, score)
    if crit:
        current["criteria"].append(crit)


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

    for block in blocks:
        if block["type"] == "table":
            parse_table_block(block["rows"], current, current_topic, _new_item, start)
            continue

        text = block["text"]
        lower = text.lower()
        if any(re.search(p, lower) for p in _IGNORE_LINE_PATTERNS):
            continue

        if _is_topic_line(text) or _SECTION_RE.match(text) and len(text) < 60 and not _looks_like_question(text):
            if _SECTION_RE.match(text) and not _TOPIC_RE.match(text) and not text.isupper():
                if current is not None:
                    items.append(current)
                    current = None
                continue
            if current is not None:
                items.append(current)
                current = None
            current_topic = text
            continue

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

        r_match = _RUBRIC_HEADER_RE.match(text) if "?" not in text else None
        if r_match and current is not None and (_extract_score(text) is None or not r_match.group(1)):
            rest = r_match.group(1).strip()
            prefix_part = text[: len(text) - len(rest)] if rest else text
            if not rest or re.search(r"[:\.\-–\)]", prefix_part) or _extract_score(rest) is not None:
                current["mode"] = "rubric"
                if rest and _extract_score(rest) is not None:
                    _append_criterion_line(current, rest)
                continue
        if r_match and current is not None and current["mode"] in ("content", "answer") and _extract_score(text) is not None:
            current["mode"] = "rubric"
            _append_criterion_line(current, text)
            continue

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
                    _append_criterion_line(
                        current,
                        text,
                        is_list=bool(block.get("is_list")),
                        list_kind=block.get("list_kind"),
                        list_level=int(block.get("list_level") or 0),
                    )
                else:
                    current["answer_lines"].append(text)
                continue
            start(_new_item(None, current_topic, _ENUM_PREFIX_RE.sub("", text, count=1) if n_match else text))
            continue

        if uses_prefix:
            if current is None:
                continue
            current["content_lines"].append(text)
            continue

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
        it["criteria"] = _reconcile_parent_child_criteria(it["criteria"])
        cleaned.append(it)
    return cleaned


__all__ = [
    "_blocks_to_text",
    "_detect_word_list_info",
    "_read_document_blocks",
    "_structure_parse",
]
