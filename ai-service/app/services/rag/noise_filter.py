"""Module nhận diện và chấm điểm chunk rác (noise filtering) cho hệ thống RAG đa định dạng.

Nhiệm vụ:
- Tầng 1 (Kiểm định tiêu đề mục): `is_low_value_section_title`, `is_plausible_heading_line` — chặn tiêu đề giả
  (ISBN, chỉ mục trang `COCOMO, 71`, ký hiệu code/toán, từ viết tắt ngắn) làm bẩn breadcrumb và xử lý
  tiêu đề bị PDF tách chữ (`FURTHER RE ADING`).
- Tầng 2 (Chấm điểm đặc trưng thống kê): `compute_noise_profile` — chấm `noise_score` ∈ [0, 1] không phụ thuộc
  định dạng (hỗ trợ PDF/DOCX/TXT, tiếng Việt/Anh); bảo vệ bảng Markdown, slide gạch đầu dòng ngắn và code thật.
- Tầng 3 (Ngữ cảnh tài liệu): `apply_chunk_context_smoothing` — kết hợp vị trí đầu/cuối tài liệu và làm mượt
  theo các chunk lân cận để lọc dải Index/References/TOC liên tiếp.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from app.config import settings

_LOW_VALUE_SECTION_RE = re.compile(
    r"^(?:"
    r"index|author index|subject index|name index|"
    r"references|bibliography|further reading|recommended reading|works cited|"
    r"table of contents|contents|list of figures|list of tables|"
    r"acknowledg(?:e)?ments?|copyright|"
    r"mục lục|chỉ mục|tài liệu tham khảo|danh mục tài liệu tham khảo|"
    r"danh mục hình vẽ|danh mục bảng biểu|lời cảm ơn|lời cam đoan|trang bìa"
    r")$",
    re.IGNORECASE,
)

_COLLAPSED_LOW_VALUE_SECTIONS = frozenset(
    {
        "index",
        "authorindex",
        "subjectindex",
        "nameindex",
        "references",
        "bibliography",
        "furtherreading",
        "recommendedreading",
        "workscited",
        "tableofcontents",
        "contents",
        "listoffigures",
        "listoftables",
        "acknowledgements",
        "acknowledgments",
        "copyright",
        "mụclục",
        "chỉmục",
        "tàiliệuthamkhảo",
        "danhmụctàiliệuthamkhảo",
        "danhmụchìnhvẽ",
        "danhmụcbảngbiểu",
        "lờicảmơn",
        "lờicamđoan",
        "trangbìa",
    }
)

_TOC_DOT_LEADER_RE = re.compile(r"(?:\.{4,}|(?:\.\s){4,}|_{5,}|-{5,})\s*\d{1,4}\b")
_TOC_LINE_END_PAGE_RE = re.compile(r"^.+\s{2,}\d{1,4}\s*$")
_COMMA_PAGE_NUM_RE = re.compile(r",\s*\d{1,4}(?:[-–]\d{1,4})?(?=[,\s.;\]]|$)")
_PAGE_TOKEN_RE = re.compile(r"^\d{1,4}(?:[-–]\d{1,4})?[,.;\]]?$")
_AUTHOR_INITIAL_RE = re.compile(r"\b[A-Z]\.(?:\s*[A-Z]\.)?")
_YEAR_PAREN_RE = re.compile(
    r"(?:\(\s*(?:19|20)\d{2}[a-z]?\s*\)|,\s*(?:19|20)\d{2}[a-z]?(?=[.,;\s]|$)|\b(?:19|20)\d{2}[a-z]?(?=\s*[)\].;,]))"
)
_BRACKET_REF_RE = re.compile(r"\[\d{1,3}\]\s+[A-ZÀ-Ỹ]")
_URL_DOI_ISBN_RE = re.compile(
    r"(?:https?://|www\.|dx\.doi\.org|\bdoi:\s*|\bISBN\b|\bISSN\b|\bp\.\s*cm\.)",
    re.IGNORECASE,
)
_BIB_MARKER_RE = re.compile(
    r"(?:\bet\s+al\.|\bpp\.|\bvol\.|\bno\.|\bed(?:s)?\.|\bproc\.|\bconf\.|\bIEEE\b|\bACM\b|\bSpringer\b|\bPrentice\s+Hall\b|\bAddison[- ]Wesley\b|\bWiley\b|\bElsevier\b|\bMicrosoft\s+Press\b|\bAcademic\s+Press\b|\bMcGraw[- ]Hill\b|\bNXB\b|\bNhà\s+xuất\s+bản\b|\bTạp\s+chí\b|\bKỷ\s+yếu\b|\btr\.\s*\d+)",
    re.IGNORECASE,
)
_FRONT_MATTER_PHRASE_RE = re.compile(
    r"(?:cataloging-in-publication|library of congress|all rights reserved|trademark claim|no part of this publication|printed in the|this page intentionally left blank)",
    re.IGNORECASE,
)
_HEADER_COMMENT_META_RE = re.compile(
    r"(?://\s*(?:object|author|creation date|modification history|version|copyright)|©\s*\d{4})",
    re.IGNORECASE,
)
_CODE_LINE_RE = re.compile(
    r"(?:^\s*(?:def |class |return |elif |else:|for .+ in |while .*:|public |private |protected |import |package |#include|SELECT\s+.+\s+FROM|function\s+\w+|const\s+\w+\s*=|let\s+\w+\s*=)|[{};]\s*$)",
    re.MULTILINE,
)
_SENTENCE_END_RE = re.compile(r"[a-zà-ỹ]{2,}[.?!](?:\s|$)")

_STOPWORDS = frozenset(
    {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "of", "to", "in", "for", "on", "with", "that", "this", "these", "those",
        "as", "by", "from", "which", "we", "you", "they", "it", "its", "can",
        "will", "may", "should", "must", "has", "have", "had", "and", "or",
        "not", "if", "when", "where", "while", "into", "between", "such", "also",
        "là", "của", "và", "các", "những", "trong", "cho", "được", "có", "một",
        "để", "với", "khi", "này", "đó", "về", "từ", "theo", "như", "tại",
        "nếu", "hoặc", "vì", "nên", "trên", "dưới", "giữa", "bởi", "được",
    }
)

_ALLOWED_SHORT_CAPS_HEADINGS = frozenset(
    {"INDEX", "PREFACE", "SUMMARY", "NOTES", "CONTENTS", "APPENDIX", "GLOSSARY", "ABSTRACT"}
)
_FALSE_HEADING_META_RE = re.compile(
    r"(?:\bISBN\b|\bISSN\b|\bDOI\s*:|https?://|www\.|Copyright|©|Library of Congress)",
    re.IGNORECASE,
)


def is_low_value_section_title(section_title: str) -> bool:
    """Kiểm tra tên mục cuối breadcrumb có phải mục phi nội dung (Index, References, Mục lục...)."""
    if not section_title:
        return False
    leaf_title = section_title.split(">")[-1].strip()
    if not leaf_title:
        return False
    if _LOW_VALUE_SECTION_RE.match(leaf_title):
        return True
    collapsed = re.sub(r"[^a-zà-ỹ]", "", leaf_title.lower())
    return collapsed in _COLLAPSED_LOW_VALUE_SECTIONS


def is_plausible_heading_line(line: str) -> bool:
    """Kiểm định sơ bộ dòng có hợp lệ làm tiêu đề mục không (chặn ISBN, chỉ mục số trang, comment code)."""
    s = line.strip()
    if not s or len(s) > 120 or len(s) < 3:
        return False
    if s.startswith(("|", "//", "/*", "#!", "{", "[")) or s.endswith(("?", ";", ",", "{", "}", "=")):
        return False
    if "=>" in s or _COMMA_PAGE_NUM_RE.search(s):
        return False
    if not s.startswith("#") and _FALSE_HEADING_META_RE.search(s):
        return False
    return True


def is_allowed_uppercase_heading(line: str) -> bool:
    """Kiểm tra dòng viết hoa toàn bộ có đủ điều kiện làm heading cấp 1 (tránh viết tắt đơn như IEEE, 128 KLOC)."""
    s = line.strip()
    letters = [c for c in s if c.isalpha()]
    alpha_words = [w for w in s.split() if any(ch.isalpha() for ch in w)]
    if len(letters) < 5 or len(s) > 85 or not s.isupper() or s.endswith("."):
        return False
    if (
        len(alpha_words) <= 1
        and s not in _ALLOWED_SHORT_CAPS_HEADINGS
        and not is_low_value_section_title(s)
    ):
        return False
    return True


def _extract_body_and_section(text: str, section_title: str) -> tuple[str, str]:
    cleaned = text.strip()
    body = cleaned
    resolved_section = section_title
    if cleaned.startswith("["):
        first_nl = cleaned.find("]\n")
        if first_nl != -1:
            if not resolved_section:
                resolved_section = cleaned[1:first_nl].strip()
            body = cleaned[first_nl + 2 :].strip()
    return body, resolved_section


def _score_references_signal(
    year_hits: int,
    url_doi_isbn_hits: int,
    bib_marker_hits: int,
    bracket_ref_hits: int,
    author_initial_hits: int,
    stopword_ratio: float,
    sentence_ends: int,
) -> float:
    ref_score = 0.0
    if year_hits >= 3:
        ref_score += 0.36
    elif year_hits == 2:
        ref_score += 0.20

    if url_doi_isbn_hits >= 2:
        ref_score += 0.34
    elif url_doi_isbn_hits == 1:
        ref_score += 0.16

    if bib_marker_hits >= 3:
        ref_score += 0.32
    elif bib_marker_hits == 2:
        ref_score += 0.20

    if bracket_ref_hits >= 3:
        ref_score += 0.36
    elif bracket_ref_hits == 2:
        ref_score += 0.20

    if author_initial_hits >= 4:
        ref_score += 0.26
    elif author_initial_hits >= 2:
        ref_score += 0.12

    strong_bib_combo = (url_doi_isbn_hits >= 2 and year_hits >= 2) or bracket_ref_hits >= 2
    if stopword_ratio >= 0.26 and sentence_ends >= 3 and not strong_bib_combo:
        ref_score -= 0.22
    elif stopword_ratio < 0.15 and (year_hits >= 2 or url_doi_isbn_hits >= 2):
        ref_score += 0.08

    return max(0.0, min(0.96, ref_score))


def compute_noise_profile(
    text: str,
    section_title: str = "",
    doc_position: Optional[float] = None,
) -> dict[str, Any]:
    """
    Đánh giá mức độ nhiễu học thuật của một chunk (0.0..1.0) theo đặc trưng thống kê,
    không phụ thuộc cứng vào định dạng tài liệu (PDF/DOCX/TXT, tiếng Việt/tiếng Anh).
    """
    drop_thr = float(getattr(settings, "rag_noise_drop_threshold", 0.70) or 0.70)
    if not text or not text.strip():
        return {"noise_score": 1.0, "noise_type": "empty", "is_noise": True}

    body, resolved_section = _extract_body_and_section(text, section_title)
    if not body:
        return {"noise_score": 1.0, "noise_type": "empty", "is_noise": True}

    if is_low_value_section_title(resolved_section):
        return {"noise_score": 0.95, "noise_type": "section_header", "is_noise": True}

    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    table_lines = sum(1 for ln in lines if ln.startswith("|"))
    if table_lines >= 2 and table_lines / max(1, len(lines)) >= 0.5:
        return {"noise_score": 0.0, "noise_type": "clean", "is_noise": False}

    if len(_TOC_DOT_LEADER_RE.findall(body)) >= 2:
        return {"noise_score": 0.92, "noise_type": "toc", "is_noise": True}
    toc_end_page_lines = sum(1 for ln in lines if _TOC_LINE_END_PAGE_RE.match(ln))
    if len(lines) >= 4 and toc_end_page_lines >= 3 and toc_end_page_lines / len(lines) >= 0.6:
        return {"noise_score": 0.86, "noise_type": "toc", "is_noise": True}

    if _FRONT_MATTER_PHRASE_RE.search(body):
        return {"noise_score": 0.88, "noise_type": "front_matter", "is_noise": True}
    if len(_HEADER_COMMENT_META_RE.findall(body)) >= 2 and len(_CODE_LINE_RE.findall(body)) == 0:
        return {"noise_score": 0.76, "noise_type": "front_matter", "is_noise": True}

    tokens = body.split()
    total_tokens = len(tokens)
    if total_tokens < 6:
        return {"noise_score": 0.0, "noise_type": "clean", "is_noise": False}

    code_hits = len(_CODE_LINE_RE.findall(body))
    if code_hits >= 3 and len(_HEADER_COMMENT_META_RE.findall(body)) == 0:
        return {"noise_score": 0.42, "noise_type": "code", "is_noise": False}

    comma_page_hits = len(_COMMA_PAGE_NUM_RE.findall(body))
    page_num_tokens = sum(1 for tok in tokens if _PAGE_TOKEN_RE.match(tok))
    page_num_ratio = page_num_tokens / total_tokens
    author_initial_hits = len(_AUTHOR_INITIAL_RE.findall(body))
    year_hits = len(_YEAR_PAREN_RE.findall(body))
    bracket_ref_hits = len(_BRACKET_REF_RE.findall(body))
    url_doi_isbn_hits = len(_URL_DOI_ISBN_RE.findall(body))
    bib_marker_hits = len(_BIB_MARKER_RE.findall(body))

    alpha_words = [w.lower() for w in re.findall(r"[A-Za-zÀ-ỹ]+", body)]
    stopword_hits = sum(1 for w in alpha_words if w in _STOPWORDS)
    stopword_ratio = stopword_hits / max(1, len(alpha_words))
    alpha_ratio = sum(1 for c in body if c.isalpha()) / max(1, len(body))
    sentence_ends = len(_SENTENCE_END_RE.findall(body))

    best_score = 0.0
    noise_type = "clean"

    if (
        (comma_page_hits >= 7 and page_num_tokens >= 9 and page_num_ratio >= 0.14)
        or (page_num_tokens >= 14 and author_initial_hits >= 4 and page_num_ratio >= 0.20)
        or (comma_page_hits >= 4 and page_num_ratio >= 0.18 and stopword_ratio < 0.16)
        or (comma_page_hits >= 4 and page_num_ratio >= 0.30 and sentence_ends == 0)
        or (comma_page_hits >= 2 and page_num_ratio >= 0.24 and stopword_ratio < 0.15 and sentence_ends <= 1)
    ):
        idx_score = min(0.96, 0.76 + min(0.20, page_num_ratio * 0.45))
        if idx_score > best_score:
            best_score = idx_score
            noise_type = "index"

    ref_score = _score_references_signal(
        year_hits=year_hits,
        url_doi_isbn_hits=url_doi_isbn_hits,
        bib_marker_hits=bib_marker_hits,
        bracket_ref_hits=bracket_ref_hits,
        author_initial_hits=author_initial_hits,
        stopword_ratio=stopword_ratio,
        sentence_ends=sentence_ends,
    )

    if (
        url_doi_isbn_hits >= 1
        and stopword_ratio < 0.08
        and sentence_ends == 0
        and len(body) < 180
        and code_hits == 0
    ):
        best_score = max(best_score, 0.78)
        noise_type = "front_matter"

    if ref_score > best_score:
        best_score = ref_score
        if ref_score >= 0.40:
            noise_type = "references"

    if alpha_ratio < 0.42 and total_tokens >= 10:
        ocr_score = min(0.90, 0.72 + (0.42 - alpha_ratio))
        if ocr_score > best_score:
            best_score = ocr_score
            noise_type = "ocr_garble"

    if doc_position is not None and 0.35 <= best_score < drop_thr:
        if doc_position <= 0.04 or doc_position >= 0.86:
            best_score = min(1.0, best_score + 0.12)

    best_score = round(best_score, 3)
    return {
        "noise_score": best_score,
        "noise_type": noise_type if best_score >= 0.40 else "clean",
        "is_noise": best_score >= drop_thr,
    }


def apply_chunk_context_smoothing(
    raw_chunks: list[dict[str, Any]],
    drop_threshold: Optional[float] = None,
) -> list[dict[str, Any]]:
    """Áp dụng Tầng 2 + Tầng 3 (vị trí tài liệu & làm mượt theo chunk lân cận), lọc bỏ rác và gắn metadata."""
    if not raw_chunks:
        return []
    drop_thr = float(
        drop_threshold
        if drop_threshold is not None
        else getattr(settings, "rag_noise_drop_threshold", 0.70) or 0.70
    )
    total = len(raw_chunks)
    profiles: list[dict[str, Any]] = []
    for idx, chunk in enumerate(raw_chunks):
        pos = idx / max(1, total - 1) if total > 1 else 0.5
        prof = compute_noise_profile(
            str(chunk.get("text", "")),
            str(chunk.get("section_title", "")),
            doc_position=pos,
        )
        profiles.append(prof)

    for idx in range(1, total - 1):
        curr = profiles[idx]
        prev_p = profiles[idx - 1]
        next_p = profiles[idx + 1]
        if (
            0.35 <= curr["noise_score"] < drop_thr
            and curr["noise_type"] != "code"
            and prev_p["noise_score"] >= drop_thr
            and next_p["noise_score"] >= drop_thr
        ):
            curr["noise_score"] = round(min(1.0, curr["noise_score"] + 0.28), 3)
            curr["noise_type"] = prev_p["noise_type"]
            curr["is_noise"] = curr["noise_score"] >= drop_thr

    kept: list[dict[str, Any]] = []
    for chunk, prof in zip(raw_chunks, profiles):
        if prof["is_noise"]:
            continue
        enriched = dict(chunk)
        enriched["noise_score"] = prof["noise_score"]
        enriched["noise_type"] = prof["noise_type"]
        kept.append(enriched)
    return kept


def is_low_value_rag_chunk(text: str, section_title: str = "") -> bool:
    """Nhận diện các đoạn rác học thuật để loại khỏi RAG (tương thích ngược)."""
    return bool(compute_noise_profile(text, section_title=section_title)["is_noise"])
