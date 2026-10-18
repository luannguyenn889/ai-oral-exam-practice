import { HttpInterceptorFn } from '@angular/common/http';

// Gắn JWT vào API nghiệp vụ; không gửi token cũ kèm request login/register.
export const authInterceptor: HttpInterceptorFn = (request, next) => {
  if (request.url.includes('/auth/login') || request.url.includes('/auth/register')) {
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
