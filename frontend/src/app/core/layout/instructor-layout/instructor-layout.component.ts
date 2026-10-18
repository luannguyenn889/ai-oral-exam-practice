import { Component } from '@angular/core';
import { RouterModule } from '@angular/router';
import { AiChatWidgetComponent } from '../ai-chat-widget/ai-chat-widget.component';
import { FooterComponent } from '../footer/footer.component';
import { HeaderComponent } from '../header/header.component';
import { SidebarComponent, SidebarItem } from '../sidebar/sidebar.component';

@Component({
  selector: 'app-instructor-layout',
  standalone: true,
  imports: [RouterModule, HeaderComponent, SidebarComponent, FooterComponent, AiChatWidgetComponent],
  templateUrl: './instructor-layout.component.html',
  styleUrl: './instructor-layout.component.css',
})
export class InstructorLayoutComponent {
  readonly role = 'instructor' as const;
  readonly navItems: SidebarItem[] = [
    { label: 'Học phần', path: '/instructor/courses', icon: 'class' },
    { label: 'Danh sách câu hỏi', path: '/instructor/questions', icon: 'quiz' },
    { label: 'Tạo câu hỏi', path: '/instructor/questions/new', icon: 'add_circle' },
  ];
  readonly footerText = '© 2026 Cổng thông tin Giảng viên — Hệ Thống Ôn Luyện Vấn Đáp AI.';
}
