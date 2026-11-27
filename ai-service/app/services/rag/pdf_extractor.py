"""Module trích xuất văn bản, bảng biểu và làm sạch trang cho tài liệu PDF (PyMuPDF, pypdf, Tesseract OCR)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from typing import Any

from app.services.rag.chunking import _detect_heading_level

_PDF_PAGE_NUM_RE = re.compile(
    r"^(?:\d{1,4}|[-–—]\s*\d{1,4}\s*[-–—]|(?:page|trang)\s*\d{1,4}(?:\s*(?:/|of|trên)\s*\d{1,4})?)$",
    re.IGNORECASE,
)


def _normalize_pdf_margin_line(line: str) -> str:
    """Chuẩn hóa dòng đầu/cuối trang PDF (thay số bằng '#') để phát hiện header/footer lặp lại."""
    s = re.sub(r"\s+", " ", line).strip().lower()
    s = re.sub(r"\d+", "#", s)
    return s


def _clean_pdf_pages_with_map(pages_text: list[str]) -> tuple[str, list[tuple[int, str]]]:
    """Làm sạch đa dạng tài liệu PDF và trả về cả văn bản nối liền lẫn danh sách (số trang, nội dung sạch)."""
    if not pages_text:
        return "", []
    if len(pages_text) == 1:
        cleaned_single = pages_text[0].strip()
        return cleaned_single, ([(1, cleaned_single)] if cleaned_single else [])

    page_lines_list: list[list[str]] = [
        [ln.strip() for ln in p.replace("\r\n", "\n").replace("\r", "\n").split("\n") if ln.strip()]
        for p in pages_text
    ]

    repeated_margins: set[str] = set()
    if len(page_lines_list) >= 4:
        margin_page_counts: dict[str, int] = {}
        for lines in page_lines_list:
            if not lines:
                continue
            candidates = set()
            for ln in lines[:2] + lines[-2:]:
                if len(ln) <= 100:
                    norm = _normalize_pdf_margin_line(ln)
                    if norm:
                        candidates.add(norm)
            for norm in candidates:
                margin_page_counts[norm] = margin_page_counts.get(norm, 0) + 1
        repeated_margins = {norm for norm, cnt in margin_page_counts.items() if cnt >= 3}

    seen_repeated_headings: set[str] = set()
    cleaned_pages: list[str] = []
    page_entries: list[tuple[int, str]] = []

    for page_num, lines in enumerate(page_lines_list, 1):
        if not lines:
            continue
        n = len(lines)
        kept: list[str] = []
        for idx, ln in enumerate(lines):
            is_margin = idx < 2 or idx >= n - 2
            if is_margin:
                if _PDF_PAGE_NUM_RE.fullmatch(ln):
                    continue
                norm = _normalize_pdf_margin_line(ln)
                if norm in repeated_margins:
                    if norm not in seen_repeated_headings and _detect_heading_level(ln) is not None:
                        seen_repeated_headings.add(norm)
                    else:
                        continue
            kept.append(ln)
        if kept:
            page_joined = "\n".join(kept)
            cleaned_pages.append(page_joined)
            page_entries.append((page_num, page_joined))

    if not cleaned_pages:
        fallback_entries = [(i, p.strip()) for i, p in enumerate(pages_text, 1) if p and p.strip()]
        return "\n\n".join(pages_text), fallback_entries

    stitched: list[str] = [cleaned_pages[0]]
    for page_str in cleaned_pages[1:]:
        prev_last_line = stitched[-1].rsplit("\n", 1)[-1].strip()
        next_first_line = page_str.split("\n", 1)[0].strip()
        prev_ends_mid_sentence = bool(prev_last_line) and not prev_last_line.endswith((".", "?", "!", ":", "…"))
        next_starts_lower = bool(next_first_line) and next_first_line[0].islower()
        if prev_ends_mid_sentence and next_starts_lower and not next_first_line.startswith("|"):
            stitched[-1] = stitched[-1] + "\n" + page_str
        else:
            stitched.append(page_str)

    return "\n\n".join(stitched), page_entries


def _clean_pdf_pages(pages_text: list[str]) -> str:
    """Làm sạch đa dạng tài liệu PDF (header/footer lặp lại, số trang, nối câu chuyển trang)."""
    stitched, _ = _clean_pdf_pages_with_map(pages_text)
    return stitched


def _rect_overlaps_any(bbox: tuple[float, float, float, float], regions: list[tuple[float, float, float, float]]) -> bool:
    x0, y0, x1, y1 = bbox
    cx = (x0 + x1) * 0.5
    cy = (y0 + y1) * 0.5
    for rx0, ry0, rx1, ry1 in regions:
        if (rx0 - 2.0) <= cx <= (rx1 + 2.0) and (ry0 - 2.0) <= cy <= (ry1 + 2.0):
            return True
    return False


def _extract_fitz_page_preserving_tables(page: Any) -> str:
    """Trích xuất nội dung 1 trang PDF qua PyMuPDF, giữ bảng biểu thành Markdown '| ... |' nếu phát hiện."""
    raw_text = (page.get_text() or "").strip()
    if not raw_text or not hasattr(page, "find_tables"):
        return raw_text
    try:
        if hasattr(page, "get_drawings") and len(page.get_drawings()) < 10:
            return raw_text
        finder = page.find_tables()
        tables = list(getattr(finder, "tables", None) or [])
        if not tables:
            return raw_text

        valid_tables: list[tuple[float, tuple[float, float, float, float], str]] = []
        for tab in tables:
            rows = tab.extract() or []
            if len(rows) < 2:
                continue
            max_cols = max(len(r) for r in rows) if rows else 0
            if max_cols < 2:
                continue
            md_lines: list[str] = []
            for r in rows:
                cells = [re.sub(r"\s+", " ", (c or "")).strip() for c in r]
                if any(cells):
                    md_lines.append("| " + " | ".join(cells) + " |")
            if len(md_lines) >= 2 and getattr(tab, "bbox", None):
                bbox = tuple(float(v) for v in tab.bbox)
                valid_tables.append((bbox[1], bbox, "\n".join(md_lines)))

        if not valid_tables:
            return raw_text

        table_bboxes = [bbox for _, bbox, _ in valid_tables]
        items: list[tuple[float, str]] = [(y0, md) for y0, _, md in valid_tables]
        for blk in page.get_text("blocks") or []:
            if len(blk) < 5:
                continue
            bx0, by0, bx1, by1 = float(blk[0]), float(blk[1]), float(blk[2]), float(blk[3])
            btext = str(blk[4] or "").strip()
            if not btext or (len(blk) >= 7 and int(blk[6]) != 0):
                continue
            if _rect_overlaps_any((bx0, by0, bx1, by1), table_bboxes):
                continue
            items.append((by0, btext))

        items.sort(key=lambda item: item[0])
        merged = "\n".join(text for _, text in items).strip()
        return merged or raw_text
    except Exception:
        return raw_text


def _ocr_pdf_pages(file_path: str) -> tuple[str, list[tuple[int, str]]]:
    """Fallback OCR bằng Tesseract khi PDF là bản scan không có lớp text."""
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError(
            "PDF này không có lớp văn bản đọc được. Cần cài PyMuPDF và Tesseract OCR."
        ) from exc

    tesseract_cmd = os.environ.get("TESSERACT_CMD") or shutil.which("tesseract")
    if not tesseract_cmd:
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        for candidate in (
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.join(local_app_data, "Programs", "Tesseract-OCR", "tesseract.exe"),
        ):
            if os.path.isfile(candidate):
                tesseract_cmd = candidate
                break
    if not tesseract_cmd:
        raise RuntimeError(
            "PDF này là bản scan không có lớp văn bản và máy chưa cài Tesseract OCR."
        )

    language_result = subprocess.run(
        [tesseract_cmd, "--list-langs"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    available_languages = set(language_result.stdout.splitlines()[1:])
    languages = [lang for lang in ("vie", "eng") if lang in available_languages]
    if not languages:
        raise RuntimeError("Tesseract chưa có dữ liệu OCR tiếng Việt hoặc tiếng Anh.")
    language = "+".join(languages)

    doc = fitz.open(file_path)
    try:
        pages_text = []
        matrix = fitz.Matrix(2, 2)
        with tempfile.TemporaryDirectory(prefix="rag_pdf_ocr_") as temp_dir:
            for page_number, page in enumerate(doc, 1):
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                image_path = os.path.join(temp_dir, f"page_{page_number:05d}.png")
                pix.save(image_path)
                result = subprocess.run(
                    [tesseract_cmd, image_path, "stdout", "-l", language, "--oem", "1", "--psm", "3"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=True,
                )
                pages_text.append(result.stdout.strip())
    finally:
        doc.close()

    if any(p.strip() for p in pages_text):
        return _clean_pdf_pages_with_map(pages_text)
    raise RuntimeError("Tesseract đã chạy nhưng không nhận diện được chữ trong PDF.")


def extract_pdf_with_pages(file_path: str) -> tuple[str, list[tuple[int, str]]]:
    """Đọc PDF và trả về cả văn bản hoàn chỉnh lẫn ánh xạ theo từng trang để gắn số trang vào chunk."""
    fitz_doc = None
    try:
        import fitz

        fitz_doc = fitz.open(file_path)
        pages_text = [_extract_fitz_page_preserving_tables(page) for page in fitz_doc]
        if any(p.strip() for p in pages_text):
            fitz_doc.close()
            return _clean_pdf_pages_with_map(pages_text)
    except Exception:
        if fitz_doc:
            fitz_doc.close()

    if fitz_doc:
        fitz_doc.close()

    try:
        import pypdf

        reader = pypdf.PdfReader(file_path)
        pages_text = [(page.extract_text() or "").strip() for page in reader.pages]
        if any(p.strip() for p in pages_text):
            return _clean_pdf_pages_with_map(pages_text)
    except Exception:
        pass

    return _ocr_pdf_pages(file_path)


def extract_text_from_pdf(file_path: str) -> str:
    """Đọc PDF có text layer (PyMuPDF -> pypdf); nếu là PDF scan thì OCR qua Tesseract."""
    text, _ = extract_pdf_with_pages(file_path)
    return text
