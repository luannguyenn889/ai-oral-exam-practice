import { CommonModule } from '@angular/common';
import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { AuthService } from '../../../core/auth/auth.service';
import { ToastService } from '../../../core/services/toast.service';
import { authErrorMessage } from '../auth-error-message';
import { navigateForRole } from '../auth-navigation';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterModule],
  templateUrl: './login.component.html',
  styleUrl: './login.component.css',
})
export class LoginComponent {
  private readonly formBuilder = inject(FormBuilder);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastService);

  readonly form = this.formBuilder.nonNullable.group({
    email: ['', [Validators.required, Validators.email, Validators.maxLength(320)]],
    password: ['', Validators.required],
  });
  loading = false;

  submit(): void {
    if (this.form.invalid || this.loading) {
      this.form.markAllAsTouched();
      return;
    }

    this.loading = true;
    const { email, password } = this.form.getRawValue();
    this.authService.login({ email: email.trim(), password }).subscribe({
      next: (user) => {
        this.loading = false;
        this.toast.success('Đăng nhập thành công.');
        void navigateForRole(this.router, user.role);
      },
      error: (error: unknown) => {
        this.loading = false;
        this.toast.error(authErrorMessage(error));
      },
    });
  }
}
