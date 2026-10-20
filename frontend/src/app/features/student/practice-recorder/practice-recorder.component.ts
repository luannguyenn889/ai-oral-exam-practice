import { Component, inject, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { PracticeApi } from '../../../data-access/api/practice.api';
import { ToastService } from '../../../core/services/toast.service';
import { Question } from '../../../shared/models';
import { SkeletonComponent } from '../../../shared/components/skeleton/skeleton.component';
import { ErrorStateComponent } from '../../../shared/components/error-state/error-state.component';

@Component({
  selector: 'app-practice-recorder',
  standalone: true,
  imports: [CommonModule, RouterModule, SkeletonComponent, ErrorStateComponent],
  templateUrl: './practice-recorder.component.html',
  styleUrl: './practice-recorder.component.css',
})
export class PracticeRecorderComponent implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private practiceApi = inject(PracticeApi);
  private toast = inject(ToastService);

  questionId = '';
  question: Question | null = null;
  loading = true;
  error: string | null = null;

  // Audio recording state
  isRecording = false;
  recordingSeconds = 0;
  private timerInterval: ReturnType<typeof setInterval> | null = null;
  private mediaRecorder: MediaRecorder | null = null;
  private audioChunks: Blob[] = [];

  recordedBlob: Blob | null = null;
  audioPreviewUrl: string | null = null;
  selectedFileName: string | null = null;

  submitting = false;

  ngOnInit(): void {
    this.questionId = this.route.snapshot.paramMap.get('questionId') || 'q-se-1';
    this.loadQuestion();
  }

  ngOnDestroy(): void {
    this.stopTimer();
    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      this.mediaRecorder.stop();
    }
    if (this.audioPreviewUrl) {
      URL.revokeObjectURL(this.audioPreviewUrl);
    }
  }

  loadQuestion(): void {
    this.loading = true;
    this.error = null;
    this.practiceApi.getQuestion(this.questionId).subscribe({
      next: (q) => {
        this.question = q;
        this.loading = false;
      },
      error: () => {
        this.error = 'Không tìm thấy câu hỏi yêu cầu. Vui lòng quay lại ngân hàng câu hỏi.';
        this.loading = false;
      },
    });
  }

  formatDuration(sec: number): string {
    const mins = Math.floor(sec / 60);
    const secs = sec % 60;
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }

  async startRecording(): Promise<void> {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.audioChunks = [];
      this.mediaRecorder = new MediaRecorder(stream);

      this.mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          this.audioChunks.push(e.data);
        }
      };

      this.mediaRecorder.onstop = () => {
        const blob = new Blob(this.audioChunks, { type: 'audio/webm' });
        this.setAudioBlob(blob, 'Ban_ghi_am_truc_tiep.webm');
        stream.getTracks().forEach((track) => track.stop());
      };

      this.mediaRecorder.start();
      this.isRecording = true;
      this.recordingSeconds = 0;
      this.startTimer();
    } catch {
      this.toast.error(
        'Không thể truy cập Microphone. Bạn có thể chọn tải file âm thanh (.wav, .mp3, .webm) hoặc bấm nút Dùng thử bản ghi mẫu.',
      );
    }
  }

  stopRecording(): void {
    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      this.mediaRecorder.stop();
    }
    this.isRecording = false;
    this.stopTimer();
  }

  onAudioFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    this.setAudioBlob(file, file.name);
  }

  useSimulatedRecording(): void {
    const dummyBlob = new Blob(['simulated-oral-exam-audio'], { type: 'audio/webm' });
    this.recordingSeconds = 75;
    this.setAudioBlob(dummyBlob, 'Ban_ghi_am_mau_demo.webm');
    this.toast.info('Đã nạp bản ghi âm mẫu để bạn trải nghiệm nhanh bước sửa Transcript & chấm RAG.');
  }

  private setAudioBlob(blob: Blob, filename: string): void {
    if (this.audioPreviewUrl) {
      URL.revokeObjectURL(this.audioPreviewUrl);
    }
    this.recordedBlob = blob;
    this.selectedFileName = filename;
    if (blob.size > 100) {
      this.audioPreviewUrl = URL.createObjectURL(blob);
    } else {
      this.audioPreviewUrl = null;
    }
  }

  submitAudioAndTranscribe(): void {
    if (!this.question || !this.recordedBlob) return;
    this.submitting = true;

    this.practiceApi.createPracticeSession(this.question.id).subscribe({
      next: (session) => {
        this.practiceApi.uploadAudio(session.id, this.recordedBlob!).subscribe({
          next: () => {
            this.practiceApi.requestTranscription(session.id).subscribe({
              next: () => {
                this.submitting = false;
                this.toast.success('Đã chuyển giọng nói thành văn bản và chuẩn hóa thuật ngữ CNTT!');
                this.router.navigate(['/student/sessions', session.id, 'transcript']);
              },
              error: () => {
                this.submitting = false;
                this.toast.error('Có lỗi khi nhận dạng giọng nói. Vui lòng thử lại.');
              },
            });
          },
          error: () => {
            this.submitting = false;
            this.toast.error('Không thể tải lên bản ghi âm.');
          },
        });
      },
      error: () => {
        this.submitting = false;
        this.toast.error('Không thể khởi tạo phiên luyện tập.');
      },
    });
  }

  private startTimer(): void {
    this.stopTimer();
    this.timerInterval = setInterval(() => {
      this.recordingSeconds++;
    }, 1000);
  }

  private stopTimer(): void {
    if (this.timerInterval) {
      clearInterval(this.timerInterval);
      this.timerInterval = null;
    }
  }
}

