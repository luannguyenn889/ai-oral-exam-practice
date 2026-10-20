import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { AiRagService } from '../../../core/services/ai-rag.service';
import { PracticeApi } from '../../../data-access/api/practice.api';
import { ToastService } from '../../../core/services/toast.service';
import { Course, RagChunkResult, RagStatus } from '../../../shared/models';
import { SkeletonComponent } from '../../../shared/components/skeleton/skeleton.component';
import { ErrorStateComponent } from '../../../shared/components/error-state/error-state.component';

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

  courseId = 'IT2030';
  course: Course | null = null;

  loading = true;
  error: string | null = null;
  ragStatus: RagStatus | null = null;

  uploading = false;
  indexing = false;
  deletingFile: string | null = null;

  // Test Hybrid RAG Search state
  searchQuery =
    'Dạ thưa thầy kiểm thử hộp đen Black-box và kiểm thử hộp trắng White-box khác nhau thế nào ạ?';
  searchMode: 'hybrid' | 'dense' | 'bm25' = 'hybrid';
  topK = 3;
  searching = false;
  cleanedQuery = '';
  searchResults: RagChunkResult[] = [];
  hasSearched = false;

  ngOnInit(): void {
    this.courseId = this.route.snapshot.paramMap.get('courseId') || 'IT2030';
    this.loadCourseInfo();
    this.loadRagStatus();
  }

  loadCourseInfo(): void {
    this.practiceApi.getCourses().subscribe({
      next: (courses) => {
        this.course = courses.find((c) => c.id === this.courseId) || null;
      },
    });
  }

  loadRagStatus(): void {
    this.loading = true;
    this.error = null;
    this.aiRagService.getRagStatus(this.courseId).subscribe({
      next: (status) => {
        this.ragStatus = status;
        this.loading = false;
      },
      error: () => {
        this.error =
          'Không thể kết nối tới dịch vụ AI (http://localhost:8000). Hãy chắc chắn bạn đã chạy start-ai-service.bat.';
        this.loading = false;
      },
    });
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    this.uploading = true;

    this.aiRagService.uploadCourseDocument(this.courseId, file, false).subscribe({
      next: (res) => {
        this.uploading = false;
        input.value = '';
        this.toast.success(
          `Đã nạp "${file.name}" thành công (${res.totalChunks} đoạn văn bản trong kho RAG).`,
        );
        this.loadRagStatus();
      },
      error: (err) => {
        this.uploading = false;
        input.value = '';
        this.toast.error(err?.error?.detail || 'Không thể tải lên và lập chỉ mục tài liệu.');
      },
    });
  }

  syncRagIndex(forceReindex = false): void {
    this.indexing = true;
    this.aiRagService.indexCourseDocuments(this.courseId, forceReindex).subscribe({
      next: (res) => {
        this.indexing = false;
        this.toast.success(
          `Đồng bộ RAG hoàn tất: ${res.totalFiles} tài liệu, tổng cộng ${res.totalChunks} đoạn (chunks).`,
        );
        this.loadRagStatus();
      },
      error: (err) => {
        this.indexing = false;
        this.toast.error(err?.error?.detail || 'Lỗi khi đồng bộ chỉ mục RAG.');
      },
    });
  }

  deleteDocument(filename: string): void {
    this.deletingFile = filename;
    this.aiRagService.deleteCourseDocument(this.courseId, filename).subscribe({
      next: () => {
        this.deletingFile = null;
        this.toast.info(`Đã xóa tài liệu "${filename}" khỏi kho RAG.`);
        this.loadRagStatus();
      },
      error: (err) => {
        this.deletingFile = null;
        this.toast.error(err?.error?.detail || 'Không thể xóa tài liệu.');
      },
    });
  }

  runTestSearch(): void {
    if (!this.searchQuery.trim()) return;
    this.searching = true;
    this.hasSearched = true;
    this.aiRagService
      .searchCourseDocuments({
        courseId: this.courseId,
        queryText: this.searchQuery,
        topK: this.topK,
        searchMode: this.searchMode,
      })
      .subscribe({
        next: (res) => {
          this.searching = false;
          this.cleanedQuery = res.cleanedQuery;
          this.searchResults = res.results;
        },
        error: (err) => {
          this.searching = false;
          this.toast.error(err?.error?.detail || 'Lỗi khi truy vấn thử kho RAG.');
        },
      });
  }
}

