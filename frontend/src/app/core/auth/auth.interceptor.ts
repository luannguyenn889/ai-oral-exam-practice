import { HttpInterceptorFn } from '@angular/common/http';

// Gắn JWT vào API nghiệp vụ Spring Boot; không gửi token sang AI Service (:8000/ai/*) hoặc login/register.
export const authInterceptor: HttpInterceptorFn = (request, next) => {
  if (
    request.url.includes('/auth/login') ||
    request.url.includes('/auth/register') ||
    request.url.includes('/ai/')
  ) {
    return next(request);
  }

  const token = localStorage.getItem('oral_exam_access_token');
  if (!token) return next(request);

  return next(
    request.clone({
      setHeaders: { Authorization: `Bearer ${token}` },
    }),
  );
};
