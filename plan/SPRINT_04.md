# Sprint 4 — STT và xác nhận transcript

**Thời gian:** Tuần 7–8 · **Sprint Goal:** audio có thể đi qua STT; sinh viên xác nhận/sửa transcript trước khi dữ liệu được gửi chấm.

## Việc theo thành viên

| Người | Công việc và đầu ra | NC |
|---|---|---:|
| TV1 | Chuẩn hóa tập audio/transcript tham chiếu đã được phép sử dụng (3); định nghĩa cách tính CER/WER, quy tắc chuẩn hóa văn bản và phiếu lỗi (2); rà soát thông báo quyền riêng tư trên luồng transcript (2) | 7 |
| TV2 | Xây màn transcript review, sửa/xác nhận và trạng thái đang xử lý (3); nối upload/request/status qua API Spring Boot (2); xử lý timeout, retry thủ công và rời trang (2) | 7 |
| TV3 | API tạo transcription job, lưu trạng thái/metadata và xác nhận transcript (3); tích hợp service-to-service với FastAPI, auth/timeout (2); API trạng thái job và lỗi có thể retry (2) | 7 |
| TV4 | Tích hợp provider STT tiếng Việt qua adapter (3); đo CER/WER/độ trễ trên tập thử, ghi cấu hình/version (2); bổ sung mock/fallback và log lỗi đã khử dữ liệu (2) | 7 |
| TV5 | Ghép đầu-cuối audio → STT → transcript review (3); viết kịch bản chấp nhận cho success/failure/retry (2); rà phân quyền và hành vi upload lỗi, sửa tài liệu chạy (2) | 7 |

**Năng lực Scrum/chia tải:** cộng 1 NC/người cho Scrum events và review chéo; tổng 8 NC/người.

## Phụ thuộc và phối hợp

- Sprint 3 cần cung cấp audio upload và rubric/session ID ổn định.
- TV4 công bố schema/provider metadata trước khi TV3 hoàn tất endpoint tích hợp.
- TV1 kiểm tra quyền sử dụng dữ liệu trước khi chạy đo; TV5 xác nhận hành vi với người dùng thử nội bộ.

## Sprint Review / điều kiện hoàn thành

- Một phiên demo đi qua upload → transcript → sửa/xác nhận; các bước lỗi có retry rõ.
- Transcript lưu đúng session; có metadata STT/provider/version/thời gian xử lý.
- Có số đo thử nghiệm CER/WER trên tập được phép, kèm mô tả cách tính và giới hạn.
- Nếu provider chưa sẵn sàng, mock thể hiện đúng contract; blocker và quyết định thay thế được ghi lại.
