import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { PracticeApi } from './practice.api';
import {
  Course,
  Question,
  Rubric,
  PracticeSession,
  Evaluation,
  ExtractedQuestion,
  QuestionExtractResult,
  InstructorPracticeRecord,
} from '../../shared/models';
import { environment } from '../../../environments/environment';

@Injectable({
  providedIn: 'root',
})
export class HttpPracticeApi extends PracticeApi {
  private http = inject(HttpClient);
  private readonly baseUrl = environment.apiBaseUrl;

  override getCourses(mineOnly = false): Observable<Course[]> {
    const query = mineOnly ? '?mineOnly=true' : '';
    return this.http.get<Course[]>(`${this.baseUrl}/courses${query}`);
  }

  override getQuestions(courseId?: string): Observable<Question[]> {
    const url = courseId
      ? `${this.baseUrl}/courses/${courseId}/questions`
      : `${this.baseUrl}/questions`;
    return this.http.get<Question[]>(url);
  }

  override getQuestion(questionId: string): Observable<Question> {
    return this.http.get<Question>(`${this.baseUrl}/questions/${questionId}`);
  }

  override createPracticeSession(questionId: string): Observable<PracticeSession> {
    return this.http.post<PracticeSession>(`${this.baseUrl}/practice/sessions`, { questionId });
  }

  override getPracticeSession(sessionId: string): Observable<PracticeSession> {
    return this.http
      .get<any>(`${this.baseUrl}/practice-records/${encodeURIComponent(sessionId)}`)
      .pipe(map((raw) => this.recordToPracticeSession(this.mapPracticeRecord(raw))));
  }

  override uploadAudio(sessionId: string, audioFile: Blob): Observable<PracticeSession> {
    const formData = new FormData();
    formData.append('file', audioFile, `recording_${sessionId}.webm`);
    return this.http
      .post<{ audioUrl: string }>(`${this.baseUrl}/practice-records/audio`, formData)
      .pipe(
        map((res) => ({
          id: sessionId,
          questionId: '',
          userId: '',
          status: 'uploaded' as const,
          audioUrl: res.audioUrl,
          isTranscriptConfirmed: false,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        })),
      );
  }

  override requestTranscription(sessionId: string): Observable<{ status: string; jobId?: string }> {
    return this.http.post<{ status: string; jobId?: string }>(
      `${this.baseUrl}/practice/sessions/${sessionId}/transcribe`,
      {},
    );
  }

  override saveConfirmedTranscript(
    sessionId: string,
    transcript: string,
  ): Observable<PracticeSession> {
    return this.http.put<PracticeSession>(
      `${this.baseUrl}/practice/sessions/${sessionId}/transcript`,
      { transcript },
    );
  }

  override requestEvaluation(
    sessionId: string,
  ): Observable<{ status: string; jobId?: string; sessionId?: string; persisted?: boolean }> {
    return this.http.post<{ status: string; jobId?: string; sessionId?: string; persisted?: boolean }>(
      `${this.baseUrl}/practice/sessions/${sessionId}/evaluate`,
      {},
    );
  }

  override getEvaluation(sessionId: string): Observable<Evaluation> {
    return this.getPracticeSession(sessionId).pipe(
      map((session) => {
        if (!session.evaluation) {
          throw new Error('Phiên luyện tập chưa có kết quả chấm điểm.');
        }
        return session.evaluation;
      }),
    );
  }

  override getPracticeHistory(_userId?: string): Observable<PracticeSession[]> {
    return this.http
      .get<any[]>(`${this.baseUrl}/practice-records/me`)
      .pipe(
        map((rows) =>
          (rows || []).map((raw) => this.recordToPracticeSession(this.mapPracticeRecord(raw))),
        ),
      );
  }

  override fetchProtectedAudioBlob(audioUrl: string): Observable<Blob> {
    const baseOrigin = this.baseUrl.replace(/\/api\/?$/, '');
    const resolvedUrl = audioUrl.startsWith('/api/') ? `${baseOrigin}${audioUrl}` : audioUrl;
    return this.http.get(resolvedUrl, { responseType: 'blob' });
  }

  override saveCourse(course: Partial<Course>): Observable<Course> {
    if (course.id) {
      return this.http.put<Course>(`${this.baseUrl}/courses/${course.id}`, course);
    }
    return this.http.post<Course>(`${this.baseUrl}/courses`, course);
  }

  override deleteCourse(courseId: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/courses/${courseId}`);
  }

  override saveQuestion(question: Partial<Question>): Observable<Question> {
    if (question.id) {
      return this.http.put<Question>(`${this.baseUrl}/questions/${question.id}`, question);
    }
    return this.http.post<Question>(`${this.baseUrl}/questions`, question);
  }

  override saveRubric(questionId: string, rubric: Rubric): Observable<Rubric> {
    return this.http.put<Rubric>(`${this.baseUrl}/questions/${questionId}/rubric`, rubric);
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
          title: q.title || '',
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
          aiGeneratedAnswer: !!q.ai_generated_answer,
          aiGeneratedRubric: !!q.ai_generated_rubric,
          instructorApproved: false,
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
        tags: q.tags,
        criteria: q.criteria.map((c) => ({
          name: c.name,
          description: c.description,
          maxScore: c.maxScore,
        })),
      })),
    };
    return this.http.post<{ success: boolean; importedCount: number; message: string }>(
      `${this.baseUrl}/questions/import/commit`,
      payload,
    );
  }

  override downloadExcelTemplate(): Observable<Blob> {
    return this.http.get(`${this.baseUrl}/questions/import/template`, {
      responseType: 'blob',
    });
  }

  override getInstructorPracticeRecords(
    courseId?: string,
    needsReviewOnly?: boolean,
  ): Observable<InstructorPracticeRecord[]> {
    const queryParts: string[] = [];
    if (courseId) {
      queryParts.push(`courseId=${encodeURIComponent(courseId)}`);
    }
    if (needsReviewOnly) {
      queryParts.push('needsReviewOnly=true');
    }
    const qs = queryParts.length > 0 ? `?${queryParts.join('&')}` : '';
    return this.http
      .get<any[]>(`${this.baseUrl}/practice-records/instructor${qs}`)
      .pipe(map((rows) => (rows || []).map((r) => this.mapPracticeRecord(r))));
  }

  override reviewPracticeRecord(
    recordId: string,
    instructorScore: number,
    instructorNotes: string,
  ): Observable<InstructorPracticeRecord> {
    return this.http
      .put<any>(`${this.baseUrl}/practice-records/${encodeURIComponent(recordId)}/review`, {
        instructorScore,
        instructorNotes,
      })
      .pipe(map((r) => this.mapPracticeRecord(r)));
  }

  private mapPracticeRecord(raw: any): InstructorPracticeRecord {
    let evaluation: Evaluation | null = null;
    if (raw?.evaluationJson) {
      try {
        evaluation = JSON.parse(raw.evaluationJson) as Evaluation;
      } catch {
        evaluation = null;
      }
    }
    return {
      id: String(raw.id),
      studentId: String(raw.studentId),
      studentName: raw.studentName || 'Sinh viên',
      studentEmail: raw.studentEmail || '',
      studentCode: raw.studentCode ?? null,
      studentDepartment: raw.studentDepartment ?? null,
      courseId: raw.courseId ? String(raw.courseId) : null,
      courseCode: raw.courseCode ?? null,
      courseName: raw.courseName ?? null,
      questionId: raw.questionId ? String(raw.questionId) : null,
      questionTitle: raw.questionTitle || 'Câu hỏi vấn đáp',
      status: raw.status || 'completed',
      transcript: raw.transcript ?? null,
      audioUrl: raw.audioUrl ?? null,
      totalScore: raw.totalScore ?? null,
      maxScore: raw.maxScore ?? 10,
      needsHumanReview: Boolean(raw.needsHumanReview),
      evaluation,
      reviewedByInstructor: Boolean(raw.reviewedByInstructor),
      instructorScore: raw.instructorScore ?? null,
      instructorNotes: raw.instructorNotes ?? null,
      reviewerName: raw.reviewerName ?? null,
      reviewedAt: raw.reviewedAt ?? null,
      createdAt: raw.createdAt || new Date().toISOString(),
    };
  }

  private recordToPracticeSession(rec: InstructorPracticeRecord): PracticeSession {
    return {
      id: rec.id,
      questionId: rec.questionId || '',
      courseId: rec.courseId || rec.courseCode || undefined,
      courseCode: rec.courseCode || undefined,
      questionTitle: rec.questionTitle,
      courseName: rec.courseName || undefined,
      userId: rec.studentId,
      status: 'completed',
      audioUrl: rec.audioUrl || undefined,
      transcript: rec.transcript || undefined,
      isTranscriptConfirmed: true,
      evaluation: rec.evaluation || undefined,
      reviewedByInstructor: rec.reviewedByInstructor,
      instructorScore: rec.instructorScore ?? null,
      instructorNotes: rec.instructorNotes ?? null,
      reviewerName: rec.reviewerName ?? null,
      reviewedAt: rec.reviewedAt ?? null,
      createdAt: rec.createdAt,
      updatedAt: rec.reviewedAt || rec.createdAt,
    };
  }
}
