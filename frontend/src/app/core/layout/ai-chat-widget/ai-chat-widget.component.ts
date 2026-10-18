import { Component } from '@angular/core';

@Component({
  selector: 'app-ai-chat-widget',
  standalone: true,
  templateUrl: './ai-chat-widget.component.html',
  styleUrl: './ai-chat-widget.component.css',
})
export class AiChatWidgetComponent {
  isOpen = false;

  toggle(): void {
    this.isOpen = !this.isOpen;
  }
}
