import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';

@Component({
  selector: 'app-error-page',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './error-page.component.html',
  styleUrl: './error-page.component.css',
})
export class ErrorPageComponent {
  reload(): void {
    window.location.reload();
  }
}
