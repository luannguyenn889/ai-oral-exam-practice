"""Đọc các block văn bản, TextBox, danh sách Word (`w:numPr`) và bảng biểu từ file `.docx` / `.txt`."""

from __future__ import annotations

import io
import re
from typing import Any, Optional

from app.services.extractor.common import _clean_html_to_text


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
