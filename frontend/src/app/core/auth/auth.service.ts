import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';
import { User, UserRole } from '../../shared/models';

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private readonly STORAGE_KEY = 'oral_exam_demo_user';

  private defaultStudent: User = {
    id: 'user-student-1',
    name: 'Nguyễn Văn Sinh Viên',
    email: 'sinhvien@hust.edu.vn',
    role: 'student',
  };

  private defaultInstructor: User = {
    id: 'user-instructor-1',
    name: 'TS. Nguyễn Văn A (Giảng viên)',
    email: 'giangvien@hust.edu.vn',
    role: 'instructor',
  };

  private currentUserSubject = new BehaviorSubject<User | null>(this.loadInitialUser());
  public currentUser$: Observable<User | null> = this.currentUserSubject.asObservable();

  private loadInitialUser(): User | null {
    const raw = localStorage.getItem(this.STORAGE_KEY);
    if (raw) {
      try {
        return JSON.parse(raw);
      } catch {
        return this.defaultStudent;
      }
    }
    return this.defaultStudent; // Mặc định chế độ demo là sinh viên
  }

  getCurrentUser(): User | null {
    return this.currentUserSubject.value;
  }

  getRole(): UserRole | null {
    return this.currentUserSubject.value?.role || null;
  }

  isLoggedIn(): boolean {
    return this.currentUserSubject.value !== null;
  }

  setRole(role: UserRole): void {
    const user = role === 'student' ? this.defaultStudent : this.defaultInstructor;
    localStorage.setItem(this.STORAGE_KEY, JSON.stringify(user));
    this.currentUserSubject.next(user);
  }

  setGoogleDemoUser(profile: { name: string; email: string; avatarUrl?: string }): void {
    const user: User = {
      id: `google-demo-${profile.email.toLowerCase()}`,
      name: profile.name,
      email: profile.email,
      role: 'student',
      avatarUrl: profile.avatarUrl,
    };
    localStorage.setItem(this.STORAGE_KEY, JSON.stringify(user));
    this.currentUserSubject.next(user);
  }

  logout(): void {
    localStorage.removeItem(this.STORAGE_KEY);
    this.currentUserSubject.next(null);
  }
}
