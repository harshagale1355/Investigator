import {
  Component, inject, signal, ElementRef, ViewChild, AfterViewChecked
} from '@angular/core';
import { CommonModule }       from '@angular/common';
import { FormsModule }        from '@angular/forms';
import { LogAnalyzerService } from '../../services/log.analyzer.service';
import { ChatMessage }        from '../../models/log.models';

const SUGGESTIONS = [
  'What are the most frequent errors?',
  'Are there any security-related issues?',
  'Summarize the database errors.',
  'What caused the timeouts?',
  'Is there any evidence of memory issues?',
];

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './chat.component.html',
  styleUrls: ['./chat.component.scss']
})
export class ChatComponent implements AfterViewChecked {
  @ViewChild('messageList') private messageList!: ElementRef;

  private svc: LogAnalyzerService = inject(LogAnalyzerService);

  readonly messages   = this.svc.chatHistory;
  readonly isQuerying = this.svc.isQuerying;
  readonly isReady    = this.svc.isReady;
  readonly ragStatus  = this.svc.ragStatus;

  input       = signal('');
  suggestions = SUGGESTIONS;
  private didScroll = false;

  ngAfterViewChecked() {
    if (!this.didScroll && this.messages().length) {
      this.scrollBottom();
      this.didScroll = true;
    }
  }

  send(q?: string) {
    const question = q ?? this.input().trim();
    if (!question || this.isQuerying() || !this.isReady()) return;
    this.input.set('');
    this.didScroll = false;
    this.svc.query(question).subscribe({
      next: () => { this.didScroll = false; },
      error: (err: { error?: { detail?: string } }) => {
        this.svc.chatHistory.update((h: ChatMessage[]) => [
          ...h,
          {
            role: 'assistant' as const,
            text: `⚠ Error: ${err?.error?.detail ?? 'Request failed'}`,
            timestamp: new Date()
          }
        ]);
        this.svc.isQuerying.set(false);
      }
    });
  }

  onKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      this.send();
    }
  }

  private scrollBottom() {
    try {
      this.messageList.nativeElement.scrollTop =
        this.messageList.nativeElement.scrollHeight;
    } catch {}
  }

  formatTime(d: Date): string {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
}