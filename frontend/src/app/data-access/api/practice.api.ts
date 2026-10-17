import { Observable } from 'rxjs';
import { Course, Question, Rubric, PracticeSession, Evaluation } from '../../shared/models';

export abstract class PracticeApi {
  abstract getCourses(): Observable<Course[]>;
  abstract getQuestions(courseId?: string): Observable<Question[]>;
  abstract getQuestion(questionId: string): Observable<Question>;
  abstract createPracticeSession(questionId: string): Observable<PracticeSession>;
  abstract getPracticeSession(sessionId: string): Observable<PracticeSession>;
  abstract uploadAudio(sessionId: string, audioFile: Blob): Observable<PracticeSession>;
  abstract requestTranscription(sessionId: string): Observable<{ status: string; jobId?: string }>;
  abstract saveConfirmedTranscript(
    sessionId: string,
    transcript: string,
  ): Observable<PracticeSession>;
  abstract requestEvaluation(sessionId: string): Observable<{ status: string; jobId?: string }>;
  abstract getEvaluation(sessionId: string): Observable<Evaluation>;
  abstract getPracticeHistory(userId?: string): Observable<PracticeSession[]>;
  abstract saveQuestion(question: Partial<Question>): Observable<Question>;
  abstract saveRubric(questionId: string, rubric: Rubric): Observable<Rubric>;
}
