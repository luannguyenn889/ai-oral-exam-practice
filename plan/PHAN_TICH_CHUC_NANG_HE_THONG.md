# Phân tích chức năng hệ thống

Tài liệu này phân tích các chức năng cần có của hệ thống **AI Oral Exam Practice** dựa trên [Product backlog](PRODUCT_BACKLOG.md), kế hoạch sprint hiện tại và phạm vi MVP. Mục tiêu là biến backlog thành danh sách chức năng rõ ràng để nhóm thiết kế API, giao diện, cơ sở dữ liệu, kiểm thử và demo.

## 1. Phạm vi hệ thống

Hệ thống phục vụ luyện thi vấn đáp bằng AI, không dùng để quyết định điểm thi chính thức. Luồng chính của MVP:

1. Người dùng đăng nhập theo vai trò.
2. Giảng viên tạo học phần, câu hỏi, đáp án tham chiếu và rubric.
3. Sinh viên chọn học phần/câu hỏi, tạo phiên luyện tập.
4. Sinh viên ghi âm, nghe lại, ghi lại và gửi câu trả lời.
5. Hệ thống chuyển giọng nói tiếng Việt thành transcript.
6. Sinh viên xem, sửa và xác nhận transcript.
7. AI chấm câu trả lời theo rubric.
8. Sinh viên xem kết quả, giải thích, gợi ý và lịch sử luyện tập.
9. Giảng viên/nghiên cứu viên chấm mẫu, so sánh với AI và xuất dữ liệu nghiên cứu đã khử định danh.

## 2. Vai trò người dùng

| Vai trò | Mục đích sử dụng | Quyền chính |
|---|---|---|
| Sinh viên | Luyện trả lời vấn đáp và nhận phản hồi | Xem học phần được tham gia, chọn câu hỏi, ghi âm, xác nhận transcript, xem kết quả và lịch sử của chính mình |
| Giảng viên | Quản lý nội dung và chấm đối chiếu | Quản lý học phần mình phụ trách, tạo/sửa câu hỏi, tạo rubric, xem phiên cần chấm mẫu, nhập điểm giảng viên |
| Nghiên cứu viên | Đánh giá chất lượng STT/AI và khả dụng | Xem/xuất dữ liệu đã khử định danh, tính metric, so sánh điểm AI và điểm người chấm |
| Quản trị viên tối thiểu | Hỗ trợ vận hành MVP nếu cần | Quản lý tài khoản, phân vai trò, khóa/mở tài khoản, cấu hình dữ liệu demo |

Ghi chú: MVP có thể chưa cần giao diện quản trị đầy đủ, nhưng backend vẫn cần ranh giới quyền rõ ràng để không phụ thuộc vào route guard frontend.

## 3. Nhóm chức năng bắt buộc cho MVP

### 3.1 Xác thực, phân quyền và phiên đăng nhập

Chức năng cần có:

- Đăng ký tài khoản bằng email và mật khẩu.
- Đăng nhập bằng email và mật khẩu.
- Đăng nhập bằng Google, chọn vai trò ở lần đầu nếu hệ thống cho phép.
- Lưu thông tin người dùng, vai trò và trạng thái hoạt động.
- Sinh token đăng nhập và kiểm tra token ở các API cần bảo vệ.
- Tự đăng xuất hoặc yêu cầu đăng nhập lại khi token hết hạn.
- Chặn truy cập API không đúng vai trò ở backend.
- Chặn truy cập màn hình không đúng vai trò ở frontend.
- Hiển thị lỗi rõ ràng khi tài khoản sai, bị khóa, hết phiên hoặc không đủ quyền.

Dữ liệu cần lưu:

- User: email, họ tên, avatar nếu có, trạng thái tài khoản.
- Role: student, instructor, admin/researcher nếu dùng.
- Provider identity nếu có đăng nhập Google.

Điều kiện kiểm tra:

- Sinh viên không gọi được API quản lý câu hỏi/rubric.
- Giảng viên không xem được lịch sử luyện tập riêng tư của sinh viên ngoài phạm vi được phép.
- Token hết hạn không cho gọi tiếp API nghiệp vụ.

### 3.2 Quản lý học phần

Chức năng cần có:

- Tạo học phần/lớp học phần.
- Sửa thông tin học phần: mã, tên, mô tả, học kỳ, trạng thái.
- Gán giảng viên phụ trách học phần.
- Gán sinh viên vào học phần.
- Sinh viên xem danh sách học phần mình được tham gia.
- Giảng viên xem danh sách học phần mình phụ trách.
- Ẩn hoặc khóa học phần không còn sử dụng mà không xóa dữ liệu lịch sử.

Dữ liệu cần lưu:

- Course: mã học phần, tên, mô tả, học kỳ, khoa/bộ môn, trạng thái.
- Course enrollment: sinh viên thuộc học phần nào.
- Course instructor: giảng viên phụ trách học phần nào.

Điều kiện kiểm tra:

- Sinh viên chỉ thấy học phần được ghi danh.
- Giảng viên chỉ quản lý học phần mình phụ trách.
- Học phần bị khóa không cho tạo phiên luyện tập mới nhưng dữ liệu cũ vẫn xem được theo quyền.

### 3.3 Quản lý câu hỏi và đáp án tham chiếu

Chức năng cần có:

- Giảng viên tạo câu hỏi trong một học phần.
- Nhập nội dung câu hỏi, chủ đề, độ khó, giới hạn thời gian nếu có.
- Nhập đáp án tham chiếu hoặc ý chính cần có.
- Sửa câu hỏi theo cơ chế phiên bản để phiên luyện tập cũ vẫn trỏ đúng nội dung đã dùng.
- Bật/tắt trạng thái sử dụng của câu hỏi.
- Sinh viên xem danh sách câu hỏi đang mở trong học phần.
- Sinh viên xem chi tiết câu hỏi trước khi bắt đầu luyện tập.
- Tìm kiếm/lọc câu hỏi theo học phần, chủ đề, độ khó hoặc tag nếu cần.

Dữ liệu cần lưu:

- Question: định danh ổn định, học phần, người tạo, trạng thái.
- Question version: tiêu đề, prompt, đáp án tham chiếu, độ khó, tag, thời gian giới hạn.

Điều kiện kiểm tra:

- Dữ liệu câu hỏi được validate trước khi lưu.
- Sửa nội dung câu hỏi không làm thay đổi kết quả của các phiên luyện tập cũ.
- Sinh viên không thấy câu hỏi bị tắt hoặc câu hỏi ngoài học phần của mình.

### 3.4 Quản lý rubric

Chức năng cần có:

- Giảng viên tạo rubric cho một phiên bản câu hỏi.
- Thêm, sửa, xóa tiêu chí trong rubric khi rubric chưa được chốt hoặc tạo version mới khi đã dùng.
- Nhập tên tiêu chí, mô tả, điểm tối đa và hướng dẫn chấm.
- Tự tính tổng điểm từ các tiêu chí.
- Kiểm tra tổng điểm hợp lệ.
- Lưu version rubric để phiên luyện tập cũ luôn gắn với rubric chính xác.
- Xem trước rubric trước khi dùng cho AI chấm.
- Cho AI service nhận rubric ở định dạng có cấu trúc.

Dữ liệu cần lưu:

- Rubric version: câu hỏi áp dụng, số version, tổng điểm, hướng dẫn chấm.
- Rubric criteria: thứ tự, tên, mô tả, điểm tối đa.

Điều kiện kiểm tra:

- Không lưu rubric nếu tiêu chí rỗng hoặc tổng điểm không hợp lệ.
- Điểm tiêu chí không âm và tổng điểm không vượt giới hạn.
- Khi sửa rubric đã được dùng, hệ thống tạo version mới thay vì ghi đè.

### 3.5 Tạo phiên luyện tập

Chức năng cần có:

- Sinh viên chọn học phần và câu hỏi.
- Hệ thống tạo phiên luyện tập gắn với sinh viên, question version và rubric version hiện hành.
- Hiển thị trạng thái tải dữ liệu, lỗi, rỗng và nút thử lại.
- Theo dõi trạng thái phiên: draft, uploaded, transcribing, transcript_review, grading, completed, failed, cancelled.
- Cho phép hủy phiên chưa hoàn tất nếu cần.

Dữ liệu cần lưu:

- Practice session: sinh viên, câu hỏi, rubric, trạng thái, thời điểm tạo/cập nhật/hoàn tất.

Điều kiện kiểm tra:

- Một phiên luôn gắn đúng người dùng, câu hỏi và rubric.
- Sinh viên không tạo được phiên cho câu hỏi ngoài học phần của mình.
- Phiên lỗi có đường phục hồi rõ ràng: thử lại upload, thử lại STT hoặc thử lại chấm.

### 3.6 Ghi âm và quản lý audio

Chức năng cần có:

- Xin quyền microphone từ trình duyệt.
- Bắt đầu ghi âm, tạm dừng/dừng ghi âm nếu trình duyệt hỗ trợ.
- Nghe lại bản ghi.
- Ghi lại trước khi gửi.
- Hiển thị thời lượng ghi âm.
- Gửi file audio lên backend.
- Kiểm tra định dạng, dung lượng, thời lượng và trạng thái phiên.
- Lưu audio ở vùng riêng tư, không public URL.
- Cho phép retry upload khi lỗi mạng hoặc lỗi server.
- Thông báo rõ khi người dùng từ chối quyền microphone, trình duyệt không hỗ trợ hoặc file quá lớn.

Dữ liệu cần lưu:

- Audio asset: session, object key, mime type, dung lượng, thời lượng, hash, thời điểm upload, thời điểm hết hạn/xóa.

Điều kiện kiểm tra:

- File sai định dạng hoặc quá dung lượng bị từ chối.
- Người không sở hữu phiên không tải/xem được audio.
- Audio không được đưa vào thư mục public frontend hoặc log.

### 3.7 Chuyển giọng nói thành chữ tiếng Việt

Chức năng cần có:

- Backend gửi audio sang AI service hoặc adapter STT.
- AI service gọi provider STT hoặc mock tùy cấu hình môi trường.
- Lưu trạng thái đang xử lý, thành công, thất bại.
- Trả transcript tiếng Việt cho backend.
- Lưu metadata STT: provider, model version, ngôn ngữ, thời gian xử lý, lỗi nếu có.
- Cho phép retry STT mà không xóa lịch sử lần chạy trước.
- Hiển thị tiến trình hoặc trạng thái chờ cho sinh viên.

Dữ liệu cần lưu:

- Transcription run: session, audio, provider, model version, raw transcript, trạng thái, lỗi, thời gian xử lý.
- Transcript hiện hành trong practice session.

Điều kiện kiểm tra:

- STT lỗi không làm mất phiên luyện tập.
- Retry tạo một transcription run mới.
- Transcript và metadata đủ để tái lập hoặc giải thích kết quả nghiên cứu.

### 3.8 Xem, sửa và xác nhận transcript

Chức năng cần có:

- Sinh viên xem transcript máy tạo.
- Sinh viên sửa lỗi nhận dạng trước khi gửi chấm.
- Lưu transcript đã chỉnh sửa.
- Xác nhận transcript để chuyển sang bước chấm.
- Cảnh báo nếu transcript rỗng hoặc quá ngắn.
- Khóa transcript sau khi đã dùng để chấm, hoặc tạo phiên bản mới nếu cần chấm lại.

Dữ liệu cần lưu:

- Transcript text đã xác nhận.
- Thời điểm xác nhận transcript.
- Có thể lưu lịch sử revision nếu nhóm nghiên cứu cần phân tích mức độ sửa.

Điều kiện kiểm tra:

- Sinh viên chỉ sửa transcript của phiên mình sở hữu.
- Chỉ transcript đã xác nhận mới được gửi sang AI chấm.
- Transcript sau khi chấm không bị thay đổi âm thầm.

### 3.9 Chấm điểm bằng AI theo rubric

Chức năng cần có:

- Backend gửi transcript, câu hỏi, đáp án tham chiếu và rubric sang AI service.
- AI service chấm theo rubric và trả kết quả có cấu trúc.
- Kiểm tra schema kết quả AI trước khi lưu.
- Kiểm tra điểm từng tiêu chí không vượt điểm tối đa.
- Lưu tổng điểm, điểm từng tiêu chí, bằng chứng, nhận xét, ý đúng, ý thiếu, ý sai và gợi ý cải thiện.
- Lưu metadata: provider, model version, prompt version, rubric version, thời gian xử lý.
- Cho phép retry chấm nếu AI lỗi hoặc trả sai định dạng.
- Đánh dấu kết quả cần giảng viên xem lại nếu AI thiếu chắc chắn hoặc lỗi giới hạn.

Dữ liệu cần lưu:

- Evaluation run: session, rubric version, provider, model version, prompt version, total score, max score, trạng thái, lỗi.
- Evaluation criterion score: tiêu chí, điểm, bằng chứng, feedback, ý thiếu/sai.

Điều kiện kiểm tra:

- Kết quả AI sai schema không được lưu như kết quả hợp lệ.
- Tổng điểm không vượt tổng điểm rubric.
- Mỗi kết quả luôn biết đã dùng câu hỏi, transcript, rubric, model và prompt nào.

### 3.10 Hiển thị kết quả cho sinh viên

Chức năng cần có:

- Hiển thị tổng điểm và điểm tối đa.
- Hiển thị điểm theo từng tiêu chí trong rubric.
- Hiển thị bằng chứng/đoạn nội dung liên quan từ câu trả lời.
- Hiển thị ý trả lời đúng, ý còn thiếu, ý sai hoặc chưa chính xác.
- Hiển thị gợi ý cải thiện cho lần luyện tập sau.
- Hiển thị thông báo rõ rằng điểm AI chỉ để luyện tập và tham khảo.
- Cho phép quay lại học phần/câu hỏi hoặc luyện lại.
- Xử lý trạng thái chấm lỗi và nút thử lại nếu được phép.

Dữ liệu cần đọc:

- Practice session.
- Question version.
- Rubric version và criteria.
- Evaluation run mới nhất hợp lệ.
- Criterion scores.

Điều kiện kiểm tra:

- Sinh viên chỉ xem được kết quả của mình.
- Kết quả hiển thị đúng rubric version đã dùng khi chấm.
- Giao diện xử lý được trường hợp chưa có kết quả, đang chấm, chấm lỗi.

### 3.11 Lịch sử luyện tập

Chức năng cần có:

- Sinh viên xem danh sách các phiên luyện tập trước.
- Lọc/sắp xếp theo học phần, câu hỏi, ngày tạo, trạng thái hoặc điểm.
- Xem chi tiết một phiên đã hoàn tất.
- Xem lại transcript, điểm, nhận xét và gợi ý.
- Không cho sinh viên xem phiên của người khác.
- Giảng viên có thể xem các phiên thuộc học phần mình phụ trách nếu phục vụ chấm mẫu/nghiên cứu và có quyền phù hợp.

Dữ liệu cần đọc:

- Practice session theo student.
- Audio metadata nếu cần, transcript, evaluation run.
- Course, question version, rubric version.

Điều kiện kiểm tra:

- Lịch sử chỉ hiện dữ liệu đúng người dùng.
- Phiên cũ vẫn đọc được dù câu hỏi/rubric hiện tại đã có version mới.

### 3.12 Chấm mẫu và so sánh với AI

Chức năng cần có:

- Giảng viên chọn phiên luyện tập cần chấm mẫu.
- Giảng viên xem câu hỏi, đáp án tham chiếu, transcript và rubric.
- Giảng viên nhập điểm từng tiêu chí và nhận xét.
- Hệ thống lưu điểm người chấm theo rubric version.
- So sánh điểm AI với điểm giảng viên theo tổng điểm và từng tiêu chí.
- Cho phép nhiều người chấm độc lập nếu nghiên cứu yêu cầu.
- Xuất dữ liệu đối chiếu đã khử định danh.

Dữ liệu cần lưu:

- Human review: session, reviewer, rubric version, tổng điểm, ghi chú.
- Human review criterion score: tiêu chí, điểm, nhận xét.

Điều kiện kiểm tra:

- Điểm giảng viên không vượt điểm tối đa từng tiêu chí.
- So sánh chỉ ghép các kết quả dùng cùng rubric version.
- Dữ liệu xuất không chứa email, tên thật hoặc thông tin định danh không cần thiết.

### 3.13 Đánh giá nghiên cứu và đo chất lượng

Chức năng cần có:

- Lưu protocol đánh giá STT, chấm AI và khả dụng.
- Tạo tập audio/transcript mẫu tách biệt với dữ liệu phát triển nếu có.
- Tính chỉ số STT, ví dụ WER/CER hoặc tỷ lệ lỗi theo tiêu chí nhóm chọn.
- Tính chênh lệch điểm AI và điểm giảng viên.
- Ghi nhận model, prompt, rubric, dữ liệu đầu vào và thời điểm chạy.
- Tổng hợp kết quả theo bảng có thể tái lập.
- Lưu hoặc xuất dữ liệu khảo sát khả dụng.

Dữ liệu cần có:

- Bộ audio mẫu, transcript chuẩn, transcript máy.
- Evaluation runs, human reviews.
- Cấu hình provider/model/prompt.
- Phiếu khảo sát người dùng nếu có.

Điều kiện kiểm tra:

- Metric có công thức rõ ràng.
- Tập đánh giá không bị trộn với dữ liệu dùng để tinh chỉnh prompt.
- Kết quả có thể chạy lại hoặc kiểm tra thủ công.

### 3.14 Hướng dẫn demo và thông báo giới hạn AI

Chức năng cần có:

- Dữ liệu demo: tài khoản mẫu, học phần mẫu, câu hỏi mẫu, rubric mẫu.
- Hướng dẫn chạy frontend, backend, AI service và database.
- Hướng dẫn cấu hình biến môi trường và secret.
- Thông báo trong giao diện rằng AI chỉ hỗ trợ luyện tập.
- Mô tả lỗi thường gặp: microphone, upload, STT, AI chấm, hết phiên đăng nhập.
- Checklist demo từ đăng nhập đến xem kết quả.

Điều kiện kiểm tra:

- Người mới clone repo có thể chạy theo hướng dẫn.
- Demo có ít nhất một luồng thành công và một số luồng lỗi được xử lý rõ.

## 4. Chức năng phi chức năng và vận hành

### 4.1 Bảo mật và riêng tư

- Không lưu password dạng thuần.
- Không commit secret, API key, audio thật hoặc dữ liệu cá nhân.
- Backend là nơi thực thi quyền truy cập chính.
- Audio lưu riêng tư, không công khai qua URL tĩnh.
- Log không chứa transcript/audio/token hoặc dữ liệu nhạy cảm quá mức.
- Có thông báo xin phép ghi âm và mục đích sử dụng dữ liệu.
- Có cơ chế đồng ý tham gia nghiên cứu riêng nếu dùng dữ liệu cho nghiên cứu.
- Có kế hoạch xóa audio hoặc đặt thời hạn lưu.

### 4.2 Tính đúng đắn và tái lập

- Câu hỏi, rubric, prompt, model và kết quả cần có version.
- Retry STT/chấm AI tạo bản ghi run mới thay vì ghi đè mất dấu vết.
- Phiên luyện tập cũ vẫn giải thích được dù nội dung hiện tại đã thay đổi.
- Điểm số dùng kiểu chính xác, không dùng số thực gây sai lệch khi cộng điểm.

### 4.3 Khả dụng và trải nghiệm

- Mọi bước dài như upload, STT, chấm AI phải có trạng thái đang xử lý.
- Các lỗi thường gặp phải có thông báo dễ hiểu và hướng xử lý.
- Giao diện cần xử lý dữ liệu rỗng, mất mạng, hết phiên và quyền bị từ chối.
- Luồng sinh viên cần ít bước, rõ ràng: chọn câu hỏi → ghi âm → xác nhận transcript → xem kết quả.

### 4.4 Tích hợp hệ thống

- Frontend chỉ gọi Spring Boot backend.
- Backend gọi AI service nội bộ.
- AI service không là nguồn dữ liệu chuẩn.
- Cần DTO rõ cho các nhóm API: auth, course, question, rubric, session, audio, transcript, evaluation, human review, research export.
- Cần mock hoặc adapter để frontend/backend vẫn phát triển khi provider STT/LLM chưa sẵn sàng.

### 4.5 Kiểm thử

- Unit test cho validate điểm rubric, phân quyền, trạng thái phiên.
- Integration test cho API chính: auth, course/question/rubric, session, upload, transcript, evaluation.
- Test luồng frontend cho sinh viên và giảng viên.
- Test lỗi: thiếu quyền, token hết hạn, upload sai định dạng, STT lỗi, AI trả sai schema.
- Test bảo mật cơ bản: không xem/sửa dữ liệu của người khác.

## 5. Ma trận chức năng theo backlog

| Backlog | Chức năng hệ thống tương ứng |
|---|---|
| PB-01 | Khảo sát repo, stack, license, API, dữ liệu, quyết định tích hợp |
| PB-02 | Xác thực, phân quyền, route theo vai trò, bảo vệ API |
| PB-03 | Quản lý học phần, câu hỏi, đáp án tham chiếu |
| PB-04 | Quản lý rubric, tiêu chí, thang điểm, version rubric |
| PB-05 | Chọn học phần/câu hỏi, tạo phiên luyện tập, trạng thái tải/lỗi |
| PB-06 | Ghi âm, nghe lại, ghi lại, upload và lưu audio riêng tư |
| PB-07 | STT tiếng Việt, sửa và xác nhận transcript, lưu metadata STT |
| PB-08 | AI chấm theo rubric, validate schema, lưu điểm và metadata model/prompt |
| PB-09 | Hiển thị giải thích, ý đúng/thiếu/sai, gợi ý và lịch sử |
| PB-10 | Giảng viên chấm mẫu, so sánh AI, xuất dữ liệu ẩn danh |
| PB-11 | Đo chất lượng STT, chênh lệch chấm, khả dụng, protocol nghiên cứu |
| PB-12 | Hướng dẫn chạy/demo, dữ liệu demo, thông báo giới hạn AI |

## 6. Ưu tiên triển khai đề xuất

| Mức ưu tiên | Chức năng |
|---|---|
| Must | Đăng nhập/phân quyền, học phần, câu hỏi, rubric, phiên luyện tập, ghi âm/upload, STT, xác nhận transcript, chấm AI, lưu kết quả |
| Should | Lịch sử luyện tập, giải thích chi tiết, gợi ý cải thiện, chấm đối chiếu, xuất dữ liệu nghiên cứu, hướng dẫn demo |
| Could | Lọc nâng cao, nhiều người chấm độc lập, lịch sử sửa transcript đầy đủ, dashboard thống kê tiến bộ |
| Won't for MVP | Thi chính thức, chống gian lận, nhận diện khuôn mặt/cảm xúc, hội thoại giọng nói hai chiều, dashboard nâng cao, hệ thống đa học phần quy mô lớn |

## 7. Checklist chức năng tối thiểu để demo MVP

- [ ] Sinh viên đăng nhập được.
- [ ] Giảng viên đăng nhập được.
- [ ] Backend chặn API sai vai trò.
- [ ] Sinh viên xem học phần và câu hỏi từ cơ sở dữ liệu.
- [ ] Giảng viên tạo/sửa câu hỏi và đáp án tham chiếu.
- [ ] Giảng viên tạo rubric có tiêu chí và tổng điểm hợp lệ.
- [ ] Sinh viên tạo phiên luyện tập từ một câu hỏi.
- [ ] Sinh viên ghi âm, nghe lại, ghi lại và upload audio.
- [ ] Hệ thống lưu audio riêng tư và lưu metadata.
- [ ] Hệ thống tạo transcript tiếng Việt từ audio.
- [ ] Sinh viên sửa và xác nhận transcript.
- [ ] AI chấm transcript theo rubric và trả kết quả có cấu trúc.
- [ ] Sinh viên xem điểm, nhận xét và gợi ý.
- [ ] Sinh viên xem lại lịch sử luyện tập của mình.
- [ ] Giảng viên chấm mẫu ít nhất một phiên và so sánh với AI.
- [ ] Nhóm xuất được dữ liệu nghiên cứu đã khử định danh.
- [ ] Có hướng dẫn chạy và dữ liệu demo.

## 8. Ranh giới ngoài phạm vi MVP

Các chức năng sau không nên đưa vào MVP nếu làm chậm luồng luyện tập cốt lõi:

- Thi chính thức hoặc dùng điểm AI làm điểm học phần.
- Giám sát/chống gian lận.
- Nhận diện khuôn mặt, cảm xúc hoặc danh tính qua giọng nói.
- Hội thoại giọng nói hai chiều thời gian thực.
- Huấn luyện mô hình STT riêng.
- Dashboard phân tích tiến bộ nâng cao.
- Hệ thống quản lý nhiều khoa/nhiều học kỳ ở quy mô lớn.
- Thanh toán, gói dịch vụ hoặc quota thương mại.

## 9. Kết luận

MVP nên tập trung vào một luồng hoàn chỉnh và kiểm chứng được: **đăng nhập → chọn câu hỏi → ghi âm → transcript → xác nhận → chấm AI → xem kết quả → xem lịch sử**. Các chức năng quản lý nội dung của giảng viên và chấm đối chiếu phục vụ nghiên cứu cần đủ dùng, nhưng không nên mở rộng thành hệ thống quản trị phức tạp trong release đầu.
