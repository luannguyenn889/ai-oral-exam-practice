import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { AuthService } from '../auth/auth.service';

@Component({
  selector: 'app-instructor-layout',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './instructor-layout.component.html',
  styleUrl: './instructor-layout.component.scss',
})
export class InstructorLayoutComponent {
  authService = inject(AuthService);
}
