describe('06 - Instructor Question Editor (HITL RAG Draft & Approval) & Import', () => {
  beforeEach(() => {
    cy.stubBackendApis();
    cy.stubAiServiceApis();
  });

  it('gợi ý đáp án từ RAG, lọc bỏ đoạn nhiễu, duyệt đáp án và lưu câu hỏi', () => {
    cy.visit('/instructor/questions/new?courseId=course-it2030', {
      onBeforeLoad(win) {
        win.localStorage.setItem(
          'oral_exam_user',
          JSON.stringify({
            id: 'inst-e2e-1',
            name: 'TS. Trần Giảng Viên',
            email: 'instructor.e2e@qnu.edu.vn',
            role: 'instructor',
            hasPassword: true,
          }),
        );
        win.localStorage.setItem('oral_exam_access_token', 'cypress-token-instructor');
      },
    });
    cy.wait('@getCourses');

    cy.get('input[name="title"]').type('Phân tích mô hình Thác nước');
    cy.get('textarea[name="content"]').type(
      'Trình bày các giai đoạn của mô hình Waterfall và khi nào nên áp dụng?',
    );

    // Gọi AI gợi ý đáp án từ RAG
    cy.contains('button', /AI gợi ý Đáp án từ giáo trình/i).click();
    cy.wait('@ragSuggestAnswer');

    cy.get('#sample-answer').should('contain.value', 'Mô hình thác nước gồm các pha tuần tự');
    cy.contains('Embedding: intfloat/multilingual-e5-small').should('be.visible');
    cy.contains('Rerank: BAAI/bge-reranker-v2-m3').should('be.visible');
    cy.contains('Tham chiếu giáo trình RAG (2/2 đoạn được chọn)').should('be.visible');

    // Bỏ chọn 1 đoạn và tạo lại từ 1 đoạn đã chọn
    cy.get('.rag-chunk-card input[type="checkbox"]').last().uncheck();
    cy.contains('button', /Tạo lại từ 1 đoạn đã chọn/i).click();
    cy.wait('@ragSuggestAnswer')
      .its('request.body.selected_chunk_ids')
      .should('have.length', 1);

    // Giảng viên xác nhận duyệt đáp án
    cy.contains('button', /Xác nhận & Duyệt đáp án/i).click();
    cy.contains(/Giảng viên đã duyệt/i).should('be.visible');

    // Lưu câu hỏi
    cy.contains('button', /Lưu câu hỏi/i).first().click();
    cy.wait('@saveQuestion');
  });

  it('hiển thị màn hình nhập câu hỏi hàng loạt từ DOCX/PDF', () => {
    cy.visit('/instructor/questions/import', {
      onBeforeLoad(win) {
        win.localStorage.setItem(
          'oral_exam_user',
          JSON.stringify({
            id: 'inst-e2e-1',
            name: 'TS. Trần Giảng Viên',
            email: 'instructor.e2e@qnu.edu.vn',
            role: 'instructor',
            hasPassword: true,
          }),
        );
        win.localStorage.setItem('oral_exam_access_token', 'cypress-token-instructor');
      },
    });
    cy.wait('@getCourses');
    cy.contains(/Nhập.*câu hỏi|Trích xuất/i).should('be.visible');
  });
});
