import {
  Component, OnInit, inject, signal
} from '@angular/core';
import { CommonModule }           from '@angular/common';
import { LogAnalyzerService }     from './services/log.analyzer.service';
import { UploadComponent }        from './components/upload/upload.component';
import { StatsPanelComponent }    from './components/stats-panel/stats-panel.component';
import { ErrorTableComponent }    from './components/error-table/error-table.component';
import { ChatComponent }          from './components/chat/chat.component';
import { ScanResult }             from './models/log.models';

type Tab = 'stats' | 'errors' | 'chat';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    UploadComponent,
    StatsPanelComponent,
    ErrorTableComponent,
    ChatComponent,
  ],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss']
})
export class AppComponent implements OnInit {
  svc: LogAnalyzerService = inject(LogAnalyzerService);

  activeTab = signal<Tab>('stats');

  readonly result  = this.svc.scanResult;
  readonly isReady = this.svc.isReady;

  ngOnInit() {
    this.svc.checkStatus().subscribe();
  }

  onUploaded(r: ScanResult) {
    // Switch to stats tab after upload
    this.activeTab.set('stats');
  }

  setTab(t: Tab) { this.activeTab.set(t); }
}