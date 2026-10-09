# Sprint 2 — Nền tảng ứng dụng và nội dung

**Thời gian:** Tuần 3–4 · **Sprint Goal:** chạy được nền tảng FE/BE/AI và cung cấp luồng đăng nhập, học phần, câu hỏi đầu tiên bằng mock hoặc API thật.

## Việc theo thành viên

| Người | Công việc và đầu ra | NC |
|---|---|---:|
| TV1 | Chốt backlog/use case theo phản hồi giảng viên (2); chuẩn hóa bộ câu hỏi và đáp án mẫu cho một học phần (3); viết protocol nháp đo STT/chấm và biểu mẫu ghi nhận (2) | 7 |
| TV2 | Khởi tạo Angular, route/layout theo vai trò và môi trường config (3); xây danh sách học phần/câu hỏi với mock + loading/empty/error (3); review DTO với TV3 (1) | 7 |
| TV3 | Khởi tạo Spring Boot, cấu hình DB/migration và health endpoint (2); đăng nhập/role guard ở API (2); API CRUD học phần, câu hỏi, đáp án tham chiếu (3) | 7 |
| TV4 | Khởi tạo FastAPI, health/schema validation/logging không chứa dữ liệu nhạy cảm (2); dựng adapter interface cho STT/LLM và mock provider (3); viết hợp đồng và ví dụ lỗi AI service (2) | 7 |
| TV5 | Thiết lập môi trường dev, cấu hình chạy các service (2); tạo dữ liệu seed và kịch bản khói cho login/course/question (2); tích hợp một lát cắt FE–BE hoặc hoàn thiện mock adapter tùy API sẵn sàng (3) | 7 |

**Năng lực Scrum/chia tải:** cộng 1 NC/người cho Scrum events và review chéo; tổng 8 NC/người.

## Phụ thuộc và phối hợp

- TV1 chốt mẫu dữ liệu trước khi TV3 tạo seed và TV2 hoàn thiện màn hình.
- TV3 là nguồn chuẩn DTO nghiệp vụ; TV2 không gọi FastAPI trực tiếp.
- TV4 cung cấp mock adapter để các luồng khác chạy độc lập nếu chưa có nhà cung cấp AI.

## Sprint Review / điều kiện hoàn thành

- Có thể chạy các service theo hướng dẫn; Angular hiển thị học phần/câu hỏi mẫu.
- API backend áp dụng phân quyền ở server; route guard FE không được xem là bảo mật.
- Có ít nhất một kịch bản hợp lệ và một kịch bản lỗi được demo cho luồng nội dung.
- Backlog được cập nhật theo quyết định về repo, nhà cung cấp và dữ liệu.
