import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { PracticeApi } from '../../../data-access/api/practice.api';
import { AiRagService } from '../../../core/services/ai-rag.service';
import { Course, Question, RagChunkResult } from '../../../shared/models';
import { ToastService } from '../../../core/services/toast.service';
import { AuthService } from '../../../core/auth/auth.service';
import { cleanHtmlToPlainText } from '../../../shared/utils/text.util';

@Component({
  selector: 'app-question-editor',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './question-editor.component.html',
  styleUrl: './question-editor.component.css',
})
export class QuestionEditorComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private practiceApi = inject(PracticeApi);
  private aiRagService = inject(AiRagService);
  private toastService = inject(ToastService);
  private authService = inject(AuthService);

  isEditMode = false;
  questionId: string | null = null;
  loading = false;
  saving = false;
  courses: Course[] = [];

  // Form Model
  courseId = '';
  topic = '';
  title = '';
  content = '';
  sampleAnswer = '';
  difficulty: 'easy' | 'medium' | 'hard' = 'medium';
  timeLimitMinutes = 3;
  tagsString = '';

  // Human-in-the-loop (AI khởi tạo từ RAG -> Giảng viên chọn lọc, chỉnh sửa & duyệt)
  isSuggestingAnswer = false;
  ragReferences: RagChunkResult[] = [];
  selectedRagChunkIds = new Set<string>();
  ragSuggestModel = '';
  ragSuggestEmbeddingModel = '';
  ragSuggestNotice = '';
  answerReviewStatus: 'manual' | 'ai_draft' | 'approved' = 'manual';
  approvedAt = '';

  get selectedCourseCode(): string {
    const found = this.courses.find((c) => c.id === this.courseId);
    return (found?.code || this.courseId || 'IT2030').trim().toUpperCase();
  }

  get selectedRagCount(): number {
    return this.ragReferences.filter((r) => this.selectedRagChunkIds.has(r.chunkId)).length;
  }

  ngOnInit(): void {
    this.questionId = this.route.snapshot.paramMap.get('questionId');
    this.isEditMode = !!this.questionId;

    const queryCourseId = this.route.snapshot.queryParamMap.get('courseId');
    if (queryCourseId) {
      this.courseId = queryCourseId;
    }

    this.loadCourses();

    if (this.isEditMode && this.questionId) {
      this.loadQuestion(this.questionId);
    }
  }

  loadCourses(): void {
    const isAdmin = this.authService.getRole() === 'admin';
    this.practiceApi.getCourses(!isAdmin).subscribe({
      next: (data) => {
        this.courses = data;
        if (!this.courseId && this.courses.length > 0) {
          this.courseId = this.courses[0].id;
        }
      },
      error: () => {
        this.toastService.error('Không thể tải danh sách môn học.');
      },
    });
  }

  loadQuestion(id: string): void {
    this.loading = true;
    this.practiceApi.getQuestion(id).subscribe({
      next: (q) => {
        this.courseId = q.courseId;
        this.topic = q.topic || '';
        this.title = cleanHtmlToPlainText(q.title);
        this.content = cleanHtmlToPlainText(q.content);
        this.sampleAnswer = cleanHtmlToPlainText(q.sampleAnswer);
        this.difficulty = q.difficulty || 'medium';
        this.timeLimitMinutes = q.timeLimitSeconds ? Math.round(q.timeLimitSeconds / 60) : 3;
        this.tagsString = q.tags ? q.tags.join(', ') : '';
        this.loading = false;
      },
      error: () => {
        this.toastService.error('Không thể tải thông tin câu hỏi.');
        this.loading = false;
      },
    });
  }

  setDifficulty(diff: 'easy' | 'medium' | 'hard'): void {
    this.difficulty = diff;
  }

  generateAiAnswerFromRag(useSelectedChunksOnly = false): void {
    const queryQuestion = this.content.trim() || this.title.trim();
    if (!queryQuestion) {
      this.toastService.warning(
        'Vui lòng nhập tiêu đề hoặc nội dung câu hỏi trước khi gọi AI gợi ý đáp án.',
      );
      return;
    }
    if (!this.courseId) {
      this.toastService.warning('Vui lòng chọn môn học để truy xuất đúng giáo trình RAG.');
      return;
    }
    if (useSelectedChunksOnly && this.selectedRagCount === 0) {
      this.toastService.warning('Vui lòng chọn ít nhất 1 đoạn trích giáo trình RAG làm căn cứ.');
      return;
    }

    this.isSuggestingAnswer = true;
    this.aiRagService
      .suggestReferenceAnswer({
        courseId: this.selectedCourseCode,
        question: queryQuestion,
        topic: this.topic.trim() || undefined,
        topK: 4,
        searchMode: 'hybrid',
        includeRubric: false,
        selectedChunkIds: useSelectedChunksOnly
          ? Array.from(this.selectedRagChunkIds)
          : undefined,
      })
      .subscribe({
        next: (res) => {
          this.isSuggestingAnswer = false;
          this.sampleAnswer = cleanHtmlToPlainText(res.sampleAnswer);
          this.ragReferences = res.ragReferences || [];
          this.selectedRagChunkIds = new Set(
            res.usedChunkIds && res.usedChunkIds.length > 0
              ? res.usedChunkIds
              : this.ragReferences.map((r) => r.chunkId),
          );
          this.ragSuggestModel = res.llmModel;
          this.ragSuggestEmbeddingModel = res.embeddingModel || '';
          this.ragSuggestNotice = res.notice;
          this.answerReviewStatus = 'ai_draft';
          this.approvedAt = '';
          this.toastService.info(
            this.ragReferences.length > 0
              ? `AI đã khởi tạo bản nháp từ ${this.selectedRagCount} đoạn giáo trình RAG. Giảng viên vui lòng rà soát và duyệt.`
              : 'AI đã khởi tạo bản nháp đáp án (chưa có giáo trình RAG cho môn này). Giảng viên vui lòng rà soát và duyệt.',
          );
        },
        error: () => {
          this.isSuggestingAnswer = false;
          this.toastService.error(
            'Không thể kết nối AI Service để gợi ý đáp án. Hãy kiểm tra AI Service đang chạy.',
          );
        },
      });
  }

  isRagChunkSelected(chunkId: string): boolean {
    return this.selectedRagChunkIds.has(chunkId);
  }

  toggleRagChunk(chunkId: string): void {
    if (this.selectedRagChunkIds.has(chunkId)) {
      this.selectedRagChunkIds.delete(chunkId);
    } else {
      this.selectedRagChunkIds.add(chunkId);
    }
  }

  approveAnswer(): void {
    if (!this.sampleAnswer.trim()) {
      this.toastService.warning('Chưa có nội dung đáp án mẫu để duyệt.');
      return;
    }
    this.answerReviewStatus = 'approved';
    const now = new Date();
    this.approvedAt = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    this.toastService.success(
      'Giảng viên đã duyệt Đáp án mẫu. Đây sẽ là nguồn đối chiếu chính khi AI chấm bài.',
    );
  }

  onSampleAnswerChange(): void {
    if (this.answerReviewStatus === 'approved') {
      const now = new Date();
      this.approvedAt = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    }
  }

  save(proceedToRubric = false): void {
    if (!this.title.trim()) {
      this.toastService.warning('Vui lòng nhập tiêu đề câu hỏi.');
      return;
    }
    if (!this.content.trim()) {
      this.toastService.warning('Vui lòng nhập nội dung câu hỏi phát vấn.');
      return;
    }
    if (!this.courseId) {
      this.toastService.warning('Vui lòng chọn môn học.');
      return;
    }

    const tags = this.tagsString
      .split(',')
      .map((t) => t.trim())
      .filter((t) => t.length > 0);

    const questionPayload: Partial<Question> = {
      id: this.questionId || undefined,
      courseId: this.courseId,
      topic: this.topic.trim(),
      title: this.title.trim(),
      content: this.content.trim(),
      sampleAnswer: this.sampleAnswer.trim(),
      difficulty: this.difficulty,
      timeLimitSeconds: (this.timeLimitMinutes || 3) * 60,
      tags: tags.length > 0 ? tags : ['CNPM'],
    };

    this.saving = true;
    this.practiceApi.saveQuestion(questionPayload).subscribe({
      next: (saved) => {
        this.saving = false;
        this.toastService.success(
          this.isEditMode ? 'Cập nhật câu hỏi thành công!' : 'Tạo mới câu hỏi thành công!',
        );

        if (proceedToRubric) {
          this.router.navigate(['/instructor/questions', saved.id, 'rubric']);
        } else {
          this.router.navigate(['/instructor/questions'], {
            queryParams: { courseId: this.courseId },
          });
        }
      },
      error: () => {
        this.saving = false;
        this.toastService.error('Có lỗi xảy ra khi lưu câu hỏi.');
      },
    });
  }
}
