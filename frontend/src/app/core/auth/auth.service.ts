import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { BehaviorSubject, Observable, map } from 'rxjs';
import { User, UserRole } from '../../shared/models';
import { environment } from '../../../environments/environment';

// Khớp với AuthResponse do backend trả về ở /api/auth/login và /api/auth/register.
interface AuthResponse {
  accessToken: string;
  tokenType: 'Bearer';
  expiresIn: number;
  user: {
    id: string;
    email: string;
    fullName: string;
    avatarUrl: string | null;
    roles: UserRole[];
  };
}

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

  // Interceptor dùng hàm này để lưu phiên thành công từ cả hai endpoint auth.
  storeAuthResponse(response: AuthResponse): User {
    const role = response.user.roles[0];
    if (!role || !['student', 'instructor', 'admin'].includes(role)) {
      throw new Error('Backend trả về vai trò người dùng không hợp lệ.');
    }
    const user: User = {
      id: response.user.id,
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
