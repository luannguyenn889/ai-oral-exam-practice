import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-empty-state',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './empty-state.component.html',
  styleUrl: './empty-state.component.scss',
})
export class EmptyStateComponent {
  @Input() icon = 'inbox';
  @Input() title = 'Chưa có dữ liệu';
  @Input() description = 'Hiện tại không có mục nào để hiển thị.';
  @Input() actionLabel?: string;
  @Output() action = new EventEmitter<void>();
}
