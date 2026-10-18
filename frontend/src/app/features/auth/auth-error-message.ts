import { HttpErrorResponse } from '@angular/common/http';

// Chuyển response lỗi phổ biến của backend thành thông báo tiếng Việt cho form auth.
export function authErrorMessage(error: unknown): string {
  if (!(error instanceof HttpErrorResponse)) return 'Không thể kết nối tới máy chủ.';
  const detail = error.error?.detail as string | undefined;
  if (error.status === 0) return 'Không kết nối được backend. Hãy kiểm tra backend và cấu hình API.';
  if (error.status === 401) return 'Email hoặc mật khẩu không chính xác.';
  if (error.status === 409) return 'Email này đã được đăng ký.';
  if (error.status === 400) return detail || 'Thông tin gửi lên chưa hợp lệ.';
  return detail || 'Có lỗi xảy ra. Vui lòng thử lại.';
}
