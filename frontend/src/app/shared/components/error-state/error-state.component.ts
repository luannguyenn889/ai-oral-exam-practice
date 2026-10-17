import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-error-state',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './error-state.component.html',
  styleUrl: './error-state.component.scss',
})
export class ErrorStateComponent {
  @Input() title = 'Đã xảy ra lỗi';
  @Input() message =
    'Không thể tải dữ liệu vào lúc này. Vui lòng kiểm tra kết nối mạng và thử lại.';
  @Input() retryLabel = 'Thử lại';
  @Output() retry = new EventEmitter<void>();
}
