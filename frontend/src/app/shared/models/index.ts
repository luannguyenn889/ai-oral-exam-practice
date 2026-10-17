// Models defined according to KE_HOACH_FRONTEND_ANGULAR.md and QUY_TAC_THIET_KE_FE.md

export type PracticeStatus =
  | 'draft'
  | 'recording'
  | 'uploaded'
  | 'transcribing'
  | 'transcript_review'
  | 'grading'
  | 'completed'
  | 'transcription_failed'
  | 'grading_failed'
  | 'cancelled';

export type UserRole = 'student' | 'instructor';

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  avatarUrl?: string;
}

export interface Course {
  id: string;
  code: string;
  name: string;
  description: string;
  instructorName?: string;
  questionCount: number;
  semester?: string;
  department?: string;
  topics?: string[];
}

export interface RubricCriterion {
  id: string;
  name: string;
  description: string;
  maxScore: number;
}

export interface Rubric {
  id: string;
  questionId: string;
  criteria: RubricCriterion[];
  totalScore: number;
}

export interface Question {
  id: string;
  courseId: string;
  topic?: string;
  title: string;
  content: string;
  sampleAnswer?: string;
  rubric?: Rubric;
  timeLimitSeconds?: number;
  difficulty?: 'easy' | 'medium' | 'hard';
  tags?: string[];
}

export interface CriterionEvaluation {
  criterionId: string;
  score: number;
  maxScore: number;
  evidence: string;
  missingOrIncorrect: string[];
  feedback: string;
}

export interface Evaluation {
  totalScore: number;
  maxScore: number;
  criteria: CriterionEvaluation[];
  strengths: string[];
  improvements: string[];
  uncertaintyNotes: string[];
  needsHumanReview: boolean;
}

export interface PracticeSession {
  id: string;
  questionId: string;
  questionTitle?: string;
  courseName?: string;
  userId: string;
  status: PracticeStatus;
  audioDurationSeconds?: number;
  audioUrl?: string;
  transcript?: string;
  isTranscriptConfirmed: boolean;
  evaluation?: Evaluation;
  createdAt: string;
  updatedAt: string;
}

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  timestamp: string;
}
