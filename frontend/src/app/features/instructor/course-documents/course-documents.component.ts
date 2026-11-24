import { Component, inject, OnInit, OnDestroy, NgZone } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import {
  AiRagService,
  ChunkingStrategyOption,
  EmbeddingProviderOption,
} from '../../../core/services/ai-rag.service';
import { PracticeApi } from '../../../data-access/api/practice.api';
import { ToastService } from '../../../core/services/toast.service';
import { AuthService } from '../../../core/auth/auth.service';
import { Course, RagStatus, RagChunkResult } from '../../../shared/models';
import { SkeletonComponent } from '../../../shared/components/skeleton/skeleton.component';
import { ErrorStateComponent } from '../../../shared/components/error-state/error-state.component';
import { environment } from '../../../../environments/environment';

// Khai báo các biến toàn cục của Google
declare const google: any;
declare const gapi: any;

export type StagedFileStatus = 'pending' | 'uploading' | 'processing' | 'done' | 'error';

export interface StagedUploadItem {
  file: File;
  status: StagedFileStatus;
  uploadPercent: number;
  addedChunks?: number;
  errorMessage?: string;
}

@Component({
  selector: 'app-course-documents',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule, SkeletonComponent, ErrorStateComponent],
  templateUrl: './course-documents.component.html',
  styleUrl: './course-documents.component.css',
})
export class CourseDocumentsComponent implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private aiRagService = inject(AiRagService);
  private practiceApi = inject(PracticeApi);
  private toast = inject(ToastService);
  private http = inject(HttpClient);
  private ngZone = inject(NgZone);
  private authService = inject(AuthService);

  courseId = '';
  courses: Course[] = [];
  course: Course | null = null;
  loading = true;
  error: string | null = null;
  ragStatus: RagStatus | null = null;
  isSyncing = false;
  syncElapsedSeconds = 0;
  private syncTimerId: ReturnType<typeof setInterval> | null = null;
  activeSyncJobId: string | null = null;
  syncPercent = 0;
  syncMessage = '';
  syncCurrentFile = '';
  syncProcessedChunks = 0;
  syncTotalChunks = 0;
  private syncPollTimerId: ReturnType<typeof setInterval> | null = null;
  stagedFiles: StagedUploadItem[] = [];
  uploadingProgressText = '';
  isUploadingLocal = false;
  activeUploadPhase: 'uploading' | 'processing' = 'uploading';
  activeUploadPercent = 0;
  uploadElapsedSeconds = 0;
  private uploadTimerId: ReturnType<typeof setInterval> | null = null;
  isDragging = false;
  googleAccessToken: string | null = null;

  // Trạng thái đọc & xóa file trực tiếp tại Server
  previewingFile: string | null = null;
  previewLoading = false;
  previewContent = '';
  previewTotalChars = 0;
  deletingFile: string | null = null;

  // Test Search state
  embeddingProvider: EmbeddingProviderOption = 'local';
  chunkingStrategy: ChunkingStrategyOption = 'recursive';
  searchQuery = 'Dạ thưa thầy...';
  searchMode: 'hybrid' | 'dense' | 'bm25' = 'hybrid';
  topK = 3;
  searching = false;
  cleanedQuery = '';
  searchResults: RagChunkResult[] = [];
  // Trạng thái hiển thị danh sách kết quả RAG
  showResults = true;

  get ragCourseCode(): string {
    return (this.course?.code || this.courseId || '').trim().toUpperCase();
  }

  ngOnInit(): void {
    this.route.paramMap.subscribe((params) => {
      this.stopPollingSyncJob();
      this.stopSyncTimer();
      this.isSyncing = false;
      this.courseId = params.get('courseId') || '';
      this.stagedFiles = [];
      this.uploadingProgressText = '';
      this.closeFilePreview();
      this.searchResults = [];
      this.cleanedQuery = '';
      this.loadCourseInfoAndRag();
    });
  }

  ngOnDestroy(): void {
    this.stopUploadTimer();
    this.stopSyncTimer();
    this.stopPollingSyncJob();
  }

  onCourseSelect(courseCode: string): void {
    if (this.isUploadingLocal) return;
    const trimmed = (courseCode || '').trim();
    if (!trimmed) {
      this.router.navigate(['/instructor/documents']);
      return;
    }
    this.router.navigate(['/instructor/courses', trimmed, 'documents']);
  }

  loadCourseInfoAndRag(): void {
    this.loading = true;
    this.error = null;
    const isAdmin = this.authService.getRole() === 'admin';
    this.practiceApi.getCourses(!isAdmin).subscribe({
      next: (courses) => {
        this.courses = courses || [];
        if (!this.courseId) {
          this.course = null;
          this.ragStatus = null;
          this.loading = false;
          return;
        }
        const paramLower = this.courseId.trim().toLowerCase();
        this.course =
          this.courses.find(
            (c) => c.id.toLowerCase() === paramLower || c.code.toLowerCase() === paramLower,
          ) || null;

        if (this.course) {
          this.aiRagService
            .syncCourseFolder(this.ragCourseCode, undefined, this.course.id)
            .subscribe({
              next: () => this.loadRagStatus(),
              error: () => this.loadRagStatus(),
            });
        } else {
          this.loadRagStatus();
        }
      },
      error: () => {
        if (!this.courseId) {
          this.courses = [];
          this.course = null;
          this.ragStatus = null;
          this.loading = false;
        } else {
          this.loadRagStatus();
        }
      },
    });
  }

  onEmbeddingProviderChange(): void {
    if (this.isUploadingLocal) return;
    this.searchResults = [];
    this.cleanedQuery = '';
    if (this.ragCourseCode) {
      this.loadRagStatus(true);
      this.checkActiveSyncJob();
    }
  }

  onChunkingStrategyChange(): void {
    if (this.isUploadingLocal) return;
    const labels: Record<ChunkingStrategyOption, string> = {
      recursive: 'Recursive theo tiêu đề & câu (Mặc định)',
      semantic: 'Semantic theo ngữ nghĩa (Embedding)',
      legacy: 'Boundary 600 ký tự (Cách cũ)',
    };
    this.toast.info(
      `Đã chọn chiến lược cắt đoạn: ${labels[this.chunkingStrategy]}. Bấm "Đồng bộ chỉ mục Server" nếu muốn lập chỉ mục lại các file hiện có.`,
    );
  }

  loadRagStatus(silent = false): void {
    if (!this.ragCourseCode) {
      this.ragStatus = null;
      this.loading = false;
      return;
    }
    if (!silent || !this.ragStatus) {
      this.loading = true;
    }
    this.error = null;
    this.aiRagService.getRagStatus(this.ragCourseCode, this.embeddingProvider).subscribe({
      next: (status) => {
        this.ragStatus = status;
        this.loading = false;
        this.checkActiveSyncJob();
      },
      error: () => { this.error = 'Chưa kết nối được với AI Service.'; this.loading = false; },
    });
  }

  connectGoogleDrive(): void {
    const client = google.accounts.oauth2.initTokenClient({
      client_id: environment.googleDriveClientId,
      scope: 'https://www.googleapis.com/auth/drive.readonly',
      callback: (tokenResponse: any) => {
        this.ngZone.run(() => {
          if (tokenResponse.access_token) {
            this.googleAccessToken = tokenResponse.access_token;
            this.toast.success('Đã kết nối Google Drive!');
          }
        });
      },
    });
    client.requestAccessToken();
  }

  openGooglePicker(): void {
    if (!this.googleAccessToken) {
      this.toast.warning('Vui lòng Kết nối Google Drive trước!');
      return;
    }

    const showPicker = () => {
      const picker = new google.picker.PickerBuilder()
        .addView(new google.picker.DocsView(google.picker.ViewId.DOCS).setIncludeFolders(true).setSelectFolderEnabled(false))
        .enableFeature(google.picker.Feature.NAV_HIDDEN)
        .setOAuthToken(this.googleAccessToken)
        .setDeveloperKey('AIzaSyAnsAtaHbLt0ngkHXzh3BdZdNEYJ5OGhoA')
        .setCallback((data: any) => {
          if (data.action === google.picker.Action.PICKED) {
            const file = data.docs[0];
            this.syncPickedFile(file.id, file.name);
          }
        })
        .build();
      picker.setVisible(true);
    };

    if (typeof google !== 'undefined' && google.picker) {
      showPicker();
      return;
    }

    this.toast.info('Đang tải thư viện Google Picker...');

    if (typeof gapi !== 'undefined') {
      gapi.load('picker', {
        callback: () => {
          this.ngZone.run(() => showPicker());
        },
        onerror: () => {
          this.ngZone.run(() => this.toast.error('Không thể tải thư viện Google Picker.'));
        }
      });
    } else {
      this.toast.error('Lỗi: Chưa nhúng thư viện Google (gapi). Vui lòng kiểm tra lại file index.html.');
    }
  }

  syncPickedFile(fileId: string, fileName: string): void {
    this.isSyncing = true;
    this.toast.info('Đang tải file từ Drive và nạp vào AI...');

    const driveUrl = `https://drive.google.com/file/d/${fileId}/view`;
    try {
      const savedLinks = JSON.parse(localStorage.getItem('drive_links') || '{}');
      savedLinks[fileName] = driveUrl;
      localStorage.setItem('drive_links', JSON.stringify(savedLinks));
    } catch {
      // Bỏ qua nếu localStorage bị khóa
    }

    fetch(`https://www.googleapis.com/drive/v3/files/${fileId}?alt=media`, {
      headers: { Authorization: `Bearer ${this.googleAccessToken}` }
    })
    .then(async (response) => {
      if (!response.ok) throw new Error('Lỗi tải file: ' + response.status);
      return await response.blob();
    })
    .then((blob) => {
      const formData = new FormData();
      formData.append('file', blob, fileName);
      formData.append('courseId', this.ragCourseCode);

      this.http.post('http://localhost:8080/api/drive/upload', formData).subscribe({
        next: () => {
          this.toast.success('Đã nạp tài liệu từ Drive vào RAG thành công!');
          this.loadRagStatus();
          this.isSyncing = false;
        },
        error: () => {
          // Dự phòng: gửi trực tiếp sang AI Service nếu cổng trung gian Backend gặp sự cố
          const fallbackFile = new File([blob], fileName, { type: blob.type });
          this.aiRagService.uploadCourseDocument(this.ragCourseCode, fallbackFile, false).subscribe({
            next: (res) => {
              this.toast.success(`Đã tải từ Drive và nạp thẳng vào AI Service (${res.addedOrUpdatedChunks} đoạn)!`);
              this.loadRagStatus();
              this.isSyncing = false;
            },
            error: () => {
              this.toast.error('Lỗi khi nạp tài liệu vào AI Service.');
              this.isSyncing = false;
            },
          });
        }
      });
    })
    .catch((err) => {
      this.toast.error(err.message || 'Không thể tải file.');
      this.isSyncing = false;
    });
  }

  onLocalFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.addFilesToStage(input.files);
    }
    input.value = '';
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    if (!this.isUploadingLocal) {
      this.isDragging = true;
    }
  }

  onDragLeave(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging = false;
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging = false;
    if (this.isUploadingLocal) return;
    if (event.dataTransfer?.files && event.dataTransfer.files.length > 0) {
      this.addFilesToStage(event.dataTransfer.files);
    }
  }

  addFilesToStage(fileList: FileList | File[]): void {
    if (this.isUploadingLocal) return;
    const files = Array.from(fileList);
    let addedCount = 0;
    let invalidCount = 0;

    for (const file of files) {
      const lowerName = file.name.toLowerCase();
      if (
        !lowerName.endsWith('.pdf') &&
        !lowerName.endsWith('.docx') &&
        !lowerName.endsWith('.txt')
      ) {
        invalidCount++;
        continue;
      }

      const newItem: StagedUploadItem = {
        file,
        status: 'pending',
        uploadPercent: 0,
      };
      const existingIndex = this.stagedFiles.findIndex((item) => item.file.name === file.name);
      if (existingIndex !== -1) {
        this.stagedFiles[existingIndex] = newItem;
      } else {
        this.stagedFiles = [...this.stagedFiles, newItem];
      }
      addedCount++;
    }

    if (invalidCount > 0) {
      this.toast.warning(
        `Có ${invalidCount} tệp không đúng định dạng (.pdf, .docx, .txt) đã được bỏ qua.`,
      );
    }
    if (addedCount > 0) {
      this.toast.info(
        `Đã thêm ${addedCount} tệp vào danh sách chờ. Kiểm tra lại rồi bấm "Bắt đầu tải lên & Xử lý RAG".`,
      );
    }
  }

  removeStagedFile(index: number): void {
    if (this.isUploadingLocal) return;
    this.stagedFiles = this.stagedFiles.filter((_, idx) => idx !== index);
  }

  clearStagedFiles(): void {
    if (this.isUploadingLocal) return;
    this.stagedFiles = [];
  }

  get pendingOrErrorCount(): number {
    return this.stagedFiles.filter((i) => i.status === 'pending' || i.status === 'error').length;
  }

  get hasLargeOrSlowModelNotice(): boolean {
    const hasLargeFile = this.stagedFiles.some(
      (i) => (i.status === 'pending' || i.status === 'uploading' || i.status === 'processing') && i.file.size > 5 * 1024 * 1024,
    );
    return hasLargeFile || this.embeddingProvider === 'e5-small' || this.embeddingProvider === 'local';
  }

  formatElapsed(seconds: number): string {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }

  private startUploadTimer(): void {
    this.stopUploadTimer();
    this.uploadElapsedSeconds = 0;
    this.uploadTimerId = setInterval(() => {
      this.uploadElapsedSeconds += 1;
    }, 1000);
  }

  private stopUploadTimer(): void {
    if (this.uploadTimerId !== null) {
      clearInterval(this.uploadTimerId);
      this.uploadTimerId = null;
    }
  }

  formatFileSize(bytes: number): string {
    if (!bytes || bytes < 1024) return `${bytes || 0} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  }

  async processStagedFiles(): Promise<void> {
    if (this.isUploadingLocal || this.pendingOrErrorCount === 0) return;

    const itemsToUpload = this.stagedFiles.filter(
      (item) => item.status === 'pending' || item.status === 'error',
    );
    const total = itemsToUpload.length;

    this.isUploadingLocal = true;
    this.activeUploadPhase = 'uploading';
    this.activeUploadPercent = 0;
    this.startUploadTimer();

    let uploadedCount = 0;
    let totalNewChunks = 0;
    let hadError = false;

    try {
      for (let i = 0; i < total; i++) {
        const item = itemsToUpload[i];
        item.status = 'uploading';
        item.uploadPercent = 0;
        item.errorMessage = undefined;
        this.activeUploadPhase = 'uploading';
        this.activeUploadPercent = 0;
        this.uploadingProgressText = `Đang xử lý (${i + 1}/${total}): ${item.file.name}`;

        try {
          await new Promise<void>((resolve, reject) => {
            this.aiRagService
              .uploadCourseDocumentWithProgress(
                this.ragCourseCode,
                item.file,
                false,
                this.embeddingProvider,
                this.chunkingStrategy,
              )
              .subscribe({
                next: (ev) => {
                  this.activeUploadPhase = ev.phase === 'done' ? 'processing' : ev.phase;
                  this.activeUploadPercent = ev.uploadPercent;
                  item.uploadPercent = ev.uploadPercent;
                  if (ev.phase === 'done' && ev.result) {
                    item.status = 'done';
                    item.addedChunks = ev.result.addedOrUpdatedChunks || 0;
                    uploadedCount++;
                    totalNewChunks += ev.result.addedOrUpdatedChunks || 0;
                    if (this.previewingFile === item.file.name) {
                      this.openFilePreview(item.file.name);
                    }
                  } else {
                    item.status = ev.phase;
                  }
                },
                error: (err) => reject(err),
                complete: () => resolve(),
              });
          });
        } catch (err: any) {
          hadError = true;
          item.status = 'error';
          item.errorMessage = err?.error?.detail || `Lỗi khi tải lên tệp "${item.file.name}".`;
          this.toast.error(item.errorMessage!);
        }
      }
    } finally {
      this.stopUploadTimer();
      this.isUploadingLocal = false;
      this.uploadingProgressText = '';
    }

    if (uploadedCount > 0) {
      this.toast.success(
        `Đã tải lên server và lập chỉ mục ${uploadedCount}/${total} tệp (${totalNewChunks} đoạn mới).`,
      );
      this.loadRagStatus();
    } else if (!hadError) {
      this.loadRagStatus();
    }
  }

  getServerFileUrl(fileName: string): string {
    return this.aiRagService.getServerDocumentUrl(this.ragCourseCode, fileName);
  }

  hasDriveLink(fileName: string): boolean {
    try {
      const savedLinks = JSON.parse(localStorage.getItem('drive_links') || '{}');
      return Boolean(savedLinks[fileName]);
    } catch {
      return false;
    }
  }

  // Hàm lấy link Drive (dùng cho HTML)
  getDriveLink(fileName: string): string {
    try {
      const savedLinks = JSON.parse(localStorage.getItem('drive_links') || '{}');
      return savedLinks[fileName] || `https://drive.google.com/drive/search?q=${encodeURIComponent(fileName)}`;
    } catch {
      return `https://drive.google.com/drive/search?q=${encodeURIComponent(fileName)}`;
    }
  }

  openFilePreview(fileName: string): void {
    this.previewingFile = fileName;
    this.previewLoading = true;
    this.previewContent = '';
    this.previewTotalChars = 0;

    this.aiRagService.previewCourseDocument(this.ragCourseCode, fileName).subscribe({
      next: (res) => {
        this.previewContent = res.content;
        this.previewTotalChars = res.totalChars;
        this.previewLoading = false;
      },
      error: (err) => {
        this.previewLoading = false;
        this.previewingFile = null;
        this.toast.error(err?.error?.detail || 'Không thể đọc nội dung tài liệu từ Server.');
      },
    });
  }

  closeFilePreview(): void {
    this.previewingFile = null;
    this.previewLoading = false;
    this.previewContent = '';
    this.previewTotalChars = 0;
  }

  deleteDocument(fileName: string): void {
    if (this.deletingFile) return;
    this.deletingFile = fileName;
    this.aiRagService.deleteCourseDocument(this.ragCourseCode, fileName).subscribe({
      next: () => {
        this.deletingFile = null;
        if (this.previewingFile === fileName) {
          this.closeFilePreview();
        }
        this.toast.success(`Đã xóa tài liệu "${fileName}" khỏi Server & RAG.`);
        this.loadRagStatus();
      },
      error: (err) => {
        this.deletingFile = null;
        this.toast.error(err?.error?.detail || 'Không thể xóa tài liệu.');
      },
    });
  }

  get chunkingStrategyLabel(): string {
    const labels: Record<ChunkingStrategyOption, string> = {
      recursive: 'Recursive tiêu đề & câu',
      semantic: 'Semantic theo ngữ nghĩa',
      legacy: 'Boundary 600 ký tự (cách cũ)',
    };
    return labels[this.chunkingStrategy];
  }

  private startSyncTimer(initialSeconds = 0): void {
    this.stopSyncTimer();
    this.syncElapsedSeconds = initialSeconds;
    this.syncTimerId = setInterval(() => {
      this.syncElapsedSeconds += 1;
    }, 1000);
  }

  private stopSyncTimer(): void {
    if (this.syncTimerId !== null) {
      clearInterval(this.syncTimerId);
      this.syncTimerId = null;
    }
  }

  private stopPollingSyncJob(): void {
    if (this.syncPollTimerId !== null) {
      clearInterval(this.syncPollTimerId);
      this.syncPollTimerId = null;
    }
    this.activeSyncJobId = null;
  }

  private applySyncJobSnapshot(job: {
    jobId: string;
    percent: number;
    message: string;
    currentFile?: string | null;
    processedChunks: number;
    totalChunks: number;
    elapsedSeconds: number;
  }): void {
    this.activeSyncJobId = job.jobId;
    this.syncPercent = Math.max(0, Math.min(100, job.percent));
    this.syncMessage = job.message || '';
    this.syncCurrentFile = job.currentFile || '';
    this.syncProcessedChunks = job.processedChunks || 0;
    this.syncTotalChunks = job.totalChunks || 0;
    if (job.elapsedSeconds > this.syncElapsedSeconds) {
      this.syncElapsedSeconds = job.elapsedSeconds;
    }
  }

  private startPollingSyncJob(jobId: string): void {
    this.stopPollingSyncJob();
    this.activeSyncJobId = jobId;
    this.syncPollTimerId = setInterval(() => {
      this.aiRagService.getIndexJobStatus(jobId).subscribe({
        next: (job) => {
          this.applySyncJobSnapshot(job);
          if (job.status === 'completed') {
            this.stopPollingSyncJob();
            this.stopSyncTimer();
            this.isSyncing = false;
            const totalChunks = job.result?.totalChunks ?? job.totalChunks;
            const totalFiles = job.result?.totalFiles ?? job.totalFiles;
            this.toast.success(
              `Đã đồng bộ chỉ mục RAG (${totalChunks} đoạn từ ${totalFiles} tài liệu, chế độ: ${job.result?.chunkingStrategy || job.chunkingStrategy}).`,
            );
            this.loadRagStatus(true);
          } else if (job.status === 'failed') {
            this.stopPollingSyncJob();
            this.stopSyncTimer();
            this.isSyncing = false;
            this.toast.error(job.error || 'Lỗi khi đồng bộ chỉ mục RAG tại Server.');
          }
        },
        error: (err) => {
          if (err?.status === 404) {
            this.stopPollingSyncJob();
            this.stopSyncTimer();
            this.isSyncing = false;
          }
        },
      });
    }, 1500);
  }

  checkActiveSyncJob(): void {
    if (!this.ragCourseCode) return;
    this.aiRagService.getActiveIndexJob(this.ragCourseCode, this.embeddingProvider).subscribe({
      next: (job) => {
        if (job && (job.status === 'queued' || job.status === 'running')) {
          this.isSyncing = true;
          this.startSyncTimer(job.elapsedSeconds);
          this.applySyncJobSnapshot(job);
          this.startPollingSyncJob(job.jobId);
        }
      },
      error: () => {
        // Bỏ qua nếu chưa hỏi được job đang chạy
      },
    });
  }

  syncRagIndex(forceReindex = false): void {
    if (this.isSyncing) return;
    this.isSyncing = true;
    this.syncPercent = 1;
    this.syncMessage = 'Đang khởi chạy tác vụ đồng bộ nền tại AI Service...';
    this.syncCurrentFile = '';
    this.syncProcessedChunks = 0;
    this.syncTotalChunks = 0;
    this.startSyncTimer(0);

    this.aiRagService
      .startIndexCourseDocumentsJob(
        this.ragCourseCode,
        forceReindex,
        this.embeddingProvider,
        this.chunkingStrategy,
      )
      .subscribe({
        next: (job) => {
          this.applySyncJobSnapshot(job);
          if (job.status === 'completed') {
            this.stopSyncTimer();
            this.isSyncing = false;
            this.loadRagStatus(true);
            return;
          }
          this.startPollingSyncJob(job.jobId);
        },
        error: () => {
          this.stopPollingSyncJob();
          this.stopSyncTimer();
          this.isSyncing = false;
          this.toast.error('Không thể khởi chạy đồng bộ chỉ mục RAG tại Server.');
        },
      });
  }

  toggleShowResults(): void {
    this.showResults = !this.showResults;
  }

  runTestSearch(): void {
    if (!this.searchQuery.trim()) return;
    this.searching = true;
    this.aiRagService.searchCourseDocuments({
      courseId: this.ragCourseCode,
      queryText: this.searchQuery,
      topK: this.topK,
      searchMode: this.searchMode,
      embeddingProvider: this.embeddingProvider,
    }).subscribe({
      next: (res) => {
        this.searching = false;
        this.cleanedQuery = res.cleanedQuery;
        this.searchResults = res.results;
        this.showResults = true;
      },
      error: () => {
        this.searching = false;
        this.toast.error('Lỗi tìm kiếm.');
      },
    });
  }
}
