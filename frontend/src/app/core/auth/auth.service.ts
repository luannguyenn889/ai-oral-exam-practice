import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { BehaviorSubject, Observable, map } from 'rxjs';
import { User, UserRole } from '../../shared/models';
import { environment } from '../../../environments/environment';

// Khớp với AuthResponse do backend trả về ở /api/auth/login, /api/auth/register và /api/auth/google.
export interface AuthResponse {
  accessToken: string | null;
  tokenType: 'Bearer' | null;
  expiresIn: number;
  needsRoleSelection?: boolean;
  user: {
    id: string | null;
    email: string;
    fullName: string;
    avatarUrl: string | null;
    roles: UserRole[];
  };
}

export type GoogleLoginResult =
  | { success: true; user: User }
  | {
      success: false;
      needsRoleSelection: true;
      email: string;
      fullName: string;
      avatarUrl?: string;
    };


interface RegisterPayload {
  email: string;
  fullName: string;
  password: string;
  role: UserRole;
}

interface LoginPayload {
  email: string;
  password: string;
}

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private readonly USER_STORAGE_KEY = 'oral_exam_user';
  private readonly TOKEN_STORAGE_KEY = 'oral_exam_access_token';
  private readonly http = inject(HttpClient);

  private currentUserSubject = new BehaviorSubject<User | null>(this.loadStoredUser());
  public currentUser$: Observable<User | null> = this.currentUserSubject.asObservable();

  private loadStoredUser(): User | null {
    // Chỉ khôi phục phiên nếu cả user và access token đều còn trong storage.
    const rawUser = localStorage.getItem(this.USER_STORAGE_KEY);
    const accessToken = localStorage.getItem(this.TOKEN_STORAGE_KEY);
    if (!rawUser || !accessToken) return null;

    try {
      return JSON.parse(rawUser) as User;
    } catch {
      localStorage.removeItem(this.USER_STORAGE_KEY);
      localStorage.removeItem(this.TOKEN_STORAGE_KEY);
      return null;
    }
  }

  getCurrentUser(): User | null {
    return this.currentUserSubject.value;
  }

  getRole(): UserRole | null {
    return this.currentUserSubject.value?.role || null;
  }

  isLoggedIn(): boolean {
    return this.currentUserSubject.value !== null && this.getAccessToken() !== null;
  }

  getAccessToken(): string | null {
    return localStorage.getItem(this.TOKEN_STORAGE_KEY);
  }

  login(payload: LoginPayload): Observable<User> {
    return this.http
      .post<AuthResponse>(`${environment.apiBaseUrl}/auth/login`, payload)
      .pipe(mapResponseAndStore(this));
  }

  register(payload: RegisterPayload): Observable<User> {
    return this.http
      .post<AuthResponse>(`${environment.apiBaseUrl}/auth/register`, payload)
      .pipe(mapResponseAndStore(this));
  }

  /**
   * Đăng nhập / Đăng ký nhanh bằng Google ID Token (hỗ trợ chọn vai trò ở lần đầu)
   * Gửi credential lên backend để xác thực với Google và lấy về JWT phiên làm việc của hệ thống.
   * Nếu là lần đầu tiên và chưa có vai trò, trả về needsRoleSelection: true để UI hiển thị màn hình chọn vai trò.
   */
  loginWithGoogle(idToken: string, role?: UserRole): Observable<GoogleLoginResult> {
    return this.http
      .post<AuthResponse>(`${environment.apiBaseUrl}/auth/google`, { idToken, role })
      .pipe(
        map((response) => {
          if (response.needsRoleSelection) {
            return {
              success: false,
              needsRoleSelection: true,
              email: response.user.email,
              fullName: response.user.fullName,
              avatarUrl: response.user.avatarUrl ?? undefined,
            };
          }
          const user = this.storeAuthResponse(response);
          return { success: true, user };
        }),
      );
  }

  // Interceptor dùng hàm này để lưu phiên thành công từ cả hai endpoint auth.
  storeAuthResponse(response: AuthResponse): User {
    if (!response.accessToken) {
      throw new Error('Không nhận được mã xác thực (Access Token) từ máy chủ.');
    }
    const role = response.user.roles[0];
    if (!role || !['student', 'instructor', 'admin'].includes(role)) {
      throw new Error('Backend trả về vai trò người dùng không hợp lệ.');
    }
    const user: User = {
      id: response.user.id || '',
      name: response.user.fullName,
      email: response.user.email,
      role,
      avatarUrl: response.user.avatarUrl ?? undefined,
    };
    localStorage.setItem(this.USER_STORAGE_KEY, JSON.stringify(user));
    localStorage.setItem(this.TOKEN_STORAGE_KEY, response.accessToken);
    this.currentUserSubject.next(user);
    return user;
  }

  logout(): void {
    localStorage.removeItem(this.USER_STORAGE_KEY);
    localStorage.removeItem(this.TOKEN_STORAGE_KEY);
    this.currentUserSubject.next(null);
  }
}

// Tách mapping khỏi hai method để login và register dùng cùng một response contract.
function mapResponseAndStore(authService: AuthService) {
  return map((response: AuthResponse) => authService.storeAuthResponse(response));
}
