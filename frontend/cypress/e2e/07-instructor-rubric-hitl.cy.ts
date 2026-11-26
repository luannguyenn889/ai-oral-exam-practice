describe('07 - Instructor Rubric Editor (HITL AI Suggestion & Validation)', () => {
  beforeEach(() => {
    cy.stubBackendApis();
    cy.stubAiServiceApis();
  });

  it('gọi AI đề xuất tiêu chí Rubric thang 10.0đ, duyệt và lưu Rubric', () => {
    cy.visit('/instructor/questions/q-waterfall-1/rubric', {
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
    cy.wait('@getQuestion');

    cy.contains('button', /AI đề xuất tiêu chí Rubric/i).click();
    cy.wait('@ragSuggestAnswer').its('request.body.include_rubric').should('eq', true);

    cy.get('input')
      .filter((_, el) => (el as HTMLInputElement).value.includes('Trình bày đúng các giai đoạn Waterfall'))
      .should('have.length', 1);
    cy.contains('10').should('be.visible');

    cy.contains('button', /Lưu Rubric/i).click();
    cy.wait('@saveRubric');
  });
});
