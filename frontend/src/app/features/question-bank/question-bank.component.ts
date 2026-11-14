import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { combineLatest } from 'rxjs';
import { PracticeApi } from '../../data-access/api/practice.api';
import { Course, Question } from '../../shared/models';
import { SkeletonComponent } from '../../shared/components/skeleton/skeleton.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../shared/components/error-state/error-state.component';

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
  ],
  templateUrl: './question-bank.component.html',
  styleUrl: './question-bank.component.css',
})
export class QuestionBankComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private practiceApi = inject(PracticeApi);

  courseId?: string;
  courses: Course[] = [];
  course: Course | null = null;
  loading = true;
  error: string | null = null;
  questions: Question[] = [];

  searchQuery = '';
  selectedTopic = 'Tất cả';
  selectedDifficulty = 'all';

  get isInstructorMode(): boolean {
    return this.router.url.startsWith('/instructor');
  }

  get availableTopics(): string[] {
    const set = new Set<string>();
    this.questions.forEach((q) => {
      if (q.topic) set.add(q.topic);
    });
    return ['Tất cả', ...Array.from(set)];
  }

  get filteredQuestions(): Question[] {
    const q = this.searchQuery.trim().toLowerCase();
    return this.questions.filter((item) => {
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

  ngOnInit(): void {
    combineLatest([this.route.paramMap, this.route.queryParamMap]).subscribe(
      ([params, queryParams]) => {
        this.courseId = params.get('courseId') || queryParams.get('courseId') || undefined;
        this.selectedTopic = 'Tất cả';
        this.loadData();
      },
    );
  }

  onCourseFilterChange(selectedCourseId: string): void {
    this.selectedTopic = 'Tất cả';
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

    this.practiceApi.getCourses().subscribe({
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
  }

  clearSearch(): void {
    this.searchQuery = '';
  }

  setTopic(topic: string): void {
    this.selectedTopic = topic;
  }

  setDifficulty(diff: string): void {
    this.selectedDifficulty = diff;
  }

  resetFilters(): void {
    this.searchQuery = '';
    this.selectedTopic = 'Tất cả';
    this.selectedDifficulty = 'all';
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
