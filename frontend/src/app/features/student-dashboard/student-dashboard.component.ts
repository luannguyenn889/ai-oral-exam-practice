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
  recentSessions: PracticeSession[] = [];

  // Bộ lọc học phần
  searchQuery = '';
  selectedDepartment = '';
  onlyWithQuestions = false;
  sortBy: 'default' | 'questions_desc' | 'name_asc' = 'default';

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
        this.recentSessions = data.slice(0, 5);
        this.loadingHistory = false;
      },
      error: () => {
        this.loadingHistory = false;
      },
    });
  }
}
