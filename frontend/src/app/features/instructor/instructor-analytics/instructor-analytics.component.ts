import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { catchError, forkJoin, of } from 'rxjs';
import { PracticeApi } from '../../../data-access/api/practice.api';
import { AuthService } from '../../../core/auth/auth.service';
import { Course, InstructorPracticeRecord, Question } from '../../../shared/models';
import { SkeletonComponent } from '../../../shared/components/skeleton/skeleton.component';
import { EmptyStateComponent } from '../../../shared/components/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../../shared/components/error-state/error-state.component';

export interface QuestionGapStat {
  questionId: string;
  questionTitle: string;
  topic: string;
  courseCode: string;
  attempts: number;
  avgScore: number;
  lowCount: number;
  lowRate: number;
}

export interface CriterionGapStat {
  key: string;
  name: string;
  attempts: number;
  avgScore: number;
  avgMaxScore: number;
  avgPercent: number;
  below60Count: number;
}

export interface TopicGapStat {
  topic: string;
  attempts: number;
  avgScore: number;
  lowCount: number;
  missingCount: number;
}

export interface MissingPointStat {
  text: string;
  count: number;
  topics: string[];
  sampleQuestion: string;
}

@Component({
  selector: 'app-instructor-analytics',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    SkeletonComponent,
    EmptyStateComponent,
    ErrorStateComponent,
  ],
  templateUrl: './instructor-analytics.component.html',
  styleUrl: './instructor-analytics.component.css',
})
export class InstructorAnalyticsComponent implements OnInit {
  private practiceApi = inject(PracticeApi);
  private authService = inject(AuthService);

  courses: Course[] = [];
  records: InstructorPracticeRecord[] = [];
  questionMap = new Map<string, Question>();

  loading = true;
  error: string | null = null;
  selectedCourseId = '';

  // Thống kê tổng quan
  totalSessions = 0;
  uniqueStudents = 0;
  averageScore = 0;
  passRate = 0;
  lowScoreCount = 0;
  needsReviewCount = 0;

  // Các bảng lỗ hổng kiến thức
  weakestQuestions: QuestionGapStat[] = [];
  weakestCriteria: CriterionGapStat[] = [];
  topicGaps: TopicGapStat[] = [];
  commonMissingPoints: MissingPointStat[] = [];
  pedagogicalInsights: string[] = [];

  get isAdmin(): boolean {
    return this.authService.getRole() === 'admin';
  }

  get filteredRecords(): InstructorPracticeRecord[] {
    if (!this.selectedCourseId) {
      return this.records;
    }
    return this.records.filter((r) => r.courseId === this.selectedCourseId);
  }

  ngOnInit(): void {
    this.loadData();
  }

  loadData(): void {
    this.loading = true;
    this.error = null;

    forkJoin({
      courses: this.practiceApi.getCourses(!this.isAdmin).pipe(catchError(() => of([]))),
      questions: this.practiceApi.getQuestions().pipe(catchError(() => of([]))),
      records: this.practiceApi.getInstructorPracticeRecords(),
    }).subscribe({
      next: ({ courses, questions, records }) => {
        this.courses = courses || [];
        this.questionMap = new Map((questions || []).map((q) => [String(q.id), q]));
        this.records = records || [];
        this.recomputeAnalytics();
        this.loading = false;
      },
      error: (err) => {
        this.error =
          err?.message || 'Không thể tải dữ liệu thống kê luyện tập của sinh viên.';
        this.loading = false;
      },
    });
  }

  onCourseChange(): void {
    this.recomputeAnalytics();
  }

  getEffectiveScore(record: InstructorPracticeRecord): number | null {
    if (
      record.reviewedByInstructor &&
      record.instructorScore !== null &&
      record.instructorScore !== undefined
    ) {
      return Number(record.instructorScore);
    }
    if (record.totalScore !== null && record.totalScore !== undefined) {
      return Number(record.totalScore);
    }
    return null;
  }

  private getTopicForRecord(record: InstructorPracticeRecord): string {
    const q = record.questionId ? this.questionMap.get(String(record.questionId)) : undefined;
    const topic = (q?.topic || '').trim();
    return topic || 'Chủ đề chung';
  }

  private getCriterionDisplayName(
    record: InstructorPracticeRecord,
    criterionId: string,
  ): string {
    const q = record.questionId ? this.questionMap.get(String(record.questionId)) : undefined;
    const matched = q?.rubric?.criteria?.find((c) => c.id === criterionId);
    if (matched?.name?.trim()) {
      return matched.name.trim();
    }
    return criterionId || 'Tiêu chí chưa đặt tên';
  }

  private recomputeAnalytics(): void {
    const list = this.filteredRecords;
    this.totalSessions = list.length;

    const studentIds = new Set(list.map((r) => r.studentId).filter(Boolean));
    this.uniqueStudents = studentIds.size;
    this.needsReviewCount = list.filter((r) => r.needsHumanReview).length;

    const scoredList = list
      .map((r) => ({ record: r, score: this.getEffectiveScore(r) }))
      .filter((item): item is { record: InstructorPracticeRecord; score: number } => item.score !== null);

    if (scoredList.length > 0) {
      const sum = scoredList.reduce((acc, item) => acc + item.score, 0);
      this.averageScore = Math.round((sum / scoredList.length) * 10) / 10;
      this.lowScoreCount = scoredList.filter((item) => item.score < 5.0).length;
      const passCount = scoredList.length - this.lowScoreCount;
      this.passRate = Math.round((passCount / scoredList.length) * 100);
    } else {
      this.averageScore = 0;
      this.lowScoreCount = 0;
      this.passRate = 0;
    }

    this.computeQuestionGaps(list);
    this.computeCriterionGaps(list);
    this.computeTopicGaps(list);
    this.computeCommonMissingPoints(list);
    this.computePedagogicalInsights();
  }

  private computeQuestionGaps(list: InstructorPracticeRecord[]): void {
    const map = new Map<
      string,
      {
        questionId: string;
        questionTitle: string;
        topic: string;
        courseCode: string;
        scores: number[];
      }
    >();

    for (const r of list) {
      const score = this.getEffectiveScore(r);
      if (score === null) continue;
      const key = r.questionId ? String(r.questionId) : r.questionTitle;
      const entry = map.get(key) || {
        questionId: r.questionId ? String(r.questionId) : '',
        questionTitle: r.questionTitle || 'Câu hỏi chưa có tiêu đề',
        topic: this.getTopicForRecord(r),
        courseCode: r.courseCode || '—',
        scores: [],
      };
      entry.scores.push(score);
      map.set(key, entry);
    }

    const stats: QuestionGapStat[] = [];
    for (const entry of map.values()) {
      const attempts = entry.scores.length;
      const avgScore =
        Math.round((entry.scores.reduce((a, b) => a + b, 0) / attempts) * 10) / 10;
      const lowCount = entry.scores.filter((s) => s < 5.0).length;
      stats.push({
        questionId: entry.questionId,
        questionTitle: entry.questionTitle,
        topic: entry.topic,
        courseCode: entry.courseCode,
        attempts,
        avgScore,
        lowCount,
        lowRate: Math.round((lowCount / attempts) * 100),
      });
    }

    this.weakestQuestions = stats.sort((a, b) => a.avgScore - b.avgScore).slice(0, 8);
  }

  private computeCriterionGaps(list: InstructorPracticeRecord[]): void {
    const map = new Map<
      string,
      {
        key: string;
        name: string;
        scores: number[];
        maxScores: number[];
        below60Count: number;
      }
    >();

    for (const r of list) {
      const criteria = r.evaluation?.criteria || [];
      for (const c of criteria) {
        const maxScore = Number(c.maxScore) || 0;
        const score = Number(c.score) || 0;
        if (maxScore <= 0) continue;

        const displayName = this.getCriterionDisplayName(r, c.criterionId);
        const key = displayName.toLowerCase();
        const entry = map.get(key) || {
          key,
          name: displayName,
          scores: [],
          maxScores: [],
          below60Count: 0,
        };
        entry.scores.push(score);
        entry.maxScores.push(maxScore);
        if (score / maxScore < 0.6) {
          entry.below60Count += 1;
        }
        map.set(key, entry);
      }
    }

    const stats: CriterionGapStat[] = [];
    for (const entry of map.values()) {
      const attempts = entry.scores.length;
      const sumScore = entry.scores.reduce((a, b) => a + b, 0);
      const sumMax = entry.maxScores.reduce((a, b) => a + b, 0);
      const avgScore = Math.round((sumScore / attempts) * 10) / 10;
      const avgMaxScore = Math.round((sumMax / attempts) * 10) / 10;
      const avgPercent = sumMax > 0 ? Math.round((sumScore / sumMax) * 100) : 0;
      stats.push({
        key: entry.key,
        name: entry.name,
        attempts,
        avgScore,
        avgMaxScore,
        avgPercent,
        below60Count: entry.below60Count,
      });
    }

    this.weakestCriteria = stats.sort((a, b) => a.avgPercent - b.avgPercent).slice(0, 8);
  }

  private computeTopicGaps(list: InstructorPracticeRecord[]): void {
    const map = new Map<
      string,
      { topic: string; scores: number[]; missingCount: number }
    >();

    for (const r of list) {
      const topic = this.getTopicForRecord(r);
      const entry = map.get(topic) || { topic, scores: [], missingCount: 0 };
      const score = this.getEffectiveScore(r);
      if (score !== null) {
        entry.scores.push(score);
      }
      const criteriaMissing = (r.evaluation?.criteria || []).reduce(
        (acc, c) => acc + (c.missingOrIncorrect?.length || 0),
        0,
      );
      entry.missingCount += criteriaMissing + (r.evaluation?.weaknesses?.length || 0);
      map.set(topic, entry);
    }

    const stats: TopicGapStat[] = [];
    for (const entry of map.values()) {
      const attempts = entry.scores.length;
      if (attempts === 0) continue;
      const avgScore =
        Math.round((entry.scores.reduce((a, b) => a + b, 0) / attempts) * 10) / 10;
      const lowCount = entry.scores.filter((s) => s < 5.0).length;
      stats.push({
        topic: entry.topic,
        attempts,
        avgScore,
        lowCount,
        missingCount: entry.missingCount,
      });
    }

    this.topicGaps = stats.sort((a, b) => a.avgScore - b.avgScore);
  }

  private computeCommonMissingPoints(list: InstructorPracticeRecord[]): void {
    const map = new Map<
      string,
      { text: string; count: number; topics: Set<string>; sampleQuestion: string }
    >();

    for (const r of list) {
      const topic = this.getTopicForRecord(r);
      const rawPoints: string[] = [];
      for (const c of r.evaluation?.criteria || []) {
        for (const item of c.missingOrIncorrect || []) {
          rawPoints.push(item);
        }
      }
      for (const w of r.evaluation?.weaknesses || []) {
        rawPoints.push(w);
      }

      for (const raw of rawPoints) {
        const cleaned = (raw || '').replace(/\s+/g, ' ').trim();
        if (cleaned.length < 4) continue;
        const normKey = cleaned.toLowerCase().replace(/[.,;:!?]+$/, '');
        const existing = map.get(normKey);
        if (existing) {
          existing.count += 1;
          existing.topics.add(topic);
        } else {
          map.set(normKey, {
            text: cleaned,
            count: 1,
            topics: new Set([topic]),
            sampleQuestion: r.questionTitle || '',
          });
        }
      }
    }

    this.commonMissingPoints = Array.from(map.values())
      .map((item) => ({
        text: item.text,
        count: item.count,
        topics: Array.from(item.topics),
        sampleQuestion: item.sampleQuestion,
      }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);
  }

  private computePedagogicalInsights(): void {
    const insights: string[] = [];
    if (this.weakestQuestions.length > 0) {
      const wq = this.weakestQuestions[0];
      insights.push(
        `Câu hỏi "${wq.questionTitle}" đang có điểm trung bình thấp nhất (${wq.avgScore}/10 qua ${wq.attempts} lượt, ${wq.lowRate}% dưới 5.0đ). Nên ôn tập lại trọng tâm hoặc rà soát lại độ khó Rubric.`,
      );
    }
    if (this.weakestCriteria.length > 0) {
      const wc = this.weakestCriteria[0];
      insights.push(
        `Tiêu chí "${wc.name}" có tỷ lệ đạt thấp nhất (${wc.avgPercent}% — trung bình ${wc.avgScore}/${wc.avgMaxScore}đ). Sinh viên thường mất điểm ở phần này khi trả lời vấn đáp.`,
      );
    }
    if (this.topicGaps.length > 0 && this.topicGaps[0].topic !== 'Chủ đề chung') {
      const tg = this.topicGaps[0];
      insights.push(
        `Chủ đề "${tg.topic}" ghi nhận điểm trung bình ${tg.avgScore}/10 với ${tg.missingCount} lượt ý kiến thức bị AI đánh giá thiếu/chưa chuẩn — đề xuất dành thêm thời gian giảng lại trên lớp.`,
      );
    }
    this.pedagogicalInsights = insights;
  }

  getBarColorClass(percent: number): string {
    if (percent < 50) return 'bar-fill--danger';
    if (percent < 70) return 'bar-fill--warning';
    return 'bar-fill--success';
  }
}
