# AI Oral Exam Practice

Khung dự án ban đầu gồm ba service độc lập: Angular frontend, Spring Boot backend và FastAPI AI service. Spring Boot là API duy nhất mà trình duyệt gọi; Spring Boot gọi AI service nội bộ. Hiện tại chỉ có endpoint health để kiểm tra kết nối, chưa triển khai nghiệp vụ STT/chấm điểm.

```mermaid
flowchart LR
  U[Browser] --> FE[Angular :4200]
  FE -->|/api proxy| BE[Spring Boot :8080]
  BE -->|service HTTP| AI[FastAPI :8000]
```

## Cấu trúc

```text
frontend/       Angular UI và API client
backend/        Spring Boot API nghiệp vụ, health check AI
ai-service/     FastAPI, điểm vào cho pipeline STT/LLM
plan/           Product backlog và kế hoạch Scrum 12 tuần
```

## Yêu cầu môi trường

- Node.js 22.12 trở lên và npm 10+ cho Angular 21.
- Java 21 và Maven 3.6.3 trở lên cho Spring Boot.
- Python 3.10 trở lên và `uv` hoặc `pip` cho FastAPI.

## Chạy từng service trên Windows PowerShell

Mở ba terminal riêng tại thư mục dự án.

### 1. AI service

```powershell
cd ai-service
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Nếu chính sách PowerShell chặn activate, chạy trực tiếp ` .\.venv\Scripts\python.exe -m pip install -e .` và ` .\.venv\Scripts\python.exe -m uvicorn ...` (bỏ khoảng trắng đầu lệnh).

### 2. Backend

```powershell
cd backend
mvn spring-boot:run
```

Backend mặc định kết nối PostgreSQL tại `localhost:5432/ai_oral_exam_practice`. Tạo database này trước lần chạy đầu. Hibernate dùng `ddl-auto: update` để tạo/cập nhật bảng cho các entity hiện có (`users`, `user_roles`) khi khởi động; SQL sẽ được in trong log backend. Đặt `DB_URL`, `DB_USERNAME`, `DB_PASSWORD` nếu PostgreSQL của bạn dùng cấu hình khác. `backend/src/main/resources/db/schema.sql` chứa schema PostgreSQL đầy đủ; Hibernate chỉ tự tạo bảng tương ứng với entity đã khai báo. Đặt `JWT_SECRET` thành chuỗi bí mật riêng dài ít nhất 32 bytes trước khi triển khai; giá trị mặc định chỉ dành cho chạy local.

### API đăng ký và đăng nhập

- `POST /api/auth/register` với JSON `{"email":"sv@example.com","fullName":"Nguyen Van A","password":"matkhau123","role":"student"}`. `role` nhận `student`, `instructor` (giáo viên) hoặc `admin` và được lưu đúng vào tài khoản.
- `POST /api/auth/login` với JSON `{"email":"sv@example.com","password":"matkhau123"}`.
- Cả hai endpoint trả `accessToken`, `tokenType`, `expiresIn` và thông tin user. Gửi token cho các API cần đăng nhập bằng header `Authorization: Bearer <accessToken>`.
- Email đã tồn tại trả `409`; thông tin đăng nhập sai hoặc tài khoản bị khóa trả `401`; dữ liệu không hợp lệ trả `400`.

### 3. Frontend

```powershell
cd frontend
npm.cmd install
npm.cmd start
```

Mở `http://localhost:4200`. Frontend dùng proxy `/api` sang Spring Boot. Backend health endpoint là `http://localhost:8080/api/health`; AI health endpoint là `http://localhost:8000/health`.

## Lệnh build

- Frontend: `cd frontend; npm.cmd run build`
- Backend: `cd backend; mvn -DskipTests package`
- AI: `cd ai-service; python -m compileall app`

## Tiếp theo

1. Chốt DTO và API cho học phần/câu hỏi/rubric/phiên luyện tập.
2. Bổ sung cấu hình DB và migration cho backend.
3. Thêm adapter STT và LLM trong AI service sau khi chốt provider, quyền dữ liệu và chi phí.
4. Thay health-only flow bằng upload audio, transcript review và đánh giá rubric theo các sprint trong `plan/`.

Không commit API key, audio thật, dữ liệu sinh viên hoặc file `.env`.
