import { Component, ElementRef, inject, OnInit, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { PracticeApi } from '../../../data-access/api/practice.api';
import { AuthService } from '../../../core/auth/auth.service';
import { ToastService } from '../../../core/services/toast.service';
import { Course, InstructorPracticeRecord } from '../../../shared/models';
import { SkeletonComponent } from '../../../shared/components/skeleton/skeleton.component';
import { EmptyStateComponent } from '../../../shared/components/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../../shared/components/error-state/error-state.component';
import { PaginationComponent } from '../../../shared/components/pagination/pagination.component';

type ReviewStatusFilter = 'all' | 'needs_review' | 'reviewed' | 'ai_graded';

@Component({
  selector: 'app-student-practice-history',
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
  templateUrl: './student-practice-history.component.html',
  styleUrl: './student-practice-history.component.css',
})
export class StudentPracticeHistoryComponent implements OnInit {
  private practiceApi = inject(PracticeApi);
  private authService = inject(AuthService);
  private toastService = inject(ToastService);

  @ViewChild('recordsTop') recordsTopRef?: ElementRef<HTMLElement>;

  courses: Course[] = [];
  records: InstructorPracticeRecord[] = [];
  loading = true;
  error: string | null = null;

  // Bộ lọc & phân trang
  searchQuery = '';
  selectedCourseId = '';
  statusFilter: ReviewStatusFilter = 'all';
  currentPage = 1;
  pageSize = 10;

  // Modal chi tiết & chốt điểm (Human-in-the-loop)
  selectedRecord: InstructorPracticeRecord | null = null;
  reviewScore = 0;
  reviewNotes = '';
  isSavingReview = false;

  get isAdmin(): boolean {
    return this.authService.getRole() === 'admin';
  }

  get filteredRecords(): InstructorPracticeRecord[] {
    const q = this.searchQuery.trim().toLowerCase();
    return this.records.filter((r) => {
      if (this.selectedCourseId && r.courseId !== this.selectedCourseId) {
        return false;
      }
      if (this.statusFilter === 'needs_review' && !r.needsHumanReview) {
        return false;
      }
      if (this.statusFilter === 'reviewed' && !r.reviewedByInstructor) {
        return false;
      }
      if (
        this.statusFilter === 'ai_graded' &&
        (r.reviewedByInstructor || r.needsHumanReview)
      ) {
        return false;
      }
      if (!q) return true;
      return (
        r.studentName.toLowerCase().includes(q) ||
        r.studentEmail.toLowerCase().includes(q) ||
        (r.studentCode && r.studentCode.toLowerCase().includes(q)) ||
        r.questionTitle.toLowerCase().includes(q) ||
        (r.courseCode && r.courseCode.toLowerCase().includes(q)) ||
        (r.courseName && r.courseName.toLowerCase().includes(q))
      );
    });
  }

  get totalPages(): number {
    return Math.max(1, Math.ceil(this.filteredRecords.length / this.pageSize));
  }

  get safeCurrentPage(): number {
    return Math.min(Math.max(1, this.currentPage), this.totalPages);
  }

  get paginatedRecords(): InstructorPracticeRecord[] {
    const start = (this.safeCurrentPage - 1) * this.pageSize;
    return this.filteredRecords.slice(start, start + this.pageSize);
  }

  get totalCount(): number {
    return this.records.length;
  }

  get needsReviewCount(): number {
    return this.records.filter((r) => r.needsHumanReview).length;
  }

  get reviewedCount(): number {
    return this.records.filter((r) => r.reviewedByInstructor).length;
  }

  get averageScoreDisplay(): string {
    const scored = this.records
      .map((r) => this.getEffectiveScore(r))
      .filter((s): s is number => s !== null && s !== undefined);
    if (scored.length === 0) return '—';
    const avg = scored.reduce((acc, v) => acc + v, 0) / scored.length;
    return avg.toFixed(1);
  }

  ngOnInit(): void {
    this.loadData();
  }

  loadData(): void {
    this.loading = true;
    this.error = null;

    this.practiceApi.getCourses(!this.isAdmin).subscribe({
      next: (courses) => {
        this.courses = courses || [];
      },
      error: () => {
        this.courses = [];
      },
    });

    this.practiceApi.getInstructorPracticeRecords().subscribe({
      next: (data) => {
        this.records = data || [];
        this.loading = false;
      },
      error: (err) => {
        this.error =
          err?.message || 'Không thể tải danh sách kết quả luyện tập của sinh viên.';
        this.loading = false;
      },
    });
  }

  getEffectiveScore(record: InstructorPracticeRecord): number | null {
    if (record.reviewedByInstructor && record.instructorScore !== null && record.instructorScore !== undefined) {
      return record.instructorScore;
    }
    return record.totalScore ?? null;
  }

  getStatusBadgeClass(record: InstructorPracticeRecord): string {
    if (record.reviewedByInstructor) return 'status-pill status-pill--reviewed';
    if (record.needsHumanReview) return 'status-pill status-pill--warning';
    return 'status-pill status-pill--ai';
  }

  getStatusLabel(record: InstructorPracticeRecord): string {
    if (record.reviewedByInstructor) return 'Giảng viên đã duyệt';
    if (record.needsHumanReview) return 'Cần giảng viên rà soát';
    return 'AI đã chấm';
  }

  onFilterChange(): void {
    this.currentPage = 1;
  }

  setStatusFilter(status: ReviewStatusFilter): void {
    this.statusFilter = status;
    this.currentPage = 1;
  }

  clearSearch(): void {
    this.searchQuery = '';
    this.currentPage = 1;
  }

  resetFilters(): void {
    this.searchQuery = '';
    this.selectedCourseId = '';
    this.statusFilter = 'all';
    this.currentPage = 1;
  }

  onPageChange(page: number): void {
    this.currentPage = page;
    this.recordsTopRef?.nativeElement.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    });
  }

  onPageSizeChange(size: number): void {
    this.pageSize = size;
    this.currentPage = 1;
  }

  openReviewModal(record: InstructorPracticeRecord): void {
    this.selectedRecord = record;
    const baseScore =
      record.reviewedByInstructor && record.instructorScore !== null && record.instructorScore !== undefined
        ? record.instructorScore
        : (record.totalScore ?? 0);
    this.reviewScore = Number(baseScore.toFixed(2));
    this.reviewNotes = record.instructorNotes || '';
  }

  get scoreDelta(): number | null {
    const aiScore = this.selectedRecord?.totalScore;
    if (aiScore === null || aiScore === undefined) return null;
    const score = Number(this.reviewScore);
    if (!Number.isFinite(score)) return null;
    return Math.round((score - Number(aiScore)) * 100) / 100;
  }

  applyAiScore(): void {
    const aiScore = this.selectedRecord?.totalScore;
    if (aiScore === null || aiScore === undefined) return;
    this.reviewScore = Number(Number(aiScore).toFixed(2));
  }

  closeReviewModal(): void {
    if (this.isSavingReview) return;
    this.selectedRecord = null;
  }

  submitReview(): void {
    if (!this.selectedRecord || this.isSavingReview) return;
    const maxScore = this.selectedRecord.maxScore || 10;
    const score = Number(this.reviewScore);
    if (!Number.isFinite(score) || score < 0 || score > maxScore) {
      this.toastService.warning(`Điểm chốt phải nằm trong khoảng từ 0 đến ${maxScore}.`);
      return;
    }

    this.isSavingReview = true;
    const targetId = this.selectedRecord.id;
    this.practiceApi
      .reviewPracticeRecord(targetId, score, this.reviewNotes.trim())
      .subscribe({
        next: (updated) => {
          this.isSavingReview = false;
          this.records = this.records.map((r) => (r.id === updated.id ? updated : r));
          this.selectedRecord = updated;
          this.toastService.success(
            `Đã chốt điểm ${updated.instructorScore}/${updated.maxScore} cho sinh viên ${updated.studentName}.`,
          );
        },
        error: (err) => {
          this.isSavingReview = false;
          this.toastService.error(err?.message || 'Không thể lưu kết quả rà soát.');
        },
      });
  }
}
