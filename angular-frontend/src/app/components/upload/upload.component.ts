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
  
  // Add constant for max file size
  private readonly MAX_FILE_SIZE_MB = 100;
  private readonly MAX_FILE_SIZE_BYTES = this.MAX_FILE_SIZE_MB * 1024 * 1024;

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
    
    // Check file size before setting the file
    const sizeError = this.checkSize(f.size);
    if (sizeError) {
      this.error.set(sizeError);
      this.file.set(null);
      return;
    }
    
    this.file.set(f);
  }

  upload() {
    const f = this.file();
    if (!f) return;
    
    // Double-check size before upload (in case file was modified elsewhere)
    const sizeError = this.checkSize(f.size);
    if (sizeError) {
      this.error.set(sizeError);
      this.file.set(null);
      return;
    }
    
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
  
  // Renamed to checkSize for consistency
  checkSize(bytes: number): string | null {
    const sizeInMB = bytes / (1024 * 1024);
    if (sizeInMB > this.MAX_FILE_SIZE_MB) {
      return `Cannot upload file larger than ${this.MAX_FILE_SIZE_MB}MB (current file: ${sizeInMB.toFixed(2)}MB)`;
    }
    return null;
  }
}