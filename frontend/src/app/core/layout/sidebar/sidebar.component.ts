import { Component, inject, Input } from '@angular/core';
import { Router, RouterModule } from '@angular/router';
import { UserRole } from '../../../shared/models';

export interface SidebarItem {
  label: string;
  path: string;
  icon: string;
}

@Component({
  selector: 'app-layout-sidebar',
  standalone: true,
  imports: [RouterModule],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.css',
})
export class SidebarComponent {
  private router = inject(Router);
  @Input() items: SidebarItem[] = [];
  @Input() role: UserRole = 'student';

  isItemActive(item: SidebarItem): boolean {
    const cleanUrl = this.router.url.split('?')[0].split('#')[0];

    if (item.path === '/instructor/courses') {
      return cleanUrl === '/instructor/courses';
    }
    if (item.path === '/instructor/documents') {
      return (
        cleanUrl === '/instructor/documents' ||
        /^\/instructor\/courses\/[^/]+\/documents$/i.test(cleanUrl)
      );
    }
    if (item.path === '/instructor/questions') {
      return (
        cleanUrl === '/instructor/questions' ||
        (cleanUrl.startsWith('/instructor/questions/') &&
          cleanUrl !== '/instructor/questions/new')
      );
    }
    if (item.path === '/instructor/questions/new') {
      return cleanUrl === '/instructor/questions/new';
    }
    if (item.path === '/student/courses') {
      return (
        cleanUrl.startsWith('/student/courses') ||
        cleanUrl.startsWith('/student/practice')
      );
    }
    return cleanUrl === item.path || cleanUrl.startsWith(item.path + '/');
  }
}
