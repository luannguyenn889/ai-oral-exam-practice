"""Module trích xuất nội dung bài giảng PowerPoint (.pptx) kèm bảng biểu và ghi chú giảng viên."""

from __future__ import annotations

import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile


def _parse_pptx_xml_paragraphs(container: ET.Element) -> list[str]:
    paras: list[str] = []
    for p_el in container.findall(".//{*}p"):
        runs = [(t_el.text or "") for t_el in p_el.findall(".//{*}t")]
        line = re.sub(r"\s+", " ", "".join(runs)).strip()
        if line:
            paras.append(line)
    return paras


def extract_pptx_with_slides(
    file_path: str, raise_on_error: bool = False
) -> tuple[str, list[tuple[int, str]]]:
    """Trích xuất nội dung slide (.pptx), gồm tiêu đề, bullet, bảng và speaker notes theo đúng thứ tự slide."""
    try:
        slide_entries: list[tuple[int, str]] = []
        full_blocks: list[str] = []
        with zipfile.ZipFile(file_path, "r") as zf:
            names = set(zf.namelist())
            slide_files = [n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)]
            slide_files.sort(key=lambda p: int(re.search(r"(\d+)\.xml$", p).group(1)))

            for slide_idx, slide_name in enumerate(slide_files, 1):
                m_num = re.search(r"(\d+)\.xml$", slide_name)
                slide_num = int(m_num.group(1)) if m_num else slide_idx
                root = ET.fromstring(zf.read(slide_name))

                title_text = ""
                body_lines: list[str] = []
                sp_tree = root.find(".//{*}spTree")
                shapes = list(sp_tree) if sp_tree is not None else []
                for elem in shapes:
                    tag = elem.tag.rsplit("}", 1)[-1]
                    if tag == "sp":
                        ph = elem.find(".//{*}ph")
                        ph_type = ph.attrib.get("type", "").lower() if ph is not None else ""
                        paras = _parse_pptx_xml_paragraphs(elem)
                        if not paras:
                            continue
                        if ph_type in ("title", "ctrtitle") and not title_text:
                            title_text = " ".join(paras).strip()
                        else:
                            body_lines.extend(paras)
                    elif tag == "graphicFrame":
                        for tbl_el in elem.findall(".//{*}tbl"):
                            for row_el in tbl_el.findall(".//{*}tr"):
                                cells = [
                                    " ".join(_parse_pptx_xml_paragraphs(tc_el)).strip()
                                    for tc_el in row_el.findall(".//{*}tc")
                                ]
                                cells = [c for c in cells if c]
                                if cells:
                                    body_lines.append("| " + " | ".join(cells) + " |")

                rels_path = f"ppt/slides/_rels/{posixpath.basename(slide_name)}.rels"
                notes_lines: list[str] = []
                if rels_path in names:
                    try:
                        rels_root = ET.fromstring(zf.read(rels_path))
                        for rel in rels_root:
                            if rel.attrib.get("Type", "").endswith("/notesSlide"):
                                target = rel.attrib.get("Target", "")
                                resolved_note = posixpath.normpath(posixpath.join("ppt/slides", target))
                                if resolved_note in names:
                                    note_root = ET.fromstring(zf.read(resolved_note))
                                    for np in _parse_pptx_xml_paragraphs(note_root):
                                        if not re.fullmatch(r"\d{1,4}", np):
                                            notes_lines.append(np)
                    except Exception:
                        pass

                slide_parts: list[str] = []
                heading = f"# Slide {slide_num}: {title_text}" if title_text else f"# Slide {slide_num}"
                if body_lines or title_text or notes_lines:
                    slide_parts.append(heading)
                    slide_parts.extend(body_lines)
                    if notes_lines:
                        slide_parts.append("Ghi chú bài giảng: " + " ".join(notes_lines))
                    slide_text = "\n".join(slide_parts).strip()
                    full_blocks.append(slide_text)
                    slide_entries.append((slide_num, slide_text))

        return "\n\n".join(full_blocks).strip(), slide_entries
    except Exception:
        if raise_on_error:
            raise
        return "", []


def extract_text_from_pptx(file_path: str, raise_on_error: bool = False) -> str:
    """Trích xuất văn bản từ bài giảng PowerPoint (.pptx)."""
    text, _ = extract_pptx_with_slides(file_path, raise_on_error=raise_on_error)
    return text
