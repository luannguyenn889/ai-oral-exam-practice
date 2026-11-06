"""Bộ kiểm thử hồi quy (Regression Test Suite) cho dịch vụ bóc tách câu hỏi & Rubric Word/Excel."""

import io
import os
import sys
from pathlib import Path

import docx
import openpyxl

AI_SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

# Đảm bảo test chạy nhanh, tất định (offline structure parser) không gọi mạng ngoài
os.environ["GEMINI_API_KEY"] = ""

from app.config import settings  # noqa: E402
from app.services.question_extractor_service import (  # noqa: E402
    _items_to_questions,
    _read_document_blocks,
    _structure_parse,
    extract_questions_from_file,
)

settings.gemini_api_key = ""


def test_phan3_freeform_with_rubric_and_table() -> None:
    """Kịch bản 1: Đề kiểu PHẦN 3 (1).docx - Câu hỏi không đánh chữ 'Câu', có câu kết bằng dấu chấm, kèm Rubric số & bảng."""
    doc = docx.Document()
    doc.add_paragraph("PHẦN 3. AGILE VÀ SCRUM")
    doc.add_paragraph("Agile là gì? Trình bày các đặc điểm cơ bản của phương pháp phát triển phần mềm Agile.")
    doc.add_paragraph("Tiêu chí chấm điểm (Rubric)")
    doc.add_paragraph("1. Nêu đúng khái niệm và Tuyên ngôn Agile (3đ)")
    doc.add_paragraph("2. Trình bày đầy đủ các đặc điểm cơ bản của Agile (4đ)")
    doc.add_paragraph("3. Phân tích ưu nhược điểm và lấy ví dụ thực tế (3đ)")

    doc.add_paragraph("Scrum là gì? Trình bày các vai trò, sự kiện và tạo phẩm trong Scrum.")
    doc.add_paragraph("Tiêu chí chấm điểm (Rubric)")
    doc.add_paragraph("1. Khái niệm Scrum và nguyên lý kiểm soát quy trình thực nghiệm (3đ)")
    doc.add_paragraph("2. Trình bày 3 vai trò: Product Owner, Scrum Master, Developers (4đ)")
    doc.add_paragraph("3. Trình bày các sự kiện và tạo phẩm chính trong Scrum (3đ)")

    doc.add_paragraph("Phân biệt sự khác nhau giữa mô hình Agile và mô hình Waterfall.")
    doc.add_paragraph("Đáp án tham chiếu:")
    doc.add_paragraph("- Waterfall phát triển tuần tự qua các pha cố định, khó thay đổi yêu cầu.")
    doc.add_paragraph("- Agile phát triển lặp và tăng trưởng, thích ứng nhanh với thay đổi.")
    doc.add_paragraph("Tiêu chí chấm điểm (Rubric)")
    tbl = doc.add_table(rows=4, cols=3)
    tbl.rows[0].cells[0].text = "Tiêu chí"
    tbl.rows[0].cells[1].text = "Mô tả"
    tbl.rows[0].cells[2].text = "Điểm"
    tbl.rows[1].cells[0].text = "Bản chất hai mô hình"
    tbl.rows[1].cells[1].text = "Nêu đúng nguyên lý tuần tự vs lặp tăng trưởng"
    tbl.rows[1].cells[2].text = "3.5"
    tbl.rows[2].cells[0].text = "Tiêu chí so sánh"
    tbl.rows[2].cells[1].text = "So sánh về yêu cầu, bàn giao, quản lý rủi ro"
    tbl.rows[2].cells[2].text = "4.5"
    tbl.rows[3].cells[0].text = "Ví dụ thực tế"
    tbl.rows[3].cells[1].text = "Nêu loại dự án phù hợp"
    tbl.rows[3].cells[2].text = "2.0"

    buf = io.BytesIO()
    doc.save(buf)
    res = extract_questions_from_file(buf.getvalue(), "PHẦN 3 (1).docx")
    assert res.total_detected == 3, f"Expected 3 questions, got {res.total_detected}"
    assert res.error_count == 0
    for q in res.questions:
        assert "Tiêu chí chấm điểm" not in q.content
        assert abs(q.total_score - 10.0) < 0.05


def test_word_auto_numbered_hierarchical_rubric() -> None:
    """Kịch bản 2: Rubric phân cấp dùng List Number & List Bullet tự động của Word (không có số '1.' trong text)."""
    doc = docx.Document()
    doc.add_paragraph("Kiến trúc phần mềm là gì? Nêu vai trò của kiến trúc.")
    doc.add_paragraph("Tiêu chí chấm điểm (Rubric):")
    doc.add_paragraph("Kiến thức chuyên môn (6đ)", style="List Number")
    doc.add_paragraph("Nêu đúng định nghĩa (2đ)", style="List Bullet")
    doc.add_paragraph("Phân tích thuộc tính chất lượng (4đ)", style="List Bullet")
    doc.add_paragraph("Kỹ năng trình bày (4đ)", style="List Number")
    doc.add_paragraph("Trả lời lưu loát (2đ)", style="List Bullet")
    doc.add_paragraph("Ví dụ thực tế (2đ)", style="List Bullet")

    buf = io.BytesIO()
    doc.save(buf)
    res = extract_questions_from_file(buf.getvalue(), "auto_list_rubric.docx")
    assert res.total_detected == 1
    q = res.questions[0]
    assert len(q.criteria) == 4, f"Expected 4 flattened sub-criteria, got {len(q.criteria)}: {q.criteria}"
    assert abs(q.total_score - 10.0) < 0.05, f"Expected 10.0 score, got {q.total_score}"
    assert q.criteria[0].name.startswith("[Kiến thức chuyên môn]")
    assert q.criteria[2].name.startswith("[Kỹ năng trình bày]")


def test_score_sum_reconciliation_for_plain_lines() -> None:
    """Kịch bản 3: Rubric cha - con viết cùng một kiểu dòng thường nhưng tổng điểm con khớp điểm cha (6 = 2 + 4)."""
    doc = docx.Document()
    doc.add_paragraph("Giải thích nguyên lý SOLID trong thiết kế hướng đối tượng.")
    doc.add_paragraph("Tiêu chí chấm điểm:")
    doc.add_paragraph("Nắm vững 5 nguyên lý SOLID (7đ)")
    doc.add_paragraph("Trình bày đúng SRP, OCP, LSP (3.5đ)")
    doc.add_paragraph("Trình bày đúng ISP, DIP (3.5đ)")
    doc.add_paragraph("Vận dụng thực tế (3đ)")
    doc.add_paragraph("Nêu được ví dụ code vi phạm và cách refactor (2đ)")
    doc.add_paragraph("Trả lời mạch lạc, rõ ràng (1đ)")

    buf = io.BytesIO()
    doc.save(buf)
    res = extract_questions_from_file(buf.getvalue(), "plain_hierarchy.docx")
    assert res.total_detected == 1
    q = res.questions[0]
    assert len(q.criteria) == 4
    assert abs(q.total_score - 10.0) < 0.05
    assert q.criteria[0].name.startswith("[Nắm vững 5 nguyên lý SOLID]")
    assert q.criteria[2].name.startswith("[Vận dụng thực tế]")


def test_percentage_rubric_scores() -> None:
    """Kịch bản 4: Rubric ghi thang điểm theo phần trăm (30%, 40%, 30%) tự quy đổi về thang 10."""
    doc = docx.Document()
    doc.add_paragraph("Trình bày quy trình kiểm thử phần mềm.")
    doc.add_paragraph("Rubric:")
    doc.add_paragraph("1. Nêu các giai đoạn kiểm thử (30%)")
    doc.add_paragraph("2. Phân tích từng mức độ Unit, Integration, System, Acceptance (40%)")
    doc.add_paragraph("3. Ví dụ thực tế (30%)")

    buf = io.BytesIO()
    doc.save(buf)
    res = extract_questions_from_file(buf.getvalue(), "pct_rubric.docx")
    q = res.questions[0]
    assert [c.max_score for c in q.criteria] == [3.0, 4.0, 3.0]
    assert abs(q.total_score - 10.0) < 0.05


def test_excel_preserves_hyphenated_terms() -> None:
    """Kịch bản 5: File Excel chứa từ ghép có dấu gạch ngang (Client-Server, UTF-8) không bị cắt đôi."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Mã câu", "Chủ đề", "Nội dung câu hỏi", "Đáp án mẫu", "Tiêu chí"])
    ws.append([
        "Q1",
        "Kiến trúc phần mềm",
        "So sánh mô hình Client-Server và Peer-to-Peer.",
        "Client-Server tập trung tại máy chủ; Peer-to-Peer phân tán ngang hàng.",
        "Nêu nguyên lý Client-Server (4đ); Nêu nguyên lý Peer-to-Peer (4đ); Ví dụ thực tế (2đ)",
    ])
    buf = io.BytesIO()
    wb.save(buf)

    res = extract_questions_from_file(buf.getvalue(), "template.xlsx")
    assert res.total_detected == 1
    q = res.questions[0]
    assert len(q.criteria) == 3, f"Expected 3 criteria, got {q.criteria}"
    assert "Client-Server" in q.criteria[0].name
    assert "Peer-to-Peer" in q.criteria[1].name
    assert abs(q.total_score - 10.0) < 0.05


def test_real_cnpm_docx() -> None:
    """Kịch bản 6: Tài liệu thực tế Bộ câu hỏi ôn tập CNPM.docx phải bóc đúng 27 câu."""
    cnpm_path = AI_SERVICE_ROOT / "data" / "documents" / "IT2030" / "Bộ câu hỏi ôn tập CNPM.docx"
    if not cnpm_path.exists():
        return
    blocks = _read_document_blocks(cnpm_path.read_bytes(), cnpm_path.name)
    items = _structure_parse(blocks)
    questions = _items_to_questions(items)
    assert len(questions) == 27, f"Expected 27 questions, got {len(questions)}"


if __name__ == "__main__":
    test_phan3_freeform_with_rubric_and_table()
    test_word_auto_numbered_hierarchical_rubric()
    test_score_sum_reconciliation_for_plain_lines()
    test_percentage_rubric_scores()
    test_excel_preserves_hyphenated_terms()
    test_real_cnpm_docx()
    print(">>> ALL 6 REGRESSION TEST SUITES PASSED! <<<")
