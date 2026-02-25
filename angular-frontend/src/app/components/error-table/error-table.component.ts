import {
  Component, inject, signal, computed
} from '@angular/core';
import { CommonModule }       from '@angular/common';
import { FormsModule }        from '@angular/forms';
import { LogAnalyzerService } from '../../services/log.analyzer.service';
import { ErrorEntry }         from '../../models/log.models';

@Component({
  selector: 'app-error-table',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './error-table.component.html',
  styleUrls: ['./error-table.component.scss']
})
export class ErrorTableComponent {
  private svc: LogAnalyzerService = inject(LogAnalyzerService);

  readonly result   = this.svc.scanResult;
  search            = signal('');
  filterCategory    = signal('all');
  currentPage       = signal(1);
  pageSize          = 50;
  expandedLine      = signal<number | null>(null);

  readonly categories = computed(() => {
    const cats = Object.keys(this.result()?.categories ?? {});
    return ['all', ...cats];
  });

  readonly filtered = computed<ErrorEntry[]>(() => {
    const errors = this.result()?.errors ?? [];
    const q      = this.search().toLowerCase();
    const cat    = this.filterCategory();
    return errors.filter(e =>
      (cat === 'all' || e.category === cat) &&
      (!q || e.content.toLowerCase().includes(q) ||
             String(e.line_number).includes(q) ||
             (e.error_code ?? '').toLowerCase().includes(q))
    );
  });

  readonly paged = computed(() => {
    const start = (this.currentPage() - 1) * this.pageSize;
    return this.filtered().slice(start, start + this.pageSize);
  });

  readonly totalPages = computed(() =>
    Math.ceil(this.filtered().length / this.pageSize)
  );

  onSearch(v: string) { this.search.set(v); this.currentPage.set(1); }
  onFilter(v: string) { this.filterCategory.set(v); this.currentPage.set(1); }
  toggleExpand(ln: number) {
    this.expandedLine.set(this.expandedLine() === ln ? null : ln);
  }

  severityClass(e: ErrorEntry): string {
    if (['Critical Error','Fatal Error','System Panic'].includes(e.matched_pattern)) return 'sev-critical';
    if (['General Error','Exception','HTTP Error'].includes(e.matched_pattern)) return 'sev-error';
    return 'sev-warn';
  }

  categoryBadge(cat: string): string {
    const map: Record<string, string> = {
      database: 'badge-blue', performance: 'badge-amber',
      security: 'badge-red', resource: 'badge-amber',
      network: 'badge-blue', io: 'badge-purple', application: 'badge-green'
    };
    return map[cat] ?? 'badge-green';
  }
}