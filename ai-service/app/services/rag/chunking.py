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
from app.services.rag.embeddings import normalize_course_id, normalize_embedding_provider
from app.services.rag.noise_filter import (
    apply_chunk_context_smoothing as _apply_chunk_context_smoothing,
    compute_noise_profile,
    is_allowed_uppercase_heading,
    is_low_value_rag_chunk,
    is_low_value_section_title as _is_low_value_section_title,
    is_plausible_heading_line,
)
from app.services.rag.text_structure import (
    _detect_heading_level,
    _format_breadcrumb,
    _is_heading_line,
    _merge_units_recursively,
    _recursive_split_piece,
    _reflow_wrapped_lines,
    _sentence_overlap,
    _split_into_sections,
    _split_sentences,
    _split_table_with_header,
    get_clean_overlap,
)

CHUNKING_STRATEGIES = ("recursive", "semantic", "legacy")
DEFAULT_CHUNKING_STRATEGY = "recursive"
CHUNKING_VERSION = "v4"

CHUNKING_STRATEGY_LABELS = {
    "recursive": "Heading-aware Recursive Chunking (750 chars, sentence overlap)",
    "semantic": "Semantic Chunking (Cosine Similarity topic-shift + Heading-aware)",
    "legacy": "Boundary-Preserved Chunking (Cách cũ: 600 chars, 100 overlap)",
}


def normalize_chunking_strategy(strategy: Optional[str]) -> str:
    s = (strategy or "").strip().lower()
    if s in CHUNKING_STRATEGIES:
        return s
    return DEFAULT_CHUNKING_STRATEGY


def get_chunking_strategy_label(strategy: Optional[str]) -> str:
    norm = normalize_chunking_strategy(strategy)
    return CHUNKING_STRATEGY_LABELS.get(norm, CHUNKING_STRATEGY_LABELS[DEFAULT_CHUNKING_STRATEGY])


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


def get_chunk_sizing_for_provider(embedding_provider: Optional[str] = None) -> tuple[int, int, int, int]:
    """Trả về kích thước chunk tối ưu theo giới hạn token của từng embedding model.

    Trả về `(rec_chunk_size, rec_overlap, sem_min_chars, sem_max_chars)`.
    Riêng `local` (MiniLM-L12-v2) bị cắt cụt ở 128 token (~420-450 ký tự) nên cần đoạn ngắn hơn.
    """
    prov = normalize_embedding_provider(embedding_provider)
    if prov == "local":
        return (420, 75, 220, 440)
    return (750, 140, 420, 1000)


def _strip_section_header(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("["):
        nl = cleaned.find("]\n")
        if nl != -1:
            return cleaned[nl + 2 :].strip()
    return cleaned


def _attach_page_numbers(
    chunks: list[dict[str, Any]],
    page_entries: Optional[list[tuple[int, str]]],
) -> list[dict[str, Any]]:
    """Ánh xạ gần đúng số trang/slide bắt đầu và kết thúc cho từng chunk theo thứ tự xuất hiện."""
    if not chunks or not page_entries:
        return chunks

    normalized_pages = [
        (page_num, re.sub(r"\s+", " ", page_text).strip())
        for page_num, page_text in page_entries
        if page_text and page_text.strip()
    ]
    if not normalized_pages:
        return chunks

    cursor = 0
    total_pages = len(normalized_pages)
    for chunk in chunks:
        body = re.sub(r"\s+", " ", _strip_section_header(str(chunk.get("text", "")))).strip()
        if len(body) < 20:
            continue
        head_probe = body[:48]
        tail_probe = body[-48:] if len(body) >= 48 else head_probe

        start_page: Optional[int] = None
        end_page: Optional[int] = None
        for idx in range(cursor, total_pages):
            p_num, p_text = normalized_pages[idx]
            if head_probe[:32] in p_text:
                start_page = p_num
                cursor = idx
                break
        if start_page is None:
            for idx in range(0, total_pages):
                p_num, p_text = normalized_pages[idx]
                if head_probe[:28] in p_text:
                    start_page = p_num
                    cursor = idx
                    break

        if start_page is not None:
            end_page = start_page
            for idx in range(cursor, min(total_pages, cursor + 4)):
                p_num, p_text = normalized_pages[idx]
                if tail_probe[-32:] in p_text:
                    end_page = p_num
                    break
            chunk["page_start"] = start_page
            chunk["page_end"] = end_page

    return chunks


def chunk_text(
    text: str,
    source_name: str,
    course_id: str = "default",
    chunk_size: Optional[int] = None,
    overlap: Optional[int] = None,
    strategy: Optional[str] = None,
    embedding_provider: Optional[str] = None,
    page_entries: Optional[list[tuple[int, str]]] = None,
) -> list[dict[str, Any]]:
    """Điều phối chia văn bản theo chiến lược được chọn và tự động khớp kích thước theo embedding model."""
    norm_strategy = normalize_chunking_strategy(strategy)
    rec_size, rec_overlap, sem_min, sem_max = get_chunk_sizing_for_provider(embedding_provider)

    if norm_strategy == "legacy":
        raw_chunks = chunk_text_legacy(
            text=text,
            source_name=source_name,
            course_id=course_id,
            chunk_size=chunk_size if chunk_size is not None else min(rec_size, 600),
            overlap=overlap if overlap is not None else min(rec_overlap, 100),
        )
    elif norm_strategy == "semantic":
        raw_chunks = chunk_text_semantic(
            text=text,
            source_name=source_name,
            course_id=course_id,
            min_chars=sem_min,
            max_chars=chunk_size if chunk_size is not None else sem_max,
            embedding_provider=embedding_provider,
        )
    else:
        raw_chunks = chunk_text_recursive(
            text=text,
            source_name=source_name,
            course_id=course_id,
            chunk_size=chunk_size if chunk_size is not None else rec_size,
            overlap=overlap if overlap is not None else rec_overlap,
        )
    raw_chunks = _attach_page_numbers(raw_chunks, page_entries)
    return _apply_chunk_context_smoothing(raw_chunks)
