describe('02 - Student Dashboard, Course Bank & Profile', () => {
  beforeEach(() => {
    cy.stubBackendApis();
    cy.stubAiServiceApis();
    cy.visit('/login');
    cy.loginAs('student');
  });

  it('hiển thị Dashboard sinh viên với KPI cá nhân và biểu đồ xu hướng', () => {
    cy.visit('/student/dashboard');
    cy.wait('@getCourses');
    cy.wait('@getMyPracticeRecords');
    cy.contains(/Nguyễn Văn Sinh Viên|Bảng điều khiển|Tổng quan/i).should('be.visible');
    cy.contains('8.5').should('be.visible');
  });

  it('chọn học phần và lọc danh sách câu hỏi trong ngân hàng đề', () => {
    cy.visit('/student/courses');
    cy.wait('@getCourses');
    cy.contains('IT2030').should('be.visible');
    cy.contains('Công nghệ Phần mềm').should('be.visible');

    cy.visit('/student/courses/course-it2030/questions');
    cy.wait('@getCourseQuestions');
    cy.contains('Mô hình thác nước (Waterfall)').should('be.visible');
    cy.contains('Vai trò trong Scrum').should('be.visible');
  });

  it('xem được trang hồ sơ cá nhân sinh viên', () => {
    cy.visit('/student/profile');
    cy.wait('@getMe');
    cy.contains(/4551050001|Nguyễn Văn Sinh Viên/i).should('be.visible');
  });
});
