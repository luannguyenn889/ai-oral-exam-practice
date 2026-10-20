import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  AiHealthStatus,
  Evaluation,
  Question,
  RagChunkResult,
  RagSearchResponse,
  RagStatus,
} from '../../shared/models';

interface RawAiHealth {
  status: string;
  service: string;
  version: string;
  default_stt_provider: string;
  default_llm_model: string;
  embedding_provider: string;
  embedding_model: string;
  gemini_key_configured: boolean;
  groq_key_configured: boolean;
}

interface RawRagStatus {
  course_id: string;
  status: string;
  total_chunks: number;
  total_files: number;
  files: string[];
  embedding_model: string;
  reranker_model: string;
  hybrid_bm25_active: boolean;
  search_modes_available: string[];
  features: string[];
  error?: string | null;
}

interface RawRagIndexResponse {
  course_id: string;
  status: string;
  total_files: number;
  added_or_updated_chunks: number;
  removed_chunks: number;
  total_chunks: number;
  embedding_model: string;
}

interface RawRagSearchResponse {
  course_id: string;
  query_text: string;
  cleaned_query: string;
  search_mode: string;
  top_k: number;
  results: {
    chunk_id: string;
    source: string;
    course_id: string;
    index: number;
    text: string;
    retrieved_by: string;
    dense_sim?: number | null;
    bm25_score?: number | null;
    rrf_score: number;
    rerank_score?: number | null;
    method: string;
  }[];
  formatted_context: string;
}

export interface SttPipelineResult {
  rawTranscript: string;
  correctedTranscript: string;
  durationSeconds: number;
  sttModel: string;
  correctionModel: string;
  processingTimeMs: number;
}

@Injectable({
  providedIn: 'root',
})
export class AiRagService {
  private http = inject(HttpClient);
  private readonly aiUrl = environment.aiServiceUrl || 'http://localhost:8000';

  getHealth(): Observable<AiHealthStatus> {
    return this.http.get<RawAiHealth>(`${this.aiUrl}/ai/health`).pipe(
      map((res) => ({
        status: res.status,
        service: res.service,
        version: res.version,
        defaultSttProvider: res.default_stt_provider,
        defaultLlmModel: res.default_llm_model,
        embeddingProvider: res.embedding_provider,
        embeddingModel: res.embedding_model,
        geminiKeyConfigured: res.gemini_key_configured,
        groqKeyConfigured: res.groq_key_configured,
      })),
    );
  }

  getRagStatus(courseId = 'IT2030'): Observable<RagStatus> {
    return this.http
      .get<RawRagStatus>(`${this.aiUrl}/ai/rag/status`, {
        params: { course_id: courseId },
      })
      .pipe(
        map((res) => ({
          courseId: res.course_id,
          status: res.status,
          totalChunks: res.total_chunks,
          totalFiles: res.total_files,
          files: res.files || [],
          embeddingModel: res.embedding_model,
          rerankerModel: res.reranker_model,
          hybridBm25Active: res.hybrid_bm25_active,
          searchModesAvailable: res.search_modes_available || [],
          features: res.features || [],
          error: res.error,
        })),
      );
  }

  indexCourseDocuments(
    courseId = 'IT2030',
    forceReindex = false,
  ): Observable<{
    courseId: string;
    status: string;
    totalFiles: number;
    addedOrUpdatedChunks: number;
    totalChunks: number;
    embeddingModel: string;
  }> {
    return this.http
      .post<RawRagIndexResponse>(`${this.aiUrl}/ai/rag/index`, {
        course_id: courseId,
        force_reindex: forceReindex,
      })
      .pipe(
        map((res) => ({
          courseId: res.course_id,
          status: res.status,
          totalFiles: res.total_files,
          addedOrUpdatedChunks: res.added_or_updated_chunks,
          totalChunks: res.total_chunks,
          embeddingModel: res.embedding_model,
        })),
      );
  }

  uploadCourseDocument(
    courseId: string,
    file: File,
    forceReindex = false,
  ): Observable<{
    courseId: string;
    status: string;
    totalFiles: number;
    addedOrUpdatedChunks: number;
    totalChunks: number;
  }> {
    const formData = new FormData();
    formData.append('course_id', courseId);
    formData.append('force_reindex', String(forceReindex));
    formData.append('file', file, file.name);
    return this.http.post<RawRagIndexResponse>(`${this.aiUrl}/ai/rag/upload`, formData).pipe(
      map((res) => ({
        courseId: res.course_id,
        status: res.status,
        totalFiles: res.total_files,
        addedOrUpdatedChunks: res.added_or_updated_chunks,
        totalChunks: res.total_chunks,
      })),
    );
  }

  deleteCourseDocument(
    courseId: string,
    filename: string,
  ): Observable<{
    courseId: string;
    status: string;
    totalFiles: number;
    totalChunks: number;
  }> {
    return this.http
      .delete<RawRagIndexResponse>(
        `${this.aiUrl}/ai/rag/documents/${encodeURIComponent(courseId)}/${encodeURIComponent(filename)}`,
      )
      .pipe(
        map((res) => ({
          courseId: res.course_id,
          status: res.status,
          totalFiles: res.total_files,
          totalChunks: res.total_chunks,
        })),
      );
  }

  searchCourseDocuments(params: {
    courseId: string;
    queryText: string;
    topK?: number;
    searchMode?: 'hybrid' | 'dense' | 'bm25';
    useRerank?: boolean;
  }): Observable<RagSearchResponse> {
    return this.http
      .post<RawRagSearchResponse>(`${this.aiUrl}/ai/rag/search`, {
        course_id: params.courseId,
        query_text: params.queryText,
        top_k: params.topK ?? 3,
        search_mode: params.searchMode ?? 'hybrid',
        use_rerank: params.useRerank ?? false,
      })
      .pipe(
        map((res) => ({
          courseId: res.course_id,
          queryText: res.query_text,
          cleanedQuery: res.cleaned_query,
          searchMode: res.search_mode,
          topK: res.top_k,
          results: (res.results || []).map(
            (r): RagChunkResult => ({
              chunkId: r.chunk_id,
              source: r.source,
              courseId: r.course_id,
              index: r.index,
              text: r.text,
              retrievedBy: r.retrieved_by,
              denseSim: r.dense_sim,
              bm25Score: r.bm25_score,
              rrfScore: r.rrf_score,
              rerankScore: r.rerank_score,
              method: r.method,
            }),
          ),
          formattedContext: res.formatted_context,
        })),
      );
  }

  transcribeUploadedAudio(
    audioBlob: Blob,
    questionText: string,
    rubricSummary: string,
    sttProvider: 'groq' | 'gemini' | 'mock' = 'groq',
    enableSpellCorrection = true,
  ): Observable<SttPipelineResult> {
    const formData = new FormData();
    const ext = audioBlob.type.includes('wav')
      ? 'wav'
      : audioBlob.type.includes('mp3') || audioBlob.type.includes('mpeg')
        ? 'mp3'
        : 'webm';
    formData.append('file', audioBlob, `recording.${ext}`);
    formData.append('question_text', questionText);
    formData.append('rubric_summary', rubricSummary);
    formData.append('stt_provider', sttProvider);
    formData.append('enable_spell_correction', String(enableSpellCorrection));

    return this.http
      .post<{
        raw_transcript: string;
        corrected_transcript: string;
        duration_seconds: number;
        stt_model: string;
        correction_model: string;
        processing_time_ms: number;
      }>(`${this.aiUrl}/ai/transcriptions/upload`, formData)
      .pipe(
        map((res) => ({
          rawTranscript: res.raw_transcript,
          correctedTranscript: res.corrected_transcript,
          durationSeconds: res.duration_seconds,
          sttModel: res.stt_model,
          correctionModel: res.correction_model,
          processingTimeMs: res.processing_time_ms,
        })),
      );
  }

  correctTranscript(
    transcript: string,
    questionText: string,
    rubricSummary: string,
  ): Observable<{ rawTranscript: string; correctedTranscript: string; correctionModel: string }> {
    return this.http
      .post<{
        raw_transcript: string;
        corrected_transcript: string;
        correction_model: string;
      }>(`${this.aiUrl}/ai/transcriptions/correct`, {
        transcript,
        question_text: questionText,
        rubric_summary: rubricSummary,
        correction_model: 'gemini-2.5-flash',
      })
      .pipe(
        map((res) => ({
          rawTranscript: res.raw_transcript,
          correctedTranscript: res.corrected_transcript,
          correctionModel: res.correction_model,
        })),
      );
  }

  evaluateSubmission(params: {
    sessionId: string;
    courseId: string;
    question: Question;
    transcript: string;
    enableRag?: boolean;
    searchMode?: 'hybrid' | 'dense' | 'bm25';
    topK?: number;
  }): Observable<Evaluation> {
    const rubricItems = (params.question.rubric?.criteria || []).map((c) => ({
      criterion_id: c.id,
      name: c.name,
      description: c.description,
      max_score: c.maxScore,
    }));

    return this.http
      .post<{
        total_score: number;
        max_score: number;
        summary: string;
        criteria: {
          criterion_id: string;
          score: number;
          max_score: number;
          evidence: string;
          missing_or_incorrect: string[];
          feedback: string;
        }[];
        strengths: string[];
        weaknesses: string[];
        improvements: string[];
        uncertainty_notes: string[];
        needs_human_review: boolean;
        rag_references: {
          chunk_id: string;
          source: string;
          retrieved_by: string;
          dense_sim?: number | null;
          rrf_score: number;
          text_preview: string;
        }[];
        metadata: {
          llm_model: string;
          embedding_model: string;
          processing_time_ms: number;
        };
      }>(`${this.aiUrl}/ai/evaluations`, {
        session_id: params.sessionId,
        course_id: params.courseId || 'IT2030',
        question: params.question.content,
        reference_answer: params.question.sampleAnswer || '',
        transcript: params.transcript,
        rubric: rubricItems,
        rag_config: {
          enabled: params.enableRag ?? true,
          search_mode: params.searchMode ?? 'hybrid',
          top_k: params.topK ?? 3,
        },
        llm_model: 'gemini-2.5-flash',
      })
      .pipe(
        map((res) => ({
          totalScore: res.total_score,
          maxScore: res.max_score,
          summary: res.summary,
          criteria: (res.criteria || []).map((c) => ({
            criterionId: c.criterion_id,
            score: c.score,
            maxScore: c.max_score,
            evidence: c.evidence,
            missingOrIncorrect: c.missing_or_incorrect || [],
            feedback: c.feedback,
          })),
          strengths: res.strengths || [],
          weaknesses: res.weaknesses || [],
          improvements: res.improvements || [],
          uncertaintyNotes: res.uncertainty_notes || [],
          needsHumanReview: res.needs_human_review,
          ragReferences: (res.rag_references || []).map((r) => ({
            chunkId: r.chunk_id,
            source: r.source,
            retrievedBy: r.retrieved_by,
            denseSim: r.dense_sim,
            rrfScore: r.rrf_score,
            textPreview: r.text_preview,
          })),
          llmModel: res.metadata?.llm_model,
          embeddingModel: res.metadata?.embedding_model,
          processingTimeMs: res.metadata?.processing_time_ms,
        })),
      );
  }
}

