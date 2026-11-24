import { Component, inject, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { PracticeApi } from '../../../data-access/api/practice.api';
import { CriterionEvaluation, Evaluation, PracticeSession, Question } from '../../../shared/models';
import { SkeletonComponent } from '../../../shared/components/skeleton/skeleton.component';
import { ErrorStateComponent } from '../../../shared/components/error-state/error-state.component';
import { cleanHtmlToPlainText } from '../../../shared/utils/text.util';

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
  audioPlaybackUrl: string | null = null;
  private ownedAudioObjectUrl: string | null = null;

  get hasInstructorReview(): boolean {
    return Boolean(this.session?.reviewedByInstructor);
  }

  get effectiveScore(): number {
    if (
      this.session?.reviewedByInstructor &&
      this.session.instructorScore !== null &&
      this.session.instructorScore !== undefined
    ) {
      return this.session.instructorScore;
    }
    return this.evaluation?.totalScore ?? 0;
  }

  get courseQuestionsLink(): string[] {
    const cid = this.question?.courseId || this.session?.courseId;
    return cid ? ['/student/courses', cid, 'questions'] : ['/student/courses'];
  }

  get courseLabel(): string {
    return this.session?.courseCode || this.session?.courseName || this.session?.courseId || 'Học phần';
  }

  ngOnInit(): void {
    this.sessionId = this.route.snapshot.paramMap.get('sessionId') || '';
    this.loadResult();
  }

  ngOnDestroy(): void {
    this.stopSpeaking();
    this.revokeAudioUrl();
  }

  private revokeAudioUrl(): void {
    if (this.ownedAudioObjectUrl) {
      URL.revokeObjectURL(this.ownedAudioObjectUrl);
      this.ownedAudioObjectUrl = null;
    }
    this.audioPlaybackUrl = null;
  }

  private loadAudioIfAvailable(audioUrl?: string): void {
    this.revokeAudioUrl();
    if (!audioUrl) return;
    if (audioUrl.startsWith('blob:')) {
      this.audioPlaybackUrl = audioUrl;
      return;
    }
    this.practiceApi.fetchProtectedAudioBlob(audioUrl).subscribe({
      next: (blob) => {
        if (blob && blob.size > 0) {
          this.ownedAudioObjectUrl = URL.createObjectURL(blob);
          this.audioPlaybackUrl = this.ownedAudioObjectUrl;
        }
      },
      error: () => {
        this.audioPlaybackUrl = null;
      },
    });
  }

  loadResult(): void {
    this.loading = true;
    this.error = null;
    this.practiceApi.getPracticeSession(this.sessionId).subscribe({
      next: (s) => {
        this.session = s;
        this.loadAudioIfAvailable(s.audioUrl);
        if (s.questionId) {
          this.practiceApi.getQuestion(s.questionId).subscribe({
            next: (q) => {
              this.question = {
                ...q,
                content: cleanHtmlToPlainText(q.content),
                sampleAnswer: cleanHtmlToPlainText(q.sampleAnswer),
              };
            },
            error: () => {
              // Keep null if question not found
            },
          });
        }

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
