import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { PracticeApi } from '../../../data-access/api/practice.api';
import { PracticeSession } from '../../../shared/models';
import { SkeletonComponent } from '../../../shared/components/skeleton/skeleton.component';

@Component({
  selector: 'app-student-history',
  standalone: true,
  imports: [CommonModule, RouterModule, SkeletonComponent],
  template: `
    <div class="history-page">
      <header class="history-header">
        <div>
          <h1 class="history-title">Lịch sử luyện tập vấn đáp AI</h1>
          <p class="history-sub">
            Xem lại các phiên luyện tập đã thực hiện, bản ghi âm chữ (Transcript) và kết quả chấm
            điểm theo Rubric kèm dẫn chứng giáo trình RAG.
          </p>
        </div>
        <a routerLink="/student/courses/IT2030/questions" class="btn btn--primary">
          <span class="material-symbols-outlined">mic</span>
          Luyện tập câu hỏi mới
        </a>
      </header>

      @if (loading) {
        <app-skeleton variant="card"></app-skeleton>
        <app-skeleton variant="card"></app-skeleton>
      } @else {
        <div class="history-list">
          @for (item of sessions; track item.id) {
            <div class="card history-card">
              <div>
                <div class="history-card__meta">
                  <span class="badge-code">{{ item.courseId || 'IT2030' }}</span>
                  <span class="history-date">{{ item.createdAt | date: 'dd/MM/yyyy HH:mm' }}</span>
                </div>
                <h2 class="history-card__title">{{ item.questionTitle }}</h2>
                @if (item.transcript) {
                  <p class="history-card__excerpt">"{{ item.transcript }}"</p>
                }
              </div>

              <div class="history-card__right">
                @if (item.evaluation) {
                  <div class="history-score">
                    <strong>{{ item.evaluation.totalScore }}</strong> /
                    {{ item.evaluation.maxScore }} điểm
                  </div>
                }
                <a
                  [routerLink]="['/student/sessions', item.id, 'result']"
                  class="btn btn--secondary btn--sm"
                >
                  Xem chi tiết & RAG
                  <span class="material-symbols-outlined">arrow_forward</span>
                </a>
              </div>
            </div>
          }
        </div>
      }
    </div>
  `,
  styles: [
    `
      .history-page {
        display: flex;
        flex-direction: column;
        gap: var(--space-5);
      }
      .history-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: var(--space-4);
        flex-wrap: wrap;
      }
      .history-title {
        font-size: var(--text-h1);
        font-weight: 700;
        margin-bottom: 4px;
      }
      .history-sub {
        font-size: var(--text-sm);
        color: var(--color-text-secondary);
      }
      .history-list {
        display: flex;
        flex-direction: column;
        gap: var(--space-3);
      }
      .history-card {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: var(--space-4);
        flex-wrap: wrap;
      }
      .history-card__meta {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        margin-bottom: 4px;
      }
      .badge-code {
        font-family: var(--font-family-mono);
        font-size: var(--text-xs);
        font-weight: 700;
        color: var(--color-primary);
        background: var(--color-primary-soft);
        padding: 2px 8px;
        border-radius: var(--radius-sm);
      }
      .history-date {
        font-size: var(--text-xs);
        color: var(--color-text-muted);
      }
      .history-card__title {
        font-size: var(--text-h3);
        font-weight: 600;
        margin-bottom: 4px;
      }
      .history-card__excerpt {
        font-size: var(--text-sm);
        color: var(--color-text-secondary);
        font-style: italic;
        max-width: 680px;
      }
      .history-card__right {
        display: flex;
        align-items: center;
        gap: var(--space-3);
      }
      .history-score {
        font-family: var(--font-family-mono);
        font-size: var(--text-body);
        color: var(--color-primary);
      }
    `,
  ],
})
export class StudentHistoryComponent implements OnInit {
  private practiceApi = inject(PracticeApi);
  loading = true;
  sessions: PracticeSession[] = [];

  ngOnInit(): void {
    this.practiceApi.getPracticeHistory().subscribe({
      next: (data) => {
        this.sessions = data;
        this.loading = false;
      },
      error: () => {
        this.loading = false;
      },
    });
  }
}

