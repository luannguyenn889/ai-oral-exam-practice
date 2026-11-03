import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { PracticeApi } from '../../data-access/api/practice.api';
import { Course } from '../../shared/models';
import { SkeletonComponent } from '../../shared/components/skeleton/skeleton.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../shared/components/error-state/error-state.component';
import { ToastService } from '../../core/services/toast.service';

@Component({
  selector: 'app-course-selection',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    SkeletonComponent,
    EmptyStateComponent,
    ErrorStateComponent,
  ],
  templateUrl: './course-selection.component.html',
  styleUrl: './course-selection.component.css',
})
export class CourseSelectionComponent implements OnInit {
  private practiceApi = inject(PracticeApi);
  private router = inject(Router);
  private toastService = inject(ToastService);

  loading = true;
  error: string | null = null;
  courses: Course[] = [];
  searchQuery = '';

  // Quản lý Modal Thêm mới học phần (dành cho giảng viên)
  showCreateModal = false;
  isCreating = false;
  newCourseCode = '';
  newCourseName = '';
  newCourseDescription = '';
  newCourseSemester = 'Học kỳ 1 - 2026';
  newCourseDepartment = 'Khoa Công nghệ Thông tin';

  get isInstructorMode(): boolean {
    return this.router.url.startsWith('/instructor');
  }

  get filteredCourses(): Course[] {
    const q = this.searchQuery.trim().toLowerCase();
    if (!q) return this.courses;
    return this.courses.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.code.toLowerCase().includes(q) ||
        (c.instructorName && c.instructorName.toLowerCase().includes(q)) ||
        (c.topics && c.topics.some((t) => t.toLowerCase().includes(q))),
    );
  }

  get emptyStateDescription(): string {
    if (this.searchQuery) {
      return `Không có học phần nào khớp với từ khóa "${this.searchQuery}". Hãy thử tìm kiếm bằng từ khóa khác.`;
    }
    return 'Hiện tại hệ thống chưa cập nhật danh sách học phần nào.';
  }

  ngOnInit(): void {
    this.loadCourses();
  }

  loadCourses(): void {
    this.loading = true;
    this.error = null;
    this.practiceApi.getCourses().subscribe({
      next: (data) => {
        this.courses = data;
        this.loading = false;
      },
      error: () => {
        this.error =
          'Không thể kết nối đến máy chủ để tải danh sách học phần. Vui lòng kiểm tra lại đường truyền mạng.';
        this.loading = false;
      },
    });
  }

  onSearchInput(event: Event): void {
    const target = event.target as HTMLInputElement;
    this.searchQuery = target.value;
  }

  clearSearch(): void {
    this.searchQuery = '';
  }

  openCreateModal(): void {
    this.newCourseCode = '';
    this.newCourseName = '';
    this.newCourseDescription = '';
    this.newCourseSemester = 'Học kỳ 1 - 2026';
    this.newCourseDepartment = 'Khoa Công nghệ Thông tin';
    this.showCreateModal = true;
  }

  closeCreateModal(): void {
    if (this.isCreating) return;
    this.showCreateModal = false;
  }

  submitCreateCourse(): void {
    const code = this.newCourseCode.trim();
    const name = this.newCourseName.trim();

    if (!code) {
      this.toastService.warning('Vui lòng nhập mã học phần (ví dụ: IT4010).');
      return;
    }
    if (!name) {
      this.toastService.warning('Vui lòng nhập tên môn học.');
      return;
    }

    this.isCreating = true;
    const payload: Partial<Course> = {
      code: code.toUpperCase(),
      name,
      description: this.newCourseDescription.trim(),
      semester: this.newCourseSemester.trim(),
      department: this.newCourseDepartment.trim(),
    };

    this.practiceApi.saveCourse(payload).subscribe({
      next: (created) => {
        this.isCreating = false;
        this.showCreateModal = false;
        this.courses.unshift(created);
        this.toastService.success(`Thêm mới học phần ${created.code} thành công!`);
      },
      error: (err) => {
        this.isCreating = false;
        const msg =
          err?.error?.message ||
          'Không thể thêm học phần. Vui lòng kiểm tra xem mã môn học có bị trùng không.';
        this.toastService.error(msg);
      },
    });
  }
}
