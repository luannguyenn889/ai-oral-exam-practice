export const environment = {
  production: false,
  // AuthService gọi backend thật; apiBaseUrl cần trỏ tới Spring Boot.
  apiBaseUrl: 'http://localhost:8080/api',
  // Chỉ các API nghiệp vụ luyện tập còn dùng mock ở giai đoạn hiện tại.
  useMock: true,
  googleClientId: '',
};
