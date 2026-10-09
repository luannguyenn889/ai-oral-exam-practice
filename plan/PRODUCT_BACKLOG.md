# Product Backlog

## Mục tiêu release

Hoàn thành MVP có thể demo và đánh giá trong 12 tuần. Ưu tiên luồng luyện tập cốt lõi và khả năng kiểm chứng kết quả; hoãn quản trị nâng cao, chống gian lận, phân tích tiến bộ phức tạp và hỗ trợ nhiều học phần quy mô lớn.

## Backlog ưu tiên

| ID | Epic / User story | Ưu tiên | Điều kiện nghiệm thu chính | Dự kiến sprint |
|---|---|---|---|---|
| PB-01 | Là nhóm phát triển, chúng tôi cần xác minh repo tham khảo, stack và ranh giới hệ thống để quyết định tích hợp | Must | Có phiếu khảo sát commit, lệnh chạy, license, API, dữ liệu và quyết định dùng/tham khảo/bỏ | 1 |
| PB-02 | Là sinh viên/giảng viên, tôi đăng nhập và chỉ truy cập chức năng/dữ liệu đúng vai trò | Must | API kiểm tra quyền; FE có route theo vai trò; thử được truy cập hợp lệ và bị từ chối | 2 |
| PB-03 | Là giảng viên, tôi tạo học phần, câu hỏi và đáp án tham chiếu | Must | Dữ liệu được validate, lưu bền vững và hiển thị đúng trong danh sách | 2 |
| PB-04 | Là giảng viên, tôi tạo rubric có tiêu chí, thang điểm và phiên bản | Must | Tổng điểm hợp lệ; sửa rubric tạo phiên bản mới; phiên cũ vẫn trỏ đúng version | 3 |
| PB-05 | Là sinh viên, tôi chọn học phần/câu hỏi và tạo phiên luyện tập | Must | Tải, rỗng, lỗi và thử lại có trạng thái rõ; phiên gắn đúng người/câu hỏi | 3 |
| PB-06 | Là sinh viên, tôi ghi âm, nghe lại, ghi lại và gửi câu trả lời | Must | Chặn định dạng/kích thước sai; thể hiện quyền micro và lỗi upload; audio không công khai | 3 |
| PB-07 | Là sinh viên, tôi nhận transcript tiếng Việt và sửa/xác nhận trước khi chấm | Must | Trạng thái STT/lỗi/retry rõ; lưu transcript và metadata phiên bản STT | 4 |
| PB-08 | Là sinh viên, tôi nhận đánh giá có cấu trúc theo rubric | Must | Kiểm tra schema, điểm, tiêu chí, bằng chứng; lưu phiên bản model/prompt/rubric | 5 |
| PB-09 | Là sinh viên, tôi xem giải thích, ý đúng/thiếu/sai, gợi ý và lịch sử | Should | Kết quả trỏ đúng phiên; lịch sử chỉ hiển thị phiên thuộc người dùng | 5 |
| PB-10 | Là giảng viên/nghiên cứu viên, tôi chấm mẫu và so sánh với AI | Must | Xuất dữ liệu ẩn danh; ghép cặp điểm theo rubric; lưu nhận xét/phiên bản | 5–6 |
| PB-11 | Là nhóm nghiên cứu, chúng tôi đo STT, chênh lệch chấm và khả dụng | Must | Protocol, tập đánh giá tách biệt, metric và bảng kết quả có thể tái lập | 1, 5–6 |
| PB-12 | Là người dùng demo, tôi có hướng dẫn và thông báo đúng về giới hạn AI | Should | Có hướng dẫn chạy, dữ liệu demo và thông báo đây là công cụ luyện tập | 6 |

## Definition of Ready

- User story có mục tiêu và người dùng rõ.
- Tiêu chí nghiệm thu đủ cụ thể để demo/đối chiếu.
- Phụ thuộc và người review đã xác định; API/DTO có mock nếu thành phần phụ thuộc chưa sẵn.
- Quyền dữ liệu/đồng ý nghiên cứu được xác định trước các việc liên quan dữ liệu người thật.

## Definition of Done

- Code/tài liệu hoàn chỉnh theo tiêu chí nghiệm thu, được thành viên khác review.
- Tích hợp đúng hợp đồng DTO/API; có trạng thái lỗi và đường phục hồi phù hợp.
- Không đưa secret vào frontend/log; quyền truy cập được thực thi ở backend.
- Có demo hoặc artifact cụ thể cuối sprint. Tính năng nghiên cứu có nguồn dữ liệu, phiên bản cấu hình và phương pháp ghi nhận rõ.
- Không coi mock là tích hợp thật; phần còn mock được ghi rõ trên board và trong demo.

## Ngoài phạm vi release

Thi chính thức, giám sát/chống gian lận, nhận diện khuôn mặt/cảm xúc, hội thoại giọng nói hai chiều, mô hình STT tự huấn luyện, dashboard nâng cao, hệ thống đa học phần quy mô lớn.
