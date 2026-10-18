import { Component, Input } from '@angular/core';
import { RouterModule } from '@angular/router';
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
  @Input() items: SidebarItem[] = [];
  @Input() role: UserRole = 'student';
}
