"""Bộ tách bảng Rubric và bảng câu hỏi từ tài liệu Word (.docx)."""

from __future__ import annotations

import re
from typing import Callable, Optional

from app.services.extractor.common import (
    _extract_score,
    _make_criterion,
    _strip_score,
    _to_float,
)


def parse_table_block(
    rows: list[list[str]],
    current: Optional[dict],
    current_topic: str,
    new_item_fn: Callable[[Optional[str], str, str], dict],
    start_fn: Callable[[dict], None],
) -> None:
    """Xử lý 1 block bảng Word: bảng Rubric, bảng Câu hỏi, hoặc bảng nội dung bổ sung."""
    header = " ".join(rows[0]).lower()
    is_rubric_table = (current is not None and current["mode"] == "rubric") or (
        current is not None and ("tiêu chí" in header or "điểm" in header) and "câu hỏi" not in header
    )
    is_question_table = any(k in header for k in ["câu hỏi", "nội dung", "đề bài", "question"])

    if is_rubric_table and current is not None:
        current["mode"] = "rubric"
        for r_idx, row in enumerate(rows):
            joined = " ".join(row).lower()
            numeric_cells = [
                c
                for c in row
                if re.fullmatch(r"\d{1,2}(?:[.,]\d{1,2})?\s*(?:đ|điểm)?", c.strip(), re.I)
            ]
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
        return

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
            item = new_item_fn(code, current_topic, content)
            if cell(c_answer):
                item["answer_lines"].append(cell(c_answer))
            if cell(c_rubric):
                for part in re.split(r"[;\n]|(?<=\d[đ\)])\s*,", cell(c_rubric)):
                    crit = _make_criterion(part, _extract_score(part))
                    if crit:
                        item["criteria"].append(crit)
            start_fn(item)
        return

    for row in rows:
        text = " | ".join(c for c in row if c)
        if current is None:
            continue
        if current["mode"] == "answer":
            current["answer_lines"].append(text)
        elif current["mode"] == "content":
            current["content_lines"].append(text)
