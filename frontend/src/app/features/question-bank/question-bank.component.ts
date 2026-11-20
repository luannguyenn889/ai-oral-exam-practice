import { Component, ElementRef, inject, OnInit, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { combineLatest } from 'rxjs';
import { PracticeApi } from '../../data-access/api/practice.api';
import { AuthService } from '../../core/auth/auth.service';
import { Course, Question } from '../../shared/models';
import { SkeletonComponent } from '../../shared/components/skeleton/skeleton.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../shared/components/error-state/error-state.component';
import { PaginationComponent } from '../../shared/components/pagination/pagination.component';

@Component({
  selector: 'app-question-bank',
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
  templateUrl: './question-bank.component.html',
  styleUrl: './question-bank.component.css',
})
export class QuestionBankComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private practiceApi = inject(PracticeApi);
  private authService = inject(AuthService);

  @ViewChild('questionsTop') questionsTopRef?: ElementRef<HTMLElement>;

  courseId?: string;
  courses: Course[] = [];
  course: Course | null = null;
  loading = true;
  error: string | null = null;
  questions: Question[] = [];

  searchQuery = '';
  selectedTopic = 'Tất cả';
  selectedDifficulty = 'all';

  currentPage = 1;
  pageSize = 10;

  get isInstructorMode(): boolean {
    return this.router.url.startsWith('/instructor');
  }

  get isAdmin(): boolean {
    return this.authService.getRole() === 'admin';
  }

  get availableTopics(): string[] {
    const allowedIds =
      this.isInstructorMode && !this.isAdmin && !this.courseId
        ? new Set(this.courses.map((c) => c.id))
        : null;
    const set = new Set<string>();
    this.questions.forEach((q) => {
      if (allowedIds && !allowedIds.has(q.courseId)) return;
      if (q.topic) set.add(q.topic);
    });
    return ['Tất cả', ...Array.from(set)];
  }

  get filteredQuestions(): Question[] {
    const q = this.searchQuery.trim().toLowerCase();
    const allowedIds =
      this.isInstructorMode && !this.isAdmin && !this.courseId
        ? new Set(this.courses.map((c) => c.id))
        : null;

    return this.questions.filter((item) => {
      if (allowedIds && !allowedIds.has(item.courseId)) return false;

      const matchSearch =
        !q ||
        item.title.toLowerCase().includes(q) ||
        item.content.toLowerCase().includes(q) ||
        (item.tags && item.tags.some((tag) => tag.toLowerCase().includes(q)));

      const matchTopic = this.selectedTopic === 'Tất cả' || item.topic === this.selectedTopic;

      const matchDifficulty =
        this.selectedDifficulty === 'all' || item.difficulty === this.selectedDifficulty;

      return matchSearch && matchTopic && matchDifficulty;
    });
  }

  get totalPages(): number {
    return Math.max(1, Math.ceil(this.filteredQuestions.length / this.pageSize));
  }

  get safeCurrentPage(): number {
    return Math.min(Math.max(1, this.currentPage), this.totalPages);
  }

  get paginatedQuestions(): Question[] {
    const start = (this.safeCurrentPage - 1) * this.pageSize;
    return this.filteredQuestions.slice(start, start + this.pageSize);
  }

  ngOnInit(): void {
    combineLatest([this.route.paramMap, this.route.queryParamMap]).subscribe(
      ([params, queryParams]) => {
        this.courseId = params.get('courseId') || queryParams.get('courseId') || undefined;
        this.selectedTopic = 'Tất cả';
        this.currentPage = 1;
        this.loadData();
      },
    );
  }

  onCourseFilterChange(selectedCourseId: string): void {
    this.selectedTopic = 'Tất cả';
    this.currentPage = 1;
    if (selectedCourseId) {
      this.router.navigate(['/instructor/questions'], {
        queryParams: { courseId: selectedCourseId },
      });
    } else {
      this.router.navigate(['/instructor/questions']);
    }
  }

  getCourseBadge(courseId?: string): string {
    if (!courseId) return '';
    const found = this.courses.find(
      (c) => c.id === courseId || c.code.toLowerCase() === courseId.toLowerCase(),
    );
    return found ? found.code : '';
  }

  loadData(): void {
    this.loading = true;
    this.error = null;

    const mineOnly = this.isInstructorMode && !this.isAdmin;
    this.practiceApi.getCourses(mineOnly).subscribe({
      next: (courses) => {
        this.courses = courses || [];
        if (this.courseId) {
          this.course =
            this.courses.find(
              (c) =>
                c.id === this.courseId ||
                c.code.toLowerCase() === this.courseId!.toLowerCase(),
            ) || null;
        } else {
          this.course = null;
        }
      },
    });

    this.practiceApi.getQuestions(this.courseId).subscribe({
      next: (data) => {
        this.questions = data;
        this.loading = false;
      },
      error: () => {
        this.error =
          'Không thể kết nối đến máy chủ để tải danh sách câu hỏi. Vui lòng kiểm tra lại kết nối mạng.';
        this.loading = false;
      },
    });
  }

  onSearchInput(event: Event): void {
    const target = event.target as HTMLInputElement;
    this.searchQuery = target.value;
    this.currentPage = 1;
  }

  clearSearch(): void {
    this.searchQuery = '';
    this.currentPage = 1;
  }

  setTopic(topic: string): void {
    this.selectedTopic = topic;
    this.currentPage = 1;
  }

  setDifficulty(diff: string): void {
    this.selectedDifficulty = diff;
    this.currentPage = 1;
  }

  resetFilters(): void {
    this.searchQuery = '';
    this.selectedTopic = 'Tất cả';
    this.selectedDifficulty = 'all';
    this.currentPage = 1;
  }

  onPageChange(page: number): void {
    this.currentPage = page;
    this.questionsTopRef?.nativeElement.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    });
  }

  onPageSizeChange(size: number): void {
    this.pageSize = size;
    this.currentPage = 1;
  }

  getDifficultyLabel(diff?: string): string {
    switch (diff) {
      case 'easy':
        return 'Cơ bản';
      case 'hard':
        return 'Nâng cao';
      case 'medium':
      default:
        return 'Trung bình';
    }
  }
}
