export const environment = {
  production: false,
  // AuthService gọi backend thật; apiBaseUrl cần trỏ tới Spring Boot.
  apiBaseUrl: 'http://localhost:8080/api',
  // Kết nối trực tiếp tới FastAPI AI Service (STT + Hybrid RAG + Rubric Grading)
  aiServiceUrl: 'http://localhost:8000',
  // Sử dụng kho câu hỏi từ BỘ ĐỀ THI.txt và gọi trực tiếp sang ai-service khi chấm/STT
  useMock: true,
  googleClientId: '569426721711-6ub3hgomi74b201otif6cpe3oq53s5fj.apps.googleusercontent.com',
};
