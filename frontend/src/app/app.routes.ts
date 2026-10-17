import { Routes } from '@angular/router';
import { roleGuard } from './core/guards/role.guard';

export const routes: Routes = [
  {
    path: '',
    redirectTo: 'student/dashboard',
    pathMatch: 'full',
  },
  {
    path: 'login',
    loadComponent: () => import('./features/auth/login.component').then((m) => m.LoginComponent),
  },

  // Luong Sinh vien
  {
    path: 'student',
    loadComponent: () =>
      import('./core/layout/student-layout.component').then((m) => m.StudentLayoutComponent),
    canActivate: [roleGuard(['student'])],
    children: [
      {
        path: '',
        redirectTo: 'dashboard',
        pathMatch: 'full',
      },
      {
        path: 'dashboard',
        loadComponent: () =>
          import('./features/student-dashboard/student-dashboard.component').then(
            (m) => m.StudentDashboardComponent,
          ),
      },
      {
        path: 'courses',
        loadComponent: () =>
          import('./features/course-selection/course-selection.component').then(
            (m) => m.CourseSelectionComponent,
          ),
      },
      {
        path: 'courses/:courseId/questions',
        loadComponent: () =>
          import('./features/question-bank/question-bank.component').then(
            (m) => m.QuestionBankComponent,
          ),
      },
      {
        path: 'practice/:questionId',
        loadComponent: () =>
          import('./shared/components/placeholder-page/placeholder-page.component').then(
            (m) => m.PlaceholderPageComponent,
          ),
        data: {
          title: 'Ghi âm bài làm vấn đáp',
          description:
            'Giao diện ghi âm, kiểm tra mic, đồng hồ đếm ngược và nghe lại audio (Giai đoạn C).',
          icon: 'mic',
        },
      },
      {
        path: 'sessions/:sessionId/transcript',
        loadComponent: () =>
          import('./shared/components/placeholder-page/placeholder-page.component').then(
            (m) => m.PlaceholderPageComponent,
          ),
        data: {
          title: 'Xem và xác nhận Transcript',
          description:
            'Trang cho phép sinh viên kiểm tra và sửa lại bản ghi nhận dạng giọng nói trước khi gửi chấm AI (Giai đoạn D).',
          icon: 'description',
        },
      },
      {
        path: 'sessions/:sessionId/result',
        loadComponent: () =>
          import('./shared/components/placeholder-page/placeholder-page.component').then(
            (m) => m.PlaceholderPageComponent,
          ),
        data: {
          title: 'Kết quả chấm điểm AI',
          description:
            'Hiển thị điểm tổng, điểm từng tiêu chí rubric, nhận xét bằng chứng và gợi ý cải thiện (Giai đoạn D).',
          icon: 'analytics',
        },
      },
      {
        path: 'history',
        loadComponent: () =>
          import('./shared/components/placeholder-page/placeholder-page.component').then(
            (m) => m.PlaceholderPageComponent,
          ),
        data: {
          title: 'Lịch sử luyện tập',
          description: 'Danh sách các phiên luyện tập đã thực hiện cùng kết quả chi tiết.',
          icon: 'history',
        },
      },
    ],
  },

  // Luong Giang vien
  {
    path: 'instructor',
    loadComponent: () =>
      import('./core/layout/instructor-layout.component').then((m) => m.InstructorLayoutComponent),
    canActivate: [roleGuard(['instructor'])],
    children: [
      {
        path: '',
        redirectTo: 'questions',
        pathMatch: 'full',
      },
      {
        path: 'courses',
        loadComponent: () =>
          import('./features/course-selection/course-selection.component').then(
            (m) => m.CourseSelectionComponent,
          ),
      },
      {
        path: 'questions',
        loadComponent: () =>
          import('./features/question-bank/question-bank.component').then(
            (m) => m.QuestionBankComponent,
          ),
      },
      {
        path: 'questions/new',
        loadComponent: () =>
          import('./shared/components/placeholder-page/placeholder-page.component').then(
            (m) => m.PlaceholderPageComponent,
          ),
        data: {
          title: 'Thêm mới câu hỏi vấn đáp',
          description: 'Soạn thảo nội dung câu hỏi và câu trả lời tham chiếu (Giai đoạn E).',
          icon: 'note_add',
        },
      },
      {
        path: 'questions/:questionId/edit',
        loadComponent: () =>
          import('./shared/components/placeholder-page/placeholder-page.component').then(
            (m) => m.PlaceholderPageComponent,
          ),
        data: {
          title: 'Chỉnh sửa câu hỏi',
          description: 'Cập nhật nội dung câu hỏi và câu trả lời tham chiếu.',
          icon: 'edit',
        },
      },
      {
        path: 'questions/:questionId/rubric',
        loadComponent: () =>
          import('./shared/components/placeholder-page/placeholder-page.component').then(
            (m) => m.PlaceholderPageComponent,
          ),
        data: {
          title: 'Thiết lập Rubric chấm điểm',
          description:
            'Tạo các tiêu chí đánh giá, thang điểm và hướng dẫn chấm cho AI (Giai đoạn E).',
          icon: 'fact_check',
        },
      },
    ],
  },

  // Trang loi va 404
  {
    path: 'error',
    loadComponent: () =>
      import('./features/error/error-page.component').then((m) => m.ErrorPageComponent),
  },
  {
    path: '**',
    loadComponent: () =>
      import('./features/error/not-found.component').then((m) => m.NotFoundComponent),
  },
];
