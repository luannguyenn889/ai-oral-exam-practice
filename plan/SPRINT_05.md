# Sprint 5 — Chấm AI, lịch sử và pilot

**Thời gian:** Tuần 9–10 · **Sprint Goal:** hoàn thành luồng chấm theo rubric, xem lại phiên và chạy pilot nhỏ để phát hiện vấn đề trước đánh giá chính thức.

## Việc theo thành viên

| Người | Công việc và đầu ra | NC |
|---|---|---:|
| TV1 | Khóa rubric/prompt và tập pilot theo hướng dẫn giảng viên (2); chấm bộ câu trả lời tham chiếu hoặc điều phối chấm (3); thiết kế form khảo sát khả dụng và quy tắc xử lý bất đồng (2) | 7 |
| TV2 | Xây màn kết quả theo tiêu chí/evidence/thiếu-sai/gợi ý (3); xây lịch sử phiên và trạng thái cần giảng viên xem lại (2); xử lý UX loading/error/retry và thông báo giới hạn AI (2) | 7 |
| TV3 | Lưu Evaluation, model/prompt/rubric version và human review (3); API lịch sử/chi tiết kết quả với phân quyền (2); validate tổng điểm, điểm tiêu chí, session ownership (2) | 7 |
| TV4 | Tích hợp đánh giá LLM theo schema rubric và evidence (3); xử lý output không hợp lệ/độ không chắc chắn/needs-human-review (2); chạy batch pilot và thống kê sai lệch theo tiêu chí (2) | 7 |
| TV5 | Tích hợp transcript confirmed → evaluation → result/history (3); chạy pilot nội bộ có giám sát, lập danh sách lỗi ưu tiên (2); kiểm tra luồng riêng tư và sửa lỗi chặn demo (2) | 7 |

**Năng lực Scrum/chia tải:** cộng 1 NC/người cho Scrum events và review chéo; tổng 8 NC/người.

## Phụ thuộc và phối hợp

- Chỉ chấm transcript đã xác nhận và rubric version đã khóa.
- TV4 không gửi tên/email/mã sinh viên đến provider nếu không cần; TV3 kiểm tra output trước khi lưu.
- TV1 + giảng viên duyệt bộ tham chiếu; TV5 điều phối pilot; lỗi blocker được ưu tiên trước khi khóa chức năng.

## Sprint Review / điều kiện hoàn thành

- Demo được câu hỏi → ghi âm → xác nhận transcript → chấm → kết quả → lịch sử.
- Điểm nằm trong thang, tiêu chí khớp rubric, evidence dựa trên transcript; kết quả có version để tái lập.
- Pilot có bảng lỗi/độ lệch ban đầu và quyết định sửa gì trước đợt đánh giá.
- Có phương án fallback khi AI lỗi; người dùng không bị mất transcript đã xác nhận.
