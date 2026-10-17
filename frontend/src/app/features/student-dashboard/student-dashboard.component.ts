import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { PracticeApi } from '../../data-access/api/practice.api';
import { Course, PracticeSession } from '../../shared/models';
import { SkeletonComponent } from '../../shared/components/skeleton/skeleton.component';
import { StatusBadgeComponent } from '../../shared/components/status-badge/status-badge.component';
import { ScoreDisplayComponent } from '../../shared/components/score-display/score-display.component';

@Component({
  selector: 'app-student-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    SkeletonComponent,
    StatusBadgeComponent,
    ScoreDisplayComponent,
  ],
  templateUrl: './student-dashboard.component.html',
  styleUrl: './student-dashboard.component.scss',
})
export class StudentDashboardComponent implements OnInit {
  private practiceApi = inject(PracticeApi);

  loadingCourses = true;
  loadingHistory = true;
  courses: Course[] = [];
  recentSessions: PracticeSession[] = [];

  ngOnInit(): void {
    this.practiceApi.getCourses().subscribe({
      next: (data) => {
        this.courses = data;
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
