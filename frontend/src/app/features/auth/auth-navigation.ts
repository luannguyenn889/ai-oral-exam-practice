import { Router } from '@angular/router';
import { UserRole } from '../../shared/models';

// Sau login hoặc register, chuyển người dùng tới khu vực đúng với role backend trả về.
export function navigateForRole(router: Router, role: UserRole): Promise<boolean> {
  const destinations: Record<UserRole, string> = {
    student: '/student/dashboard',
    instructor: '/instructor/questions',
    admin: '/admin/dashboard',
  };
  return router.navigateByUrl(destinations[role]);
}
