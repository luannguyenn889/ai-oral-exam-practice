import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-score-display',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './score-display.component.html',
  styleUrl: './score-display.component.css',
})
export class ScoreDisplayComponent {
  @Input({ required: true }) score!: number;
  @Input() maxScore = 10;
  @Input() size: 'display' | 'md' | 'sm' = 'md';

  get formattedScore(): string {
    return this.score.toLocaleString('vi-VN', { maximumFractionDigits: 1 });
  }

  get colorVariant(): 'success' | 'warning' | 'danger' {
    const ratio = this.score / (this.maxScore || 10);
    if (ratio >= 0.8) return 'success';
    if (ratio >= 0.5) return 'warning';
    return 'danger';
  }
}
