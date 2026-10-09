# Sprint 6 — Đánh giá nghiên cứu và bàn giao

**Thời gian:** Tuần 11–12 · **Sprint Goal:** chạy protocol đánh giá đã duyệt, hoàn thiện báo cáo/demo và bàn giao sản phẩm có thể cài/chạy, với giới hạn và số liệu được trình bày trung thực.

## Việc theo thành viên

| Người | Công việc và đầu ra | NC |
|---|---|---:|
| TV1 | Điều phối thu thập/chấm tập đánh giá đã được phép (3); phân tích MAE/RMSE/sai lệch và khảo sát khả dụng (2); viết kết quả, giới hạn và hướng phát triển (2) | 7 |
| TV2 | Sửa lỗi UI ưu tiên pilot và kiểm tra desktop/mobile (3); hoàn thiện hướng dẫn sinh viên/ảnh màn hình (2); chuẩn bị phần demo FE và rà thông báo AI (2) | 7 |
| TV3 | Sửa lỗi API/quyền/truy vấn ưu tiên (3); hoàn thiện migration, cấu hình mẫu và hướng dẫn chạy backend (2); hỗ trợ xuất dữ liệu đã khử định danh, rà không lộ secret (2) | 7 |
| TV4 | Chạy lại pipeline AI với cấu hình đã khóa và lưu phiên bản (3); phân tích bất đồng lớn theo tiêu chí/evidence (2); viết phương pháp, cấu hình và giới hạn AI (2) | 7 |
| TV5 | Chạy kịch bản nghiệm thu/release candidate và ghi kết quả (3); hoàn thiện script demo, dữ liệu mẫu và hướng dẫn cài/chạy toàn hệ thống (2); ghép báo cáo/slide, điều phối rehearsal (2) | 7 |

**Năng lực Scrum/chia tải:** cộng 1 NC/người cho Scrum events và review chéo; tổng 8 NC/người.

## Phụ thuộc và phối hợp

- Chỉ phân tích dữ liệu đã được duyệt sử dụng, khử định danh và tách khỏi tập dùng điều chỉnh prompt.
- TV1 cung cấp bảng số liệu đã kiểm tra; TV4 cung cấp cấu hình/version; TV5 tổng hợp cùng kết quả nghiệm thu.
- Ưu tiên sửa lỗi làm sai dữ liệu, quyền riêng tư, điểm hoặc demo; tính năng ngoài MVP không nhận vào sprint cuối nếu làm rủi ro release.

## Sprint Review / điều kiện hoàn thành

- Báo cáo kết quả gồm phương pháp, dữ liệu, chỉ số, chênh lệch, lỗi và giới hạn; không tuyên bố AI tương đương giảng viên chỉ dựa vào tương quan.
- Web app MVP chạy được theo hướng dẫn, có dữ liệu demo và kịch bản demo lặp lại được.
- Bàn giao mã, DTO/API, hướng dẫn cài/chạy, protocol, dataset đã được phép/ẩn danh, bảng kết quả và tài liệu người dùng.
- Ghi rõ hạng mục chưa hoàn thành, mock còn tồn tại và quyết định tiếp theo.
