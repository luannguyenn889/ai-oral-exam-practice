"""Module nhận diện cấu trúc tài liệu, chuẩn hóa văn bản PDF và chia khối đệ quy cho phân hệ RAG.

Nhiệm vụ:
- Nhận diện cấp tiêu đề đa dạng (`_detect_heading_level`, `_split_into_sections`, `_format_breadcrumb`)
  và ghép breadcrumb phân cấp dạng `[Chương 2 > 2.1 Mô hình Thác nước]`.
- Chuẩn hóa văn bản trích xuất từ PDF (`_reflow_wrapped_lines`, `_split_sentences`, `_sentence_overlap`, `get_clean_overlap`).
- Chia khối bảng biểu có lặp dòng tiêu đề (`_split_table_with_header`) và tách đệ quy theo cấu trúc (`_recursive_split_piece`).
"""

from __future__ import annotations

import re
from typing import Optional

from app.services.rag.noise_filter import is_allowed_uppercase_heading, is_plausible_heading_line

_HEADING_TOP_EXPLICIT_RE = re.compile(
    r"^(?:chương|phần|chapter|part|unit)\s*(?:[\dIVXLivxl]+|[A-Z])\b.*$",
    re.IGNORECASE,
)
_HEADING_SUB_EXPLICIT_RE = re.compile(
    r"^(?:mục|bài|section)\s*(?:[\dIVXLivxl]+|[A-Z])\b.*$",
    re.IGNORECASE,
)
_HEADING_MULTI_NUMBERED_RE = re.compile(r"^(?:[IVX]{1,4}\.|(?:\d{1,2}\.){1,3}\d{1,2}\.?)\s+\S+")
_HEADING_SINGLE_NUMBERED_RE = re.compile(r"^\d{1,2}\.\s+(.+)$")
_PROSE_START_RE = re.compile(
    r"^(?:it|this|that|there|these|those|when|where|while|if|however|therefore|moreover|because|although|since|for|in|on|at|the|a|an|nếu|khi|vì|tuy|ngoài|đây|đó|nó|họ|chúng)\b",
    re.IGNORECASE,
)
_DANGLING_END_RE = re.compile(
    r"\b(?:of|to|for|with|in|on|at|by|from|and|or|the|a|an|is|are|was|were|that|which|của|và|hoặc|tại|trong|với|cho|là)\s*$",
    re.IGNORECASE,
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.?!…])\s+(?=[A-ZÀ-Ỹ0-9\"'(«\[-])")


def get_clean_overlap(text: str, max_chars: int = 100) -> str:
    """Lấy phần đuôi để overlap nhưng bắt buộc giữ trọn vẹn từ ngữ (không cắt ngang từ)."""
    if not text or len(text) <= max_chars:
        return text
    tail = text[-max_chars:].strip()
    first_space = tail.find(" ")
    if first_space != -1 and first_space < len(tail) - 1:
        cleaned = tail[first_space + 1 :].strip()
        cleaned = cleaned.lstrip(".,:;|-)]} ")
        return cleaned
    return tail


def _detect_heading_level(line: str) -> Optional[int]:
    """Xác định cấp tiêu đề (1..4) tổng quát cho mọi loại tài liệu, trả về None nếu là dòng thường."""
    s = line.strip()
    if not is_plausible_heading_line(s):
        return None

    m_md = re.match(r"^(#{1,4})\s+(.+)$", s)
    if m_md:
        return len(m_md.group(1))

    if _HEADING_TOP_EXPLICIT_RE.match(s):
        return 1
    if _HEADING_SUB_EXPLICIT_RE.match(s):
        return 2

    if _HEADING_MULTI_NUMBERED_RE.match(s) and len(s) <= 95 and not s.endswith("."):
        prefix_token = s.split()[0].rstrip(".")
        if re.fullmatch(r"[IVX]{1,4}", prefix_token):
            return 1
        dot_depth = prefix_token.count(".") + 1
        return min(4, max(2, dot_depth))

    m_single = _HEADING_SINGLE_NUMBERED_RE.match(s)
    if m_single and not s.endswith("."):
        body = m_single.group(1).strip()
        words = body.split()
        if (
            len(s) <= 55
            and len(words) <= 7
            and not _PROSE_START_RE.match(body)
            and not _DANGLING_END_RE.search(body)
        ):
            return 2

    if is_allowed_uppercase_heading(s):
        return 1

    return None


def _is_heading_line(line: str) -> bool:
    return _detect_heading_level(line) is not None


def _format_breadcrumb(heading_stack: list[tuple[int, str]], max_chars: int = 140) -> str:
    """Ghép ngăn xếp tiêu đề thành breadcrumb phân cấp, VD: 'Chương 2 > 2.1 Mô hình Thác nước'."""
    if not heading_stack:
        return ""
    titles = [t for _, t in heading_stack[-3:]]
    crumb = " > ".join(titles)
    while len(crumb) > max_chars and len(titles) > 1:
        titles = titles[1:]
        crumb = " > ".join(titles)
    return crumb[:max_chars].strip()


def _split_into_sections(text: str) -> list[tuple[str, str]]:
    """Tách văn bản thành các vùng (breadcrumb_title, section_body) theo ngăn xếp tiêu đề đa cấp."""
    sections: list[tuple[str, str]] = []
    heading_stack: list[tuple[int, str]] = []
    current_lines: list[str] = []

    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = raw_line.strip()
        if not stripped:
            if current_lines and current_lines[-1] != "":
                current_lines.append("")
            continue
        if re.fullmatch(r"\d{1,4}", stripped):
            continue
        h_level = _detect_heading_level(stripped)
        if h_level is not None:
            body = "\n".join(current_lines).strip()
            if body:
                sections.append((_format_breadcrumb(heading_stack), body))
            clean_title = re.sub(r"^#{1,4}\s*", "", stripped).strip()
            while heading_stack and heading_stack[-1][0] >= h_level:
                heading_stack.pop()
            heading_stack.append((h_level, clean_title))
            current_lines = []
        else:
            current_lines.append(stripped)

    tail_body = "\n".join(current_lines).strip()
    if tail_body:
        sections.append((_format_breadcrumb(heading_stack), tail_body))
    elif heading_stack and not sections:
        crumb = _format_breadcrumb(heading_stack)
        sections.append((crumb, crumb))

    return sections


def _reflow_wrapped_lines(text: str) -> str:
    """Nối các dòng bị ngắt cứng trong PDF thành đoạn văn liền mạch, giữ nguyên cấu trúc bảng và danh sách."""
    if not text:
        return ""
    s = text.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"([A-Za-zÀ-ỹ])-\n([a-zà-ỹ])", r"\1\2", s)

    blocks: list[str] = []
    prose_buf: list[str] = []
    table_buf: list[str] = []
    list_item_re = re.compile(r"^(?:[-•●◦▪*]|\d{1,2}[.)])\s+")

    def flush_prose() -> None:
        if prose_buf:
            blocks.append(" ".join(prose_buf))
            prose_buf.clear()

    def flush_table() -> None:
        if table_buf:
            blocks.append("\n".join(table_buf))
            table_buf.clear()

    for raw_line in s.split("\n"):
        line = raw_line.strip()
        if not line:
            flush_prose()
            flush_table()
            continue
        if line.startswith("|"):
            flush_prose()
            table_buf.append(line)
            continue
        flush_table()
        if list_item_re.match(line):
            flush_prose()
            prose_buf.append(line)
        else:
            prose_buf.append(line)

    flush_prose()
    flush_table()
    return "\n\n".join(blocks)


def _split_sentences(text: str) -> list[str]:
    """Tách văn bản thành các câu hoàn chỉnh (bảo toàn dấu câu và không cắt sau số thứ tự '1.', '2.')."""
    cleaned = re.sub(r"[ \t]+", " ", text).strip()
    if not cleaned:
        return []
    parts = _SENTENCE_SPLIT_RE.split(cleaned)
    merged: list[str] = []
    for p in parts:
        part = p.strip()
        if not part:
            continue
        if merged and re.fullmatch(r"\d{1,2}\.", merged[-1]):
            merged[-1] = f"{merged[-1]} {part}"
        else:
            merged.append(part)
    return merged


def _sentence_overlap(text: str, max_chars: int = 140) -> str:
    """Lấy 1-2 câu hoàn chỉnh ở cuối chunk trước để làm overlap, không cắt ngang câu."""
    sentences = _split_sentences(text)
    if not sentences:
        return ""
    chosen: list[str] = []
    total_len = 0
    for sent in reversed(sentences[-3:]):
        if len(sent) > max_chars:
            if not chosen:
                return get_clean_overlap(sent, max_chars=max_chars)
            break
        if total_len + len(sent) + (1 if chosen else 0) <= max_chars:
            chosen.insert(0, sent)
            total_len += len(sent) + (1 if len(chosen) > 1 else 0)
        else:
            break
    return " ".join(chosen).strip()


def _split_table_with_header(table_block: str, max_chars: int) -> list[str]:
    """Tách bảng dài thành nhiều đoạn nhưng luôn lặp lại dòng tiêu đề cột (row 0) ở đầu mỗi đoạn."""
    rows = [ln.strip() for ln in table_block.split("\n") if ln.strip()]
    if len(rows) <= 2 or len(table_block) <= max_chars:
        return [table_block]

    header_row = rows[0]
    pieces: list[str] = []
    buf_rows: list[str] = [header_row]
    buf_len = len(header_row)

    for row in rows[1:]:
        candidate_len = buf_len + 1 + len(row)
        if candidate_len <= max_chars or len(buf_rows) == 1:
            buf_rows.append(row)
            buf_len = candidate_len
        else:
            pieces.append("\n".join(buf_rows))
            buf_rows = [header_row, row]
            buf_len = len(header_row) + 1 + len(row)

    if len(buf_rows) > 1:
        pieces.append("\n".join(buf_rows))
    return pieces


def _merge_units_recursively(units: list[str], joiner: str, max_chars: int) -> list[str]:
    pieces: list[str] = []
    buf = ""
    for unit in units:
        if len(unit) > max_chars:
            if buf:
                pieces.append(buf)
                buf = ""
            pieces.extend(_recursive_split_piece(unit, max_chars))
            continue
        candidate = f"{buf}{joiner}{unit}" if buf else unit
        if len(candidate) <= max_chars:
            buf = candidate
        else:
            if buf:
                pieces.append(buf)
            buf = unit
    if buf:
        pieces.append(buf)
    return pieces


def _recursive_split_piece(text: str, max_chars: int) -> list[str]:
    """Cắt đệ quy một khối văn bản theo thứ tự ưu tiên: bảng -> đoạn -> dòng -> câu -> mệnh đề -> từ."""
    s = text.strip()
    if not s:
        return []
    if len(s) <= max_chars:
        return [s]

    non_empty_lines = [ln.strip() for ln in s.split("\n") if ln.strip()]
    if len(non_empty_lines) >= 2 and all(ln.startswith("|") for ln in non_empty_lines):
        return _split_table_with_header(s, max_chars)

    for sep in ("\n\n", "\n"):
        if sep in s:
            units = [u.strip() for u in s.split(sep) if u.strip()]
            if len(units) > 1:
                return _merge_units_recursively(units, sep, max_chars)

    sentences = _split_sentences(s)
    if len(sentences) > 1:
        return _merge_units_recursively(sentences, " ", max_chars)

    for sep in ("; ", ", "):
        if sep in s:
            units = [u.strip() for u in s.split(sep) if u.strip()]
            if len(units) > 1:
                return _merge_units_recursively(units, sep, max_chars)

    words = s.split()
    out: list[str] = []
    buf = ""
    for w in words:
        if len(buf) + len(w) + (1 if buf else 0) <= max_chars:
            buf = f"{buf} {w}".strip()
        else:
            if buf:
                out.append(buf)
            buf = w
    if buf:
        out.append(buf)
    return out
