import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

export interface ToastMessage {
  id: string;
  type: 'success' | 'warning' | 'danger' | 'info';
  message: string;
  duration?: number;
}

@Injectable({
  providedIn: 'root',
})
export class ToastService {
  private toastsSubject = new BehaviorSubject<ToastMessage[]>([]);
  public toasts$: Observable<ToastMessage[]> = this.toastsSubject.asObservable();

  show(type: 'success' | 'warning' | 'danger' | 'info', message: string, duration?: number): void {
    const defaultDuration = type === 'danger' ? 7000 : type === 'warning' ? 5000 : 3000;
    const finalDuration = duration !== undefined ? duration : defaultDuration;

    const current = this.toastsSubject.value;
    // Tối đa 3 toast hiển thị cùng lúc theo mục 7 QUY_TAC_THIET_KE_FE.md
    const id = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`;
    const newToast: ToastMessage = { id, type, message, duration: finalDuration };

    const updated = [newToast, ...current].slice(0, 3);
    this.toastsSubject.next(updated);

    if (finalDuration > 0) {
      setTimeout(() => {
        this.dismiss(id);
      }, finalDuration);
    }
  }

  success(message: string, duration?: number): void {
    this.show('success', message, duration);
  }

  warning(message: string, duration?: number): void {
    this.show('warning', message, duration);
  }

  error(message: string, duration?: number): void {
    this.show('danger', message, duration);
  }

  info(message: string, duration?: number): void {
    this.show('info', message, duration);
  }

  dismiss(id: string): void {
    const current = this.toastsSubject.value;
    this.toastsSubject.next(current.filter((t) => t.id !== id));
  }
}
