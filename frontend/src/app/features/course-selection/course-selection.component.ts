import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { PracticeApi } from '../../data-access/api/practice.api';
import { Course } from '../../shared/models';
import { SkeletonComponent } from '../../shared/components/skeleton/skeleton.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../shared/components/error-state/error-state.component';

@Component({
  selector: 'app-course-selection',
  standalone: true,
  imports: [
    CommonModule,
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

  loading = true;
  error: string | null = null;
  courses: Course[] = [];
  searchQuery = '';

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
    return 'Hiện tại hệ thống chưa cập nhật danh sách học phần nào cho lớp của bạn.';
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
}
