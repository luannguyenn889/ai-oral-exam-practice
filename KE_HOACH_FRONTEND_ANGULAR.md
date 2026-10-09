# Kế hoạch triển khai Frontend Angular

## 1. Mục tiêu

Xây dựng frontend Angular cho hệ thống ôn luyện thi vấn đáp, ưu tiên hoàn thành luồng sinh viên từ chọn câu hỏi đến xem kết quả. Frontend có thể phát triển trước backend bằng dữ liệu giả, nhưng phải theo DTO và hợp đồng API thống nhất với Spring Boot.

### Stack đã thống nhất

- **Frontend:** Angular + TypeScript.
- **Backend nghiệp vụ:** Spring Boot; Angular chỉ giao tiếp với Spring Boot.
- **AI service:** Python FastAPI; Spring Boot gọi service này để xử lý STT và chấm điểm.

## 2. Phạm vi FE MVP

### Sinh viên

1. Đăng nhập hoặc chọn chế độ demo trong giai đoạn phát triển.
2. Xem học phần và chọn câu hỏi.
3. Ghi âm, dừng, nghe lại hoặc ghi lại câu trả lời.
4. Gửi bài và theo dõi trạng thái xử lý.
5. Xem, chỉnh sửa và xác nhận transcript trước khi chấm.
6. Xem điểm tổng, điểm từng tiêu chí, bằng chứng, nội dung thiếu/sai và gợi ý cải thiện.
7. Xem lại các phiên luyện tập trước.

### Giảng viên

1. Xem học phần phụ trách.
2. Xem/thêm/sửa câu hỏi và đáp án tham chiếu.
3. Tạo rubric gồm tiêu chí, mô tả, điểm tối đa và hướng dẫn bổ sung.
4. Xem trước rubric và tổng điểm.

### Hoãn khỏi FE MVP

Dashboard thống kê nâng cao, biểu đồ tiến bộ phức tạp, quản trị viên toàn hệ thống, thông báo thời gian thực và mọi chức năng giám sát thi. Chỉ thêm sau khi luồng luyện tập cơ bản chạy ổn định.

## 3. Điều kiện cần thống nhất trước khi lập trình

- Phiên bản Angular và quy ước cấu trúc project.
- Tên route và vai trò người dùng.
- DTO dùng chung cho học phần, câu hỏi, rubric, phiên luyện tập, transcript, kết quả và lỗi API.
- Định dạng audio được hỗ trợ, giới hạn thời lượng/dung lượng và quy tắc upload multipart.
- Trạng thái xử lý phiên: `draft`, `recording`, `uploaded`, `transcribing`, `transcript_review`, `grading`, `completed`, `transcription_failed`, `grading_failed`, `cancelled`.
- API nào chạy đồng bộ; API nào trả `job_id` để frontend kiểm tra trạng thái.
- Cách hiển thị thông báo về AI và cách người dùng xác nhận transcript.

## 4. Sơ đồ điều hướng đề xuất

```text
/login
/student/dashboard
/student/courses
/student/courses/:courseId/questions
/student/practice/:questionId
/student/sessions/:sessionId/transcript
/student/sessions/:sessionId/result
/student/history
/instructor/courses
/instructor/questions
/instructor/questions/new
/instructor/questions/:questionId/edit
/instructor/questions/:questionId/rubric
```

Route guard chỉ cải thiện điều hướng và trải nghiệm; Spring Boot vẫn phải xác thực và phân quyền trên mọi API.

## 5. Mô hình frontend đề xuất

Đặt các model theo hợp đồng backend, tránh tạo kiểu dữ liệu riêng theo từng component:

```ts
export type PracticeStatus =
  | 'draft'
  | 'recording'
  | 'uploaded'
  | 'transcribing'
  | 'transcript_review'
  | 'grading'
  | 'completed'
  | 'transcription_failed'
  | 'grading_failed'
  | 'cancelled';

export interface RubricCriterion {
  id: string;
  name: string;
  description: string;
  maxScore: number;
}

export interface CriterionEvaluation {
  criterionId: string;
  score: number;
  maxScore: number;
  evidence: string;
  missingOrIncorrect: string[];
  feedback: string;
}

export interface Evaluation {
  totalScore: number;
  maxScore: number;
  criteria: CriterionEvaluation[];
  strengths: string[];
  improvements: string[];
  uncertaintyNotes: string[];
  needsHumanReview: boolean;
}
```

Các model `Course`, `Question`, `Rubric`, `PracticeSession`, `ApiError` cần được bổ sung cùng Spring Boot. Chốt cách đặt tên JSON (camelCase hay snake_case) và quy tắc ngày giờ trước khi tích hợp.

## 6. Cấu trúc mã Angular gợi ý

```text
src/app/
  core/
    auth/
    guards/
    interceptors/
    layout/
  shared/
    components/
    models/
    utilities/
  features/
    student-dashboard/
    course-selection/
    question-bank/
    practice-session/
    transcript-review/
    evaluation-result/
    practice-history/
    instructor-questions/
    rubric-editor/
  data-access/
    api/
    mock/
```

Component tập trung hiển thị và nhận thao tác. API service quản lý tải/gửi dữ liệu. Logic ghi âm nên tách vào `AudioRecorderService`; logic trạng thái phiên nên tập trung trong feature service/store phù hợp quy mô dự án.

## 7. Trình tự thực hiện

### Giai đoạn A — Khởi tạo và quy ước

- Tạo Angular app, cấu hình lint/format theo quy ước nhóm.
- Tạo layout, menu theo vai trò, route và trang lỗi/không tìm thấy.
- Khai báo model TypeScript và dữ liệu mock.
- Tạo môi trường `development` và `production`; URL Spring Boot lấy từ environment, không hard-code trong component.

**Đầu ra:** ứng dụng chạy được, điều hướng được, có layout sinh viên và giảng viên.

### Giai đoạn B — Luồng chọn câu hỏi

- Trang danh sách học phần.
- Trang danh sách câu hỏi theo học phần/chủ đề.
- Trạng thái tải, danh sách rỗng, lỗi tải và thử lại.

**Đầu ra:** sinh viên chọn được câu hỏi bằng dữ liệu mock.

### Giai đoạn C — Ghi âm và quản lý phiên

- Màn hình hướng dẫn micro và xin quyền ghi âm.
- Nút bắt đầu/dừng, thời lượng, trạng thái ghi âm.
- Nghe lại, xóa/ghi lại và xác nhận gửi.
- Xử lý không có micro, trình duyệt từ chối quyền, file rỗng/quá dài, rời trang khi đang ghi.
- Dùng mock để mô phỏng upload và trạng thái đang xử lý.

**Đầu ra:** hoàn thành thao tác ghi âm trên trình duyệt mà chưa cần STT thật.

### Giai đoạn D — Transcript và kết quả

- Trang xác nhận transcript cho phép sửa trước khi yêu cầu chấm.
- Màn hình loading/chấm, lỗi và retry.
- Trang kết quả hiển thị tổng điểm, điểm từng tiêu chí, bằng chứng, điểm thiếu/sai và khuyến nghị.
- Trạng thái cần giảng viên xem lại nếu AI không chắc chắn.

**Đầu ra:** demo được toàn bộ luồng với dữ liệu mẫu có cấu trúc.

### Giai đoạn E — Khu vực giảng viên

- Danh sách câu hỏi, tạo/sửa câu hỏi và đáp án tham chiếu.
- Trình chỉnh sửa rubric có kiểm tra điểm tối đa và tổng điểm.
- Xem trước câu hỏi cùng rubric như cách sinh viên sẽ sử dụng.

**Đầu ra:** giảng viên cấu hình được nội dung mẫu cho một học phần.

### Giai đoạn F — Tích hợp Spring Boot

Thay mock bằng API thật theo lát cắt nhỏ, giữ nguyên interface mà component sử dụng:

1. Đăng nhập/hồ sơ và phân quyền.
2. Học phần/câu hỏi/rubric.
3. Tạo phiên và tải audio.
4. Yêu cầu STT, nhận transcript và hiển thị để xác nhận.
5. Gửi transcript đã xác nhận để chấm.
6. Kết quả và lịch sử phiên.

Khi tích hợp, xử lý thống nhất HTTP lỗi, timeout, mất mạng, upload thất bại, hết phiên đăng nhập và retry. Không retry tự động các yêu cầu tạo dữ liệu nếu backend chưa hỗ trợ idempotency.

## 8. Mock API và hợp đồng giao tiếp

Tạo `PracticeApi`/service abstraction dùng chung và thay provider mock bằng provider HTTP khi backend có sẵn. Component không nên biết đang dùng mock hay backend.

Các hoạt động frontend cần:

- `getCourses()`
- `getQuestions(courseId, filters)`
- `getQuestion(questionId)`
- `createPracticeSession(questionId)`
- `uploadAudio(sessionId, audioFile)`
- `requestTranscription(sessionId)`
- `saveConfirmedTranscript(sessionId, transcript)`
- `requestEvaluation(sessionId)`
- `getEvaluation(sessionId)`
- `getPracticeHistory(filters)`
- `saveQuestion(question)` / `saveRubric(questionId, rubric)`

Nếu Spring Boot dùng job bất đồng bộ, API trả `jobId` và frontend hiển thị trạng thái `transcribing`/`grading`, truy vấn trạng thái theo nhịp hợp lý, dừng truy vấn khi hoàn tất hoặc lỗi. Không gọi FastAPI từ Angular; thông tin xác thực AI service phải ở server.

## 9. Tiêu chí nghiệm thu frontend

- Người dùng đi hết luồng chọn câu hỏi → ghi âm → xác nhận transcript → xem kết quả bằng mock.
- Giao diện có loading, empty, success và error state cho các thao tác chính.
- Từ chối micro hoặc trình duyệt không hỗ trợ được giải thích rõ và không làm trang treo.
- Transcript có thể chỉnh sửa trước khi gửi chấm; kết quả thể hiện đúng các trường rubric.
- Component không chứa dữ liệu nghiệp vụ hard-code; dữ liệu đi qua service và model.
- Không để lộ API key/provider secret; FE chỉ gọi Spring Boot.
- Dùng được ở kích thước desktop và mobile; các nút ghi âm/gửi có trạng thái disabled phù hợp.
- Khi nối backend, định dạng request/response khớp hợp đồng và lỗi API được hiển thị thân thiện.

## 10. Lịch FE gợi ý (3 tuần, có thể chạy song song backend)

| Thời gian | Công việc | Đầu ra |
|---|---|---|
| Tuần 1 | Khởi tạo Angular, route/layout, DTO, mock data, chọn học phần/câu hỏi | Prototype có điều hướng và luồng chọn câu hỏi |
| Tuần 2 | Ghi âm, phát lại, transcript review, kết quả mock | Demo được luồng sinh viên cốt lõi |
| Tuần 3 | Câu hỏi/rubric giảng viên, hoàn thiện trạng thái lỗi, tích hợp API đầu tiên | FE MVP sẵn sàng ghép Spring Boot |

## 11. Bàn giao FE

- Mã nguồn Angular và hướng dẫn chạy.
- Danh sách route và ảnh/chụp prototype các màn hình chính.
- DTO/API contract được thống nhất với backend.
- Mock data/service phục vụ demo offline.
- Danh sách API còn chờ Spring Boot và trạng thái tích hợp.
- Checklist các kịch bản micro, upload, transcript, chấm và lỗi.

## 12. Việc làm đầu tiên

1. Tạo project Angular và thống nhất phiên bản/cấu trúc với nhóm.
2. Chốt DTO `Question`, `Rubric`, `PracticeSession`, `Evaluation` với người làm Spring Boot.
3. Làm route và màn hình chọn câu hỏi bằng mock.
4. Tiếp đến làm ghi âm/phát lại, rồi transcript review và kết quả mock.
5. Mỗi tuần tích hợp ít nhất một API Spring Boot để phát hiện lệch hợp đồng sớm.
