import { Component, ElementRef, inject, OnInit, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { catchError, forkJoin, of } from 'rxjs';
import { PracticeApi } from '../../../data-access/api/practice.api';
import { Course, PracticeSession } from '../../../shared/models';
import { SkeletonComponent } from '../../../shared/components/skeleton/skeleton.component';
import { EmptyStateComponent } from '../../../shared/components/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../../shared/components/error-state/error-state.component';
import { PaginationComponent } from '../../../shared/components/pagination/pagination.component';

type StudentHistoryFilter = 'all' | 'reviewed' | 'ai_only';

@Component({
  selector: 'app-student-history',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    SkeletonComponent,
    EmptyStateComponent,
    ErrorStateComponent,
    PaginationComponent,
  ],
  templateUrl: './student-history.component.html',
  styleUrl: './student-history.component.css',
})
export class StudentHistoryComponent implements OnInit {
  private practiceApi = inject(PracticeApi);

  @ViewChild('historyTop') historyTopRef?: ElementRef<HTMLElement>;

  loading = true;
  error: string | null = null;
  courses: Course[] = [];
  sessions: PracticeSession[] = [];

  // Bộ lọc & phân trang
  searchQuery = '';
  selectedCourseFilter = '';
  statusFilter: StudentHistoryFilter = 'all';
  currentPage = 1;
  pageSize = 8;

  get filteredSessions(): PracticeSession[] {
    const q = this.searchQuery.trim().toLowerCase();
    return this.sessions.filter((s) => {
      if (this.selectedCourseFilter) {
        const matchCourse =
          s.courseId === this.selectedCourseFilter ||
          (s.courseCode && s.courseCode.toUpperCase() === this.selectedCourseFilter.toUpperCase());
        if (!matchCourse) return false;
      }
      if (this.statusFilter === 'reviewed' && !s.reviewedByInstructor) {
        return false;
      }
      if (this.statusFilter === 'ai_only' && s.reviewedByInstructor) {
        return false;
      }
      if (!q) return true;
      const hay = `${s.questionTitle || ''} ${s.transcript || ''} ${s.courseCode || ''} ${s.courseName || ''} ${s.instructorNotes || ''}`.toLowerCase();
      return hay.includes(q);
    });
  }

  get totalPages(): number {
    return Math.max(1, Math.ceil(this.filteredSessions.length / this.pageSize));
  }

  get safeCurrentPage(): number {
    return Math.min(Math.max(1, this.currentPage), this.totalPages);
  }

  get paginatedSessions(): PracticeSession[] {
    const start = (this.safeCurrentPage - 1) * this.pageSize;
    return this.filteredSessions.slice(start, start + this.pageSize);
  }

  get hasActiveFilter(): boolean {
    return Boolean(
      this.searchQuery.trim() || this.selectedCourseFilter || this.statusFilter !== 'all',
    );
  }

  get reviewedCount(): number {
    return this.sessions.filter((s) => s.reviewedByInstructor).length;
  }

  get averageScoreDisplay(): string {
    const scores = this.sessions
      .map((s) => this.getEffectiveScore(s))
      .filter((v): v is number => v !== null);
    if (scores.length === 0) return '—';
    const avg = scores.reduce((a, b) => a + b, 0) / scores.length;
    return avg.toFixed(1);
  }

  get newPracticeLink(): string[] {
    if (this.selectedCourseFilter) {
      const matched = this.courses.find(
        (c) => c.id === this.selectedCourseFilter || c.code === this.selectedCourseFilter,
      );
      if (matched) {
        return ['/student/courses', matched.id, 'questions'];
      }
    }
    return ['/student/courses'];
  }

  ngOnInit(): void {
    this.loadData();
  }

  loadData(): void {
    this.loading = true;
    this.error = null;
    forkJoin({
      courses: this.practiceApi.getCourses().pipe(catchError(() => of([]))),
      sessions: this.practiceApi.getPracticeHistory(),
    }).subscribe({
      next: ({ courses, sessions }) => {
        this.courses = courses || [];
        this.sessions = sessions || [];
        this.loading = false;
      },
      error: (err) => {
        this.error = err?.message || 'Không thể tải lịch sử luyện tập của bạn.';
        this.loading = false;
      },
    });
  }

  getEffectiveScore(session: PracticeSession): number | null {
    if (
      session.reviewedByInstructor &&
      session.instructorScore !== null &&
      session.instructorScore !== undefined
    ) {
      return Number(session.instructorScore);
    }
    if (session.evaluation?.totalScore !== null && session.evaluation?.totalScore !== undefined) {
      return Number(session.evaluation.totalScore);
    }
    return null;
  }

  getMaxScore(session: PracticeSession): number {
    return session.evaluation?.maxScore || 10;
  }

  getCourseLabel(session: PracticeSession): string {
    if (session.courseCode) return session.courseCode;
    const matched = this.courses.find((c) => c.id === session.courseId);
    if (matched) return matched.code;
    return session.courseName || 'Học phần';
  }

  onFilterChange(): void {
    this.currentPage = 1;
  }

  setStatusFilter(filter: StudentHistoryFilter): void {
    this.statusFilter = filter;
    this.currentPage = 1;
  }

  resetFilters(): void {
    this.searchQuery = '';
    this.selectedCourseFilter = '';
    this.statusFilter = 'all';
    this.currentPage = 1;
  }

  onPageChange(page: number): void {
    this.currentPage = page;
    this.historyTopRef?.nativeElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  onPageSizeChange(size: number): void {
    this.pageSize = size;
    this.currentPage = 1;
  }
}
