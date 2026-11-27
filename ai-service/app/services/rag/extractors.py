"""Module điều phối trích xuất văn bản thô đa định dạng (.docx, .pdf, .pptx, .txt) phục vụ lập chỉ mục RAG."""

from __future__ import annotations

import os
import re
from typing import Any, Optional

import docx

from app.services.rag.pdf_extractor import (
    _PDF_PAGE_NUM_RE,
    _clean_pdf_pages,
    _clean_pdf_pages_with_map,
    _extract_fitz_page_preserving_tables,
    _normalize_pdf_margin_line,
    extract_pdf_with_pages,
    extract_text_from_pdf,
)
from app.services.rag.pptx_extractor import (
    extract_pptx_with_slides,
    extract_text_from_pptx,
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


def extract_text_from_docx(file_path: str, raise_on_error: bool = False) -> str:
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
        if raise_on_error:
            raise
        return ""


def extract_text_from_txt(file_path: str, raise_on_error: bool = False) -> str:
    """Trích xuất văn bản từ file text thuần."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().strip()
    except Exception:
        if raise_on_error:
            raise
        return ""


def extract_document_with_pages(
    file_path: str, raise_on_error: bool = True
) -> tuple[str, list[tuple[int, str]]]:
    """Hàm thống nhất đọc đa định dạng (.docx, .pdf, .pptx, .txt) kèm ánh xạ số trang/slide nếu có."""
    extension = os.path.splitext(file_path)[1].lower()
    if extension == ".docx":
        return extract_text_from_docx(file_path, raise_on_error=raise_on_error), []
    if extension == ".pdf":
        return extract_pdf_with_pages(file_path)
    if extension == ".pptx":
        return extract_pptx_with_slides(file_path, raise_on_error=raise_on_error)
    return extract_text_from_txt(file_path, raise_on_error=raise_on_error), []


__all__ = [
    "_PDF_PAGE_NUM_RE",
    "_clean_pdf_pages",
    "_clean_pdf_pages_with_map",
    "_detect_docx_heading_level",
    "_extract_fitz_page_preserving_tables",
    "_normalize_pdf_margin_line",
    "extract_document_with_pages",
    "extract_pdf_with_pages",
    "extract_pptx_with_slides",
    "extract_text_from_docx",
    "extract_text_from_pdf",
    "extract_text_from_pptx",
    "extract_text_from_txt",
]
