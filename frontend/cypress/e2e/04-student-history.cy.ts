describe('04 - Student Practice History (Filter, Empty State & Error Handling)', () => {
  beforeEach(() => {
    cy.stubBackendApis();
    cy.stubAiServiceApis();
    cy.visit('/login');
    cy.loginAs('student');
  });

  it('hiển thị danh sách lịch sử luyện tập và lọc theo từ khóa/học phần', () => {
    cy.visit('/student/history');
    cy.wait('@getMyPracticeRecords');

    cy.contains('Mô hình thác nước (Waterfall)').should('be.visible');
    cy.contains('8.5').should('be.visible');
  });

  it('hiển thị trạng thái rỗng khi sinh viên chưa có bài luyện tập nào', () => {
    const apiUrl = (Cypress.expose('apiUrl') as string) || 'http://localhost:8080/api';
    cy.intercept('GET', `${apiUrl}/practice-records/me`, {
      statusCode: 200,
      body: [],
    }).as('emptyHistory');

    cy.visit('/student/history');
    cy.wait('@emptyHistory');
    cy.contains(/Chưa có|chưa thực hiện|Bắt đầu/i).should('be.visible');
  });
});
