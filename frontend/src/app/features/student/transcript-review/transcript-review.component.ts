import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { PracticeApi } from '../../../data-access/api/practice.api';
import { AiRagService } from '../../../core/services/ai-rag.service';
import { ToastService } from '../../../core/services/toast.service';
import { PracticeSession, Question } from '../../../shared/models';
import { SkeletonComponent } from '../../../shared/components/skeleton/skeleton.component';
import { ErrorStateComponent } from '../../../shared/components/error-state/error-state.component';

@Component({
  selector: 'app-transcript-review',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule, SkeletonComponent, ErrorStateComponent],
  templateUrl: './transcript-review.component.html',
  styleUrl: './transcript-review.component.css',
})
export class TranscriptReviewComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private practiceApi = inject(PracticeApi);
  private aiRagService = inject(AiRagService);
  private toast = inject(ToastService);

  sessionId = '';
  session: PracticeSession | null = null;
  question: Question | null = null;
  editedTranscript = '';
  showRawComparison = true;

  loading = true;
  error: string | null = null;
  correcting = false;
  grading = false;

  ngOnInit(): void {
    this.sessionId = this.route.snapshot.paramMap.get('sessionId') || 'session-demo-1';
    this.loadSession();
  }

  loadSession(): void {
    this.loading = true;
    this.error = null;
    this.practiceApi.getPracticeSession(this.sessionId).subscribe({
      next: (s) => {
        this.session = s;
        this.editedTranscript = s.transcript || s.rawTranscript || '';
        this.practiceApi.getQuestion(s.questionId).subscribe({
          next: (q) => {
            this.question = q;
            this.loading = false;
          },
          error: () => {
            this.loading = false;
          },
        });
      },
      error: () => {
        this.error = 'Không tìm thấy phiên luyện tập này.';
        this.loading = false;
      },
    });
  }

  runAiSpellCorrectionAgain(): void {
    if (!this.editedTranscript.trim()) return;
    this.correcting = true;
    const rubricSummary = (this.question?.rubric?.criteria || [])
      .map((c) => `${c.name}: ${c.description}`)
      .join('; ');

    this.aiRagService
      .correctTranscript(
        this.editedTranscript,
        this.question?.content || this.session?.questionTitle || '',
        rubricSummary,
      )
      .subscribe({
        next: (res) => {
          this.correcting = false;
          this.editedTranscript = res.correctedTranscript;
          this.toast.success(
            'Gemini AI đã hiệu đính chính tả và thuật ngữ chuyên ngành CNTT theo ngữ cảnh đề bài!',
          );
        },
        error: () => {
          this.correcting = false;
          this.toast.error('Không thể kết nối AI Service để hiệu đính chính tả.');
        },
      });
  }

  fillSampleAnswerForTesting(): void {
    if (this.question?.sampleAnswer) {
      this.editedTranscript = this.question.sampleAnswer;
      this.toast.info('Đã điền nội dung trả lời mẫu để bạn thử nghiệm chấm điểm với Hybrid RAG.');
    }
  }

  confirmAndEvaluate(): void {
    if (!this.session || !this.editedTranscript.trim()) return;
    this.grading = true;

    this.practiceApi.saveConfirmedTranscript(this.session.id, this.editedTranscript).subscribe({
      next: () => {
        this.practiceApi.requestEvaluation(this.session!.id).subscribe({
          next: () => {
            this.grading = false;
            this.toast.success('Đã hoàn tất đối chiếu giáo trình Hybrid RAG và chấm điểm Rubric!');
            this.router.navigate(['/student/sessions', this.session!.id, 'result']);
          },
          error: () => {
            this.grading = false;
            this.toast.error('Có lỗi trong quá trình chấm điểm AI.');
          },
        });
      },
      error: () => {
        this.grading = false;
        this.toast.error('Không thể lưu bản ghi văn bản.');
      },
    });
  }
}

