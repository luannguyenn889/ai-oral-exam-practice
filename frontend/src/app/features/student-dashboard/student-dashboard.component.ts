import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { PracticeApi } from '../../data-access/api/practice.api';
import { AuthService } from '../../core/auth/auth.service';
import { Course, PracticeSession } from '../../shared/models';
import { SkeletonComponent } from '../../shared/components/skeleton/skeleton.component';
import { StatusBadgeComponent } from '../../shared/components/status-badge/status-badge.component';
import { ScoreDisplayComponent } from '../../shared/components/score-display/score-display.component';

@Component({
  selector: 'app-student-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    SkeletonComponent,
    StatusBadgeComponent,
    ScoreDisplayComponent,
  ],
  templateUrl: './student-dashboard.component.html',
  styleUrl: './student-dashboard.component.css',
})
export class StudentDashboardComponent implements OnInit {
  private practiceApi = inject(PracticeApi);
  private authService = inject(AuthService);

  loadingCourses = true;
  loadingHistory = true;
  courses: Course[] = [];
  allSessions: PracticeSession[] = [];
  recentSessions: PracticeSession[] = [];

  // Bộ lọc học phần
  searchQuery = '';
  selectedDepartment = '';
  onlyWithQuestions = false;
  sortBy: 'default' | 'questions_desc' | 'name_asc' = 'default';

  getEffectiveScore(session: PracticeSession): number | null {
    if (
      session.reviewedByInstructor &&
      session.instructorScore !== null &&
      session.instructorScore !== undefined
    ) {
      return Number(session.instructorScore);
    }
    if (session.evaluation?.totalScore !== null && session.evaluation?.totalScore !== undefined) {
      return Number(session.evaluation.totalScore);
    }
    return null;
  }

  get totalPracticedCount(): number {
    return this.allSessions.length;
  }

  get instructorReviewedCount(): number {
    return this.allSessions.filter((s) => s.reviewedByInstructor).length;
  }

  get scoredSessions(): { session: PracticeSession; score: number; maxScore: number }[] {
    return this.allSessions
      .map((session) => ({
        session,
        score: this.getEffectiveScore(session),
        maxScore: session.evaluation?.maxScore || 10,
      }))
      .filter(
        (item): item is { session: PracticeSession; score: number; maxScore: number } =>
          item.score !== null,
      );
  }

  get averageScoreDisplay(): string {
    const list = this.scoredSessions;
    if (list.length === 0) return '—';
    const avg = list.reduce((acc, item) => acc + item.score, 0) / list.length;
    return avg.toFixed(1);
  }

  get highestScoreDisplay(): string {
    const list = this.scoredSessions;
    if (list.length === 0) return '—';
    const max = Math.max(...list.map((item) => item.score));
    return max.toFixed(1);
  }

  get scoreTrendDelta(): number | null {
    const list = this.scoredSessions;
    if (list.length < 2) return null;
    const windowSize = Math.min(3, Math.floor(list.length / 2));
    const recentSlice = list.slice(0, windowSize);
    const prevSlice = list.slice(windowSize, windowSize * 2);
    if (prevSlice.length === 0) return null;
    const recentAvg = recentSlice.reduce((a, b) => a + b.score, 0) / recentSlice.length;
    const prevAvg = prevSlice.reduce((a, b) => a + b.score, 0) / prevSlice.length;
    return Math.round((recentAvg - prevAvg) * 10) / 10;
  }

  get trendBars(): { id: string; label: string; title: string; score: number; percent: number; reviewed: boolean }[] {
    return this.scoredSessions
      .slice(0, 8)
      .reverse()
      .map((item, idx) => ({
        id: item.session.id,
        label: `#${idx + 1}`,
        title: `${item.session.questionTitle || 'Phiên luyện tập'} — ${item.score}/${item.maxScore}đ`,
        score: item.score,
        percent: Math.min(100, Math.max(8, Math.round((item.score / (item.maxScore || 10)) * 100))),
        reviewed: Boolean(item.session.reviewedByInstructor),
      }));
  }

  get availableDepartments(): string[] {
    const set = new Set<string>();
    for (const c of this.courses) {
      const dept = (c.department || '').trim();
      if (dept) {
        set.add(dept);
      }
    }
    return Array.from(set).sort((a, b) => a.localeCompare(b, 'vi'));
  }

  get hasActiveCourseFilter(): boolean {
    return (
      Boolean(this.searchQuery.trim()) ||
      Boolean(this.selectedDepartment) ||
      this.onlyWithQuestions ||
      this.sortBy !== 'default'
    );
  }

  get filteredCourses(): Course[] {
    const query = this.searchQuery.trim().toLowerCase();
    let list = this.courses.filter((c) => {
      if (this.selectedDepartment && (c.department || '').trim() !== this.selectedDepartment) {
        return false;
      }
      if (this.onlyWithQuestions && (c.questionCount || 0) <= 0) {
        return false;
      }
      if (query) {
        const hay = `${c.code} ${c.name} ${c.description || ''} ${c.department || ''}`.toLowerCase();
        if (!hay.includes(query)) {
          return false;
        }
      }
      return true;
    });

    if (this.sortBy === 'questions_desc') {
      list = [...list].sort((a, b) => (b.questionCount || 0) - (a.questionCount || 0));
    } else if (this.sortBy === 'name_asc') {
      list = [...list].sort((a, b) => a.name.localeCompare(b.name, 'vi'));
    }

    return list;
  }

  resetCourseFilters(): void {
    this.searchQuery = '';
    this.selectedDepartment = '';
    this.onlyWithQuestions = false;
    this.sortBy = 'default';
  }

  ngOnInit(): void {
    this.practiceApi.getCourses().subscribe({
      next: (data) => {
        this.courses = data;
        const userDept = this.authService.getCurrentUser()?.department?.trim();
        if (userDept && this.availableDepartments.includes(userDept) && !this.selectedDepartment) {
          this.selectedDepartment = userDept;
        }
        this.loadingCourses = false;
      },
      error: () => {
        this.loadingCourses = false;
      },
    });

    this.practiceApi.getPracticeHistory().subscribe({
      next: (data) => {
        this.allSessions = data || [];
        this.recentSessions = this.allSessions.slice(0, 5);
        this.loadingHistory = false;
      },
      error: () => {
        this.loadingHistory = false;
      },
    });
  }
}
