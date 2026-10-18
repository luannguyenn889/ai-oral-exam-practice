import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-skeleton',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './skeleton.component.html',
  styleUrl: './skeleton.component.css',
})
export class SkeletonComponent {
  @Input() variant: 'text' | 'title' | 'avatar' | 'card' | 'button' = 'text';
  @Input() width?: string;
  @Input() height?: string;
  @Input() radius?: string;
}
