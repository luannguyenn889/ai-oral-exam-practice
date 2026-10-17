import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PracticeStatus } from '../../models';

@Component({
  selector: 'app-status-badge',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './status-badge.component.html',
  styleUrl: './status-badge.component.scss',
})
export class StatusBadgeComponent {
  @Input({ required: true }) status!: PracticeStatus;

  get colorVariant(): 'success' | 'warning' | 'danger' | 'info' | 'muted' {
    switch (this.status) {
      case 'completed':
        return 'success';
      case 'transcribing':
      case 'grading':
      case 'uploaded':
        return 'info';
      case 'transcript_review':
        return 'warning';
      case 'recording':
      case 'transcription_failed':
      case 'grading_failed':
        return 'danger';
      case 'cancelled':
      case 'draft':
      default:
        return 'muted';
    }
  }

  get isPulse(): boolean {
    return (
      this.status === 'recording' || this.status === 'transcribing' || this.status === 'grading'
    );
  }

  get iconName(): string | null {
    switch (this.status) {
      case 'completed':
        return 'check';
      case 'recording':
        return 'mic';
      case 'transcription_failed':
      case 'grading_failed':
        return 'error';
      default:
        return null;
    }
  }

  get statusLabel(): string {
    switch (this.status) {
      case 'draft':
        return 'Bản nháp';
      case 'recording':
        return 'Đang ghi âm';
      case 'uploaded':
        return 'Đã tải audio';
      case 'transcribing':
        return 'Đang chuyển lời';
      case 'transcript_review':
        return 'Chờ xác nhận';
      case 'grading':
        return 'Đang chấm điểm';
      case 'completed':
        return 'Hoàn thành';
      case 'transcription_failed':
        return 'Lỗi chuyển lời';
      case 'grading_failed':
        return 'Lỗi chấm điểm';
      case 'cancelled':
        return 'Đã hủy';
      default:
        return this.status;
    }
  }
}
