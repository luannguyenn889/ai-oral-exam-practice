import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of, delay, throwError, catchError, map } from 'rxjs';
import { environment } from '../../../environments/environment';
import { PracticeApi } from '../api/practice.api';
import {
  Course,
  Question,
  Rubric,
  PracticeSession,
  Evaluation,
  ExtractedQuestion,
  QuestionExtractResult,
} from '../../shared/models';
import { AiRagService } from '../../core/services/ai-rag.service';

@Injectable({
  providedIn: 'root',
})
export class MockPracticeApi extends PracticeApi {
  private http = inject(HttpClient);
  private aiRagService = inject(AiRagService);
  private sessionAudioBlobs = new Map<string, Blob>();

  private readonly sessionStorageKey = 'oral_exam_practice_sessions_v2';
  private mockCourses: Course[] = [];
  private mockQuestions: Question[] = [];
  private mockSessions: PracticeSession[] = [];

  constructor() {
    super();
    this.restoreSessionsFromStorage();
  }

  private restoreSessionsFromStorage(): void {
    try {
      sessionStorage.removeItem('oral_exam_practice_sessions_v1');
      const raw = sessionStorage.getItem(this.sessionStorageKey);
      if (raw) {
        const parsed = JSON.parse(raw) as PracticeSession[];
        if (Array.isArray(parsed)) {
          this.mockSessions = parsed.filter((s) => s && s.id && s.id !== 'session-demo-1');
        }
      }
    } catch {
      // Ignore storage read errors
    }
  }

  private persistSessionsToStorage(): void {
    try {
      sessionStorage.setItem(this.sessionStorageKey, JSON.stringify(this.mockSessions));
    } catch {
      // Ignore storage write errors
    }
  }

  private findSession(sessionId: string): PracticeSession | undefined {
    if (!sessionId) return undefined;
    return this.mockSessions.find((item) => item.id === sessionId);
  }

  override getCourses(): Observable<Course[]> {
    return this.http.get<Course[]>(`${environment.apiBaseUrl}/courses`).pipe(
      map((courses) => {
        this.mockCourses = Array.isArray(courses) ? [...courses] : [];
        return this.mockCourses;
      }),
      catchError((err) => {
        console.error('Lỗi khi tải danh sách học phần từ Backend:', err);
        const errorMsg =
          err?.error?.message ||
          err?.message ||
          'Không thể kết nối đến Backend Database để tải danh sách học phần.';
        return throwError(() => new Error(errorMsg));
      }),
    );
  }

  private mapServerQuestion(res: any): Question {
    return {
      id: String(res.id),
      courseId: String(res.courseId || ''),
      topic: res.topic || '',
      title: res.title || '',
      content: res.content || '',
      sampleAnswer: res.sampleAnswer || '',
      difficulty: res.difficulty || 'medium',
      timeLimitSeconds: res.timeLimitSeconds || 180,
      tags: res.tags || [],
      parentQuestionId: res.parentQuestionId ? String(res.parentQuestionId) : null,
      rubric: res.rubric
        ? {
            id: String(res.rubric.id),
            questionId: String(res.id),
            totalScore: Number(res.rubric.totalScore) || 10.0,
            gradingInstructions: res.rubric.gradingInstructions,
            criteria: (res.rubric.criteria || []).map((c: any) => ({
              id: String(c.id),
              name: c.name,
              description: c.description,
              maxScore: Number(c.maxScore) || 2.5,
            })),
          }
        : undefined,
    };
  }

  override getQuestions(courseId?: string): Observable<Question[]> {
    const url = courseId
      ? `${environment.apiBaseUrl}/courses/${courseId}/questions`
      : `${environment.apiBaseUrl}/questions`;

    return this.http.get<any[]>(url).pipe(
      map((serverList) => {
        const questions = (serverList || []).map((q) => this.mapServerQuestion(q));
        if (!courseId) {
          this.mockQuestions = [...questions];
        } else {
          const ids = new Set(questions.map((q) => q.id));
          this.mockQuestions = [
            ...this.mockQuestions.filter(
              (item) => item.courseId !== courseId && !ids.has(item.id),
            ),
            ...questions,
          ];
        }
        return questions;
      }),
      catchError((err) => {
        console.error('Lỗi khi tải danh sách câu hỏi từ Backend:', err);
        const errorMsg =
          err?.error?.message ||
          err?.message ||
          'Không thể tải danh sách câu hỏi từ Backend Database.';
        return throwError(() => new Error(errorMsg));
      }),
    );
  }

  override getQuestion(questionId: string): Observable<Question> {
    if (!questionId || !questionId.trim()) {
      return throwError(() => new Error('Mã câu hỏi không hợp lệ.'));
    }
    return this.http.get<any>(`${environment.apiBaseUrl}/questions/${questionId}`).pipe(
      map((serverQ) => {
        const q = this.mapServerQuestion(serverQ);
        const idx = this.mockQuestions.findIndex((item) => item.id === q.id);
        if (idx !== -1) {
          this.mockQuestions[idx] = q;
        } else {
          this.mockQuestions.unshift(q);
        }
        return q;
      }),
      catchError((err) => {
        console.error('Lỗi khi lấy chi tiết câu hỏi từ Backend:', err);
        const cached = this.mockQuestions.find((item) => item.id === questionId);
        if (cached) {
          return of({ ...cached });
        }
        return throwError(
          () =>
            new Error(
              err?.error?.message ||
                err?.message ||
                'Không tìm thấy câu hỏi yêu cầu từ Backend Database.',
            ),
        );
      }),
    );
  }

  override createPracticeSession(questionId: string): Observable<PracticeSession> {
    return this.getQuestion(questionId).pipe(
      map((q) => {
        const course = this.mockCourses.find(
          (c) => c.id === q.courseId || c.code.toUpperCase() === (q.courseId || '').toUpperCase(),
        );
        const newSession: PracticeSession = {
          id: `session-${Date.now()}`,
          questionId: q.id,
          courseId: q.courseId || '',
          questionTitle: q.title || 'Câu hỏi luyện tập',
          courseName: course?.name || 'Học phần vấn đáp',
          userId: 'user-student-1',
          status: 'recording',
          isTranscriptConfirmed: false,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        };
        (newSession as any)._question = q;
        (newSession as any)._courseCode = course?.code;
        this.mockSessions.unshift(newSession);
        this.persistSessionsToStorage();
        return newSession;
      }),
    );
  }

  override getPracticeSession(sessionId: string): Observable<PracticeSession> {
    const s = this.findSession(sessionId);
    if (!s) {
      return throwError(() => new Error('Không tìm thấy phiên luyện tập này.'));
    }
    return of({ ...s }).pipe(delay(50));
  }

  override uploadAudio(sessionId: string, audioFile: Blob): Observable<PracticeSession> {
    const s = this.findSession(sessionId);
    if (!s) {
      return throwError(() => new Error('Không tìm thấy phiên luyện tập này.'));
    }
    this.sessionAudioBlobs.set(sessionId, audioFile);
    s.status = 'uploaded';
    if (audioFile.size > 50) {
      s.audioUrl = URL.createObjectURL(audioFile);
    }
    s.updatedAt = new Date().toISOString();
    this.persistSessionsToStorage();
    return of({ ...s }).pipe(delay(50));
  }

  override requestTranscription(sessionId: string): Observable<{ status: string; jobId?: string }> {
    const s = this.findSession(sessionId);
    if (!s) {
      return throwError(() => new Error('Không tìm thấy phiên luyện tập này.'));
    }
    const q: Question | undefined =
      (s as any)._question || this.mockQuestions.find((item) => item.id === s.questionId);
    if (!q) {
      return throwError(
        () => new Error('Không tìm thấy thông tin câu hỏi của phiên luyện tập.'),
      );
    }
    const audioBlob = this.sessionAudioBlobs.get(sessionId);

    if (!audioBlob || audioBlob.size < 50) {
      return throwError(
        () =>
          new Error(
            'Không tìm thấy file ghi âm giọng nói của bạn. Vui lòng ghi âm lại trước khi chuyển văn bản.',
          ),
      );
    }

    const rubricSummary = (q.rubric?.criteria || [])
      .map((c: any) => `${c.name}: ${c.description}`)
      .join('; ');

    return this.aiRagService
      .transcribeUploadedAudio(
        audioBlob,
        q.content || s.questionTitle || '',
        rubricSummary,
        'groq',
        true,
      )
      .pipe(
        map((res) => {
          s.status = 'transcript_review';
          s.rawTranscript = res.rawTranscript;
          s.transcript = res.correctedTranscript || res.rawTranscript;
          s.audioDurationSeconds = res.durationSeconds || s.audioDurationSeconds;
          s.sttModel = res.sttModel;
          s.correctionModel = res.correctionModel;
          s.updatedAt = new Date().toISOString();
          this.persistSessionsToStorage();
          return { status: 'success', jobId: `job-stt-${Date.now()}` };
        }),
        catchError((err) => {
          console.error('Lỗi khi nhận diện giọng nói (STT):', err);
          return throwError(
            () =>
              new Error(
                `Lỗi khi chuyển đổi giọng nói thành văn bản: ${err?.message || 'Không thể kết nối đến AI Speech-to-Text service'}. Vui lòng kiểm tra AI Service.`,
              ),
          );
        }),
      );
  }

  override saveConfirmedTranscript(
    sessionId: string,
    transcript: string,
  ): Observable<PracticeSession> {
    const s = this.findSession(sessionId);
    if (!s) {
      return throwError(() => new Error('Không tìm thấy phiên luyện tập này.'));
    }
    s.transcript = transcript;
    s.isTranscriptConfirmed = true;
    s.status = 'grading';
    s.updatedAt = new Date().toISOString();
    this.persistSessionsToStorage();
    return of({ ...s }).pipe(delay(50));
  }

  override requestEvaluation(sessionId: string): Observable<{ status: string; jobId?: string }> {
    const s = this.findSession(sessionId);
    if (!s) {
      return throwError(() => new Error('Không tìm thấy phiên luyện tập này.'));
    }
    const q: Question | undefined =
      (s as any)._question || this.mockQuestions.find((item) => item.id === s.questionId);
    if (!q) {
      return throwError(
        () => new Error('Không tìm thấy thông tin câu hỏi của phiên luyện tập.'),
      );
    }
    const transcriptToGrade = s.transcript && s.transcript.trim();

    if (!transcriptToGrade) {
      return throwError(
        () =>
          new Error(
            'Chưa có nội dung câu trả lời của sinh viên. Vui lòng nói hoặc xác nhận câu trả lời trước khi gửi chấm điểm.',
          ),
      );
    }

    const resolvedCourse = this.mockCourses.find(
      (c) =>
        c.id === (s.courseId || q.courseId) ||
        c.code.toUpperCase() === (s.courseId || q.courseId || '').toUpperCase(),
    );
    const ragCourseCode = resolvedCourse?.code || (s as any)._courseCode || s.courseId || q.courseId || '';

    return this.aiRagService
      .evaluateSubmission({
        sessionId: s.id,
        courseId: ragCourseCode,
        question: q,
        transcript: transcriptToGrade,
        enableRag: true,
        searchMode: 'hybrid',
        topK: 3,
      })
      .pipe(
        map((evalResult) => {
          s.status = 'completed';
          s.transcript = transcriptToGrade;
          s.evaluation = evalResult;
          s.updatedAt = new Date().toISOString();
          this.persistSessionsToStorage();
          return { status: 'success', jobId: `job-eval-${Date.now()}` };
        }),
        catchError((err) => {
          console.error('Lỗi khi AI chấm điểm câu trả lời:', err);
          return throwError(
            () =>
              new Error(
                `Lỗi khi AI chấm điểm: ${err?.message || 'Không thể kết nối đến AI Evaluation Service'}. Vui lòng kiểm tra AI Service.`,
              ),
          );
        }),
      );
  }

  override getEvaluation(sessionId: string): Observable<Evaluation> {
    const s = this.findSession(sessionId);
    if (!s) {
      return throwError(() => new Error('Không tìm thấy phiên luyện tập này.'));
    }
    if (s.evaluation) {
      return of(s.evaluation).pipe(delay(50));
    }
    return throwError(() => new Error('Chưa có kết quả đánh giá cho phiên luyện tập này.'));
  }

  override getPracticeHistory(_userId?: string): Observable<PracticeSession[]> {
    return of([...this.mockSessions]).pipe(delay(200));
  }

  override saveCourse(course: Partial<Course>): Observable<Course> {
    const backendUrl = `${environment.apiBaseUrl}/courses`;
    const isUuid = course.id && course.id.includes('-') && course.id.length > 20;
    const existingCourse = course.id
      ? this.mockCourses.find((c) => c.id === course.id)
      : undefined;
    const oldCode = isUuid ? existingCourse?.code : undefined;

    const payload = {
      id: isUuid ? course.id : null,
      code: (course.code || 'IT-NEW').toUpperCase().trim(),
      name: (course.name || 'Học phần mới').trim(),
      description: (course.description || '').trim(),
      semester: (course.semester || 'Học kỳ 1 - 2026').trim(),
      department: (course.department || 'Khoa Công nghệ Thông tin').trim(),
    };

    const req$ = isUuid
      ? this.http.put<any>(`${backendUrl}/${course.id}`, payload)
      : this.http.post<any>(backendUrl, payload);

    return req$.pipe(
      map((saved) => {
        const courseObj: Course = {
          id: String(saved.id),
          code: saved.code,
          name: saved.name,
          description: saved.description || '',
          semester: saved.semester || 'Học kỳ 1 - 2026',
          department: saved.department || 'Khoa Công nghệ Thông tin',
          questionCount: saved.questionCount || 0,
          topics: saved.topics || [],
          createdBy: saved.createdBy ? String(saved.createdBy) : undefined,
          instructorName: saved.instructorName || 'TS. Nguyễn Luân (Khoa CNTT - ĐH Quy Nhơn)',
        };
        const idx = this.mockCourses.findIndex(
          (c) => c.id === courseObj.id || c.code.toUpperCase() === courseObj.code.toUpperCase(),
        );
        if (idx !== -1) {
          this.mockCourses[idx] = courseObj;
        } else {
          this.mockCourses.unshift(courseObj);
        }
        this.aiRagService
          .syncCourseFolder(courseObj.code, oldCode, courseObj.id)
          .subscribe({ error: () => {} });
        return courseObj;
      }),
      catchError((err) => {
        console.error('Lỗi khi lưu học phần vào Backend Database:', err);
        const errorMsg =
          err?.error?.message ||
          err?.message ||
          'Không thể kết nối đến Backend Database (http://localhost:8080/api/courses). Vui lòng đảm bảo Backend đã chạy.';
        return throwError(() => new Error(errorMsg));
      }),
    );
  }

  override deleteCourse(courseId: string): Observable<void> {
    const existing = this.mockCourses.find(
      (c) => c.id === courseId || c.code.toUpperCase() === courseId.toUpperCase(),
    );
    const backendUrl = `${environment.apiBaseUrl}/courses/${encodeURIComponent(courseId)}`;

    return this.http.delete<any>(backendUrl).pipe(
      map(() => {
        const targetCode = existing?.code || courseId;
        const targetId = existing?.id || courseId;
        this.mockCourses = this.mockCourses.filter(
          (c) => c.id !== targetId && c.code.toUpperCase() !== targetCode.toUpperCase(),
        );
        this.mockQuestions = this.mockQuestions.filter(
          (q) => q.courseId !== targetId && q.courseId !== targetCode,
        );
        this.aiRagService
          .deleteCourseFolder(targetCode, targetId)
          .subscribe({ error: () => {} });
        return undefined;
      }),
      catchError((err) => {
        console.error('Lỗi khi xóa học phần trong Backend Database:', err);
        const errorMsg =
          err?.error?.message ||
          err?.message ||
          'Không thể xóa học phần trong Backend Database (http://localhost:8080/api/courses).';
        return throwError(() => new Error(errorMsg));
      }),
    );
  }

  override saveQuestion(question: Partial<Question>): Observable<Question> {
    const isUuid = question.id && question.id.includes('-') && question.id.length > 20;
    const backendUrl = `${environment.apiBaseUrl}/questions`;
    const payload = {
      id: isUuid ? question.id : null,
      courseId: question.courseId,
      topic: question.topic || 'Chủ đề chung',
      title: question.title || (question.content ? question.content.substring(0, 60) + '...' : 'Câu hỏi'),
      content: question.content || '',
      sampleAnswer: question.sampleAnswer || '',
      difficulty: question.difficulty || 'medium',
      timeLimitSeconds: question.timeLimitSeconds || 180,
      tags: question.tags || [],
      parentQuestionId: question.parentQuestionId || null,
    };

    const req$ = isUuid
      ? this.http.put<any>(`${backendUrl}/${question.id}`, payload)
      : this.http.post<any>(backendUrl, payload);

    return req$.pipe(
      map((saved) => {
        const q = this.mapServerQuestion(saved);
        const idx = this.mockQuestions.findIndex((item) => item.id === q.id);
        if (idx !== -1) {
          this.mockQuestions[idx] = q;
        } else {
          this.mockQuestions.unshift(q);
        }
        return q;
      }),
      catchError((err) => {
        console.error('Lỗi khi lưu câu hỏi vào Backend Database:', err);
        const errorMsg =
          err?.error?.message ||
          err?.message ||
          'Không thể lưu câu hỏi vào Backend Database. Vui lòng kiểm tra kết nối Backend.';
        return throwError(() => new Error(errorMsg));
      }),
    );
  }

  override saveRubric(questionId: string, rubric: Rubric): Observable<Rubric> {
    const payload = {
      criteria: rubric.criteria.map((c) => ({
        name: c.name,
        description: c.description,
        maxScore: c.maxScore,
      })),
      totalScore: rubric.totalScore,
      gradingInstructions: rubric.gradingInstructions || '',
    };

    return this.http
      .put<any>(`${environment.apiBaseUrl}/questions/${questionId}/rubric`, payload)
      .pipe(
        map((res) => {
          const updatedRubric: Rubric = {
            id: String(res.id),
            questionId,
            totalScore: Number(res.totalScore) || 10.0,
            gradingInstructions: res.gradingInstructions,
            criteria: (res.criteria || []).map((c: any) => ({
              id: String(c.id),
              name: c.name,
              description: c.description,
              maxScore: Number(c.maxScore),
            })),
          };
          const q = this.mockQuestions.find((item) => item.id === questionId);
          if (q) {
            q.rubric = updatedRubric;
          }
          return updatedRubric;
        }),
        catchError((err) => {
          console.error('Lỗi khi lưu Rubric vào Backend Database:', err);
          const errorMsg =
            err?.error?.message ||
            err?.message ||
            'Không thể lưu Rubric vào Backend Database. Vui lòng kiểm tra kết nối Backend.';
          return throwError(() => new Error(errorMsg));
        }),
      );
  }

  override extractQuestionsFromFile(
    file: File,
    courseId?: string,
  ): Observable<QuestionExtractResult> {
    const formData = new FormData();
    formData.append('file', file);
    if (courseId) {
      formData.append('course_id', courseId);
    }
    const aiUrl = `${environment.aiServiceUrl || 'http://localhost:8000'}/ai/questions/extract-document`;

    return this.http.post<any>(aiUrl, formData).pipe(
      map((res) => {
        const questions: ExtractedQuestion[] = (res.questions || []).map((q: any) => ({
          tempId: q.temp_id || `temp-${Math.random().toString(36).substring(2, 7)}`,
          code: q.code || '',
          topic: q.topic || 'Chủ đề chung',
          title: q.title || (q.content ? q.content.substring(0, 60) + '...' : 'Câu hỏi'),
          content: q.content || '',
          sampleAnswer: q.sample_answer || '',
          difficulty: q.difficulty || 'medium',
          timeLimitSeconds: q.time_limit_seconds || 180,
          parentCode: q.parent_code || null,
          isFollowup: !!q.is_followup,
          tags: q.tags || [],
          criteria: (q.criteria || []).map((c: any) => ({
            name: c.name || '',
            description: c.description || '',
            maxScore: Number(c.max_score) || 2.5,
          })),
          totalScore: Number(q.total_score) || 10.0,
          status: q.status || 'valid',
          errors: q.errors || [],
          warnings: q.warnings || [],
        }));

        return {
          fileName: res.file_name || file.name,
          totalDetected: res.total_detected ?? questions.length,
          validCount: res.valid_count ?? questions.filter((x) => x.status === 'valid').length,
          errorCount: res.error_count ?? questions.filter((x) => x.status === 'error').length,
          warningCount:
            res.warning_count ?? questions.filter((x) => x.status === 'warning').length,
          questions,
        };
      }),
      catchError((err) => {
        console.error('Lỗi khi gọi AI service trích xuất tài liệu:', err);
        return throwError(
          () =>
            new Error(
              `Không thể kết nối đến AI Service (${aiUrl}). Vui lòng đảm bảo AI service đang chạy tại cổng 8000 (uvicorn app.main:app --port 8000). Chi tiết: ${err.message || 'Lỗi kết nối mạng'}`,
            ),
        );
      }),
    );
  }

  override commitBatchQuestions(
    courseId: string,
    questions: ExtractedQuestion[],
  ): Observable<{ success: boolean; importedCount: number; message: string }> {
    const payload = {
      courseId,
      questions: questions.map((q) => ({
        code: q.code,
        topic: q.topic,
        title: q.title,
        content: q.content,
        sampleAnswer: q.sampleAnswer,
        difficulty: q.difficulty,
        timeLimitSeconds: q.timeLimitSeconds,
        parentCode: q.parentCode || null,
        tags: q.tags || [],
        criteria: (q.criteria || []).map((c) => ({
          name: c.name,
          description: c.description,
          maxScore: c.maxScore,
        })),
      })),
    };

    return this.http
      .post<{ success: boolean; importedCount: number; message: string }>(
        `${environment.apiBaseUrl}/questions/import/commit`,
        payload,
      )
      .pipe(
        map((res) => {
          // Tự động đồng bộ lại danh sách câu hỏi từ database
          this.getQuestions(courseId).subscribe();
          return res;
        }),
        catchError((err) => {
          console.error('Lỗi khi commit câu hỏi vào Backend DB:', err);
          const errorMsg =
            err?.error?.message ||
            err?.message ||
            'Không thể kết nối đến Backend Database (http://localhost:8080/api/questions/import/commit). Vui lòng đảm bảo Backend đã chạy.';
          return throwError(() => new Error(errorMsg));
        }),
      );
  }

  override downloadExcelTemplate(): Observable<Blob> {
    return this.http
      .get('http://localhost:8080/api/questions/import/template', {
        responseType: 'blob',
      })
      .pipe(
        catchError(() => {
          const fallback = new Blob(
            ['Mã câu,Chương / Chủ đề,Tiêu đề tóm tắt,Nội dung câu hỏi,Câu trả lời mẫu,Độ khó,Thời gian (giây),Mã câu hỏi cha,Tiêu chí 1,Mô tả tiêu chí 1,Điểm tiêu chí 1,Tiêu chí 2,Mô tả tiêu chí 2,Điểm tiêu chí 2,Tiêu chí 3,Mô tả tiêu chí 3,Điểm tiêu chí 3\n'],
            { type: 'text/csv;charset=utf-8;' },
          );
          return of(fallback);
        }),
      );
  }
}
