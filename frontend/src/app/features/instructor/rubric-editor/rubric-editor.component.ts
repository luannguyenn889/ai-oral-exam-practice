import { Component, inject, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { PracticeApi } from '../../../data-access/api/practice.api';
import { AiRagService } from '../../../core/services/ai-rag.service';
import { AuthService } from '../../../core/auth/auth.service';
import { Course, Question, RagChunkResult, Rubric, RubricCriterion } from '../../../shared/models';
import { ToastService } from '../../../core/services/toast.service';
import { cleanHtmlToPlainText } from '../../../shared/utils/text.util';

interface RubricDraft {
  criteria: RubricCriterion[];
  gradingInstructions: string;
  savedAt: string;
}

@Component({
  selector: 'app-rubric-editor',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './rubric-editor.component.html',
  styleUrl: './rubric-editor.component.css',
})
export class RubricEditorComponent implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private practiceApi = inject(PracticeApi);
  private aiRagService = inject(AiRagService);
  private authService = inject(AuthService);
  private toastService = inject(ToastService);

  questionId = '';
  question: Question | null = null;
  courses: Course[] = [];
  loading = false;
  saving = false;

  // Human-in-the-loop: AI đề xuất Rubric thang 10 từ Đáp án mẫu & giáo trình RAG
  isSuggestingRubric = false;
  aiElapsedSeconds = 0;
  private aiTimerId: ReturnType<typeof setInterval> | null = null;
  rubricReviewStatus: 'manual' | 'ai_draft' | 'approved' = 'manual';
  rubricApprovedAt = '';
  ragReferences: RagChunkResult[] = [];
  showRagReferences = false;

  get ragCourseCode(): string {
    const cid = this.question?.courseId || '';
    const found = this.courses.find((c) => c.id === cid || c.code === cid);
    return (found?.code || cid || 'IT2030').trim().toUpperCase();
  }

  criteria: RubricCriterion[] = [];
  gradingInstructions =
    'Chấm điểm khách quan theo từng ý trong tiêu chí: ưu tiên độ chính xác của khái niệm và thuật ngữ chuyên môn, chiều sâu phân tích cơ chế và khả năng lấy ví dụ thực tế. Ghi rõ điểm mạnh và ý còn thiếu trong nhận xét.';

  // Trạng thái lưu nháp tự động (Draft / Auto-save)
  lastAutoSavedAt = '';
  pendingDraft: RubricDraft | null = null;
  pendingDraftTime = '';
  private autoSaveTimer: ReturnType<typeof setTimeout> | null = null;

  private get draftStorageKey(): string {
    return `rubric_draft_${this.questionId}`;
  }

  get currentTotalScore(): number {
    const sum = this.criteria.reduce((acc, c) => acc + (Number(c.maxScore) || 0), 0);
    return Math.round(sum * 10) / 10;
  }

  get isTotalScoreValid(): boolean {
    return Math.abs(this.currentTotalScore - 10) < 0.01;
  }

  ngOnInit(): void {
    this.questionId = this.route.snapshot.paramMap.get('questionId') || '';
    const isAdmin = this.authService.getRole() === 'admin';
    this.practiceApi.getCourses(!isAdmin).subscribe({
      next: (list) => (this.courses = list || []),
      error: () => (this.courses = []),
    });
    if (this.questionId) {
      this.loadData(this.questionId);
    }
  }

  ngOnDestroy(): void {
    if (this.autoSaveTimer !== null) {
      clearTimeout(this.autoSaveTimer);
      this.autoSaveTimer = null;
    }
    this.stopAiTimer();
  }

  formatAiElapsed(): string {
    const mins = Math.floor(this.aiElapsedSeconds / 60);
    const secs = this.aiElapsedSeconds % 60;
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }

  private startAiTimer(): void {
    this.stopAiTimer();
    this.aiElapsedSeconds = 0;
    this.aiTimerId = setInterval(() => {
      this.aiElapsedSeconds += 1;
    }, 1000);
  }

  private stopAiTimer(): void {
    if (this.aiTimerId !== null) {
      clearInterval(this.aiTimerId);
      this.aiTimerId = null;
    }
  }

  loadData(id: string): void {
    this.loading = true;
    this.practiceApi.getQuestion(id).subscribe({
      next: (q) => {
        this.question = q;
        if (q.rubric && q.rubric.criteria && q.rubric.criteria.length > 0) {
          this.criteria = q.rubric.criteria.map((c) => ({ ...c }));
        } else {
          this.applyDefault4CriteriaTemplate(false);
        }
        this.checkExistingDraft();
        this.loading = false;
      },
      error: () => {
        this.toastService.error('Không thể tải thông tin câu hỏi và Rubric.');
        this.checkExistingDraft();
        this.loading = false;
      },
    });
  }

  onRubricChange(): void {
    if (!this.questionId || this.loading) return;
    if (this.autoSaveTimer !== null) {
      clearTimeout(this.autoSaveTimer);
    }
    this.autoSaveTimer = setTimeout(() => {
      this.saveDraftNow();
    }, 600);
  }

  private saveDraftNow(): void {
    if (!this.questionId) return;
    try {
      const now = new Date();
      const draft: RubricDraft = {
        criteria: this.criteria.map((c) => ({ ...c })),
        gradingInstructions: this.gradingInstructions,
        savedAt: now.toISOString(),
      };
      localStorage.setItem(this.draftStorageKey, JSON.stringify(draft));
      this.lastAutoSavedAt = this.formatTime(now);
      this.pendingDraft = null;
    } catch {
      // Bỏ qua nếu trình duyệt chặn hoặc đầy localStorage
    }
  }

  private checkExistingDraft(): void {
    if (!this.questionId) return;
    try {
      const raw = localStorage.getItem(this.draftStorageKey);
      if (!raw) return;
      const draft = JSON.parse(raw) as RubricDraft;
      if (!draft || !Array.isArray(draft.criteria) || draft.criteria.length === 0) {
        return;
      }
      const sameCriteria = JSON.stringify(draft.criteria) === JSON.stringify(this.criteria);
      const sameInstructions =
        (draft.gradingInstructions || '') === (this.gradingInstructions || '');
      if (sameCriteria && sameInstructions) {
        return;
      }
      this.pendingDraft = draft;
      this.pendingDraftTime = draft.savedAt ? this.formatTime(new Date(draft.savedAt)) : '';
    } catch {
      this.pendingDraft = null;
    }
  }

  restoreDraft(): void {
    if (!this.pendingDraft) return;
    this.criteria = this.pendingDraft.criteria.map((c) => ({ ...c }));
    if (typeof this.pendingDraft.gradingInstructions === 'string') {
      this.gradingInstructions = this.pendingDraft.gradingInstructions;
    }
    this.lastAutoSavedAt = this.pendingDraftTime;
    this.pendingDraft = null;
    this.toastService.success('Đã khôi phục bản nháp Rubric chưa lưu.');
  }

  discardDraft(): void {
    this.pendingDraft = null;
    this.clearDraft();
    this.toastService.info('Đã bỏ bản nháp và giữ nguyên dữ liệu từ máy chủ.');
  }

  private clearDraft(): void {
    if (!this.questionId) return;
    try {
      localStorage.removeItem(this.draftStorageKey);
    } catch {
      // ignore
    }
  }

  private formatTime(date: Date): string {
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleTimeString('vi-VN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  }

  addCriterion(): void {
    const nextIndex = this.criteria.length + 1;
    this.criteria.push({
      id: `c-new-${Date.now()}-${nextIndex}`,
      name: `Tiêu chí ${nextIndex}: Nội dung đánh giá`,
      description:
        'Nêu rõ các ý chính bắt buộc phải có và mức điểm từng phần (VD: Trình bày đúng khái niệm +1.0đ; giải thích được cơ chế +1.0đ).',
      maxScore: 2.0,
    });
    this.onRubricChange();
  }

  removeCriterion(index: number): void {
    if (this.criteria.length <= 1) {
      this.toastService.warning('Rubric cần có ít nhất 1 tiêu chí đánh giá.');
      return;
    }
    this.criteria.splice(index, 1);
    this.onRubricChange();
  }

  moveUp(index: number): void {
    if (index > 0) {
      const temp = this.criteria[index];
      this.criteria[index] = this.criteria[index - 1];
      this.criteria[index - 1] = temp;
      this.onRubricChange();
    }
  }

  moveDown(index: number): void {
    if (index < this.criteria.length - 1) {
      const temp = this.criteria[index];
      this.criteria[index] = this.criteria[index + 1];
      this.criteria[index + 1] = temp;
      this.onRubricChange();
    }
  }

  applyDefault4CriteriaTemplate(triggerAutoSave = true): void {
    this.criteria = [
      {
        id: 'c1',
        name: 'Khái niệm & Kiến thức cốt lõi',
        description:
          'Nêu đúng và đầy đủ định nghĩa, bản chất và các thuật ngữ chuyên môn trọng tâm của câu hỏi.',
        maxScore: 3.0,
      },
      {
        id: 'c2',
        name: 'Phân tích cơ chế & So sánh chuyên sâu',
        description:
          'Giải thích rõ nguyên lý hoạt động, phân biệt được sự khác nhau hoặc ưu/nhược điểm giữa các khái niệm liên quan.',
        maxScore: 3.0,
      },
      {
        id: 'c3',
        name: 'Ví dụ thực tế & Khả năng vận dụng',
        description:
          'Đưa ra được ví dụ cụ thể (tình huống dự án hoặc đoạn mã minh họa) gắn đúng với lý thuyết đã nêu.',
        maxScore: 2.5,
      },
      {
        id: 'c4',
        name: 'Diễn đạt mạch lạc & Thuật ngữ chuẩn',
        description:
          'Trình bày có cấu trúc rõ ràng, trả lời đúng trọng tâm và sử dụng chính xác thuật ngữ chuyên ngành.',
        maxScore: 1.5,
      },
    ];
    if (triggerAutoSave) {
      this.onRubricChange();
    }
  }

  apply3CriteriaTemplate(): void {
    this.criteria = [
      {
        id: 'c1',
        name: 'Độ chính xác lý thuyết & Trọng tâm',
        description:
          'Trình bày đúng bản chất kiến thức cốt lõi, trả lời trực diện vào trọng tâm câu hỏi.',
        maxScore: 4.0,
      },
      {
        id: 'c2',
        name: 'Phân tích & Ví dụ vận dụng thực tế',
        description:
          'Giải thích được cách áp dụng vào bài toán/dự án thực tế và nêu ví dụ minh họa hợp lý.',
        maxScore: 3.5,
      },
      {
        id: 'c3',
        name: 'Cấu trúc trình bày & Thuật ngữ',
        description:
          'Diễn đạt rõ ràng, mạch lạc, dùng đúng thuật ngữ chuyên môn và phản xạ tự tin.',
        maxScore: 2.5,
      },
    ];
    this.onRubricChange();
  }

  suggestRubricWithAi(): void {
    if (!this.question || !this.question.content?.trim()) {
      this.toastService.warning('Chưa có nội dung câu hỏi để AI đề xuất Rubric.');
      return;
    }

    this.isSuggestingRubric = true;
    this.startAiTimer();
    this.aiRagService
      .suggestReferenceAnswer({
        courseId: this.ragCourseCode,
        question: this.question.content,
        topic: this.question.topic || undefined,
        referenceAnswer: this.question.sampleAnswer || undefined,
        topK: 4,
        searchMode: 'hybrid',
        includeRubric: true,
      })
      .subscribe({
        next: (res) => {
          this.isSuggestingRubric = false;
          this.stopAiTimer();
          this.ragReferences = res.ragReferences || [];
          const suggested = res.suggestedCriteria || [];
          if (suggested.length === 0) {
            this.toastService.warning(
              'AI chưa trả về tiêu chí Rubric phù hợp. Vui lòng thử lại hoặc dùng mẫu nhanh.',
            );
            return;
          }

          this.criteria = suggested.map((item, idx) => ({
            id: `c-ai-${Date.now()}-${idx + 1}`,
            name: cleanHtmlToPlainText(item.name),
            description: cleanHtmlToPlainText(item.description),
            maxScore: Math.round((Number(item.maxScore) || 0) * 10) / 10,
          }));
          this.rubricReviewStatus = 'ai_draft';
          this.rubricApprovedAt = '';
          this.onRubricChange();
          this.toastService.info(
            `AI đã đề xuất ${this.criteria.length} tiêu chí thang 10.0đ dựa trên Đáp án mẫu & giáo trình RAG. Giảng viên vui lòng rà soát và duyệt.`,
          );
        },
        error: () => {
          this.isSuggestingRubric = false;
          this.stopAiTimer();
          this.toastService.error(
            'Không thể kết nối AI Service để đề xuất Rubric. Hãy kiểm tra AI Service đang chạy.',
          );
        },
      });
  }

  approveAiRubric(): void {
    this.rubricReviewStatus = 'approved';
    const now = new Date();
    this.rubricApprovedAt = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    this.toastService.success('Giảng viên đã duyệt bộ tiêu chí Rubric.');
  }

  saveRubric(): void {
    if (this.criteria.length === 0) {
      this.toastService.warning('Vui lòng thêm ít nhất một tiêu chí chấm điểm.');
      return;
    }

    for (let i = 0; i < this.criteria.length; i++) {
      if (!this.criteria[i].name.trim()) {
        this.toastService.warning(`Vui lòng nhập tên cho tiêu chí số ${i + 1}.`);
        return;
      }
    }

    if (!this.isTotalScoreValid) {
      const diff = Math.round((10 - this.currentTotalScore) * 10) / 10;
      this.toastService.warning(
        `Tổng điểm hiện tại là ${this.currentTotalScore}đ. Vui lòng điều chỉnh để tròn đúng 10.0đ (đang lệch ${diff > 0 ? '+' : ''}${diff}đ).`,
      );
      return;
    }

    const rubricPayload: Rubric = {
      id: this.question?.rubric?.id || `rubric-${Date.now()}`,
      questionId: this.questionId,
      criteria: this.criteria.map((c) => ({
        ...c,
        maxScore: Number(c.maxScore),
      })),
      totalScore: this.currentTotalScore,
    };

    this.saving = true;
    this.practiceApi.saveRubric(this.questionId, rubricPayload).subscribe({
      next: () => {
        this.saving = false;
        this.clearDraft();
        this.toastService.success('Lưu Rubric chấm điểm thành công!');
        this.router.navigate(['/instructor/questions'], {
          queryParams: { courseId: this.question?.courseId },
        });
      },
      error: () => {
        this.saving = false;
        this.toastService.error('Có lỗi xảy ra khi lưu Rubric.');
      },
    });
  }
}
