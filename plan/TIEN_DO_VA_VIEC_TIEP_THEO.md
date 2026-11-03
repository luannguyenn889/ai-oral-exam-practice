# Tiến độ và kế hoạch công việc tiếp theo

**Cập nhật:** 22/10/2026 · **Đang ở:** tuần 4–5. Đã xong Đăng nhập, **phần AI (Python)** và **giao diện luyện tập (chạy bằng dữ liệu giả)**. **Backend chưa lưu gì ngoài tài khoản.**

Từ tuần 4, **mỗi sprint làm xong hẳn một chức năng** (có giao diện, có lưu dữ liệu, chạy được để demo). Các file `SPRINT_02`–`SPRINT_06` chỉ để tham khảo; nếu khác nhau thì làm theo file này.

## 1. Đã làm được gì (rà soát theo code thực tế)

| Phần | Đã xong | Chưa làm |
|---|---|---|
| Đăng nhập | Đăng ký, đăng nhập email, đăng nhập Google, chọn vai trò lần đầu | Chặn gọi sai vai trò ở API; tự đăng xuất khi hết phiên |
| Backend (Spring Boot) | Quản lý tài khoản; file `schema.sql` đã thiết kế sẵn các bảng; có kết nối kiểm tra sức khỏe tới AI | **Chưa có** học phần, câu hỏi, rubric, phiên luyện tập, kết quả chấm. **Chưa gọi AI để chấm** |
| Frontend (Angular) | Đủ màn hình cho 3 vai trò: chọn học phần, danh sách câu hỏi, ghi âm, xem/sửa transcript, kết quả + dẫn chứng giáo trình, lịch sử, giảng viên tải giáo trình, trang quản trị | Đang dùng **dữ liệu giả** (câu hỏi, lịch sử lưu tạm trong trình duyệt). Chưa có trang giảng viên **soạn câu hỏi/rubric**. Chưa chạy qua API thật |
| AI (Python) | **Chạy thật:** chuyển giọng nói thành chữ, sửa thuật ngữ CNTT, tìm trong giáo trình (Hybrid RAG), chấm theo rubric; có kiểm thử; có file `.bat` chạy; có nhật ký trên terminal | Đo độ chính xác trên ghi âm thật; đưa bộ đề từ file `.txt` sang dữ liệu do giảng viên nhập |

**Nhận xét:** Phần AI đi nhanh hơn kế hoạch cũ nhiều. **Nút thắt hiện nay là Backend + dữ liệu thật.** Vì vậy, các sprint sau chuyển trọng tâm sang **nối giao diện ↔ backend ↔ AI**, không làm lại phần AI.

> [!IMPORTANT]
> Khi backend xong thì chỉ cần đổi `useMock: false` ở giao diện. Câu hỏi và rubric **do giảng viên nhập và lưu ở backend**, rồi backend gửi sang AI khi chấm. Đường đọc file `BỘ ĐỀ THI.txt` bên AI chỉ để lấy **đề mẫu**, không dùng cho hệ thống thật.

## 2. Cách chia việc

- Mỗi sprint có **1 chức năng chính** và **1 người chủ trì** (đổi người mỗi sprint). Người chủ trì lo ghép các phần lại và demo cuối sprint.
- Vai trò chính: **TV2** giao diện, **TV3** backend, **TV4** AI, **TV1** dữ liệu và nghiên cứu, **TV5** ghép nối và kiểm thử.
- **Việc soạn nội dung (câu hỏi, đáp án, rubric, ghi âm mẫu, chấm mẫu) cả nhóm cùng làm** trong 1–2 ngày đầu sprint, rồi gửi giảng viên duyệt.
- **NC** = số ngày làm việc ước tính. Sprint 1 tuần ≈ 4 NC/người.
- Chỉ tính **xong** khi chạy thật từ giao diện tới cơ sở dữ liệu và demo được cả trường hợp đúng lẫn lỗi.

## 3. Lộ trình mới

| Sprint | Tuần | Chức năng | Chủ trì | Trạng thái |
|---|---|---|---|---|
| 1 | 4–5 | Xem học phần và câu hỏi từ cơ sở dữ liệu, chặn sai vai trò | TV3 | **Đang làm — ưu tiên số 1** |
| 2 | 6 | Giảng viên soạn câu hỏi và rubric | TV2 | Giao diện đã có một phần |
| 3 | 7 | Sinh viên ghi âm → ra chữ → sửa (nối backend + AI) | TV5 | AI và giao diện xong, thiếu backend |
| 4 | 8 | AI chấm điểm, lưu và hiển thị kết quả | TV4 | AI và giao diện xong, thiếu backend |
| 5 | 9 | Lịch sử luyện tập + giảng viên quản lý giáo trình | TV1 | Giao diện đã có, cần lưu thật |
| 6 | 10 | Giảng viên chấm đối chiếu, đo độ chính xác AI, chạy thử | TV3 | Chưa làm |
| 7 | 11–12 | Đánh giá, viết báo cáo, bàn giao | TV5 | Chưa làm |

(Rút từ 7 sprint cũ xuống còn nội dung gọn hơn vì AI và giao diện đã xong; thời gian dư dùng để đo chất lượng.)

---

## Sprint 1 — Xem học phần và câu hỏi từ cơ sở dữ liệu (tuần 4–5)

**Kết quả cần có:** Sinh viên đăng nhập thấy học phần mình học và câu hỏi lấy **từ cơ sở dữ liệu** (không phải dữ liệu giả). Giảng viên thấy học phần mình dạy. Ai vào sai chức năng thì bị chặn. Token hết hạn thì tự về trang đăng nhập.

**Cả nhóm (1 NC/người):** Chốt bộ câu hỏi, đáp án và rubric cho học phần **Nhập môn Công nghệ phần mềm**. Đã có 8 câu mẫu từ `BỘ ĐỀ THI.txt`; mỗi người đọc lại, sửa và gửi giảng viên duyệt.

| Người | Việc cần làm | NC |
|---|---|---:|
| TV1 | Đổi 8 câu mẫu thành file dữ liệu nạp vào hệ thống; làm danh sách kiểm tra sprint | 2 |
| TV2 | Trang chọn học phần và danh sách câu hỏi lấy dữ liệu thật; báo lỗi rõ ràng; tự đăng xuất khi hết phiên (401) và hiện trang lỗi khi bị chặn (403) | 3 |
| TV3 | Làm bảng và API học phần, câu hỏi theo `schema.sql`; chặn gọi sai vai trò; trả thông báo lỗi thống nhất | 4 |
| TV4 | Chuẩn hóa dữ liệu AI cần nhận (câu hỏi, rubric, transcript) để backend gọi đúng; viết ví dụ gọi thử | 2 |
| TV5 | Hướng dẫn chạy cả 3 phần trên máy; nạp dữ liệu mẫu; kiểm tra sinh viên không vào được phần giảng viên | 3 |

## Sprint 2 — Giảng viên soạn câu hỏi và rubric (tuần 6)

**Kết quả cần có:** Giảng viên thêm, sửa câu hỏi và đáp án; tạo rubric (tiêu chí và điểm). Sửa rubric thì bản cũ vẫn được giữ.

**Cả nhóm (1 NC/người):** Rà rubric cho các câu còn thiếu, gửi giảng viên duyệt.

| Người | Việc cần làm | NC |
|---|---|---:|
| TV1 | Kiểm tra rubric mẫu có tổng đúng 10 điểm; kiểm thử trang soạn | 2 |
| TV2 | Trang giảng viên thêm/sửa câu hỏi; trang soạn rubric: thêm/xóa tiêu chí, tự cộng tổng điểm | 4 |
| TV3 | API lưu câu hỏi và rubric; kiểm tra tổng điểm; sửa rubric thì lưu thành bản mới | 4 |
| TV4 | Bỏ đường đọc file `.txt` thành chức năng chính; giữ làm "đề mẫu" tham khảo (đổi sang file JSON) | 2 |
| TV5 | Kiểm tra: rubric cũ vẫn dùng được cho bài đã chấm; tình huống nhập sai | 2 |

## Sprint 3 — Sinh viên ghi âm → ra chữ → sửa (tuần 7)

**Kết quả cần có:** Sinh viên ghi âm, nghe lại, gửi. Nhận đoạn chữ, sửa rồi xác nhận. File ghi âm được lưu kín. **Phần ra chữ và sửa thuật ngữ đã chạy bên AI; sprint này nối với backend.**

| Người | Việc cần làm | NC |
|---|---|---:|
| TV1 | Quy định xin phép ghi âm, thời gian lưu file, thông báo cho sinh viên; thu bộ ghi âm mẫu (có tiếng ồn) | 3 |
| TV2 | Chuyển trang ghi âm và trang sửa transcript sang gọi backend; báo lỗi khi không có micro hoặc AI lỗi | 4 |
| TV3 | API tạo lượt luyện tập, nhận và lưu file ghi âm (giới hạn loại và dung lượng), gọi AI lấy transcript, lưu bản sinh viên sửa | 4 |
| TV4 | Đo độ chính xác chuyển giọng nói trên bộ ghi âm mẫu; thêm cách thử lại khi dịch vụ ngoài quá tải | 3 |
| TV5 | Ghép cả luồng; thử trên Chrome, Edge, điện thoại | 3 |

## Sprint 4 — AI chấm điểm và hiển thị kết quả (tuần 8)

**Kết quả cần có:** Sau khi xác nhận, hệ thống chấm theo rubric, **lưu kết quả vào cơ sở dữ liệu**, sinh viên thấy điểm, từng tiêu chí, ý thiếu, gợi ý và đoạn giáo trình dẫn chứng.

**Cả nhóm (1 NC/người):** Chấm tay các câu trả lời mẫu theo rubric để so với điểm AI.

| Người | Việc cần làm | NC |
|---|---|---:|
| TV1 | Gom điểm chấm tay; thống nhất cách xử lý khi mọi người chấm lệch | 2 |
| TV2 | Trang kết quả đọc dữ liệu thật; nhắc điểm AI chỉ để tham khảo | 2 |
| TV3 | API gửi bài sang AI và lưu kết quả; kiểm tra điểm không vượt mức tối đa; lưu phiên bản rubric đã dùng | 4 |
| TV4 | Chỉnh lời nhắc chấm cho đỡ lệch; xử lý khi AI trả sai định dạng; ghi lại thời gian xử lý | 3 |
| TV5 | Ghép luồng; thử lỗi: AI tắt, hết lượt dùng, transcript rỗng | 3 |

## Sprint 5 — Lịch sử luyện tập + quản lý giáo trình (tuần 9)

**Kết quả cần có:** Sinh viên xem lại các lần luyện (chỉ thấy bài của mình), lưu bền vững, không mất khi đóng trình duyệt. Giảng viên tải giáo trình lên theo từng học phần.

| Người | Việc cần làm | NC |
|---|---|---:|
| TV1 | Kiểm thử quyền: không xem được bài người khác; rà thông báo cho người dùng | 2 |
| TV2 | Trang lịch sử đọc dữ liệu thật; trang giáo trình gọi qua backend | 3 |
| TV3 | API lịch sử; API giáo trình (lưu danh sách, chỉ giảng viên phụ trách mới thêm/xóa) | 4 |
| TV4 | Tạo lại chỉ mục giáo trình khi có file mới/xóa; thử giáo trình dài | 3 |
| TV5 | Ghép và kiểm thử; thử giảng viên A không sửa được học phần của B | 3 |

## Sprint 6 — Giảng viên chấm đối chiếu, chạy thử (tuần 10)

**Kết quả cần có:** Giảng viên tự chấm một số bài và so với điểm AI. Nhóm chạy thử toàn hệ thống.

**Cả nhóm (1 NC/người):** Mỗi người luyện 3–5 lần, ghi lỗi vào danh sách chung.

| Người | Việc cần làm | NC |
|---|---|---:|
| TV1 | Phiếu khảo sát người dùng; xếp thứ tự lỗi cần sửa | 2 |
| TV2 | Trang giảng viên chấm bài và xem so sánh với điểm AI | 3 |
| TV3 | API lưu điểm giảng viên chấm; xuất dữ liệu ẩn danh | 4 |
| TV4 | Chấm hàng loạt bài chạy thử; thống kê AI lệch bao nhiêu so với giảng viên | 3 |
| TV5 | Sửa lỗi gom từ chạy thử; làm sạch dữ liệu giả còn sót | 3 |

## Sprint 7 — Đánh giá và bàn giao (tuần 11–12)

Làm theo [Sprint 6 cũ](SPRINT_06.md): thu dữ liệu đánh giá, tính độ chính xác, sửa lỗi quan trọng, viết hướng dẫn cài đặt, báo cáo, slide. **Cả nhóm:** tập demo và đọc chéo báo cáo.

---

## 4. Việc cần chốt ngay trong tuần này

1. **Khóa API:** `GEMINI_API_KEY` và `GROQ_API_KEY` đã bị dán trong khung chat nên coi như lộ. **Tạo khóa mới**, chỉ để trong `ai-service/.env` (không đưa lên git).
2. **Lỗi đã sửa trong backend:** `User.java` đã bỏ Lombok để tránh lỗi biên dịch; TV3 nên cập nhật Lombok bản mới cho cả nhóm trước khi viết thêm lớp.
3. TV2 và TV3 chốt **dữ liệu gửi qua lại** của Học phần/Câu hỏi (tên trường, kiểu mã là chuỗi UUID) trước khi code.
4. Quyết định nơi lưu file ghi âm và file giáo trình (hiện giáo trình đang lưu bên AI, ghi âm chưa có).

## 5. Lưu ý khi làm việc chung

- Giao diện được dùng dữ liệu giả khi API chưa xong, nhưng **phải bỏ dữ liệu giả trước buổi demo** (hiện còn trong `mock-practice.api.ts`).
- Giao diện viết bằng CSS thường (không dùng SCSS), làm theo `QUY_TAC_THIET_KE_FE.md`.
- Không gửi ghi âm hay thông tin cá nhân ra dịch vụ bên ngoài (Groq, Gemini) khi chưa được người đó đồng ý; ghi rõ điều này trong thông báo cho sinh viên.
- Khi chạy AI: dùng `start-ai-service.bat` ở thư mục gốc.

## 6. Nếu nhóm ít người

| Số người | Cách chia lại |
|---|---|
| 4 | Không có TV5: người chủ trì sprint lo ghép và kiểm thử; các trang phụ của giảng viên chia cho TV1 và TV2 |
| 3 | 1 người giao diện, 1 người backend, 1 người AI + dữ liệu; việc soạn nội dung vẫn làm chung |

Thiếu người thì **bớt chức năng phụ** (trang so sánh điểm, khảo sát), không dồn thêm việc cho từng người.
