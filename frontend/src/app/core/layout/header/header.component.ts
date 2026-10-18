import { CommonModule } from '@angular/common';
import { Component, Input, inject } from '@angular/core';
import { RouterModule } from '@angular/router';
import { AuthService } from '../../auth/auth.service';
import { UserRole } from '../../../shared/models';

@Component({
  selector: 'app-layout-header',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './header.component.html',
  styleUrl: './header.component.css',
})
export class HeaderComponent {
  @Input() title = '';
  @Input() icon = 'school';
  @Input() roleLabel = '';
  @Input() role: UserRole = 'student';

  readonly authService = inject(AuthService);
}
