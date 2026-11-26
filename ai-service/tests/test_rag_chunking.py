"""Kiểm thử 3 chiến lược chia đoạn RAG: recursive (mặc định), semantic và legacy (cách cũ)."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import docx

AI_SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from app.services import rag_service  # noqa: E402


SAMPLE_DOC = """Chương 1. Tổng quan về Công nghệ Phần mềm
Công nghệ phần mềm là ngành kỹ thuật nghiên cứu quy trình, phương pháp và công cụ xây dựng phần mềm chất lượng cao. Mục tiêu cốt lõi là đảm bảo sản phẩm đúng yêu cầu, đúng tiến độ và dễ bảo trì lâu dài.

Chương 2. Mô hình Thác nước (Waterfall)
Mô hình Thác nước là mô hình phát triển phần mềm tuần tự, tuyến tính qua các giai đoạn cố định. Giai đoạn sau chỉ bắt đầu khi giai đoạn trước đã hoàn tất và được nghiệm thu đầy đủ.
Các giai đoạn chính bao gồm: Thu thập yêu cầu, Phân tích thiết kế, Lập trình, Kiểm thử, Triển khai và Bảo trì. Ưu điểm là dễ quản lý, tài liệu hóa đầy đủ. Nhược điểm là kém linh hoạt khi yêu cầu thay đổi giữa chừng.
"""


def test_legacy_chunking_preserved() -> None:
    chunks = rag_service.chunk_text(
        SAMPLE_DOC,
        source_name="giao_trinh.docx",
        course_id="IT2030",
        strategy="legacy",
    )
    assert len(chunks) >= 1
    assert all(c["course_id"] == "IT2030" for c in chunks)
    # Cách cũ không chèn tiền tố [Chương ...]
    assert not chunks[0]["text"].startswith("[Chương 1")


def test_recursive_chunking_heading_aware() -> None:
    chunks = rag_service.chunk_text(
        SAMPLE_DOC,
        source_name="giao_trinh.docx",
        course_id="IT2030",
        strategy="recursive",
    )
    assert len(chunks) == 2, f"Expected 2 section chunks, got {len(chunks)}: {chunks}"
    assert chunks[0]["section_title"] == "Chương 1. Tổng quan về Công nghệ Phần mềm"
    assert chunks[0]["text"].startswith("[Chương 1. Tổng quan về Công nghệ Phần mềm]\n")
    assert "Thác nước" not in chunks[0]["text"]
    assert chunks[1]["section_title"] == "Chương 2. Mô hình Thác nước (Waterfall)"
    assert chunks[1]["text"].startswith("[Chương 2. Mô hình Thác nước (Waterfall)]\n")


def test_semantic_chunking_splits_on_topic_shift() -> None:
    # Tạo một mục văn bản dài viết liền mạch gồm 2 chủ đề khác hẳn nhau (> 950 ký tự)
    topic_a = [
        f"Câu {i} bàn chuyên sâu về kiến trúc cơ sở dữ liệu quan hệ, chuẩn hóa lược đồ và giao dịch ACID trong hệ quản trị SQL."
        for i in range(1, 6)
    ]
    topic_b = [
        f"Câu {i} trình bày về thuật toán học máy không giám sát, phân cụm K-Means và mạng nơ-ron tích chập trong thị giác máy tính."
        for i in range(6, 11)
    ]
    long_prose = "Chương 3. Kiến thức tổng hợp\n" + " ".join(topic_a + topic_b)

    def fake_embed(texts, task="document", provider=None):
        # 5 câu đầu gần [1, 0], 5 câu sau gần [0, 1] -> cosine similarity tụt về 0 đúng điểm chuyển chủ đề
        vecs = []
        for t in texts:
            if "ACID" in t:
                vecs.append([1.0, 0.0])
            else:
                vecs.append([0.0, 1.0])
        return vecs

    with patch.object(rag_service, "embed_texts", side_effect=fake_embed):
        chunks = rag_service.chunk_text(
            long_prose,
            source_name="lien_mach.txt",
            course_id="IT2030",
            strategy="semantic",
        )

    assert len(chunks) == 2, f"Expected 2 semantic chunks at topic shift, got {len(chunks)}"
    assert "ACID" in chunks[0]["text"] and "K-Means" not in chunks[0]["text"]
    assert "K-Means" in chunks[1]["text"] and "ACID" not in chunks[1]["text"]
    assert chunks[0]["text"].startswith("[Chương 3. Kiến thức tổng hợp]\n")


def test_pdf_reflow_and_numbered_list() -> None:
    pdf_wrapped = (
        "Chapter 3 | Agile software development\n"
        "Scrum master is a facilitator who arranges daily meetings and com-\n"
        "municates with customers outside the team. Everyone participates in\n"
        "this short-term planning. Rising and Janoff (2000) list advantages:\n"
        "1. The product is broken down into manageable chunks.\n"
        "2. Progress is visible to all stakeholders."
    )
    chunks = rag_service.chunk_text(
        pdf_wrapped,
        source_name="sommerville.pdf",
        course_id="SOFTWARE IT",
        strategy="recursive",
    )
    assert len(chunks) == 1
    assert "communicates" in chunks[0]["text"]
    assert "com-\nmunicates" not in chunks[0]["text"]
    assert "1. The product is broken down into manageable chunks." in chunks[0]["text"]

    # Trang chỉ có tiêu đề lặp lại + số trang "77" không được tạo thành chunk rác
    page_num_noise = pdf_wrapped + "\nChapter 3 | Key points\n77\n"
    for strat in ("recursive", "semantic"):
        res = rag_service.chunk_text(
            page_num_noise,
            source_name="sommerville.pdf",
            course_id="SOFTWARE IT",
            strategy=strat,
        )
        assert all("77" != c["text"].splitlines()[-1].strip() for c in res)

    # Dòng liệt kê dài bắt đầu bằng "5. It is..." không bị nhận nhầm thành tiêu đề mục
    numbered_list_doc = (
        "2.3.6 Extreme Programming and Agile Processes\n"
        "Waterfall has several limitations in practice:\n"
        "5. It is a document-driven process that requires formal documents at the end\n"
        "of each phase. Despite these limitations, the waterfall model has been widely used."
    )
    list_chunks = rag_service.chunk_text(
        numbered_list_doc,
        source_name="concise.pdf",
        course_id="SOFTWARE IT",
        strategy="recursive",
    )
    assert len(list_chunks) == 1
    assert list_chunks[0]["section_title"] == "2.3.6 Extreme Programming and Agile Processes"
    assert "5. It is a document-driven process that requires formal documents at the end of each phase." in list_chunks[0]["text"]


def test_hierarchical_breadcrumb_stack() -> None:
    doc = """Chương 2. Các mô hình phát triển
2.1 Mô hình Thác nước
Mô hình Thác nước phát triển tuần tự qua các pha cố định và yêu cầu tài liệu hóa đầy đủ ở từng giai đoạn.
2.1.1 Ưu và nhược điểm
Ưu điểm là dễ quản lý tiến độ và phân chia vai trò rõ ràng; nhược điểm là rất khó thay đổi yêu cầu ở giai đoạn sau.
Chương 3. Phát triển Agile
Agile tập trung vào chuyển giao phần mềm hoạt động thường xuyên và thích ứng nhanh với thay đổi của khách hàng.
"""
    chunks = rag_service.chunk_text(
        doc,
        source_name="giao_trinh_vn.txt",
        course_id="IT2030",
        strategy="recursive",
    )
    assert len(chunks) == 3, f"Expected 3 hierarchical sections, got {len(chunks)}: {chunks}"
    assert chunks[0]["section_title"] == "Chương 2. Các mô hình phát triển > 2.1 Mô hình Thác nước"
    assert (
        chunks[1]["section_title"]
        == "Chương 2. Các mô hình phát triển > 2.1 Mô hình Thác nước > 2.1.1 Ưu và nhược điểm"
    )
    assert chunks[2]["section_title"] == "Chương 3. Phát triển Agile"
    assert "Chương 2" not in chunks[2]["section_title"]


def test_generic_pdf_running_header_footer_and_page_stitch() -> None:
    pages = [
        "Giáo trình Công nghệ Phần mềm\nChương 1. Tổng quan\nCông nghệ phần mềm nghiên cứu các phương pháp kỹ thuật để xây dựng phần mềm chất lượng cao và dễ\nTrang 1 / 5",
        "Giáo trình Công nghệ Phần mềm\nbảo trì trong suốt vòng đời dự án. Các nguyên lý kỹ thuật giúp kiểm soát chi phí và rủi ro hiệu quả.\nTrang 2 / 5",
        "Giáo trình Công nghệ Phần mềm\nChương 2. Quy trình phần mềm\nQuy trình phần mềm bao gồm đặc tả, thiết kế, phát triển, kiểm chứng và tiến hóa hệ thống.\nTrang 3 / 5",
        "Giáo trình Công nghệ Phần mềm\nCác hoạt động hỗ trợ gồm quản lý cấu hình, đảm bảo chất lượng và quản lý dự án phần mềm.\nTrang 4 / 5",
        "Giáo trình Công nghệ Phần mềm\nMỗi tổ chức có thể điều chỉnh quy trình phù hợp với quy mô đội ngũ và độ phức tạp sản phẩm.\nTrang 5 / 5",
    ]
    cleaned = rag_service._clean_pdf_pages(pages)
    assert "Trang 2 / 5" not in cleaned
    assert "Trang 5 / 5" not in cleaned
    assert cleaned.count("Giáo trình Công nghệ Phần mềm") <= 1
    # Câu chảy qua trang 1 -> trang 2 được nối liền mạch
    assert "dễ\nbảo trì" in cleaned or "dễ bảo trì" in cleaned

    chunks = rag_service.chunk_text(
        cleaned,
        source_name="bai_giang.pdf",
        course_id="IT2030",
        strategy="recursive",
    )
    assert any("dễ bảo trì trong suốt vòng đời dự án." in c["text"] for c in chunks)


def test_docx_interleaved_table_and_header_repeat() -> None:
    doc = docx.Document()
    doc.add_heading("Chương 2. So sánh các mô hình", level=1)
    doc.add_heading("So sánh Waterfall và Agile", level=2)
    doc.add_paragraph("Bảng dưới đây tổng hợp các tiêu chí so sánh cốt lõi giữa hai mô hình phát triển phần mềm.")

    tbl = doc.add_table(rows=9, cols=3)
    headers = ["Tiêu chí so sánh", "Mô hình Waterfall", "Mô hình Agile"]
    for j, h in enumerate(headers):
        tbl.rows[0].cells[j].text = h
    for i in range(1, 9):
        tbl.rows[i].cells[0].text = f"Tiêu chí chi tiết số {i} về quy trình"
        tbl.rows[i].cells[1].text = f"Waterfall xử lý tuần tự cố định theo kế hoạch ban đầu cho mục {i}"
        tbl.rows[i].cells[2].text = f"Agile xử lý lặp tăng trưởng linh hoạt theo từng Sprint cho mục {i}"

    doc.add_heading("Chương 3. Kiểm thử phần mềm", level=1)
    doc.add_paragraph("Kiểm thử phần mềm giúp phát hiện lỗi sớm và xác minh hệ thống đáp ứng đúng yêu cầu nghiệp vụ.")

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        doc.save(tmp_path)
        extracted = rag_service.extract_text_from_docx(tmp_path)
        chunks = rag_service.chunk_text_recursive(
            extracted,
            source_name="so_sanh.docx",
            course_id="IT2030",
            chunk_size=550,
            overlap=80,
        )
        table_chunks = [c for c in chunks if "Tiêu chí chi tiết số" in c["text"]]
        assert len(table_chunks) >= 2, f"Expected long table split into >=2 chunks, got {len(table_chunks)}"
        for tc in table_chunks:
            assert tc["section_title"] == "Chương 2. So sánh các mô hình > So sánh Waterfall và Agile"
            assert "| Tiêu chí so sánh | Mô hình Waterfall | Mô hình Agile |" in tc["text"]

        ch3_chunks = [c for c in chunks if "Kiểm thử phần mềm giúp" in c["text"]]
        assert len(ch3_chunks) == 1
        assert ch3_chunks[0]["section_title"] == "Chương 3. Kiểm thử phần mềm"
        assert "Tiêu chí chi tiết số" not in ch3_chunks[0]["text"]
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_low_value_rag_chunk_filtering_at_index_and_query() -> None:
    index_noise = (
        "Barnes, J. P., 336, 339 Basili, V. R., 674, 679, 712, 730 Bass, B. M., 606, 617 "
        "Bass, L., 149, 150, 154, 173, 174 Bate, R., 722, 731 Baumer, D., 432, 450 "
        "Beck, K., 57, 59, 64, 78, 80, 91, 117, 183, 204, 221, 232, 259, 611, 617, 631, 649"
    )
    refs_noise = (
        "Poole, G. and Huisman, J. W. (2001). 'Using Extreme Programming in a Maintenance Environment'. "
        "IEEE Software, 18 (6), 42–50. Rising, L. and Janoff, N. S. (2000). 'The Scrum Software Development "
        "Process for Small Teams'. IEEE Software, 17 (4), 26–32. Schwaber, K. (2004). Agile Project "
        "Management with Scrum. Schwaber, K. and Beedle, M. (2001). Agile Software Development with Scrum."
    )
    refs_ieee_noise = (
        "[MTTF = > 8.6 Summary]\n"
        "Software engineering. IEEE Transactions on Computers, 25(12), Dec. 1976.\n"
        "[11] B. Boehm. Tutorial: software risk management. IEEE Computer Society, 1989. "
        "[12] B. W. Boehm. Software Engineering Economics. Prentice Hall, Englewood Cliffs, NJ, 1981. "
        "[13] B. W. Boehm. Software engineering economics. IEEE Transactions on Software Engineering, 10(1):135–152, Jan. 1984. "
        "[14] B. W. Boehm. Improving software productivity. IEEE Computer, pages 43–57, Sept. 1987."
    )
    toc_noise = (
        "Chapter 1. Introduction .......................... 12\n"
        "Chapter 2. Software Processes .................... 34\n"
        "Chapter 3. Agile Software Development ............ 58\n"
    )
    valid_prose = (
        "[Chapter 3 | Agile software development > 3.1 Agile methods]\n"
        "Agile software development methods focus on iterative delivery, rapid feedback, and close "
        "collaboration with customers rather than heavy upfront specification and rigid documentation."
    )

    assert rag_service.is_low_value_rag_chunk(index_noise) is True
    assert rag_service.is_low_value_rag_chunk(refs_noise) is True
    assert rag_service.is_low_value_rag_chunk(refs_ieee_noise) is True
    assert rag_service.is_low_value_rag_chunk(toc_noise) is True
    assert rag_service.is_low_value_rag_chunk(valid_prose) is False

    mixed_doc = (
        "# Chapter 3. Agile software development\n"
        "Agile software development methods focus on iterative delivery and continuous customer collaboration.\n\n"
        "# Index\n"
        f"{index_noise}\n\n"
        "# References\n"
        f"{refs_noise}\n"
    )
    chunks = rag_service.chunk_text_recursive(
        mixed_doc,
        source_name="sommerville.pdf",
        course_id="SE_FILTER",
    )
    assert len(chunks) >= 1
    assert all("Barnes, J. P., 336" not in c["text"] for c in chunks)
    assert all("Poole, G. and Huisman" not in c["text"] for c in chunks)
    assert any("iterative delivery" in c["text"] for c in chunks)

    # Kiểm thử lọc chunk rác ngay lúc truy vấn (kể cả trên kho vector đã index từ trước)
    from unittest.mock import patch
    from app.services.rag import store as rag_store

    class _MockColl:
        def get(self, where=None, include=None):
            return {"ids": ["c1", "c2", "c3"]}

        def query(self, query_embeddings, n_results, where=None, include=None):
            return {
                "ids": [["c1", "c2", "c3"]],
                "documents": [[index_noise, refs_noise, valid_prose]],
                "metadatas": [[
                    {"source": "sommerville.pdf", "course_id": "SE_FILTER", "index": 1, "section_title": ""},
                    {"source": "sommerville.pdf", "course_id": "SE_FILTER", "index": 2, "section_title": ""},
                    {"source": "sommerville.pdf", "course_id": "SE_FILTER", "index": 3, "section_title": "Chapter 3 > 3.1 Agile methods"},
                ]],
                "distances": [[0.15, 0.16, 0.22]],
            }

    with (
        patch.object(rag_store, "get_chroma_collection", return_value=_MockColl()),
        patch.object(rag_store, "embed_texts", return_value=[[0.1] * 8]),
        patch.object(rag_store, "get_bm25_index", return_value=(None, [])),
    ):
        results = rag_store.query_relevant_chunks(
            query_text="Trình bày về Agile software development?",
            course_id="SE_FILTER",
            top_k=3,
            search_mode="hybrid",
            use_rerank=False,
        )
        assert len(results) == 1
        assert results[0]["id"] == "c3"
        assert "iterative delivery" in results[0]["text"]


def test_multiformat_noise_filter_and_heading_validation() -> None:
    # 1. Tầng 1: Không nhận nhầm ISBN / Index / Ký hiệu / Code comment thành tiêu đề mục (tránh bẩn breadcrumb)
    dirty_headings_doc = (
        "ISBN: 978-1-84800-301-9\n"
        "COCOMO, 71\n"
        "IEEE\n"
        "// APP-SYSTEM/AUTH/RBAC/USER_ROLE\n"
        "2.3.1 Waterfall Model\n"
        "The waterfall model organizes software development into sequential phases: "
        "requirements analysis, system design, implementation, testing, deployment, and maintenance.\n\n"
        "FURTHER RE ADING\n"
        "Bowen, J. P. and Hinchey, M. G., IEEE Computer, 39 (1), January 2006. http://dx.doi.org/10.1109/MC.2006.35.\n"
        "Kitchenham, R. Jeffrey, IEEE Software, 24 (2), March 2007. http://dx.doi.org/10.1109/MS.2007.49."
    )
    cleaned_chunks = rag_service.chunk_text(
        dirty_headings_doc,
        source_name="concise.pdf",
        course_id="SE_MULTI",
        strategy="recursive",
    )
    assert len(cleaned_chunks) == 1
    assert cleaned_chunks[0]["section_title"] == "2.3.1 Waterfall Model"
    assert "ISBN" not in cleaned_chunks[0]["text"]
    assert "COCOMO" not in cleaned_chunks[0]["text"]
    assert "IEEE" not in cleaned_chunks[0]["section_title"]

    # 2. Tầng 2: Bắt đa định dạng rác (Further Reading + DOI, Copyright CIP, References tiếng Việt, Index ngắn, TOC không chấm)
    further_reading_doi = (
        "[Chapter 24 | Quality management]\n"
        "Kitchenham, R. Jeffrey and C. Connaughton, IEEE Software, 24 (2), March-April 2007.) "
        "http://dx.doi.org/10.1109/MS.2007.49. 'The Case for Quantitative Project Management'. "
        "Bowen, J. P. and M. G. Hinchey, IEEE Computer, 39 (1), January 2006.) http://dx.doi.org/10.1109/MC.2006.35."
    )
    copyright_cip = (
        "Library of Congress Cataloging-in-Publication Data\n"
        "Sommerville, Ian\nSoftware engineering / Ian Sommerville. — 9th ed.\np. cm.\n"
        "All rights reserved. No part of this publication may be reproduced."
    )
    vn_references = (
        "TÀI LIỆU THAM KHẢO\n"
        "[1] Nguyễn Văn A (2020), Kỹ thuật phần mềm, NXB Giáo dục, tr. 45-60.\n"
        "[2] Trần Thị B (2021), Phân tích thiết kế hệ thống, NXB Khoa học và Kỹ thuật, tr. 12-30."
    )
    short_index = "103 story cards and, 66, 67 success criteria and, 272–73 task cards and, 68, 69"
    tabular_toc = (
        "Chapter 1 Introduction      1\n"
        "Chapter 2 Software Processes      27\n"
        "Chapter 3 Agile Software Development      56\n"
        "Chapter 4 Requirements Engineering      82\n"
    )
    header_comment_noise = (
        "// Object: currentRole\n// Author: R. Looek\n// Creation date: 13/11/2009\n"
        "// © St Andrews University 2009\n// Modification history\n// Version 1.0"
    )

    for sample in (
        further_reading_doi,
        copyright_cip,
        vn_references,
        short_index,
        tabular_toc,
        header_comment_noise,
    ):
        prof = rag_service.compute_noise_profile(sample)
        assert prof["is_noise"] is True, f"Expected noise=True for {sample[:60]!r}, got {prof}"

    # 3. Bảo vệ nội dung hợp lệ: slide gạch đầu dòng ngắn, bảng DOCX, và code thật
    slide_bullets = (
        "[Chương 3 > 3.2 Quy trình Scrum]\n"
        "- Product Backlog chứa danh sách yêu cầu ưu tiên.\n"
        "- Sprint kéo dài từ 2 đến 4 tuần.\n"
        "- Daily Standup giúp nhóm đồng bộ tiến độ mỗi ngày."
    )
    real_code = (
        "[Chương 4 > 4.2 Cài đặt QuickSort]\n"
        "def quicksort(arr):\n"
        "    if len(arr) <= 1:\n"
        "        return arr\n"
        "    pivot = arr[len(arr) // 2]\n"
        "    return quicksort([x for x in arr if x < pivot])"
    )
    assert rag_service.compute_noise_profile(slide_bullets)["is_noise"] is False
    code_prof = rag_service.compute_noise_profile(real_code)
    assert code_prof["is_noise"] is False
    assert code_prof["noise_type"] == "code"


if __name__ == "__main__":
    test_legacy_chunking_preserved()
    test_recursive_chunking_heading_aware()
    test_semantic_chunking_splits_on_topic_shift()
    test_pdf_reflow_and_numbered_list()
    test_hierarchical_breadcrumb_stack()
    test_generic_pdf_running_header_footer_and_page_stitch()
    test_docx_interleaved_table_and_header_repeat()
    test_low_value_rag_chunk_filtering_at_index_and_query()
    test_multiformat_noise_filter_and_heading_validation()
    print(">>> ALL 9 RAG CHUNKING TESTS PASSED! <<<")
