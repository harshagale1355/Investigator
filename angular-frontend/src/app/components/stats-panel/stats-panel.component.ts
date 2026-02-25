import { Component, inject } from '@angular/core';
import { CommonModule }       from '@angular/common';
import { LogAnalyzerService } from '../../services/log.analyzer.service';

@Component({
  selector: 'app-stats-panel',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './stats-panel.component.html',
  styleUrls: ['./stats-panel.component.scss']
})
export class StatsPanelComponent {
  svc: LogAnalyzerService = inject(LogAnalyzerService);

  readonly result     = this.svc.scanResult;
  readonly errorRate  = this.svc.errorRate;
  readonly topCategory= this.svc.topCategory;

  categoryEntries() {
    const cats = this.result()?.categories ?? {};
    return Object.entries(cats).sort((a, b) => b[1] - a[1]);
  }

  topPatterns() {
    const pm = this.result()?.pattern_matches ?? {};
    return Object.entries(pm).sort((a, b) => b[1] - a[1]).slice(0, 5);
  }

  categoryColor(cat: string): string {
    const map: Record<string, string> = {
      database: 'blue', performance: 'amber', security: 'red',
      resource: 'amber', network: 'blue', io: 'purple', application: 'green'
    };
    return map[cat] ?? 'green';
  }
}