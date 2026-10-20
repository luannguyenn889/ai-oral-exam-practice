# Tiến độ và kế hoạch công việc tiếp theo

**Cập nhật:** 19/10/2026 · **Đang ở:** tuần 4, đã xong Đăng nhập / Đăng ký.

Từ tuần 4, **mỗi sprint làm xong hẳn một chức năng** (có giao diện, có lưu dữ liệu, chạy được để demo). Các file `SPRINT_02`–`SPRINT_06` chỉ để tham khảo; nếu khác nhau thì làm theo file này.

## 1. Đã làm được gì

| Phần | Đã xong | Chưa làm |
|---|---|---|
| Đăng nhập | Đăng ký, đăng nhập bằng email, đăng nhập bằng Google, chọn vai trò khi đăng nhập Google lần đầu | Chặn người dùng gọi chức năng không đúng vai trò; tự đăng xuất khi hết phiên |
| Backend (Spring Boot) | Lưu và quản lý tài khoản người dùng | Học phần, câu hỏi, rubric, phiên luyện tập… |
| Frontend (Angular) | Giao diện cho 3 vai trò, trang chọn học phần, trang danh sách câu hỏi (đang dùng dữ liệu giả) | Lấy dữ liệu thật; trang ghi âm, xem transcript, xem kết quả, lịch sử, trang giảng viên |
| AI (Python) | Mới chạy được service | Chuyển giọng nói thành chữ, chấm điểm |

## 2. Cách chia việc

- Mỗi sprint có **1 chức năng chính** và **1 người chủ trì** (đổi người mỗi sprint). Người chủ trì lo ghép các phần lại và demo cuối sprint.
- Mỗi người vẫn làm phần mình mạnh: **TV2** giao diện, **TV3** backend, **TV4** AI, **TV1** dữ liệu và nghiên cứu, **TV5** ghép nối và kiểm thử.
- **Việc soạn nội dung (câu hỏi, đáp án, rubric, ghi âm mẫu, chấm mẫu) cả nhóm cùng làm** trong 1–2 ngày đầu sprint, rồi gửi giảng viên duyệt.
- **NC** = số ngày làm việc ước tính. Sprint 1 tuần ≈ 4 NC/người, sprint 2 tuần ≈ 8 NC/người (đã tính thời gian họp nhóm).
- Chỉ tính **xong** khi chức năng chạy thật từ giao diện tới cơ sở dữ liệu và demo được cả trường hợp đúng lẫn trường hợp lỗi.

## 3. Lộ trình

| Sprint | Tuần | Chức năng | Chủ trì |
|---|---|---|---|
| 1 | 4 | Xem học phần và câu hỏi | TV3 |
| 2 | 5 | Giảng viên soạn câu hỏi và rubric | TV2 |
| 3 | 6 | Sinh viên ghi âm câu trả lời | TV5 |
| 4 | 7–8 | Chuyển giọng nói thành chữ, sinh viên sửa lại | TV4 |
| 5 | 9 | AI chấm điểm và hiển thị kết quả | TV3 |
| 6 | 10 | Lịch sử luyện tập, giảng viên chấm đối chiếu, chạy thử | TV1 |
| 7 | 11–12 | Đánh giá, viết báo cáo, bàn giao | TV5 |

---

## Sprint 1 — Xem học phần và câu hỏi (tuần 4)

**Kết quả cần có:** Sinh viên đăng nhập thấy học phần của mình và các câu hỏi (lấy từ cơ sở dữ liệu, không phải dữ liệu giả). Giảng viên thấy học phần mình dạy. Ai vào sai chức năng thì bị chặn.

**Cả nhóm (1 NC/người):** Soạn bộ câu hỏi và đáp án mẫu cho 1 học phần. Mỗi người viết 2–3 câu, cả nhóm đọc chéo, gửi giảng viên duyệt.

| Người | Việc cần làm | NC |
|---|---|---:|
| TV1 | Gom câu hỏi đã soạn thành dữ liệu mẫu để nạp vào hệ thống; viết danh sách kiểm tra cho sprint này | 2,5 |
| TV2 | Trang chọn học phần và trang câu hỏi lấy dữ liệu thật; báo lỗi rõ ràng; tự đăng xuất khi hết phiên | 2,5 |
| TV3 | Làm API học phần và câu hỏi; chặn người dùng gọi sai vai trò; trả thông báo lỗi thống nhất | 2,5 |
| TV4 | Làm khung cho phần AI, tạm trả kết quả giả để các phần khác dùng được; ghi rõ dữ liệu gửi/nhận | 2,5 |
| TV5 | Hướng dẫn chạy toàn bộ hệ thống trên máy; trang giảng viên xem danh sách học phần và câu hỏi; kiểm tra sinh viên không vào được phần giảng viên | 2,5 |

## Sprint 2 — Giảng viên soạn câu hỏi và rubric (tuần 5)

**Kết quả cần có:** Giảng viên thêm, sửa câu hỏi và đáp án; tạo rubric (các tiêu chí chấm và điểm). Khi sửa rubric, bản cũ vẫn được giữ lại.

**Cả nhóm (1 NC/người):** Soạn rubric chấm điểm cho bộ câu hỏi đã chốt, gửi giảng viên duyệt.

| Người | Việc cần làm | NC |
|---|---|---:|
| TV1 | Đưa rubric đã soạn vào dữ liệu mẫu; kiểm tra trang soạn câu hỏi và rubric | 2,5 |
| TV2 | Trang giảng viên thêm/sửa câu hỏi và đáp án | 2,5 |
| TV3 | API lưu câu hỏi và rubric; kiểm tra tổng điểm hợp lệ; sửa rubric thì lưu thành bản mới | 2,5 |
| TV4 | Chuẩn bị cách đưa rubric và đáp án vào AI để chấm sau này | 2,5 |
| TV5 | Trang soạn rubric: thêm/xóa tiêu chí, tự cộng tổng điểm, xem trước | 2,5 |

## Sprint 3 — Sinh viên ghi âm câu trả lời (tuần 6)

**Kết quả cần có:** Sinh viên chọn câu hỏi, ghi âm, nghe lại, ghi lại và gửi đi. File ghi âm được lưu kín, người ngoài không mở được.

| Người | Việc cần làm | NC |
|---|---|---:|
| TV1 | Viết quy định xin phép ghi âm, thời gian lưu file, nội dung thông báo cho sinh viên; kịch bản kiểm tra micro | 3,5 |
| TV2 | Trang ghi âm: bắt đầu, dừng, nghe lại, ghi lại, gửi; báo lỗi khi không có micro hoặc bị từ chối quyền | 3,5 |
| TV3 | API tạo lượt luyện tập và nhận file ghi âm; giới hạn loại file và dung lượng; lưu file an toàn | 3,5 |
| TV4 | Thử 1–2 dịch vụ chuyển giọng nói tiếng Việt thành chữ, ghi lại tốc độ và độ chính xác | 3,5 |
| TV5 | Ghép trang ghi âm với API; thử trên Chrome, Edge, điện thoại | 3,5 |

## Sprint 4 — Chuyển giọng nói thành chữ (tuần 7–8)

**Kết quả cần có:** Sau khi gửi ghi âm, sinh viên nhận được đoạn chữ (transcript), sửa lỗi nếu cần rồi xác nhận. Nếu lỗi thì bấm thử lại được.

**Cả nhóm (1 NC/người):** Mỗi người tự ghi âm vài câu trả lời mẫu và gõ lại chính xác nội dung, để so sánh với kết quả máy nhận dạng.

| Người | Việc cần làm | NC |
|---|---|---:|
| TV1 | Quy định cách so sánh chữ máy nhận dạng với chữ gõ tay để tính độ chính xác; gom bộ ghi âm mẫu | 6 |
| TV2 | Trang xem và sửa transcript; hiện "đang xử lý"; nút thử lại khi lỗi | 6 |
| TV3 | API gửi ghi âm sang AI, lưu transcript, nhận bản sinh viên đã sửa | 6 |
| TV4 | Nối dịch vụ nhận dạng giọng nói thật; đo độ chính xác trên bộ ghi âm mẫu | 6 |
| TV5 | Ghép cả luồng ghi âm → ra chữ → sửa; kiểm tra các trường hợp lỗi | 6 |

## Sprint 5 — AI chấm điểm và hiển thị kết quả (tuần 9)

**Kết quả cần có:** Sau khi xác nhận transcript, AI chấm theo rubric. Sinh viên thấy tổng điểm, điểm từng tiêu chí, ý đúng, ý thiếu và gợi ý cải thiện.

**Cả nhóm (1 NC/người):** Chấm tay một số câu trả lời mẫu theo rubric, để sau so với điểm AI.

| Người | Việc cần làm | NC |
|---|---|---:|
| TV1 | Gom điểm chấm tay; thống nhất cách xử lý khi mọi người chấm khác nhau | 2,5 |
| TV2 | Trang kết quả: điểm, nhận xét, gợi ý; nhắc rằng điểm AI chỉ để tham khảo | 2,5 |
| TV3 | API gửi bài sang AI chấm và lưu kết quả; kiểm tra điểm không vượt mức tối đa | 2,5 |
| TV4 | Cho AI chấm theo rubric và trả kết quả đúng định dạng; xử lý khi AI trả kết quả sai | 2,5 |
| TV5 | Ghép luồng transcript → chấm → kết quả; kiểm tra khi chấm bị lỗi | 2,5 |

## Sprint 6 — Lịch sử, chấm đối chiếu, chạy thử (tuần 10)

**Kết quả cần có:** Sinh viên xem lại các lần luyện tập trước. Giảng viên tự chấm một số bài và so với điểm AI. Nhóm chạy thử toàn bộ hệ thống.

**Cả nhóm (1 NC/người):** Mỗi người luyện tập 3–5 lần trên hệ thống, ghi lại lỗi gặp phải vào một danh sách chung.

| Người | Việc cần làm | NC |
|---|---|---:|
| TV1 | Làm phiếu khảo sát người dùng; gom lỗi chạy thử và xếp thứ tự cần sửa | 2,5 |
| TV2 | Trang lịch sử luyện tập (chỉ thấy bài của mình) | 2,5 |
| TV3 | API lịch sử; API cho giảng viên lưu điểm tự chấm | 2,5 |
| TV4 | Cho AI chấm hàng loạt bài chạy thử; thống kê AI chấm lệch so với giảng viên bao nhiêu | 2,5 |
| TV5 | Trang giảng viên chấm bài và xem so sánh với điểm AI | 2,5 |

## Sprint 7 — Đánh giá và bàn giao (tuần 11–12)

Làm theo [Sprint 6 cũ](SPRINT_06.md): thu dữ liệu đánh giá, tính độ chính xác, sửa lỗi quan trọng, viết hướng dẫn cài đặt, báo cáo, slide. **Cả nhóm:** tập demo và đọc chéo báo cáo.

---

## 4. Lưu ý khi làm việc chung

- Đầu mỗi sprint, người làm giao diện (TV2) và người làm backend (TV3) ngồi chốt **dữ liệu gửi qua lại gồm những gì** trước khi code.
- Giao diện được dùng dữ liệu giả khi API chưa xong, nhưng **phải bỏ dữ liệu giả trước buổi demo**.
- Giao diện viết bằng CSS thường (không dùng SCSS), làm theo `QUY_TAC_THIET_KE_FE.md`.
- Không gửi ghi âm hay thông tin cá nhân ra dịch vụ bên ngoài khi chưa được người đó đồng ý.

## 5. Nếu nhóm ít người

| Số người | Cách chia lại |
|---|---|
| 4 | Không có TV5: người chủ trì sprint lo ghép và kiểm thử; các trang phụ của giảng viên chia cho TV1 và TV2 |
| 3 | 1 người làm giao diện, 1 người làm backend, 1 người làm AI và dữ liệu; việc soạn nội dung vẫn làm chung |

Thiếu người thì **bớt chức năng phụ** (trang so sánh điểm, khảo sát), không dồn thêm việc cho từng người.
