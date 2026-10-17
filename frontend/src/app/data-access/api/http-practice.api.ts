import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { PracticeApi } from './practice.api';
import { Course, Question, Rubric, PracticeSession, Evaluation } from '../../shared/models';
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

  override saveQuestion(question: Partial<Question>): Observable<Question> {
    if (question.id) {
      return this.http.put<Question>(`${this.baseUrl}/questions/${question.id}`, question);
    }
    return this.http.post<Question>(`${this.baseUrl}/questions`, question);
  }

  override saveRubric(questionId: string, rubric: Rubric): Observable<Rubric> {
    return this.http.put<Rubric>(`${this.baseUrl}/questions/${questionId}/rubric`, rubric);
  }
}
