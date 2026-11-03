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
} from '../../shared/models';
import { environment } from '../../../environments/environment';

@Injectable({
  providedIn: 'root',
})
export class HttpPracticeApi extends PracticeApi {
  private http = inject(HttpClient);
  private readonly baseUrl = environment.apiBaseUrl;

  override getCourses(): Observable<Course[]> {
    return this.http.get<Course[]>(`${this.baseUrl}/courses`);
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
    return this.http.get<PracticeSession>(`${this.baseUrl}/practice/sessions/${sessionId}`);
  }

  override uploadAudio(sessionId: string, audioFile: Blob): Observable<PracticeSession> {
    const formData = new FormData();
    formData.append('audio', audioFile, 'recording.webm');
    return this.http.post<PracticeSession>(
      `${this.baseUrl}/practice/sessions/${sessionId}/audio`,
      formData,
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

  override requestEvaluation(sessionId: string): Observable<{ status: string; jobId?: string }> {
    return this.http.post<{ status: string; jobId?: string }>(
      `${this.baseUrl}/practice/sessions/${sessionId}/evaluate`,
      {},
    );
  }

  override getEvaluation(sessionId: string): Observable<Evaluation> {
    return this.http.get<Evaluation>(`${this.baseUrl}/practice/sessions/${sessionId}/evaluation`);
  }

  override getPracticeHistory(userId?: string): Observable<PracticeSession[]> {
    const url = userId
      ? `${this.baseUrl}/practice/history?userId=${userId}`
      : `${this.baseUrl}/practice/history`;
    return this.http.get<PracticeSession[]>(url);
  }

  override saveCourse(course: Partial<Course>): Observable<Course> {
    if (course.id) {
      return this.http.put<Course>(`${this.baseUrl}/courses/${course.id}`, course);
    }
    return this.http.post<Course>(`${this.baseUrl}/courses`, course);
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
}
