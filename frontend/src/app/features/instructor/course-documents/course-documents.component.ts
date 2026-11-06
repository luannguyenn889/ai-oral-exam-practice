import { Component, inject, OnInit, NgZone } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { HttpClient } from '@angular/common/http';
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
  private aiRagService = inject(AiRagService);
  private practiceApi = inject(PracticeApi);
  private toast = inject(ToastService);
  private http = inject(HttpClient);
  private ngZone = inject(NgZone);

  courseId = 'IT2030';
  course: Course | null = null;
  loading = true;
  error: string | null = null;
  ragStatus: RagStatus | null = null;
  isSyncing = false;
  googleAccessToken: string | null = null;

  // Test Search state
  searchQuery = 'Dạ thưa thầy...';
  searchMode: 'hybrid' | 'dense' | 'bm25' = 'hybrid';
  topK = 3;
  searching = false;
  cleanedQuery = '';
  searchResults: RagChunkResult[] = [];
  // Trạng thái hiển thị danh sách kết quả RAG
  showResults = true;

  ngOnInit(): void {
    this.courseId = this.route.snapshot.paramMap.get('courseId') || 'IT2030';
    this.loadCourseInfo();
    this.loadRagStatus();
  }

  loadCourseInfo(): void {
    this.practiceApi.getCourses().subscribe({
      next: (courses) => this.course = courses.find((c) => c.id === this.courseId) || null,
    });
  }

  loadRagStatus(): void {
    this.loading = true;
    this.error = null;
    this.aiRagService.getRagStatus(this.courseId).subscribe({
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
    const savedLinks = JSON.parse(localStorage.getItem('drive_links') || '{}');
    savedLinks[fileName] = driveUrl;
    localStorage.setItem('drive_links', JSON.stringify(savedLinks));

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
      formData.append('courseId', this.courseId);

      this.http.post('http://localhost:8080/api/drive/upload', formData).subscribe({
        next: () => {
          this.toast.success('Đã nạp tài liệu vào RAG thành công!');
          this.loadRagStatus();
          this.isSyncing = false;
        },
        error: () => {
          this.toast.error('Lỗi khi gửi file sang Backend.');
          this.isSyncing = false;
        }
      });
    })
    .catch((err) => {
      this.toast.error(err.message || 'Không thể tải file.');
      this.isSyncing = false;
    });
  }

  // Hàm lấy link Drive (dùng cho HTML)
  getDriveLink(fileName: string): string {
    const savedLinks = JSON.parse(localStorage.getItem('drive_links') || '{}');
    return savedLinks[fileName] || `https://drive.google.com/drive/search?q=${encodeURIComponent(fileName)}`;
  }

  syncRagIndex(forceReindex = false): void {
    // Giữ hàm rỗng để tránh lỗi
  }

  toggleShowResults(): void {
    this.showResults = !this.showResults;
  }

  runTestSearch(): void {
    if (!this.searchQuery.trim()) return;
    this.searching = true;
    this.aiRagService.searchCourseDocuments({
      courseId: this.courseId,
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
