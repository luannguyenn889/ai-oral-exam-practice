describe('08 - Instructor Review Modal, Knowledge Gap Analytics & Admin Dashboard', () => {
  beforeEach(() => {
    cy.stubBackendApis();
    cy.stubAiServiceApis();
  });

  it('giảng viên mở modal rà soát bài làm, chốt điểm và xem thống kê lỗ hổng kiến thức', () => {
    cy.visit('/instructor/student-history', {
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
    cy.wait('@getInstructorPracticeRecords');

    cy.contains('Nguyễn Văn Sinh Viên').should('be.visible');
    cy.contains('button', /Xem chi tiết & Duyệt|Xem & Cập nhật/i)
      .first()
      .click();

    cy.get('#review-score').scrollIntoView().should('be.visible').clear().type('9');
    cy.contains('button', /Lưu|Chốt điểm/i).click();
    cy.wait('@reviewPracticeRecord');

    cy.visit('/instructor/analytics');
    cy.wait('@getInstructorPracticeRecords');
    cy.contains(/Thống kê lỗ hổng kiến thức/i).should('be.visible');
    cy.contains('1 lượt').should('be.visible');
  });

  it('quản trị viên xem được trạng thái AI Service trên Admin Dashboard', () => {
    cy.visit('/admin/dashboard', {
      onBeforeLoad(win) {
        win.localStorage.setItem(
          'oral_exam_user',
          JSON.stringify({
            id: 'admin-e2e-1',
            name: 'Quản trị Hệ thống',
            email: 'admin.e2e@qnu.edu.vn',
            role: 'admin',
            hasPassword: true,
          }),
        );
        win.localStorage.setItem('oral_exam_access_token', 'cypress-token-admin');
      },
    });

    cy.wait('@aiHealth');
    cy.contains(/AI Service \(ai-service v1\.0\.0\) đang hoạt động ổn định/i).should('be.visible');
  });
});
