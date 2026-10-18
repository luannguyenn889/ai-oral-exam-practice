import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { RouterModule } from '@angular/router';
import { AiChatWidgetComponent } from '../ai-chat-widget/ai-chat-widget.component';
import { FooterComponent } from '../footer/footer.component';
import { HeaderComponent } from '../header/header.component';
import { SidebarComponent, SidebarItem } from '../sidebar/sidebar.component';

@Component({
  selector: 'app-admin-layout',
  standalone: true,
  imports: [CommonModule, RouterModule, HeaderComponent, SidebarComponent, FooterComponent, AiChatWidgetComponent],
  templateUrl: './admin-layout.component.html',
  styleUrl: './admin-layout.component.css',
})
export class AdminLayoutComponent {
  readonly role = 'admin' as const;
  readonly navItems: SidebarItem[] = [
    { label: 'Tổng quan', path: '/admin/dashboard', icon: 'dashboard' },
  ];
  readonly footerText = '© 2026 Hệ Thống Ôn Luyện Vấn Đáp AI — Cổng quản trị.';
}
