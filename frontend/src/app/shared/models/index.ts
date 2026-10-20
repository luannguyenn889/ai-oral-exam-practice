// Models defined according to KE_HOACH_FRONTEND_ANGULAR.md, QUY_TAC_THIET_KE_FE.md, and KE_HOACH_GIAO_DIEN_THEO_VAI_TRO_AI_RAG.md

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

export type UserRole = 'student' | 'instructor' | 'admin';

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

export interface RagReference {
  chunkId: string;
  source: string;
  retrievedBy: string;
  denseSim?: number | null;
  rrfScore: number;
  textPreview: string;
}

export interface Evaluation {
  totalScore: number;
  maxScore: number;
  summary?: string;
  criteria: CriterionEvaluation[];
  strengths: string[];
  weaknesses?: string[];
  improvements: string[];
  uncertaintyNotes: string[];
  needsHumanReview: boolean;
  ragReferences?: RagReference[];
  llmModel?: string;
  embeddingModel?: string;
  processingTimeMs?: number;
}

export interface PracticeSession {
  id: string;
  questionId: string;
  courseId?: string;
  questionTitle?: string;
  courseName?: string;
  userId: string;
  status: PracticeStatus;
  audioDurationSeconds?: number;
  audioUrl?: string;
  rawTranscript?: string;
  transcript?: string;
  sttModel?: string;
  correctionModel?: string;
  isTranscriptConfirmed: boolean;
  evaluation?: Evaluation;
  createdAt: string;
  updatedAt: string;
}

export interface RagStatus {
  courseId: string;
  status: string;
  totalChunks: number;
  totalFiles: number;
  files: string[];
  embeddingModel: string;
  rerankerModel: string;
  hybridBm25Active: boolean;
  searchModesAvailable: string[];
  features: string[];
  error?: string | null;
}

export interface RagChunkResult {
  chunkId: string;
  source: string;
  courseId: string;
  index: number;
  text: string;
  retrievedBy: string;
  denseSim?: number | null;
  bm25Score?: number | null;
  rrfScore: number;
  rerankScore?: number | null;
  method: string;
}

export interface RagSearchResponse {
  courseId: string;
  queryText: string;
  cleanedQuery: string;
  searchMode: string;
  topK: number;
  results: RagChunkResult[];
  formattedContext: string;
}

export interface AiHealthStatus {
  status: string;
  service: string;
  version: string;
  defaultSttProvider: string;
  defaultLlmModel: string;
  embeddingProvider: string;
  embeddingModel: string;
  geminiKeyConfigured: boolean;
  groqKeyConfigured: boolean;
}

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  timestamp: string;
}
