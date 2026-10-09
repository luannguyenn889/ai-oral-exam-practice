# Sprint 3 — Rubric và phiên ghi âm

**Thời gian:** Tuần 5–6 · **Sprint Goal:** giảng viên cấu hình được câu hỏi/rubric có phiên bản; sinh viên tạo phiên, ghi/nghe lại và tải audio an toàn.

## Việc theo thành viên

| Người | Công việc và đầu ra | NC |
|---|---|---:|
| TV1 | Hoàn thiện tiêu chí rubric và hướng dẫn chấm cho câu hỏi mẫu với giảng viên (3); lập hướng dẫn đồng ý, ẩn danh, thời hạn lưu/xóa audio (2); tạo checklist chấm mẫu (2) | 7 |
| TV2 | Xây form câu hỏi/đáp án và rubric editor có kiểm tra điểm (3); xây UI chọn câu hỏi/tạo phiên luyện tập (2); triển khai AudioRecorderService, nghe lại và quyền micro/error state (2) | 7 |
| TV3 | Thiết kế/lập bảng Question, RubricVersion, PracticeSession và migration (3); API quản lý rubric version (2); API tạo phiên và upload audio có validate/quyền truy cập (2) | 7 |
| TV4 | Hoàn thiện schema đầu vào STT, giới hạn audio và adapter provider (2); thử nghiệm mẫu audio không định danh, ghi metadata/độ trễ (3); chuẩn hóa lỗi STT và retry an toàn (2) | 7 |
| TV5 | Nối FE–BE cho câu hỏi/rubric/phiên theo hợp đồng (3); rà luồng lưu trữ audio và cấu hình giới hạn (2); chạy kịch bản micro/upload trên môi trường dev, ghi lỗi và hướng dẫn demo (2) | 7 |

**Năng lực Scrum/chia tải:** cộng 1 NC/người cho Scrum events và review chéo; tổng 8 NC/người.

## Phụ thuộc và phối hợp

- TV1 cung cấp rubric mẫu đã được giảng viên xem; TV3 lưu version bất biến; TV4 dùng cùng cấu trúc cho chấm AI ở sprint sau.
- TV2 dùng mock trong lúc API upload chưa sẵn; TV5 ghép dần, không chờ toàn bộ backend.
- Chỉ dùng audio thử nghiệm được phép; không đưa dữ liệu nhận diện cá nhân vào provider ngoài khi chưa có chấp thuận.

## Sprint Review / điều kiện hoàn thành

- Giảng viên tạo câu hỏi/rubric mẫu; tổng điểm và từng tiêu chí được validate.
- Sinh viên chọn câu hỏi, ghi/nghe lại/ghi lại, gửi phiên; lỗi micro/upload được giải thích.
- Audio private, quyền truy cập do backend kiểm soát; thời hạn lưu được ghi nhận.
- Đã thống nhất trạng thái phiên và hành vi retry STT trước khi bắt đầu sprint 4.
