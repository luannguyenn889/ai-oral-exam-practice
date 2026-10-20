import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AiRagService } from '../../../core/services/ai-rag.service';
import { AiHealthStatus, RagStatus } from '../../../shared/models';
import { SkeletonComponent } from '../../../shared/components/skeleton/skeleton.component';

@Component({
  selector: 'app-admin-dashboard',
  standalone: true,
  imports: [CommonModule, SkeletonComponent],
  templateUrl: './admin-dashboard.component.html',
  styleUrl: './admin-dashboard.component.css',
})
export class AdminDashboardComponent implements OnInit {
  private aiRagService = inject(AiRagService);

  loading = true;
  health: AiHealthStatus | null = null;
  ragStatus: RagStatus | null = null;
  offlineError: string | null = null;

  ngOnInit(): void {
    this.checkSystemStatus();
  }

  checkSystemStatus(): void {
    this.loading = true;
    this.offlineError = null;
    this.aiRagService.getHealth().subscribe({
      next: (h) => {
        this.health = h;
        this.aiRagService.getRagStatus('IT2030').subscribe({
          next: (r) => {
            this.ragStatus = r;
            this.loading = false;
          },
          error: () => {
            this.loading = false;
          },
        });
      },
      error: () => {
        this.health = null;
        this.offlineError =
          'Dịch vụ AI (FastAPI Port 8000) hiện đang Offline. Hãy chạy start-ai-service.bat để bật dịch vụ.';
        this.loading = false;
      },
    });
  }
}

