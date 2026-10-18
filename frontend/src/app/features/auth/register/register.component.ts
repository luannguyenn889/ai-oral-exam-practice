import { CommonModule } from '@angular/common';
import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { AuthService } from '../../../core/auth/auth.service';
import { ToastService } from '../../../core/services/toast.service';
import { UserRole } from '../../../shared/models';
import { authErrorMessage } from '../auth-error-message';
import { navigateForRole } from '../auth-navigation';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterModule],
  templateUrl: './register.component.html',
  styleUrl: './register.component.css',
})
export class RegisterComponent {
  private readonly formBuilder = inject(FormBuilder);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastService);

  readonly roles: { value: UserRole; label: string }[] = [
    { value: 'student', label: 'Sinh viên' },
    { value: 'instructor', label: 'Giáo viên' },
    { value: 'admin', label: 'Quản trị viên' },
  ];
  readonly form = this.formBuilder.nonNullable.group({
    fullName: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(160)]],
    email: ['', [Validators.required, Validators.email, Validators.maxLength(320)]],
    password: ['', [Validators.required, Validators.minLength(8)]],
    role: this.formBuilder.nonNullable.control<UserRole>('student', Validators.required),
  });
  loading = false;

  submit(): void {
    if (this.form.invalid || this.loading) {
      this.form.markAllAsTouched();
      return;
    }

    const { fullName, email, password, role } = this.form.getRawValue();
    // BCrypt phía backend giới hạn mật khẩu 72 bytes UTF-8.
    if (new TextEncoder().encode(password).length > 72) {
      this.toast.error('Mật khẩu không được vượt quá 72 bytes UTF-8.');
      return;
    }

    this.loading = true;
    this.authService.register({
      fullName: fullName.trim(),
      email: email.trim(),
      password,
      role,
    }).subscribe({
      next: (user) => {
        this.loading = false;
        this.toast.success('Tạo tài khoản thành công.');
        void navigateForRole(this.router, user.role);
      },
      error: (error: unknown) => {
        this.loading = false;
        this.toast.error(authErrorMessage(error));
      },
    });
  }
}
