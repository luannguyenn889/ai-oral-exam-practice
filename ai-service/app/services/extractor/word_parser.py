"""Module bóc tách cấu trúc theo vùng (State Machine) cho đề thi Word (.docx) và Text (.txt).

Nhiệm vụ:
- Đọc tài liệu theo đúng thứ tự xuất hiện (`_read_document_blocks`, `_blocks_to_text`):
    + Đọc xen kẽ đoạn văn (kèm TextBox) và bảng biểu, nhận biết cả danh sách đánh số/bullet tự động của Word qua XML `w:numPr` (`_detect_word_list_info`).
- Phân vùng nội dung bằng máy trạng thái (`_structure_parse`):
    + Tách chính xác 3 vùng của mỗi câu hỏi: `content` (câu hỏi phát vấn), `answer` (đáp án tham chiếu) và `rubric` (tiêu chí chấm điểm).
    + Nhận diện chủ đề (`PHẦN`, `CHƯƠNG`), câu hỏi cha/câu hỏi phụ, bảng câu hỏi và bảng Rubric mà không trộn lẫn tiêu đề vùng vào nội dung câu hỏi.
    + Giữ nguyên văn nội dung gốc của giảng viên và làm phẳng tiêu chí phân cấp cha-con.
"""

import io
import re
from typing import Any, Optional

from app.services.extractor.common import (
    _BULLET_RE,
    _ENUM_PREFIX_RE,
    _SCORE_RE,
    _SUB_NUMBERED_RE,
    _clean_html_to_text,
    _extract_score,
    _make_criterion,
    _reconcile_parent_child_criteria,
    _strip_score,
    _to_float,
)

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


def _detect_word_list_info(child: Any, para: Any, doc: Any) -> tuple[bool, Optional[str], int]:
    """Trích xuất thông tin danh sách tự động của Word: (is_list, list_kind, list_level)."""
    ppr = child.pPr
    style_name = (para.style.name or "").lower() if para.style is not None else ""
    is_list = False
    list_kind: Optional[str] = None
    list_level = 0

    if "list" in style_name:
        is_list = True
        if "bullet" in style_name:
            list_kind = "bullet"
        elif "number" in style_name:
            list_kind = "ordered"
        m_lvl = re.search(r"(\d+)$", style_name.strip())
        if m_lvl:
            list_level = max(0, int(m_lvl.group(1)) - 1)

    if ppr is not None and ppr.numPr is not None:
        is_list = True
        ilvl_el = getattr(ppr.numPr, "ilvl", None)
        if ilvl_el is not None and getattr(ilvl_el, "val", None) is not None:
            try:
                list_level = int(ilvl_el.val)
            except (TypeError, ValueError):
                pass
        num_id_el = getattr(ppr.numPr, "numId", None)
        num_id = getattr(num_id_el, "val", None) if num_id_el is not None else None
        if num_id is not None and list_kind is None:
            try:
                numbering = doc.part.numbering_part.element
                abs_id = None
                for num in numbering.findall(".//{*}num"):
                    if num.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}numId") == str(num_id):
                        abs_el = num.find("{*}abstractNumId")
                        if abs_el is not None:
                            abs_id = abs_el.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val")
                        break
                if abs_id is not None:
                    for abs_num in numbering.findall(".//{*}abstractNum"):
                        if abs_num.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}abstractNumId") == str(abs_id):
                            for lvl in abs_num.findall("{*}lvl"):
                                if lvl.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}ilvl") == str(list_level):
                                    fmt_el = lvl.find("{*}numFmt")
                                    fmt_val = fmt_el.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val") if fmt_el is not None else ""
                                    if fmt_val == "bullet":
                                        list_kind = "bullet"
                                    elif fmt_val in ("lowerLetter", "upperLetter", "lowerRoman"):
                                        list_kind = "bullet"
                                        list_level = max(1, list_level)
                                    else:
                                        list_kind = "ordered"
                                    break
                            break
            except Exception:
                pass
        if list_kind is None:
            list_kind = "bullet" if list_level >= 1 else "ordered"

    return is_list, list_kind, list_level


def _read_document_blocks(file_bytes: bytes, filename: str) -> list[dict]:
    """Đọc tài liệu theo đúng thứ tự: [{'type':'line','text','is_list','list_kind','list_level'} | {'type':'table','rows'}]."""
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
                is_list, list_kind, list_level = _detect_word_list_info(child, para, doc)
                raw_para_text = para.text or ""
                if not raw_para_text.strip():
                    txbx_texts = [
                        "".join(p_el.itertext()).strip()
                        for p_el in child.findall(".//{*}txbxContent//{*}p")
                    ]
                    raw_para_text = "\n".join(t for t in txbx_texts if t)
                raw_para_text = _clean_html_to_text(raw_para_text)
                for part in raw_para_text.split("\n"):
                    text = re.sub(r"[ \t]+", " ", part).strip()
                    if text:
                        blocks.append({
                            "type": "line",
                            "text": text,
                            "is_list": is_list,
                            "list_kind": list_kind,
                            "list_level": list_level,
                        })
            elif tag == "tbl":
                table = Table(child, doc)
                rows: list[list[str]] = []
                for row in table.rows:
                    cells: list[str] = []
                    prev_tc = None
                    for cell in row.cells:
                        if cell._tc is prev_tc:
                            continue
                        prev_tc = cell._tc
                        cells.append(_clean_html_to_text(cell.text or ""))
                    if any(cells):
                        rows.append(cells)
                if rows:
                    blocks.append({"type": "table", "rows": rows})
    else:
        try:
            raw_text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raw_text = file_bytes.decode("latin-1", errors="ignore")
        raw_text = _clean_html_to_text(raw_text)
        for line in raw_text.splitlines():
            text = re.sub(r"[ \t]+", " ", line).strip()
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

    def add_criterion_line(
        text: str,
        is_list: bool = False,
        list_kind: Optional[str] = None,
        list_level: int = 0,
    ) -> None:
        assert current is not None
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

        if score is None and current["criteria"] and not is_child_item and not is_major_num:
            target = current["criteria"][-1]
            if target.get("children"):
                target = target["children"][-1]
            target["description"] = (target["description"] + " " + text_s).strip()
            return

        crit = _make_criterion(text_s, score)
        if crit:
            current["criteria"].append(crit)

    for block in blocks:
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
                        continue
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

            for row in rows:
                text = " | ".join(c for c in row if c)
                if current is None:
                    continue
                if current["mode"] == "answer":
                    current["answer_lines"].append(text)
                elif current["mode"] == "content":
                    current["content_lines"].append(text)
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
                    add_criterion_line(rest)
                continue
        if r_match and current is not None and current["mode"] in ("content", "answer") and _extract_score(text) is not None:
            current["mode"] = "rubric"
            add_criterion_line(text)
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
                    add_criterion_line(
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
