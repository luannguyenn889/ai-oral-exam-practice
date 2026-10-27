import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { PracticeApi } from '../../../data-access/api/practice.api';
import { Course, Question } from '../../../shared/models';
import { ToastService } from '../../../core/services/toast.service';

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
  private toastService = inject(ToastService);

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
    this.practiceApi.getCourses().subscribe({
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
        this.title = q.title;
        this.content = q.content;
        this.sampleAnswer = q.sampleAnswer || '';
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
