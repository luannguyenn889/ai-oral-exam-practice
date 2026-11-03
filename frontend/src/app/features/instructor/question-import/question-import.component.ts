import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { PracticeApi } from '../../../data-access/api/practice.api';
import { Course, ExtractedQuestion, QuestionExtractResult } from '../../../shared/models';
import { ToastService } from '../../../core/services/toast.service';

@Component({
  selector: 'app-question-import',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './question-import.component.html',
  styleUrl: './question-import.component.css',
})
export class QuestionImportComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private practiceApi = inject(PracticeApi);
  private toastService = inject(ToastService);

  courses: Course[] = [];
  selectedCourseId = '';

  // Trạng thái xử lý file
  selectedFile: File | null = null;
  isDragging = false;
  isAnalyzing = false;
  isSubmitting = false;

  // Dữ liệu bóc tách được từ AI
  extractResult: QuestionExtractResult | null = null;
  questions: ExtractedQuestion[] = [];

  // Bộ lọc bảng preview: 'all' | 'issues' | 'valid'
  filterMode: 'all' | 'issues' | 'valid' = 'all';

  // Toggle mở chi tiết Rubric cho từng câu hỏi
  expandedRubrics = new Set<string>();

  get filteredQuestions(): ExtractedQuestion[] {
    if (this.filterMode === 'issues') {
      return this.questions.filter((q) => q.status === 'error' || q.status === 'warning');
    }
    if (this.filterMode === 'valid') {
      return this.questions.filter((q) => q.status === 'valid');
    }
    return this.questions;
  }

  get totalCount(): number {
    return this.questions.length;
  }

  get validCount(): number {
    return this.questions.filter((q) => q.status === 'valid').length;
  }

  get warningCount(): number {
    return this.questions.filter((q) => q.status === 'warning').length;
  }

  get errorCount(): number {
    return this.questions.filter((q) => q.status === 'error').length;
  }

  get hasBlockingErrors(): boolean {
    return this.errorCount > 0;
  }

  ngOnInit(): void {
    const courseIdParam = this.route.snapshot.queryParamMap.get('courseId');
    if (courseIdParam) {
      this.selectedCourseId = courseIdParam;
    }
    this.loadCourses();
  }

  loadCourses(): void {
    this.practiceApi.getCourses().subscribe({
      next: (courses) => {
        this.courses = courses;
        if (!this.selectedCourseId && courses.length > 0) {
          this.selectedCourseId = courses[0].id;
        }
      },
      error: () => {
        this.toastService.error('Không thể tải danh sách môn học.');
      },
    });
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging = true;
  }

  onDragLeave(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging = false;
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging = false;
    const files = event.dataTransfer?.files;
    if (files && files.length > 0) {
      this.handleFileSelected(files[0]);
    }
  }

  onFileInputChange(event: Event): void {
    const target = event.target as HTMLInputElement;
    if (target.files && target.files.length > 0) {
      this.handleFileSelected(target.files[0]);
    }
  }

  handleFileSelected(file: File): void {
    const name = file.name.toLowerCase();
    if (!name.endsWith('.xlsx') && !name.endsWith('.xls') && !name.endsWith('.docx') && !name.endsWith('.txt')) {
      this.toastService.warning('Chỉ hỗ trợ file Excel (.xlsx), Word (.docx) hoặc Text (.txt).');
      return;
    }
    this.selectedFile = file;
    this.startAnalysis();
  }

  startAnalysis(): void {
    if (!this.selectedFile) return;

    this.isAnalyzing = true;
    this.practiceApi.extractQuestionsFromFile(this.selectedFile, this.selectedCourseId).subscribe({
      next: (result) => {
        this.isAnalyzing = false;
        this.extractResult = result;
        this.questions = result.questions.map((q) => ({ ...q }));
        this.validateAllQuestions();
        this.toastService.success(
          `AI đã phân tích xong! Phát hiện ${result.totalDetected} câu hỏi và thang điểm Rubric.`,
        );
      },
      error: (err) => {
        this.isAnalyzing = false;
        const msg = err?.error?.detail || 'Có lỗi xảy ra khi phân tích tài liệu bằng AI.';
        this.toastService.error(msg);
      },
    });
  }

  validateAllQuestions(): void {
    const codes = new Set(this.questions.map((q) => q.code.trim().toUpperCase()).filter(Boolean));

    for (const q of this.questions) {
      q.errors = [];
      q.warnings = [];

      // Kiểm tra nội dung & đáp án
      if (!q.content.trim()) {
        q.errors.push('Thiếu nội dung câu hỏi phát vấn');
      }
      if (!q.sampleAnswer.trim()) {
        q.errors.push('Thiếu đáp án tham chiếu (Reference Answer)');
      }

      // Kiểm tra liên kết câu hỏi cha / con
      if (q.parentCode) {
        const pClean = q.parentCode.trim().toUpperCase();
        if (pClean === q.code.trim().toUpperCase()) {
          q.errors.push('Mã câu hỏi cha không được trùng với mã của chính câu này');
        } else if (!codes.has(pClean)) {
          q.warnings.push(`Chưa tìm thấy câu hỏi cha mang mã '${q.parentCode}'`);
        }
      }

      // Kiểm tra tổng điểm Rubric
      const sum = Math.round(q.criteria.reduce((acc, c) => acc + (Number(c.maxScore) || 0), 0) * 10) / 10;
      q.totalScore = sum;
      if (Math.abs(sum - 10.0) > 0.05) {
        q.warnings.push(`Tổng điểm Rubric là ${sum}đ (Cần đúng 10.0đ)`);
      }

      if (q.errors.length > 0) {
        q.status = 'error';
      } else if (q.warnings.length > 0) {
        q.status = 'warning';
      } else {
        q.status = 'valid';
      }
    }
  }

  toggleRubric(tempId: string): void {
    if (this.expandedRubrics.has(tempId)) {
      this.expandedRubrics.delete(tempId);
    } else {
      this.expandedRubrics.add(tempId);
    }
  }

  isRubricExpanded(tempId: string): boolean {
    return this.expandedRubrics.has(tempId);
  }

  balanceRubricTo10(question: ExtractedQuestion): void {
    if (question.criteria.length === 0) return;
    const diff = Math.round((10.0 - question.totalScore) * 10) / 10;
    // Cộng chênh lệch vào tiêu chí đầu tiên hoặc chia đều
    const first = question.criteria[0];
    first.maxScore = Math.max(0.5, Math.round((Number(first.maxScore) + diff) * 10) / 10);
    this.validateAllQuestions();
    this.toastService.info(`Đã tự động cân bằng tổng điểm Rubric câu ${question.code} về đúng 10.0đ.`);
  }

  removeQuestion(index: number): void {
    this.questions.splice(index, 1);
    this.validateAllQuestions();
  }

  addNewQuestionRow(): void {
    const nextNo = this.questions.length + 1;
    this.questions.push({
      tempId: `manual-${Date.now()}`,
      code: `Q${nextNo}`,
      topic: 'Chủ đề ôn tập',
      title: `Câu hỏi ${nextNo}`,
      content: '',
      sampleAnswer: '',
      difficulty: 'medium',
      timeLimitSeconds: 180,
      parentCode: null,
      isFollowup: false,
      tags: ['CNPM'],
      criteria: [
        { name: 'Kiến thức cốt lõi', description: 'Trình bày chính xác định nghĩa trọng tâm', maxScore: 4.0 },
        { name: 'Phân tích & Ví dụ', description: 'Lấy ví dụ cụ thể minh họa bản chất vấn đề', maxScore: 4.0 },
        { name: 'Kỹ năng phản xạ', description: 'Diễn đạt tự tin, đúng thuật ngữ', maxScore: 2.0 },
      ],
      totalScore: 10.0,
      status: 'error',
      errors: ['Thiếu nội dung câu hỏi phát vấn', 'Thiếu đáp án tham chiếu (Reference Answer)'],
      warnings: [],
    });
    this.validateAllQuestions();
  }

  resetAll(): void {
    this.selectedFile = null;
    this.extractResult = null;
    this.questions = [];
  }

  downloadTemplate(): void {
    this.practiceApi.downloadExcelTemplate().subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'Mau_Ngan_Hang_Cau_Hoi_Van_Dap.xlsx';
        a.click();
        window.URL.revokeObjectURL(url);
        this.toastService.success('Đã tải xuống file mẫu Excel thành công!');
      },
      error: () => {
        this.toastService.error('Không thể tải file mẫu. Vui lòng thử lại sau.');
      },
    });
  }

  submitBatch(): void {
    this.validateAllQuestions();
    if (this.questions.length === 0) {
      this.toastService.warning('Danh sách câu hỏi đang rỗng.');
      return;
    }
    if (this.hasBlockingErrors) {
      this.toastService.warning(
        `Còn ${this.errorCount} câu hỏi có lỗi (màu đỏ). Vui lòng điền đủ nội dung và đáp án trước khi lưu!`,
      );
      this.filterMode = 'issues';
      return;
    }

    this.isSubmitting = true;
    this.practiceApi.commitBatchQuestions(this.selectedCourseId, this.questions).subscribe({
      next: (res) => {
        this.isSubmitting = false;
        this.toastService.success(res.message || `Đã nhập thành công ${res.importedCount} câu hỏi vào ngân hàng!`);
        this.router.navigate(['/instructor/questions'], {
          queryParams: { courseId: this.selectedCourseId },
        });
      },
      error: () => {
        this.isSubmitting = false;
        this.toastService.error('Có lỗi xảy ra khi lưu câu hỏi vào ngân hàng.');
      },
    });
  }
}

