import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { AuthService } from '../../../core/auth/auth.service';
import { PracticeApi } from '../../../data-access/api/practice.api';
import { ToastService } from '../../../core/services/toast.service';
import { SkeletonComponent } from '../../../shared/components/skeleton/skeleton.component';

@Component({
  selector: 'app-student-profile',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule, SkeletonComponent],
  templateUrl: './student-profile.component.html',
  styleUrl: './student-profile.component.css',
})
export class StudentProfileComponent implements OnInit {
  private authService = inject(AuthService);
  private practiceApi = inject(PracticeApi);
  private toast = inject(ToastService);

  loading = true;
  savingProfile = false;
  changingPassword = false;

  // Thông tin cá nhân
  email = '';
  fullName = '';
  studentCode = '';
  department = '';
  avatarUrl = '';
  hasPassword = true;
  availableDepartments: string[] = ['Khoa Công nghệ Thông tin'];

  // Đổi mật khẩu
  currentPassword = '';
  newPassword = '';
  confirmPassword = '';
  showCurrentPassword = false;
  showNewPassword = false;
  showConfirmPassword = false;

  get avatarInitials(): string {
    const parts = (this.fullName || this.email || 'SV').trim().split(/\s+/);
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return `${parts[0][0] || ''}${parts[parts.length - 1][0] || ''}`.toUpperCase();
  }

  ngOnInit(): void {
    const cached = this.authService.getCurrentUser();
    if (cached) {
      this.email = cached.email;
      this.fullName = cached.name;
      this.studentCode = cached.studentCode || '';
      this.department = cached.department || '';
      this.avatarUrl = cached.avatarUrl || '';
      this.hasPassword = cached.hasPassword ?? true;
    }

    this.practiceApi.getCourses().subscribe({
      next: (courses) => {
        const set = new Set<string>(['Khoa Công nghệ Thông tin']);
        for (const c of courses || []) {
          const dept = (c.department || '').trim();
          if (dept) set.add(dept);
        }
        this.availableDepartments = Array.from(set).sort((a, b) => a.localeCompare(b, 'vi'));
      },
    });

    this.authService.fetchProfile().subscribe({
      next: (user) => {
        this.email = user.email;
        this.fullName = user.name;
        this.studentCode = user.studentCode || '';
        this.department = user.department || '';
        this.avatarUrl = user.avatarUrl || '';
        this.hasPassword = user.hasPassword ?? true;
        this.loading = false;
      },
      error: () => {
        this.loading = false;
      },
    });
  }

  saveProfile(): void {
    const trimmedName = this.fullName.trim();
    if (trimmedName.length < 2) {
      this.toast.warning('Họ và tên phải có ít nhất 2 ký tự.');
      return;
    }

    this.savingProfile = true;
    this.authService
      .updateProfile({
        fullName: trimmedName,
        studentCode: this.studentCode.trim(),
        department: this.department.trim(),
        avatarUrl: this.avatarUrl.trim(),
      })
      .subscribe({
        next: (user) => {
          this.savingProfile = false;
          this.fullName = user.name;
          this.studentCode = user.studentCode || '';
          this.department = user.department || '';
          this.avatarUrl = user.avatarUrl || '';
          this.toast.success('Đã cập nhật thông tin tài khoản.');
        },
        error: (err) => {
          this.savingProfile = false;
          this.toast.error(err?.error?.message || 'Không thể cập nhật thông tin tài khoản.');
        },
      });
  }

  submitChangePassword(): void {
    if (this.hasPassword && !this.currentPassword) {
      this.toast.warning('Vui lòng nhập mật khẩu hiện tại.');
      return;
    }
    if (!this.newPassword || this.newPassword.length < 8) {
      this.toast.warning('Mật khẩu mới phải có ít nhất 8 ký tự.');
      return;
    }
    if (this.newPassword !== this.confirmPassword) {
      this.toast.warning('Mật khẩu xác nhận không khớp.');
      return;
    }

    this.changingPassword = true;
    this.authService
      .changePassword({
        currentPassword: this.currentPassword,
        newPassword: this.newPassword,
      })
      .subscribe({
        next: (res) => {
          this.changingPassword = false;
          this.hasPassword = res.hasPassword;
          this.currentPassword = '';
          this.newPassword = '';
          this.confirmPassword = '';
          this.toast.success('Đổi mật khẩu thành công.');
        },
        error: (err) => {
          this.changingPassword = false;
          this.toast.error(err?.error?.message || 'Không thể đổi mật khẩu. Vui lòng kiểm tra lại.');
        },
      });
  }
}
