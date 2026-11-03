import { Component, inject, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { PracticeApi } from '../../../data-access/api/practice.api';
import { CriterionEvaluation, Evaluation, PracticeSession, Question } from '../../../shared/models';
import { SkeletonComponent } from '../../../shared/components/skeleton/skeleton.component';
import { ErrorStateComponent } from '../../../shared/components/error-state/error-state.component';

@Component({
  selector: 'app-session-result',
  standalone: true,
  imports: [CommonModule, RouterModule, SkeletonComponent, ErrorStateComponent],
  templateUrl: './session-result.component.html',
  styleUrl: './session-result.component.css',
})
export class SessionResultComponent implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private practiceApi = inject(PracticeApi);

  sessionId = '';
  session: PracticeSession | null = null;
  question: Question | null = null;
  evaluation: Evaluation | null = null;

  loading = true;
  error: string | null = null;
  isSpeaking = false;

  ngOnInit(): void {
    this.sessionId = this.route.snapshot.paramMap.get('sessionId') || 'session-demo-1';
    this.loadResult();
  }

  ngOnDestroy(): void {
    this.stopSpeaking();
  }

  loadResult(): void {
    this.loading = true;
    this.error = null;
    this.practiceApi.getPracticeSession(this.sessionId).subscribe({
      next: (s) => {
        this.session = s;
        this.practiceApi.getQuestion(s.questionId).subscribe({
          next: (q) => {
            this.question = q;
          },
          error: () => {
            // Keep null if question not found
          },
        });

        if (s.evaluation) {
          this.evaluation = s.evaluation;
          this.loading = false;
        } else {
          // Tự động gọi AI Service chấm điểm nếu phiên luyện tập chưa có kết quả chấm
          this.practiceApi.requestEvaluation(this.sessionId).subscribe({
            next: () => {
              this.practiceApi.getPracticeSession(this.sessionId).subscribe({
                next: (updatedSession) => {
                  this.session = updatedSession;
                  this.evaluation = updatedSession.evaluation || null;
                  this.loading = false;
                },
                error: () => {
                  this.loading = false;
                },
              });
            },
            error: () => {
              this.error =
                'Không thể kết nối AI Service (http://localhost:8000/ai/evaluations) để chấm điểm.';
              this.loading = false;
            },
          });
        }
      },
      error: () => {
        this.error = 'Không thể tải kết quả đánh giá của phiên luyện tập này.';
        this.loading = false;
      },
    });
  }

  getCriterionName(criterionId: string, index: number): string {
    const found = this.question?.rubric?.criteria?.find((c) => c.id === criterionId);
    return found ? found.name : `Tiêu chí ${index + 1} (${criterionId})`;
  }

  getScorePercent(c: CriterionEvaluation): number {
    if (!c.maxScore) return 0;
    return Math.min(100, Math.round((c.score / c.maxScore) * 100));
  }

  getGradeLabel(score: number, maxScore: number): string {
    const ratio = maxScore > 0 ? score / maxScore : 0;
    if (ratio >= 0.85) return 'Xuất sắc / Giỏi';
    if (ratio >= 0.7) return 'Khá';
    if (ratio >= 0.5) return 'Đạt yêu cầu';
    return 'Cần ôn tập thêm';
  }

  toggleTtsFeedback(): void {
    if (typeof window === 'undefined' || !('speechSynthesis' in window) || !this.evaluation) {
      return;
    }
    if (this.isSpeaking) {
      this.stopSpeaking();
      return;
    }

    const parts: string[] = [
      `Kết quả đánh giá của bạn là ${this.evaluation.totalScore} trên ${this.evaluation.maxScore} điểm.`,
    ];
    if (this.evaluation.summary) {
      parts.push(`Nhận xét từ giảng viên AI: ${this.evaluation.summary}`);
    }
    if (this.evaluation.improvements && this.evaluation.improvements.length > 0) {
      parts.push(`Gợi ý cải thiện: ${this.evaluation.improvements.join('. ')}`);
    }

    const utterance = new SpeechSynthesisUtterance(parts.join(' '));
    utterance.lang = 'vi-VN';
    utterance.rate = 1.0;
    utterance.onend = () => {
      this.isSpeaking = false;
    };
    utterance.onerror = () => {
      this.isSpeaking = false;
    };

    this.isSpeaking = true;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  }

  stopSpeaking(): void {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    this.isSpeaking = false;
  }
}
