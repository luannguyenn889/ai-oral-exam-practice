import { HttpClient } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';

interface HealthResponse {
  status: string;
  service: string;
  aiService: string;
}

@Component({
  selector: 'app-root',
  standalone: true,
  template: `
    <main class="page-shell">
      <header class="topbar">
        <a class="brand" href="/" aria-label="Trang chủ">
          <span class="brand-mark">O</span>
          <span>Oral Practice</span>
        </a>
        <span class="phase-tag">Project scaffold</span>
      </header>

      <section class="hero">
        <p class="eyebrow">AI ORAL EXAM PRACTICE</p>
        <h1>Luyện nói, hiểu rõ<br><span>mình cần cải thiện gì.</span></h1>
        <p class="intro">Khung ứng dụng đã sẵn sàng cho luồng luyện vấn đáp. Các chức năng học phần, ghi âm, transcript và chấm rubric sẽ được phát triển theo backlog Scrum.</p>
      </section>

      <section class="status-panel" aria-live="polite">
        <div>
          <p class="eyebrow">KẾT NỐI DỊCH VỤ</p>
          <h2>{{ statusMessage() }}</h2>
        </div>
        <button type="button" class="refresh-button" (click)="refresh()">Kiểm tra lại</button>
      </section>

      <section class="service-grid" aria-label="Các thành phần hệ thống">
        <article class="service-card">
          <span class="service-index">01 / FE</span>
          <h3>Giao diện luyện tập</h3>
          <p>Angular · chọn câu hỏi, ghi âm, transcript và kết quả.</p>
          <span class="service-state ready">Đang chạy</span>
        </article>
        <article class="service-card">
          <span class="service-index">02 / BE</span>
          <h3>API nghiệp vụ</h3>
          <p>Spring Boot · tài khoản, học phần, phiên luyện và dữ liệu.</p>
          <span class="service-state" [class.ready]="backendUp()">{{ backendLabel() }}</span>
        </article>
        <article class="service-card">
          <span class="service-index">03 / AI</span>
          <h3>Xử lý tiếng nói &amp; câu trả lời</h3>
          <p>FastAPI · điểm nối cho STT tiếng Việt và chấm theo rubric.</p>
          <span class="service-state" [class.ready]="aiUp()">{{ aiLabel() }}</span>
        </article>
      </section>

      <footer class="footnote">Bản hiện tại là khung kỹ thuật; chưa xử lý audio hay đưa ra điểm AI.</footer>
    </main>
  `,
  styleUrl: './app.component.css',
})
export class AppComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly health = signal<HealthResponse | null>(null);
  private readonly requestFailed = signal(false);

  ngOnInit(): void {
    this.refresh();
  }

  refresh(): void {
    this.requestFailed.set(false);
    this.http.get<HealthResponse>('/api/health').subscribe({
      next: (response) => this.health.set(response),
      error: () => {
        this.health.set(null);
        this.requestFailed.set(true);
      },
    });
  }

  statusMessage(): string {
    if (this.requestFailed()) return 'Chưa kết nối được backend';
    if (!this.health()) return 'Đang kiểm tra…';
    return 'Trạng thái các service';
  }

  backendUp(): boolean {
    return this.health()?.status === 'UP';
  }

  aiUp(): boolean {
    return this.health()?.aiService === 'UP';
  }

  backendLabel(): string {
    if (this.requestFailed()) return 'Chưa kết nối';
    if (!this.health()) return 'Đang kiểm tra';
    return this.backendUp() ? 'Đang chạy' : 'Không khả dụng';
  }

  aiLabel(): string {
    if (this.requestFailed() || !this.health()) return 'Chưa xác định';
    return this.aiUp() ? 'Đang chạy' : 'Chưa kết nối';
  }
}
