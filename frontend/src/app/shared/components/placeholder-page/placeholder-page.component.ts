import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';

@Component({
  selector: 'app-placeholder-page',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './placeholder-page.component.html',
  styleUrl: './placeholder-page.component.css',
})
export class PlaceholderPageComponent {
  @Input() title = 'Trang chức năng';
  @Input() description = 'Chức năng đang được xây dựng theo lộ trình.';
  @Input() icon = 'pending';
}
