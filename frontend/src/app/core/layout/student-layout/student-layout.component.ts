import { Component } from '@angular/core';
import { RouterModule } from '@angular/router';
import { AiChatWidgetComponent } from '../ai-chat-widget/ai-chat-widget.component';
import { FooterComponent } from '../footer/footer.component';
import { HeaderComponent } from '../header/header.component';
import { SidebarComponent, SidebarItem } from '../sidebar/sidebar.component';

@Component({
  selector: 'app-student-layout',
  standalone: true,
  imports: [RouterModule, HeaderComponent, SidebarComponent, FooterComponent, AiChatWidgetComponent],
  templateUrl: './student-layout.component.html',
  styleUrl: './student-layout.component.css',
})
export class StudentLayoutComponent {
  readonly role = 'student' as const;
  readonly navItems: SidebarItem[] = [
    { label: 'Tổng quan', path: '/student/dashboard', icon: 'dashboard' },
    { label: 'Học phần & Câu hỏi', path: '/student/courses', icon: 'menu_book' },
    { label: 'Lịch sử luyện tập', path: '/student/history', icon: 'history' },
  ];
  readonly footerText = '© 2026 Hệ Thống Ôn Luyện Vấn Đáp Tích Hợp AI. Sản phẩm phục vụ Đồ án NCKH.';
}
