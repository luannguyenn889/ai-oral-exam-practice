import { AfterViewInit, Component, ElementRef, ViewChild, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { ToastService } from '../../core/services/toast.service';
import { UserRole } from '../../shared/models';
import { environment } from '../../../environments/environment';

interface GoogleCredentialResponse {
  credential: string;
}

interface GoogleIdentityServices {
  accounts: {
    id: {
      initialize(options: {
        client_id: string;
        callback: (response: GoogleCredentialResponse) => void;
      }): void;
      renderButton(element: HTMLElement, options: Record<string, string | number>): void;
    };
  };
}

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './login.component.html',
  styleUrl: './login.component.scss',
})
export class LoginComponent implements AfterViewInit {
  @ViewChild('googleButton') private googleButton?: ElementRef<HTMLElement>;

  private authService = inject(AuthService);
  private router = inject(Router);
  private toast = inject(ToastService);

  readonly googleClientId = environment.googleClientId;
  googleLoading = false;

  async ngAfterViewInit(): Promise<void> {
    if (!this.googleClientId || !this.googleButton) return;

    try {
      await this.loadGoogleIdentityServices();
      const google = (window as Window & { google?: GoogleIdentityServices }).google;
      if (!google) throw new Error('Google Identity Services chưa sẵn sàng.');

      google.accounts.id.initialize({
        client_id: this.googleClientId,
        callback: (response) => this.handleGoogleCredential(response),
      });
      google.accounts.id.renderButton(this.googleButton.nativeElement, {
        type: 'standard',
        theme: 'outline',
        size: 'large',
        text: 'continue_with',
        shape: 'rectangular',
        width: 360,
        logo_alignment: 'left',
      });
    } catch {
      this.toast.error('Không tải được dịch vụ đăng nhập Google. Vui lòng thử lại.');
    }
  }

  selectRole(role: UserRole): void {
    this.authService.setRole(role);
    this.toast.success(
      `Đã đăng nhập với vai trò ${role === 'student' ? 'Sinh viên' : 'Giảng viên'}`,
    );
    if (role === 'student') {
      this.router.navigate(['/student/dashboard']);
    } else {
      this.router.navigate(['/instructor/questions']);
    }
  }

  private handleGoogleCredential(response: GoogleCredentialResponse): void {
    try {
      const profile = this.readGoogleProfile(response.credential);
      if (!profile.email || !profile.email_verified) {
        throw new Error('Tài khoản Google chưa xác minh email.');
      }

      this.authService.setGoogleDemoUser({
        name: profile.name || profile.email,
        email: profile.email,
        avatarUrl: profile.picture,
      });
      this.toast.success(`Đăng nhập demo thành công với ${profile.email}`);
      this.router.navigate(['/student/dashboard']);
    } catch {
      this.toast.error('Không đọc được thông tin tài khoản Google. Vui lòng thử lại.');
    }
  }

  private readGoogleProfile(credential: string): {
    name?: string;
    email?: string;
    email_verified?: boolean;
    picture?: string;
  } {
    const payload = credential.split('.')[1];
    if (!payload) throw new Error('Google credential không hợp lệ.');

    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/');
    const binary = atob(base64.padEnd(Math.ceil(base64.length / 4) * 4, '='));
    const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
    return JSON.parse(new TextDecoder().decode(bytes));
  }

  private loadGoogleIdentityServices(): Promise<void> {
    const existingScript = document.querySelector<HTMLScriptElement>(
      'script[src="https://accounts.google.com/gsi/client"]',
    );
    const google = (window as Window & { google?: GoogleIdentityServices }).google;
    if (google) return Promise.resolve();

    return new Promise((resolve, reject) => {
      const script = existingScript ?? document.createElement('script');
      script.src = 'https://accounts.google.com/gsi/client';
      script.async = true;
      script.defer = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error('Không tải được Google Identity Services.'));
      if (!existingScript) document.head.appendChild(script);
    });
  }
}
