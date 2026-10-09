# Bộ kế hoạch Scrum — Hệ thống luyện thi vấn đáp bằng AI

Bộ tài liệu này chuyển kế hoạch NCKH và kế hoạch Frontend Angular hiện có thành kế hoạch thực thi Scrum 12 tuần cho nhóm 5 người. Phạm vi giữ theo MVP trong tài liệu gốc: Angular, Spring Boot, Python FastAPI, STT tiếng Việt, chấm theo rubric và đánh giá nghiên cứu. Repo `speed-to-text-demo` vẫn là hạng mục cần khảo sát; chưa mặc định tái sử dụng.

## Cấu trúc

- [Product backlog](PRODUCT_BACKLOG.md): mục tiêu, user story, ưu tiên, điều kiện nghiệm thu và Definition of Done.
- [Sprint 1 — Khảo sát và chốt thiết kế](SPRINT_01.md): tuần 1–2.
- [Sprint 2 — Nền tảng ứng dụng và nội dung](SPRINT_02.md): tuần 3–4.
- [Sprint 3 — Rubric và phiên ghi âm](SPRINT_03.md): tuần 5–6.
- [Sprint 4 — STT và xác nhận transcript](SPRINT_04.md): tuần 7–8.
- [Sprint 5 — Chấm AI, lịch sử và pilot](SPRINT_05.md): tuần 9–10.
- [Sprint 6 — Đánh giá nghiên cứu và bàn giao](SPRINT_06.md): tuần 11–12.

## Mục tiêu sản phẩm

Sinh viên có thể chọn câu hỏi, ghi âm câu trả lời, xem và xác nhận transcript tiếng Việt, nhận phản hồi theo rubric và xem lại lịch sử; giảng viên cấu hình câu hỏi/rubric và đối chiếu kết quả AI với điểm tham chiếu. Sản phẩm phục vụ luyện tập, không dùng để quyết định điểm thi chính thức.

## Nhóm và cách chia tải

Thành viên được đặt tên tạm là TV1–TV5; thay bằng tên thật khi nhóm thống nhất. Mỗi người có một mảng dẫn dắt nhưng vẫn có nhiệm vụ review/tích hợp liên mảng để tránh điểm nghẽn:

| Thành viên | Mảng dẫn dắt | Mảng phối hợp |
|---|---|---|
| TV1 | Phân tích yêu cầu, nghiên cứu và dữ liệu đánh giá | Điều phối backlog, rà soát UX và báo cáo |
| TV2 | Angular, luồng sinh viên và giao diện kết quả | DTO, tích hợp API và accessibility cơ bản |
| TV3 | Spring Boot, nghiệp vụ và cơ sở dữ liệu | Hợp đồng API, lưu trữ và phân quyền |
| TV4 | FastAPI, adapter STT/LLM và schema đánh giá | Đo chất lượng AI, logging phiên bản và xử lý lỗi |
| TV5 | Tích hợp đầu-cuối, nghiệm thu và triển khai demo | Công cụ nghiên cứu, tài liệu chạy và hỗ trợ FE/BE |

## Quy ước ước tính

- Dùng **ngày công tập trung (NC)** để cân bằng tải giữa người, không dùng story point cá nhân. Một NC là khoảng một ngày làm việc tập trung; sai số dự kiến ±20%.
- Mỗi sprint 2 tuần, tải mục tiêu là **8 NC/người**: khoảng 7 NC cho đầu việc bàn giao và 1 NC cho planning, daily, review, retrospective, refinement/review chéo. Tổng kế hoạch là khoảng 40 NC/sprint, chia đều 8 NC/người. Nếu lịch học làm giảm capacity, giảm phạm vi sprint thay vì dồn thêm việc.
- Daily Scrum 15 phút mỗi ngày; Sprint Planning tối đa nửa ngày; refinement khoảng 1–2 giờ/tuần; Review và Retrospective cuối sprint. Scrum Master/Product Owner do nhóm luân phiên điều phối; giảng viên hướng dẫn duyệt quyết định học thuật, không mặc định là thành viên thực thi.
- Đầu sprint, nhóm chọn backlog theo thứ tự ưu tiên và capacity thật. Cuối sprint chỉ tính hoàn thành khi đạt Definition of Done và có demo/đầu ra xem được.

## Cách dùng

1. Điền tên thật, lịch học và capacity thực tế của 5 người.
2. Chốt câu hỏi, rubric, quyền thu thập/lưu audio với giảng viên trước khi thu dữ liệu người tham gia.
3. Tạo board với cột `Backlog → Ready → In Progress → Review → Done`; giới hạn WIP gợi ý: tối đa 2 việc đang làm/người.
4. Đầu mỗi sprint xác nhận Sprint Goal, chọn việc theo thứ tự ưu tiên và ghi người phụ trách cùng người review.
5. Cuối sprint demo increment chạy được, cập nhật backlog và điều chỉnh sprint sau theo bằng chứng thực tế.

## Rủi ro và điều kiện cần chốt sớm

- Tuần 1 khảo sát repo tham khảo và giấy phép; nếu không tích hợp được, dùng adapter/mock hoặc tự triển khai STT để không chặn luồng chính.
- Chốt học phần, câu hỏi mẫu, rubric, nhà cung cấp AI, ngân sách, lưu trữ và thời hạn xóa audio trước khi làm luồng thật.
- Nghiên cứu chỉ thu dữ liệu sau khi có chấp thuận phù hợp và người tham gia đồng ý; khử định danh trước khi phân tích.
- Dịch vụ AI bên ngoài được bọc sau adapter, có mock để FE và backend vẫn phát triển khi API chưa sẵn sàng.
