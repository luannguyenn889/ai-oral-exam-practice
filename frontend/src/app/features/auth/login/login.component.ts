import { CommonModule } from '@angular/common';
import {
  AfterViewInit,
  ChangeDetectorRef,
  Component,
  ElementRef,
  inject,
  NgZone,
  ViewChild,
} from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { environment } from '../../../../environments/environment';
import { AuthService } from '../../../core/auth/auth.service';
import { ToastService } from '../../../core/services/toast.service';
import { UserRole } from '../../../shared/models';
import { authErrorMessage } from '../auth-error-message';
import { navigateForRole } from '../auth-navigation';

// Khai báo kiểu dữ liệu cho thư viện Google Identity Services (GIS) được nạp từ script gsi/client
declare const google: {
  accounts: {
    id: {
      initialize: (config: {
        client_id: string;
        callback: (response: { credential: string }) => void;
      }) => void;
      renderButton: (
        parent: HTMLElement,
        options: {
          theme?: 'outline' | 'filled_blue' | 'filled_black';
          size?: 'large' | 'medium' | 'small';
          text?: 'signin_with' | 'signup_with' | 'continue_with' | 'signin';
          shape?: 'rectangular' | 'pill' | 'circle' | 'square';
          width?: number | string;
          locale?: string;
        },
      ) => void;
    };
  };
};

// Thông tin tài khoản Google chờ người dùng chọn vai trò ở lần đầu đăng nhập
export interface PendingGoogleUser {
  idToken: string;
  email: string;
  fullName: string;
  avatarUrl?: string;
}

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterModule],
  templateUrl: './login.component.html',
  styleUrl: './login.component.css',
})
export class LoginComponent implements AfterViewInit {
  // Tham chiếu đến thẻ div chứa nút đăng nhập Google trên template HTML
  @ViewChild('googleBtnRef') googleBtnRef?: ElementRef<HTMLDivElement>;

  private readonly formBuilder = inject(FormBuilder);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastService);
  private readonly ngZone = inject(NgZone);
  private readonly cdr = inject(ChangeDetectorRef);

  // Trạng thái tài khoản Google đang chờ hoàn tất chọn vai trò
  pendingGoogleUser: PendingGoogleUser | null = null;
  // Vai trò được chọn mặc định là Sinh viên ('student')
  selectedRole: UserRole = 'student';

  // Form đăng nhập truyền thống bằng email và mật khẩu
  readonly form = this.formBuilder.nonNullable.group({
    email: ['', [Validators.required, Validators.email, Validators.maxLength(320)]],
    password: ['', Validators.required],
  });
  loading = false;

  ngAfterViewInit(): void {
    // Khởi tạo nút đăng nhập Google sau khi giao diện đã render xong DOM
    this.initGoogleSignIn();
  }

  /**
   * Khởi tạo Google Identity Services SDK và render nút Google Sign-In chuẩn.
   * Sử dụng cơ chế thử lại (retry) trong trường hợp script Google tải bất đồng bộ chậm hơn DOM.
   */
  private initGoogleSignIn(): void {
    const clientId = environment.googleClientId;
    if (!clientId) return;

    let attempts = 0;
    const maxAttempts = 25; // Tối đa 25 lần x 200ms = 5 giây chờ SDK sẵn sàng

    const tryRender = () => {
      attempts++;
      if (typeof google !== 'undefined' && google.accounts?.id && this.googleBtnRef?.nativeElement) {
        // 1. Cấu hình Client ID và hàm callback nhận kết quả từ Google
        google.accounts.id.initialize({
          client_id: clientId,
          callback: (response: { credential: string }) => {
            // Callback của Google SDK được gọi từ iframe bên ngoài Angular Zone.
            // Phải dùng ngZone.run() để Angular nhận biết sự kiện và kích hoạt Change Detection.
            this.ngZone.run(() => {
              this.handleGoogleLogin(response.credential);
            });
          },
        });

        // 2. Render nút bấm chính hãng của Google vào thẻ div mục tiêu
        google.accounts.id.renderButton(this.googleBtnRef.nativeElement, {
          theme: 'outline',
          size: 'large',
          text: 'signin_with',
          shape: 'rectangular',
          width: 386,
          locale: 'vi', // Hiển thị tiếng Việt: "Đăng nhập bằng Google"
        });
      } else if (attempts < maxAttempts) {
        setTimeout(tryRender, 200);
      }
    };

    tryRender();
  }

  /**
   * Xử lý gửi Google ID Token lên backend để xác thực.
   * - Nếu tài khoản đã tồn tại: đăng nhập thành công và chuyển hướng ngay.
   * - Nếu là lần đầu đăng nhập: nhận needsRoleSelection = true và hiển thị bước chọn vai trò.
   */
  private handleGoogleLogin(credential: string): void {
    if (this.loading) return;

    this.loading = true;
    this.cdr.markForCheck();

    this.authService.loginWithGoogle(credential).subscribe({
      next: (result) => {
        this.loading = false;
        if (!result.success) {
          // Lần đầu đăng nhập bằng Google: hiển thị giao diện chọn vai trò
          this.pendingGoogleUser = {
            idToken: credential,
            email: result.email,
            fullName: result.fullName,
            avatarUrl: result.avatarUrl,
          };
          this.selectedRole = 'student';
        } else {
          this.toast.success('Đăng nhập Google thành công.');
          // Điều hướng người dùng về đúng layout theo vai trò (Sinh viên, Giảng viên hoặc Quản trị viên)
          void navigateForRole(this.router, result.user.role);
        }
        this.cdr.markForCheck();
      },
      error: (error: unknown) => {
        this.loading = false;
        this.toast.error(authErrorMessage(error));
        this.cdr.markForCheck();
      },
    });
  }

  /**
   * Thay đổi vai trò muốn đăng ký khi đăng nhập Google lần đầu
   */
  selectRole(role: UserRole): void {
    this.selectedRole = role;
    this.cdr.markForCheck();
  }

  /**
   * Xác nhận vai trò đã chọn và hoàn tất đăng nhập/tạo tài khoản với Google
   */
  confirmRole(): void {
    if (!this.pendingGoogleUser || !this.selectedRole || this.loading) return;

    this.loading = true;
    this.cdr.markForCheck();

    this.authService.loginWithGoogle(this.pendingGoogleUser.idToken, this.selectedRole).subscribe({
      next: (result) => {
        this.loading = false;
        if (result.success) {
          const roleLabel = this.selectedRole === 'instructor' ? 'Giảng viên' : 'Sinh viên';
          this.toast.success(`Đăng nhập Google thành công với vai trò ${roleLabel}.`);
          void navigateForRole(this.router, result.user.role);
        }
        this.cdr.markForCheck();
      },
      error: (error: unknown) => {
        this.loading = false;
        this.toast.error(authErrorMessage(error));
        this.cdr.markForCheck();
      },
    });
  }

  /**
   * Hủy bỏ quá trình chọn vai trò Google và quay về màn hình đăng nhập bình thường
   */
  cancelGoogleLogin(): void {
    this.pendingGoogleUser = null;
    this.selectedRole = 'student';
    this.cdr.markForCheck();
    // Sau khi DOM chuyển về khối @else, thẻ #googleBtnRef xuất hiện lại nên cần render lại nút Google
    setTimeout(() => {
      this.initGoogleSignIn();
      this.cdr.markForCheck();
    }, 100);
  }

  /**
   * Xử lý đăng nhập truyền thống bằng email và mật khẩu
   */
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

