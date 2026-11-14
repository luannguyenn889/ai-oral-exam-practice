import { Component, inject, OnInit, NgZone } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { AiRagService } from '../../../core/services/ai-rag.service';
import { PracticeApi } from '../../../data-access/api/practice.api';
import { ToastService } from '../../../core/services/toast.service';
import { Course, RagStatus, RagChunkResult } from '../../../shared/models';
import { SkeletonComponent } from '../../../shared/components/skeleton/skeleton.component';
import { ErrorStateComponent } from '../../../shared/components/error-state/error-state.component';
import { environment } from '../../../../environments/environment';

// Khai báo các biến toàn cục của Google
declare const google: any;
declare const gapi: any;

@Component({
  selector: 'app-course-documents',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule, SkeletonComponent, ErrorStateComponent],
  templateUrl: './course-documents.component.html',
  styleUrl: './course-documents.component.css',
})
export class CourseDocumentsComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private aiRagService = inject(AiRagService);
  private practiceApi = inject(PracticeApi);
  private toast = inject(ToastService);
  private http = inject(HttpClient);
  private ngZone = inject(NgZone);

  courseId = '';
  courses: Course[] = [];
  course: Course | null = null;
  loading = true;
  error: string | null = null;
  ragStatus: RagStatus | null = null;
  isSyncing = false;
  stagedFiles: File[] = [];
  uploadingProgressText = '';
  isUploadingLocal = false;
  isDragging = false;
  googleAccessToken: string | null = null;

  // Trạng thái đọc & xóa file trực tiếp tại Server
  previewingFile: string | null = null;
  previewLoading = false;
  previewContent = '';
  previewTotalChars = 0;
  deletingFile: string | null = null;

  // Test Search state
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
      this.courseId = params.get('courseId') || '';
      this.stagedFiles = [];
      this.uploadingProgressText = '';
      this.closeFilePreview();
      this.searchResults = [];
      this.cleanedQuery = '';
      this.loadCourseInfoAndRag();
    });
  }

  onCourseSelect(courseCode: string): void {
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
    this.practiceApi.getCourses().subscribe({
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

  loadRagStatus(): void {
    if (!this.ragCourseCode) {
      this.ragStatus = null;
      this.loading = false;
      return;
    }
    this.loading = true;
    this.error = null;
    this.aiRagService.getRagStatus(this.ragCourseCode).subscribe({
      next: (status) => { this.ragStatus = status; this.loading = false; },
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

      const existingIndex = this.stagedFiles.findIndex((f) => f.name === file.name);
      if (existingIndex !== -1) {
        this.stagedFiles[existingIndex] = file;
      } else {
        this.stagedFiles = [...this.stagedFiles, file];
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

  formatFileSize(bytes: number): string {
    if (!bytes || bytes < 1024) return `${bytes || 0} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  }

  async processStagedFiles(): Promise<void> {
    if (this.isUploadingLocal || this.stagedFiles.length === 0) return;

    this.isUploadingLocal = true;
    const filesToUpload = [...this.stagedFiles];
    const total = filesToUpload.length;
    let uploadedCount = 0;
    let totalNewChunks = 0;
    let hadError = false;

    for (let i = 0; i < total; i++) {
      const file = filesToUpload[i];
      this.uploadingProgressText = `Đang tải lên & lập chỉ mục (${i + 1}/${total}): ${file.name}`;
      try {
        const res = await firstValueFrom(
          this.aiRagService.uploadCourseDocument(this.ragCourseCode, file, false),
        );
        uploadedCount++;
        totalNewChunks += res.addedOrUpdatedChunks || 0;
        this.stagedFiles = this.stagedFiles.filter((f) => f !== file);
        if (this.previewingFile === file.name) {
          this.openFilePreview(file.name);
        }
      } catch (err: any) {
        hadError = true;
        this.toast.error(err?.error?.detail || `Lỗi khi tải lên tệp "${file.name}".`);
      }
    }

    this.isUploadingLocal = false;
    this.uploadingProgressText = '';

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

  syncRagIndex(forceReindex = false): void {
    if (this.isSyncing) return;
    this.isSyncing = true;
    this.aiRagService.indexCourseDocuments(this.ragCourseCode, forceReindex).subscribe({
      next: (res) => {
        this.isSyncing = false;
        this.toast.success(
          `Đã đồng bộ chỉ mục RAG (${res.totalChunks} đoạn từ ${res.totalFiles} tài liệu).`,
        );
        this.loadRagStatus();
      },
      error: () => {
        this.isSyncing = false;
        this.toast.error('Lỗi khi đồng bộ chỉ mục RAG tại Server.');
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
      searchMode: this.searchMode
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
