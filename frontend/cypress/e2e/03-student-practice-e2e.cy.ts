describe('03 - Student 3-Step Oral Practice Flow (Record -> Transcript -> Result)', () => {
  beforeEach(() => {
    cy.stubBackendApis();
    cy.stubAiServiceApis();
  });

  it('hoàn thành đủ 3 bước: Ghi âm (có Xóa & Thu lại) -> Xác nhận Transcript -> Xem kết quả chấm AI', () => {
    cy.visit('/student/practice/q-waterfall-1', {
      onBeforeLoad(win) {
        const user = {
          id: 'stu-e2e-1',
          name: 'Nguyễn Văn Sinh Viên',
          email: 'student.e2e@qnu.edu.vn',
          role: 'student',
          studentCode: '4551050001',
          department: 'Công nghệ thông tin',
          hasPassword: true,
        };
        win.localStorage.setItem('oral_exam_user', JSON.stringify(user));
        win.localStorage.setItem('oral_exam_access_token', 'cypress-token-student');
      },
    });
    cy.mockMicrophone();
    cy.wait('@getQuestion');

    // Bước 1: Kiểm tra thông báo riêng tư & ghi âm
    cy.contains(/Quyền riêng tư/i).should('be.visible');
    cy.contains('button', /Bắt đầu thu âm bằng Microphone/i).click();
    cy.contains('button', /Dừng thu âm/i).should('be.visible');
    cy.wait(1100);
    cy.contains('button', /Dừng thu âm/i).click();

    // Kiểm tra nút Xóa & Thu lại
    cy.contains('button', /Xóa & Thu lại/i).click();
    cy.contains('button', /Bắt đầu thu âm bằng Microphone/i).should('be.visible');

    // Thu lại bằng Microphone giả lập (256 bytes) & nộp STT
    cy.contains('button', /Bắt đầu thu âm bằng Microphone/i).click();
    cy.wait(300);
    cy.contains('button', /Dừng thu âm/i).click();
    cy.contains('button', /Nộp âm thanh & Chuyển thành văn bản/i).click();

    cy.wait('@sttUpload');
    cy.url().should('include', '/student/sessions/');
    cy.url().should('include', '/transcript');

    // Bước 2: Xem & sửa Transcript -> gửi chấm Hybrid RAG
    cy.get('#transcriptEditor').should('contain.value', 'Mô hình thác nước');
    cy.get('#transcriptEditor').type(' Phù hợp dự án ít thay đổi.');
    cy.contains('button', /Xác nhận nội dung & Chấm điểm với Hybrid RAG/i).click();

    cy.wait('@evaluateAnswer');
    cy.url().should('include', '/result');

    // Bước 3: Kiểm tra kết quả chấm điểm & dẫn chứng RAG
    cy.contains('8.5').should('be.visible');
    cy.contains(/Sinh viên trả lời đúng trọng tâm/i).should('be.visible');
  });
});
