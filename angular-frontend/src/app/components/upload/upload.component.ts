import {
  Component, Output, EventEmitter, signal, inject
} from '@angular/core';
import { CommonModule }     from '@angular/common';
import { LogAnalyzerService } from '../../services/log.analyzer.service';
import { ScanResult }        from '../../models/log.models';

@Component({
  selector: 'app-upload',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './upload.component.html',
  styleUrls: ['./upload.component.scss']
})
export class UploadComponent {
  @Output() uploaded = new EventEmitter<ScanResult>();

  private svc: LogAnalyzerService = inject(LogAnalyzerService);

  isDragging = signal(false);
  error      = signal<string | null>(null);
  file       = signal<File | null>(null);

  readonly isUploading = this.svc.isUploading;

  onDragOver(e: DragEvent) {
    e.preventDefault();
    this.isDragging.set(true);
  }

  onDragLeave() { this.isDragging.set(false); }

  onDrop(e: DragEvent) {
    e.preventDefault();
    this.isDragging.set(false);
    const f = e.dataTransfer?.files[0];
    if (f) this.processFile(f);
  }

  onFileInput(e: Event) {
    const f = (e.target as HTMLInputElement).files?.[0];
    if (f) this.processFile(f);
  }

  private processFile(f: File) {
    this.error.set(null);
    this.file.set(f);
  }

  upload() {
    const f = this.file();
    if (!f) return;
    this.svc.upload(f).subscribe({
      next : r => this.uploaded.emit(r),
      error: e => {
        this.error.set(e?.error?.detail ?? 'Upload failed. Is the server running?');
        this.svc.isUploading.set(false);
      }
    });
  }

  formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
}