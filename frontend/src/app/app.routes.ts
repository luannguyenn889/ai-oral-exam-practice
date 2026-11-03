import { Routes } from '@angular/router';
import { roleGuard } from './core/guards/role.guard';

export const routes: Routes = [
  {
    path: '',
    redirectTo: 'login',
    pathMatch: 'full',
  },
  {
    path: 'login',
    loadComponent: () =>
      import('./features/auth/login/login.component').then((m) => m.LoginComponent),
  },
  {
    path: 'register',
    loadComponent: () =>
      import('./features/auth/register/register.component').then((m) => m.RegisterComponent),
  },

  // Luồng Sinh viên (/student/*)
  {
    path: 'student',
    loadComponent: () =>
      import('./core/layout/student-layout/student-layout.component').then(
        (m) => m.StudentLayoutComponent,
      ),
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
          import('./features/student/practice-recorder/practice-recorder.component').then(
            (m) => m.PracticeRecorderComponent,
          ),
      },
      {
        path: 'sessions/:sessionId/transcript',
        loadComponent: () =>
          import('./features/student/transcript-review/transcript-review.component').then(
            (m) => m.TranscriptReviewComponent,
          ),
      },
      {
        path: 'sessions/:sessionId/result',
        loadComponent: () =>
          import('./features/student/session-result/session-result.component').then(
            (m) => m.SessionResultComponent,
          ),
      },
      {
        path: 'history',
        loadComponent: () =>
          import('./features/student/student-history/student-history.component').then(
            (m) => m.StudentHistoryComponent,
          ),
      },
    ],
  },

  // Luồng Giảng viên (/instructor/*)
  {
    path: 'instructor',
    loadComponent: () =>
      import('./core/layout/instructor-layout/instructor-layout.component').then(
        (m) => m.InstructorLayoutComponent,
      ),
    canActivate: [roleGuard(['instructor'])],
    children: [
      {
        path: '',
        redirectTo: 'courses',
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
        path: 'courses/:courseId/documents',
        loadComponent: () =>
          import('./features/instructor/course-documents/course-documents.component').then(
            (m) => m.CourseDocumentsComponent,
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
          import('./features/instructor/question-editor/question-editor.component').then(
            (m) => m.QuestionEditorComponent,
          ),
      },
      {
        path: 'questions/import',
        loadComponent: () =>
          import('./features/instructor/question-import/question-import.component').then(
            (m) => m.QuestionImportComponent,
          ),
      },
      {
        path: 'questions/:questionId/edit',
        loadComponent: () =>
          import('./features/instructor/question-editor/question-editor.component').then(
            (m) => m.QuestionEditorComponent,
          ),
      },
      {
        path: 'questions/:questionId/rubric',
        loadComponent: () =>
          import('./features/instructor/rubric-editor/rubric-editor.component').then(
            (m) => m.RubricEditorComponent,
          ),
      },
    ],
  },

  // Luồng Quản trị viên (/admin/*)
  {
    path: 'admin',
    loadComponent: () =>
      import('./core/layout/admin-layout/admin-layout.component').then(
        (m) => m.AdminLayoutComponent,
      ),
    canActivate: [roleGuard(['admin'])],
    children: [
      {
        path: '',
        redirectTo: 'dashboard',
        pathMatch: 'full',
      },
      {
        path: 'dashboard',
        loadComponent: () =>
          import('./features/admin/admin-dashboard/admin-dashboard.component').then(
            (m) => m.AdminDashboardComponent,
          ),
      },
    ],
  },

  // Trang lỗi và 404
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
