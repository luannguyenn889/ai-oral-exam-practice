import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../auth/auth.service';
import { UserRole } from '../../shared/models';

export const roleGuard = (allowedRoles: UserRole[]): CanActivateFn => {
  return () => {
    const authService = inject(AuthService);
    const router = inject(Router);

    const currentUser = authService.getCurrentUser();
    if (!currentUser) {
      router.navigate(['/login']);
      return false;
    }

    if (!allowedRoles.includes(currentUser.role)) {
      // Chuyển hướng về trang dashboard tương ứng với vai trò thực tế
      if (currentUser.role === 'student') {
        router.navigate(['/student/dashboard']);
      } else {
        router.navigate(['/instructor/questions']);
      }
      return false;
    }

    return true;
  };
};
