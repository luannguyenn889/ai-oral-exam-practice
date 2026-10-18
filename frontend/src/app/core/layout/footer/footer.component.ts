import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-layout-footer',
  standalone: true,
  templateUrl: './footer.component.html',
  styleUrl: './footer.component.css',
})
export class FooterComponent {
  @Input() text = '';
}
