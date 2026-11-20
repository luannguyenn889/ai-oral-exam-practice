import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

export type PageToken = number | '...';

@Component({
  selector: 'app-pagination',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './pagination.component.html',
  styleUrl: './pagination.component.css',
})
export class PaginationComponent {
  @Input() totalItems = 0;
  @Input() currentPage = 1;
  @Input() pageSize = 10;
  @Input() pageSizeOptions: number[] = [5, 10, 20, 50];
  @Input() itemLabel = 'mục';

  @Output() pageChange = new EventEmitter<number>();
  @Output() pageSizeChange = new EventEmitter<number>();

  get totalPages(): number {
    const size = Math.max(1, this.pageSize);
    return Math.max(1, Math.ceil(this.totalItems / size));
  }

  get safePage(): number {
    return Math.min(Math.max(1, this.currentPage), this.totalPages);
  }

  get startItem(): number {
    if (this.totalItems === 0) return 0;
    return (this.safePage - 1) * this.pageSize + 1;
  }

  get endItem(): number {
    return Math.min(this.totalItems, this.safePage * this.pageSize);
  }

  get pageTokens(): PageToken[] {
    const total = this.totalPages;
    const current = this.safePage;

    if (total <= 7) {
      return Array.from({ length: total }, (_, idx) => idx + 1);
    }

    const tokens: PageToken[] = [1];
    let left = Math.max(2, current - 1);
    let right = Math.min(total - 1, current + 1);

    if (current <= 3) {
      left = 2;
      right = 4;
    } else if (current >= total - 2) {
      left = total - 3;
      right = total - 1;
    }

    if (left > 2) {
      tokens.push('...');
    }

    for (let p = left; p <= right; p++) {
      tokens.push(p);
    }

    if (right < total - 1) {
      tokens.push('...');
    }

    tokens.push(total);
    return tokens;
  }

  goToPage(page: number): void {
    const clamped = Math.min(Math.max(1, page), this.totalPages);
    if (clamped !== this.safePage) {
      this.pageChange.emit(clamped);
    }
  }

  onPageSizeSelect(rawSize: number | string): void {
    const parsed = Number(rawSize);
    if (Number.isFinite(parsed) && parsed > 0 && parsed !== this.pageSize) {
      this.pageSizeChange.emit(parsed);
    }
  }
}
