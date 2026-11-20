"""Module trích xuất văn bản thô đa định dạng (.docx, .pdf, .txt) phục vụ lập chỉ mục RAG.

Nhiệm vụ:
- Đọc file Word (.docx) (`extract_text_from_docx`):
    + Duyệt xen kẽ đoạn văn và bảng biểu theo đúng thứ tự xuất hiện trong tài liệu (giữ bảng nằm đúng dưới tiêu đề mục chứa nó).
    + Nhận diện Word Heading Style (Heading 1..4, Title) để gắn dấu cấp tiêu đề phục vụ breadcrumb đa cấp.
    + Đọc cả nội dung trong TextBox (`w:txbxContent`) và loại bỏ ô gộp bị lặp trong bảng.
- Đọc file PDF (.pdf) (`extract_text_from_pdf`):
    + Hỗ trợ đọc lớp text theo thứ tự ưu tiên PyMuPDF -> pypdf; tự động fallback sang OCR bằng Tesseract (`vie+eng`) đối với PDF bản scan.
    + Tự động làm sạch tổng quát qua `_clean_pdf_pages`: thống kê tần suất 2 dòng đầu/cuối trang để loại bỏ header/footer lặp lại, xóa số trang đứng riêng và nối liền câu chảy qua ranh giới chuyển trang.
- Đọc file văn bản thuần (.txt) (`extract_text_from_txt`).
"""

import os
import re
import shutil
import subprocess
import tempfile
from typing import Any, Optional

import docx

from app.services.rag.chunking import _detect_heading_level

_PDF_PAGE_NUM_RE = re.compile(
    r"^(?:\d{1,4}|[-–—]\s*\d{1,4}\s*[-–—]|(?:page|trang)\s*\d{1,4}(?:\s*(?:/|of|trên)\s*\d{1,4})?)$",
    re.IGNORECASE,
)


def _detect_docx_heading_level(para: Any) -> Optional[int]:
    """Nhận diện cấp độ tiêu đề từ Style của Word (Heading 1..4, Title)."""
    style_name = (para.style.name or "").strip().lower() if para.style is not None else ""
    if not style_name:
        return None
    if style_name == "title":
        return 1
    m = re.match(r"^heading\s*(\d)", style_name)
    if m:
        return min(4, max(1, int(m.group(1))))
    return None


def extract_text_from_docx(file_path: str) -> str:
    """Trích xuất văn bản và bảng biểu từ .docx theo đúng thứ tự xuất hiện (đoạn văn + bảng xen kẽ)."""
    try:
        from docx.table import Table
        from docx.text.paragraph import Paragraph

        doc = docx.Document(file_path)
        content_parts: list[str] = []

        for child in doc.element.body.iterchildren():
            tag = child.tag.rsplit("}", 1)[-1]
            if tag == "p":
                para = Paragraph(child, doc)
                raw_text = (para.text or "").strip()
                if not raw_text:
                    txbx_texts = [
                        "".join(p_el.itertext()).strip()
                        for p_el in child.findall(".//{*}txbxContent//{*}p")
                    ]
                    raw_text = "\n".join(t for t in txbx_texts if t).strip()
                if not raw_text:
                    continue
                h_lvl = _detect_docx_heading_level(para)
                if h_lvl is not None and not raw_text.startswith("#"):
                    content_parts.append(f"{'#' * h_lvl} {raw_text}")
                else:
                    content_parts.append(raw_text)
            elif tag == "tbl":
                table = Table(child, doc)
                table_lines: list[str] = []
                for row in table.rows:
                    row_cells: list[str] = []
                    prev_tc = None
                    for cell in row.cells:
                        if cell._tc is prev_tc:
                            continue
                        prev_tc = cell._tc
                        cell_text = re.sub(r"\s+", " ", cell.text or "").strip()
                        if cell_text:
                            row_cells.append(cell_text)
                    if row_cells:
                        table_lines.append("| " + " | ".join(row_cells) + " |")
                if table_lines:
                    content_parts.append("")
                    content_parts.extend(table_lines)
                    content_parts.append("")

        return "\n".join(content_parts).strip()
    except Exception:
        return ""


def _normalize_pdf_margin_line(line: str) -> str:
    """Chuẩn hóa dòng đầu/cuối trang PDF (thay số bằng '#') để phát hiện header/footer lặp lại."""
    s = re.sub(r"\s+", " ", line).strip().lower()
    s = re.sub(r"\d+", "#", s)
    return s


def _clean_pdf_pages(pages_text: list[str]) -> str:
    """
    Làm sạch đa dạng tài liệu PDF (giáo trình, slide, báo cáo, bản scan OCR):
    - Tự động phát hiện và loại bỏ header/footer lặp lại ở đầu/cuối trang (>= 3 trang).
    - Loại bỏ số trang đứng riêng ở lề trên/dưới.
    - Nối liền câu chảy qua ranh giới chuyển trang.
    """
    if not pages_text:
        return ""
    if len(pages_text) == 1:
        return pages_text[0].strip()

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

    for lines in page_lines_list:
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
            cleaned_pages.append("\n".join(kept))

    if not cleaned_pages:
        return "\n\n".join(pages_text)

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

    return "\n\n".join(stitched)


def extract_text_from_txt(file_path: str) -> str:
    """Trích xuất văn bản từ file text thuần."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().strip()
    except Exception:
        return ""


def extract_text_from_pdf(file_path: str) -> str:
    """Đọc PDF có text layer (PyMuPDF -> pypdf); nếu là PDF scan thì OCR qua Tesseract."""
    fitz_doc = None
    try:
        import fitz

        fitz_doc = fitz.open(file_path)
        pages_text = []
        for page in fitz_doc:
            t = page.get_text().strip()
            if t:
                pages_text.append(t)
        if pages_text:
            fitz_doc.close()
            return _clean_pdf_pages(pages_text)
    except Exception:
        if fitz_doc:
            fitz_doc.close()

    if fitz_doc:
        fitz_doc.close()

    try:
        import pypdf

        reader = pypdf.PdfReader(file_path)
        pages_text = []
        for page in reader.pages:
            t = page.extract_text()
            if t and t.strip():
                pages_text.append(t.strip())
        if pages_text:
            return _clean_pdf_pages(pages_text)
    except Exception:
        pass

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
                    [
                        tesseract_cmd,
                        image_path,
                        "stdout",
                        "-l",
                        language,
                        "--oem",
                        "1",
                        "--psm",
                        "3",
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=True,
                )
                page_text = result.stdout.strip()
                if page_text:
                    pages_text.append(page_text)
    finally:
        doc.close()
    if pages_text:
        return _clean_pdf_pages(pages_text)
    raise RuntimeError("Tesseract đã chạy nhưng không nhận diện được chữ trong PDF.")
