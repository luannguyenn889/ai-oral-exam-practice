describe('05 - Instructor Course Documents, RAG Config, Background Sync & Search', () => {
  beforeEach(() => {
    cy.stubBackendApis();
    cy.stubAiServiceApis();
  });

  it('đồng bộ cấu hình RAG (Embedding/Chunking/Rerank), khóa dropdown khi sync, khôi phục sau F5 và tìm thử RAG', () => {
    const aiUrl = (Cypress.expose('aiUrl') as string) || 'http://localhost:8000';
    const runningJob = {
      job_id: 'rag-job-e2e-1',
      course_id: 'IT2030',
      status: 'running',
      phase: 'embedding',
      percent: 45,
      message: 'Đang tạo vector (45/100 đoạn) — Sommerville.pdf',
      current_file: 'Sommerville - Software Engineering 9ed.pdf',
      processed_files: 0,
      total_files: 1,
      processed_chunks: 45,
      total_chunks: 100,
      embedding_provider: 'e5-small',
      chunking_strategy: 'recursive',
      elapsed_seconds: 12,
      result: null,
      error: null,
    };

    cy.visit('/instructor/courses/IT2030/documents', {
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

    cy.wait('@getRagStatus');

    // Đổi mô hình Rerank -> gọi PUT /config
    cy.get('select[aria-label="Chọn mô hình Cross-Encoder Rerank"]').select('minilm');
    cy.wait('@updateCourseRagConfig').its('request.body.reranker_provider').should('eq', 'minilm');

    // Tìm thử trong giáo trình
    cy.contains('button', /Tìm thử trong giáo trình/i).click();
    cy.wait('@ragSearch');
    cy.contains('Sommerville - Software Engineering 9ed.pdf').should('be.visible');
    cy.contains('The waterfall model takes the fundamental process activities').should('be.visible');

    // Bắt đầu đồng bộ chỉ mục nền -> khóa cả 3 dropdown & khôi phục sau F5
    cy.intercept('POST', `${aiUrl}/ai/rag/index/start`, {
      statusCode: 200,
      body: runningJob,
    }).as('startIndexJob');
    cy.intercept('GET', `${aiUrl}/ai/rag/index/jobs/rag-job-e2e-1`, {
      statusCode: 200,
      body: runningJob,
    }).as('pollIndexJob');
    cy.intercept('GET', `${aiUrl}/ai/rag/index/active*`, {
      statusCode: 200,
      body: runningJob,
    }).as('getActiveJobRunning');

    cy.contains('button', /Đồng bộ chỉ mục Server/i).click();
    cy.wait('@startIndexJob');

    cy.contains(/Đang đồng bộ & lập chỉ mục kho RAG.*45%/i).should('be.visible');
    cy.get('select[aria-label="Chọn mô hình Embedding thử nghiệm"]').should('be.disabled');
    cy.get('select[aria-label="Chọn chiến lược chia đoạn tài liệu"]').should('be.disabled');
    cy.get('select[aria-label="Chọn mô hình Cross-Encoder Rerank"]').should('be.disabled');

    // Reload trang (F5) -> tự khôi phục banner tiến trình
    cy.reload();
    cy.wait('@getActiveJobRunning');
    cy.contains(/Đang đồng bộ & lập chỉ mục kho RAG.*45%/i).should('be.visible');
  });
});
