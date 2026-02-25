import { Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap, interval, switchMap, takeWhile, startWith } from 'rxjs';
import {
  ScanResult, QueryResponse, StatusResponse,
  PatternsResponse, ChatMessage
} from '../models/log.models';

export type RagStatus = 'idle' | 'building' | 'ready' | 'error';

@Injectable({ providedIn: 'root' })
export class LogAnalyzerService {
  private readonly API = 'http://localhost:8000';

  readonly scanResult  = signal<ScanResult | null>(null);
  readonly isUploading = signal(false);
  readonly isQuerying  = signal(false);
  readonly ragStatus   = signal<RagStatus>('idle');
  readonly currentFile = signal<string | null>(null);
  readonly chatHistory = signal<ChatMessage[]>([]);

  // Derived
  readonly isReady = computed(() => this.ragStatus() === 'ready');

  readonly errorRate = computed(() => {
    const r = this.scanResult();
    if (!r || r.total_lines === 0) return 0;
    return ((r.error_count / r.total_lines) * 100).toFixed(2);
  });

  readonly topCategory = computed(() => {
    const r = this.scanResult();
    if (!r) return null;
    const cats = Object.entries(r.categories);
    if (!cats.length) return null;
    return cats.sort((a, b) => b[1] - a[1])[0][0];
  });

  constructor(private http: HttpClient) {}

  getPatterns(): Observable<PatternsResponse> {
    return this.http.get<PatternsResponse>(`${this.API}/patterns`);
  }

  checkStatus(): Observable<StatusResponse> {
    return this.http.get<StatusResponse>(`${this.API}/status`).pipe(
      tap(s => {
        if (s.ready) this.ragStatus.set('ready');
        this.currentFile.set(s.filename);
      })
    );
  }

  /** Upload file → get scan results immediately, then poll for RAG readiness */
  upload(file: File): Observable<ScanResult> {
    const fd = new FormData();
    fd.append('file', file);
    this.isUploading.set(true);
    this.ragStatus.set('idle');

    return this.http.post<ScanResult>(`${this.API}/upload`, fd).pipe(
      tap(result => {
        this.scanResult.set(result);
        this.currentFile.set(result.filename ?? file.name);
        this.isUploading.set(false);
        this.ragStatus.set('building');
        this.chatHistory.set([]);
        this._pollRagStatus();   // start polling in background
      })
    );
  }

  /** Poll /rag-status every 3 s until ready or error */
  private _pollRagStatus(): void {
    interval(3000).pipe(
      startWith(0),
      switchMap(() => this.http.get<{ status: RagStatus }>(`${this.API}/rag-status`)),
      tap(r => this.ragStatus.set(r.status)),
      takeWhile(r => r.status === 'building', true)
    ).subscribe();
  }

  query(question: string): Observable<QueryResponse> {
    this.isQuerying.set(true);
    this.chatHistory.update((h: ChatMessage[]) => [
      ...h, { role: 'user', text: question, timestamp: new Date() }
    ]);
    return this.http.post<QueryResponse>(`${this.API}/query`, { question }).pipe(
      tap(res => {
        this.chatHistory.update((h: ChatMessage[]) => [
          ...h, { role: 'assistant', text: res.answer, timestamp: new Date() }
        ]);
        this.isQuerying.set(false);
      })
    );
  }
}