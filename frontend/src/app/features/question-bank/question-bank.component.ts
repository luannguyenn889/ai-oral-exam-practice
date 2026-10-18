import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterModule } from '@angular/router';
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
  private practiceApi = inject(PracticeApi);

  courseId?: string;
  course: Course | null = null;
  loading = true;
  error: string | null = null;
  questions: Question[] = [];

  searchQuery = '';
  selectedTopic = 'Tất cả';
  selectedDifficulty = 'all';

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
    this.courseId = this.route.snapshot.paramMap.get('courseId') || undefined;
    this.loadData();
  }

  loadData(): void {
    this.loading = true;
    this.error = null;

    if (this.courseId) {
      this.practiceApi.getCourses().subscribe({
        next: (courses) => {
          this.course = courses.find((c) => c.id === this.courseId) || null;
        },
      });
    }

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
