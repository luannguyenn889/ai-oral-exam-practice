"""Module phân đoạn văn bản (Chunking) hỗ trợ đa chiến lược cho hệ thống RAG.

Nhiệm vụ:
- Nhận diện cấu trúc tài liệu tổng quát (`_detect_heading_level`, `_split_into_sections`, `_format_breadcrumb`):
    + Xây dựng ngăn xếp tiêu đề đa cấp (1..4) cho nhiều loại tài liệu (Markdown/Word Heading, Chương/Phần/Mục, đánh số phân cấp 2.1/2.1.1, số La Mã, tiêu đề ngắn).
    + Gắn ngữ cảnh phân cấp dạng `[Chương 2 > 2.1 Mô hình Thác nước]` vào đầu mỗi đoạn.
- Chuẩn hóa dòng PDF & bảo toàn bảng biểu (`_reflow_wrapped_lines`, `_split_sentences`, `_split_table_with_header`):
    + Nối từ bị gạch nối qua dòng và nối các dòng bị ngắt cứng trong PDF; không tách câu sau số thứ tự (`1.`, `2.`).
    + Giữ tách biệt khối bảng biểu và tự động lặp lại dòng tiêu đề cột khi bảng dài phải chia nhiều đoạn.
- Cung cấp 3 chiến lược chia đoạn qua hàm điều phối `chunk_text`:
    + `recursive` (mặc định): Heading-aware Recursive Chunking (750 ký tự, gối đầu 1-2 câu hoàn chỉnh qua `_sentence_overlap`).
    + `semantic`: Kết hợp Heading-aware với Cosine Similarity giữa embedding các câu liên tiếp để tách tại điểm chuyển chủ đề.
    + `legacy`: Giữ nguyên Boundary-Preserved Chunking (600 ký tự, overlap 100 ký tự) phục vụ đối chứng thực nghiệm.
"""

import math
import re
import sys
from typing import Any, Callable, Optional

from app.services.rag.embeddings import embed_texts as _embed_texts_impl
from app.services.rag.embeddings import normalize_course_id
from app.services.rag.noise_filter import (
    apply_chunk_context_smoothing as _apply_chunk_context_smoothing,
    compute_noise_profile,
    is_allowed_uppercase_heading,
    is_low_value_rag_chunk,
    is_low_value_section_title as _is_low_value_section_title,
    is_plausible_heading_line,
)

CHUNKING_STRATEGIES = ("recursive", "semantic", "legacy")
DEFAULT_CHUNKING_STRATEGY = "recursive"
CHUNKING_VERSION = "v4"

CHUNKING_STRATEGY_LABELS = {
    "recursive": "Heading-aware Recursive Chunking (750 chars, sentence overlap)",
    "semantic": "Semantic Chunking (Cosine Similarity topic-shift + Heading-aware)",
    "legacy": "Boundary-Preserved Chunking (Cách cũ: 600 chars, 100 overlap)",
}

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


def normalize_chunking_strategy(strategy: Optional[str]) -> str:
    s = (strategy or "").strip().lower()
    if s in CHUNKING_STRATEGIES:
        return s
    return DEFAULT_CHUNKING_STRATEGY


def get_chunking_strategy_label(strategy: Optional[str]) -> str:
    norm = normalize_chunking_strategy(strategy)
    return CHUNKING_STRATEGY_LABELS.get(norm, CHUNKING_STRATEGY_LABELS[DEFAULT_CHUNKING_STRATEGY])


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


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _resolve_embed_fn() -> Callable[..., list[list[float]]]:
    facade = sys.modules.get("app.services.rag_service")
    if facade is not None and hasattr(facade, "embed_texts"):
        return getattr(facade, "embed_texts")
    return _embed_texts_impl


def chunk_text_legacy(
    text: str,
    source_name: str,
    course_id: str = "default",
    chunk_size: int = 600,
    overlap: int = 100,
) -> list[dict[str, Any]]:
    """[Cách cũ] Boundary-Preserved Chunking: chunk_size=600 ký tự, overlap=100 ký tự."""
    if not text:
        return []

    norm_course = normalize_course_id(course_id)
    paragraphs = text.split("\n")
    chunks: list[dict[str, Any]] = []
    current_chunk = ""
    chunk_index = 1

    for p in paragraphs:
        p = re.sub(r"^#{1,4}\s+", "", p.strip())
        if not p:
            continue

        if len(current_chunk) + len(p) + 1 <= chunk_size:
            current_chunk = f"{current_chunk}\n{p}" if current_chunk else p
        else:
            if current_chunk:
                clean_entry = current_chunk.strip().lstrip(".,:;|-)]} ")
                if len(clean_entry) > 30 and not is_low_value_rag_chunk(clean_entry):
                    chunks.append(
                        {
                            "id": f"{norm_course}::{source_name}_chunk_{chunk_index}",
                            "text": clean_entry,
                            "source": source_name,
                            "course_id": norm_course,
                            "index": chunk_index,
                            "section_title": "",
                        }
                    )
                    chunk_index += 1

                tail_overlap = get_clean_overlap(current_chunk, max_chars=overlap)
                current_chunk = f"{tail_overlap}\n{p}" if tail_overlap else p
            else:
                sentences = re.split(r"(?<=[.?!])\s+", p)
                sub_chunk = ""
                for s in sentences:
                    if len(sub_chunk) + len(s) + 1 <= chunk_size:
                        sub_chunk = f"{sub_chunk} {s}".strip()
                    else:
                        if sub_chunk:
                            clean_s = sub_chunk.strip().lstrip(".,:;|-)]} ")
                            if len(clean_s) > 30 and not is_low_value_rag_chunk(clean_s):
                                chunks.append(
                                    {
                                        "id": f"{norm_course}::{source_name}_chunk_{chunk_index}",
                                        "text": clean_s,
                                        "source": source_name,
                                        "course_id": norm_course,
                                        "index": chunk_index,
                                        "section_title": "",
                                    }
                                )
                                chunk_index += 1
                        sub_chunk = s
                current_chunk = sub_chunk

    if current_chunk.strip():
        clean_entry = current_chunk.strip().lstrip(".,:;|-)]} ")
        if len(clean_entry) > 20 and not is_low_value_rag_chunk(clean_entry):
            chunks.append(
                {
                    "id": f"{norm_course}::{source_name}_chunk_{chunk_index}",
                    "text": clean_entry,
                    "source": source_name,
                    "course_id": norm_course,
                    "index": chunk_index,
                    "section_title": "",
                }
            )

    return chunks


def chunk_text_recursive(
    text: str,
    source_name: str,
    course_id: str = "default",
    chunk_size: int = 750,
    overlap: int = 140,
) -> list[dict[str, Any]]:
    """Heading-aware Recursive Chunking với breadcrumb đa cấp, nối dòng PDF và lặp header bảng."""
    if not text or not text.strip():
        return []

    norm_course = normalize_course_id(course_id)
    sections = _split_into_sections(text)
    chunks: list[dict[str, Any]] = []
    chunk_index = 1

    for section_title, section_body in sections:
        prefix = f"[{section_title}]\n" if section_title else ""
        effective_max = max(250, chunk_size - len(prefix))
        reflowed_body = _reflow_wrapped_lines(section_body)
        raw_pieces = _recursive_split_piece(reflowed_body, effective_max)

        prev_piece = ""
        for piece in raw_pieces:
            piece_clean = piece.strip()
            if not piece_clean:
                continue
            body_text = piece_clean
            if prev_piece and overlap > 0 and not piece_clean.startswith("|"):
                ov = _sentence_overlap(prev_piece, max_chars=overlap)
                if ov and not piece_clean.startswith(ov):
                    body_text = f"{ov}\n{piece_clean}"
            final_text = f"{prefix}{body_text}".strip()
            if (
                len(piece_clean) >= 50
                and not piece_clean.isdigit()
                and not is_low_value_rag_chunk(final_text, section_title)
            ):
                chunks.append(
                    {
                        "id": f"{norm_course}::{source_name}_chunk_{chunk_index}",
                        "text": final_text,
                        "source": source_name,
                        "course_id": norm_course,
                        "index": chunk_index,
                        "section_title": section_title,
                    }
                )
                chunk_index += 1
            prev_piece = piece_clean

    return chunks


def chunk_text_semantic(
    text: str,
    source_name: str,
    course_id: str = "default",
    min_chars: int = 420,
    max_chars: int = 1000,
    embedding_provider: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Semantic Chunking kết hợp Heading-aware và Cosine Similarity phát hiện chuyển chủ đề."""
    if not text or not text.strip():
        return []

    norm_course = normalize_course_id(course_id)
    sections = _split_into_sections(text)
    chunks: list[dict[str, Any]] = []
    chunk_index = 1
    embed_fn = _resolve_embed_fn()

    for section_title, section_body in sections:
        prefix = f"[{section_title}]\n" if section_title else ""
        effective_max = max(350, max_chars - len(prefix))
        reflowed_body = _reflow_wrapped_lines(section_body)

        if len(reflowed_body) <= effective_max:
            final_text = f"{prefix}{reflowed_body}".strip()
            if (
                len(reflowed_body) >= 50
                and not reflowed_body.isdigit()
                and not is_low_value_rag_chunk(final_text, section_title)
            ):
                chunks.append(
                    {
                        "id": f"{norm_course}::{source_name}_chunk_{chunk_index}",
                        "text": final_text,
                        "source": source_name,
                        "course_id": norm_course,
                        "index": chunk_index,
                        "section_title": section_title,
                    }
                )
                chunk_index += 1
            continue

        sentences: list[str] = []
        for para in reflowed_body.split("\n\n"):
            para_s = para.strip()
            if para_s:
                sentences.extend(_split_sentences(para_s))

        if len(sentences) <= 2:
            sub_pieces = _recursive_split_piece(reflowed_body, effective_max)
        else:
            try:
                units = (
                    [
                        " ".join(sentences[i : i + 2]).strip()
                        for i in range(0, len(sentences), 2)
                    ]
                    if len(sentences) > 36
                    else sentences
                )
                sent_embeddings = embed_fn(
                    units, task="document", provider=embedding_provider
                )
                sims = [
                    _cosine_similarity(sent_embeddings[i], sent_embeddings[i + 1])
                    for i in range(len(units) - 1)
                ]
                sorted_sims = sorted(sims)
                p25_idx = max(0, int(len(sorted_sims) * 0.25) - 1)
                threshold = min(0.62, sorted_sims[p25_idx]) if sorted_sims else 0.55

                groups: list[str] = []
                buf_sents: list[str] = [units[0]]
                buf_len = len(units[0])

                for idx in range(len(sims)):
                    next_sent = units[idx + 1]
                    sim = sims[idx]
                    should_split = (
                        (sim <= threshold and buf_len >= min_chars)
                        or (buf_len + len(next_sent) + 1 > effective_max)
                    )
                    if should_split and buf_sents:
                        groups.append(" ".join(buf_sents).strip())
                        buf_sents = [next_sent]
                        buf_len = len(next_sent)
                    else:
                        buf_sents.append(next_sent)
                        buf_len += len(next_sent) + 1

                if buf_sents:
                    tail_group = " ".join(buf_sents).strip()
                    if groups and len(tail_group) < min_chars and len(groups[-1]) + len(tail_group) + 1 <= effective_max:
                        groups[-1] = f"{groups[-1]} {tail_group}".strip()
                    else:
                        groups.append(tail_group)

                sub_pieces = []
                for g in groups:
                    if len(g) > effective_max:
                        sub_pieces.extend(_recursive_split_piece(g, effective_max))
                    elif g:
                        sub_pieces.append(g)
            except Exception as exc:
                print(f"[AI-SERVICE] Semantic chunking fallback sang recursive: {exc}", flush=True)
                sub_pieces = _recursive_split_piece(reflowed_body, effective_max)

        for piece in sub_pieces:
            piece_s = piece.strip()
            if len(piece_s) < 50 or piece_s.isdigit():
                continue
            final_text = f"{prefix}{piece_s}".strip()
            if is_low_value_rag_chunk(final_text, section_title):
                continue
            chunks.append(
                {
                    "id": f"{norm_course}::{source_name}_chunk_{chunk_index}",
                    "text": final_text,
                    "source": source_name,
                    "course_id": norm_course,
                    "index": chunk_index,
                    "section_title": section_title,
                }
            )
            chunk_index += 1

    return chunks


def chunk_text(
    text: str,
    source_name: str,
    course_id: str = "default",
    chunk_size: int = 600,
    overlap: int = 100,
    strategy: Optional[str] = None,
    embedding_provider: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Điều phối chia văn bản theo chiến lược được chọn: recursive (mặc định), semantic, hoặc legacy."""
    norm_strategy = normalize_chunking_strategy(strategy)
    if norm_strategy == "legacy":
        raw_chunks = chunk_text_legacy(
            text=text,
            source_name=source_name,
            course_id=course_id,
            chunk_size=chunk_size,
            overlap=overlap,
        )
    elif norm_strategy == "semantic":
        raw_chunks = chunk_text_semantic(
            text=text,
            source_name=source_name,
            course_id=course_id,
            embedding_provider=embedding_provider,
        )
    else:
        raw_chunks = chunk_text_recursive(
            text=text,
            source_name=source_name,
            course_id=course_id,
        )
    return _apply_chunk_context_smoothing(raw_chunks)
