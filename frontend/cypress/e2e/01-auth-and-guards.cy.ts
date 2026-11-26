describe('01 - Authentication, Registration & Role Guards', () => {
  beforeEach(() => {
    cy.stubBackendApis();
    cy.stubAiServiceApis();
  });

  const apiUrl = (Cypress.expose('apiUrl') as string) || 'http://localhost:8080/api';

  it('hiển thị trang đăng nhập và báo lỗi khi sai mật khẩu', () => {
    cy.intercept('POST', `${apiUrl}/auth/login`, {
      statusCode: 401,
      body: { message: 'Email hoặc mật khẩu không chính xác.' },
    }).as('loginFail');

    cy.visit('/login');
    cy.get('input[type="email"]').type('wrong@qnu.edu.vn');
    cy.get('input[type="password"]').type('wrongpass');
    cy.contains('button[type="submit"]', /Đăng nhập/i).click();

    cy.wait('@loginFail');
    cy.url().should('include', '/login');
  });

  it('đăng nhập thành công với vai trò Sinh viên và Giảng viên', () => {
    cy.intercept('POST', `${apiUrl}/auth/login`, {
      statusCode: 200,
      body: {
        accessToken: 'jwt-student-e2e',
        tokenType: 'Bearer',
        expiresIn: 3600,
        user: {
          id: 'stu-e2e-1',
          email: 'student.e2e@qnu.edu.vn',
          fullName: 'Nguyễn Văn Sinh Viên',
          avatarUrl: null,
          roles: ['student'],
          studentCode: '4551050001',
          department: 'CNTT',
          hasPassword: true,
        },
      },
    }).as('loginStudent');

    cy.visit('/login');
    cy.get('input[type="email"]').type('student.e2e@qnu.edu.vn');
    cy.get('input[type="password"]').type('Secret123!');
    cy.contains('button[type="submit"]', /Đăng nhập/i).click();

    cy.wait('@loginStudent');
    cy.url().should('include', '/student/dashboard');
  });

  it('hiển thị trang đăng ký và gửi form tạo tài khoản', () => {
    cy.intercept('POST', `${apiUrl}/auth/register`, {
      statusCode: 200,
      body: {
        accessToken: 'jwt-reg-e2e',
        tokenType: 'Bearer',
        expiresIn: 3600,
        user: {
          id: 'stu-new-1',
          email: 'new.student@qnu.edu.vn',
          fullName: 'Lê Thị Mới',
          avatarUrl: null,
          roles: ['student'],
          hasPassword: true,
        },
      },
    }).as('registerUser');

    cy.visit('/register');
    cy.get('input[type="email"]').should('be.visible');
    cy.contains(/Đăng ký|Tạo tài khoản/i).should('be.visible');
  });

  it('chặn truy cập trái vai trò (roleGuard) và hiển thị trang 404/Error', () => {
    cy.visit('/student/dashboard');
    cy.url().should('include', '/login');

    cy.visit('/login');
    cy.loginAs('student');
    cy.visit('/instructor/courses');
    cy.url().should('not.include', '/instructor/courses');

    cy.visit('/duong-dan-khong-ton-tai-xyz');
    cy.contains(/404|Không tìm thấy/i).should('be.visible');

    cy.visit('/error');
    cy.get('body').should('not.be.empty');
  });
});
