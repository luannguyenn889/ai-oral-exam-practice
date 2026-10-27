import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { PracticeApi } from '../../../data-access/api/practice.api';
import { Question, Rubric, RubricCriterion } from '../../../shared/models';
import { ToastService } from '../../../core/services/toast.service';

@Component({
  selector: 'app-rubric-editor',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './rubric-editor.component.html',
  styleUrl: './rubric-editor.component.css',
})
export class RubricEditorComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private practiceApi = inject(PracticeApi);
  private toastService = inject(ToastService);

  questionId = '';
  question: Question | null = null;
  loading = false;
  saving = false;

  criteria: RubricCriterion[] = [];
  gradingInstructions =
    'Chấm điểm khách quan dựa trên tính chính xác của thuật ngữ, chiều sâu phân tích và tính ứng dụng thực tế.';

  get currentTotalScore(): number {
    const sum = this.criteria.reduce((acc, c) => acc + (Number(c.maxScore) || 0), 0);
    return Math.round(sum * 10) / 10;
  }

  get isTotalScoreValid(): boolean {
    return Math.abs(this.currentTotalScore - 10) < 0.01;
  }

  ngOnInit(): void {
    this.questionId = this.route.snapshot.paramMap.get('questionId') || '';
    if (this.questionId) {
      this.loadData(this.questionId);
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
          this.applyDefault4CriteriaTemplate();
        }
        this.loading = false;
      },
      error: () => {
        this.toastService.error('Không thể tải thông tin câu hỏi và Rubric.');
        this.loading = false;
      },
    });
  }

  addCriterion(): void {
    const nextIndex = this.criteria.length + 1;
    this.criteria.push({
      id: `c-new-${Date.now()}-${nextIndex}`,
      name: `Tiêu chí ${nextIndex}: Nội dung đánh giá`,
      description: 'Mô tả cụ thể các ý cần đạt để AI đối chiếu và cho điểm...',
      maxScore: 2.0,
    });
  }

  removeCriterion(index: number): void {
    if (this.criteria.length <= 1) {
      this.toastService.warning('Rubric cần có ít nhất 1 tiêu chí đánh giá.');
      return;
    }
    this.criteria.splice(index, 1);
  }

  moveUp(index: number): void {
    if (index > 0) {
      const temp = this.criteria[index];
      this.criteria[index] = this.criteria[index - 1];
      this.criteria[index - 1] = temp;
    }
  }

  moveDown(index: number): void {
    if (index < this.criteria.length - 1) {
      const temp = this.criteria[index];
      this.criteria[index] = this.criteria[index + 1];
      this.criteria[index + 1] = temp;
    }
  }

  applyDefault4CriteriaTemplate(): void {
    this.criteria = [
      {
        id: 'c1',
        name: 'Khái niệm & Kiến thức cốt lõi',
        description:
          'Trình bày chính xác và đầy đủ các định nghĩa, thuật ngữ chuyên môn trọng tâm.',
        maxScore: 3.0,
      },
      {
        id: 'c2',
        name: 'Phân tích & So sánh chuyên sâu',
        description:
          'Phân tích rõ cơ chế hoạt động, sự khác biệt và ưu nhược điểm liên quan.',
        maxScore: 3.0,
      },
      {
        id: 'c3',
        name: 'Ví dụ thực tế & Tính ứng dụng',
        description:
          'Đưa ra được ví dụ mã nguồn hoặc tình huống thực tế minh họa đúng bản chất.',
        maxScore: 2.5,
      },
      {
        id: 'c4',
        name: 'Phản xạ & Kỹ năng trình bày',
        description:
          'Diễn đạt mạch lạc, phản xạ tự tin, dùng thuật ngữ chuyên ngành chuẩn xác.',
        maxScore: 1.5,
      },
    ];
  }

  apply3CriteriaTemplate(): void {
    this.criteria = [
      {
        id: 'c1',
        name: 'Độ chính xác nội dung & Lý thuyết',
        description:
          'Nắm vững lý thuyết trọng tâm, trả lời đúng trọng tâm câu hỏi mà không lan man.',
        maxScore: 4.0,
      },
      {
        id: 'c2',
        name: 'Minh họa & Khả năng vận dụng',
        description:
          'Lấy được ví dụ cụ thể, giải thích được cách giải quyết vấn đề trong dự án.',
        maxScore: 3.5,
      },
      {
        id: 'c3',
        name: 'Khả năng diễn đạt & Thuật ngữ',
        description:
          'Trình bày rõ ràng, phát âm chính xác thuật ngữ công nghệ, tự tin.',
        maxScore: 2.5,
      },
    ];
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
