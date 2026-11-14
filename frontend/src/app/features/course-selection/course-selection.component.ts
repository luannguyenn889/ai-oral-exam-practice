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

  // Quản lý Modal Thêm mới / Chỉnh sửa học phần (dành cho giảng viên)
  showCourseModal = false;
  editingCourse: Course | null = null;
  isSaving = false;
  formCourseCode = '';
  formCourseName = '';
  formCourseDescription = '';
  formCourseSemester = 'Học kỳ 1 - 2026';
  formCourseDepartment = 'Khoa Công nghệ Thông tin';

  // Quản lý Modal Xác nhận xóa học phần
  deletingCourse: Course | null = null;
  isDeleting = false;

  get isInstructorMode(): boolean {
    return this.router.url.startsWith('/instructor');
  }

  get previewFolderCode(): string {
    const cleaned = this.formCourseCode
      .trim()
      .toUpperCase()
      .replace(/[^A-Z0-9_-]/g, '');
    return cleaned || 'IT4010';
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
    this.editingCourse = null;
    this.formCourseCode = '';
    this.formCourseName = '';
    this.formCourseDescription = '';
    this.formCourseSemester = 'Học kỳ 1 - 2026';
    this.formCourseDepartment = 'Khoa Công nghệ Thông tin';
    this.showCourseModal = true;
  }

  openEditModal(course: Course): void {
    this.editingCourse = course;
    this.formCourseCode = course.code;
    this.formCourseName = course.name;
    this.formCourseDescription = course.description || '';
    this.formCourseSemester = course.semester || 'Học kỳ 1 - 2026';
    this.formCourseDepartment = course.department || 'Khoa Công nghệ Thông tin';
    this.showCourseModal = true;
  }

  closeCourseModal(): void {
    if (this.isSaving) return;
    this.showCourseModal = false;
    this.editingCourse = null;
  }

  submitCourseForm(): void {
    const code = this.formCourseCode.trim();
    const name = this.formCourseName.trim();

    if (!code) {
      this.toastService.warning('Vui lòng nhập mã học phần (ví dụ: IT4010).');
      return;
    }
    if (!name) {
      this.toastService.warning('Vui lòng nhập tên môn học.');
      return;
    }

    this.isSaving = true;
    const wasEditing = !!this.editingCourse;
    const targetId = this.editingCourse?.id;
    const payload: Partial<Course> = {
      id: targetId,
      code: code.toUpperCase(),
      name,
      description: this.formCourseDescription.trim(),
      semester: this.formCourseSemester.trim(),
      department: this.formCourseDepartment.trim(),
    };

    this.practiceApi.saveCourse(payload).subscribe({
      next: (saved) => {
        this.isSaving = false;
        this.showCourseModal = false;
        this.editingCourse = null;
        if (wasEditing && targetId) {
          this.courses = this.courses.map((c) => (c.id === targetId ? saved : c));
          this.toastService.success(
            `Cập nhật học phần ${saved.code} thành công! Thư mục lưu trữ: ${saved.code}.`,
          );
        } else {
          this.courses = [saved, ...this.courses];
          this.toastService.success(
            `Thêm mới học phần ${saved.code} thành công! Đã tạo thư mục lưu trữ ${saved.code}.`,
          );
        }
      },
      error: (err) => {
        this.isSaving = false;
        const msg =
          err?.error?.message ||
          err?.message ||
          'Không thể lưu học phần. Vui lòng kiểm tra xem mã môn học có bị trùng không.';
        this.toastService.error(msg);
      },
    });
  }

  openDeleteModal(course: Course): void {
    this.deletingCourse = course;
  }

  closeDeleteModal(): void {
    if (this.isDeleting) return;
    this.deletingCourse = null;
  }

  confirmDeleteCourse(): void {
    if (!this.deletingCourse || this.isDeleting) return;
    const target = this.deletingCourse;
    this.isDeleting = true;

    this.practiceApi.deleteCourse(target.id).subscribe({
      next: () => {
        this.isDeleting = false;
        this.deletingCourse = null;
        this.courses = this.courses.filter((c) => c.id !== target.id);
        this.toastService.success(`Đã xóa học phần ${target.code} và kho tài liệu liên quan.`);
      },
      error: (err) => {
        this.isDeleting = false;
        const msg =
          err?.error?.message ||
          err?.message ||
          'Không thể xóa học phần. Vui lòng kiểm tra kết nối máy chủ.';
        this.toastService.error(msg);
      },
    });
  }
}
