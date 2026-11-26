import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpEvent, HttpEventType } from '@angular/common/http';
import { Observable, filter, map } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  AiHealthStatus,
  Evaluation,
  Question,
  RagChunkResult,
  RagSearchResponse,
  RagStatus,
  RagSuggestAnswerResponse,
} from '../../shared/models';

export interface RagUploadProgressEvent {
  phase: 'uploading' | 'processing' | 'done';
  uploadPercent: number;
  result?: {
    courseId: string;
    status: string;
    totalFiles: number;
    addedOrUpdatedChunks: number;
    totalChunks: number;
  };
}

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
  embedding_provider?: 'local' | 'e5-small' | 'gemini';
  embedding_model: string;
  reranker_provider?: 'minilm' | 'bge-m3';
  reranker_model: string;
  chunking_strategy?: string;
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
  chunking_strategy?: string;
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

export type EmbeddingProviderOption = 'local' | 'e5-small' | 'gemini';
export type ChunkingStrategyOption = 'recursive' | 'semantic' | 'legacy';
export type RerankerProviderOption = 'minilm' | 'bge-m3';

export interface RagIndexJobStatus {
  jobId: string;
  courseId: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  phase: string;
  percent: number;
  message: string;
  currentFile?: string | null;
  processedFiles: number;
  totalFiles: number;
  processedChunks: number;
  totalChunks: number;
  embeddingProvider: string;
  chunkingStrategy: string;
  elapsedSeconds: number;
  result?: {
    courseId: string;
    status: string;
    totalFiles: number;
    addedOrUpdatedChunks: number;
    removedChunks: number;
    totalChunks: number;
    embeddingModel: string;
    chunkingStrategy?: string;
  } | null;
  error?: string | null;
}

interface RawRagIndexJob {
  job_id: string;
  course_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  phase: string;
  percent: number;
  message: string;
  current_file?: string | null;
  processed_files: number;
  total_files: number;
  processed_chunks: number;
  total_chunks: number;
  embedding_provider: string;
  chunking_strategy: string;
  elapsed_seconds: number;
  result?: RawRagIndexResponse | null;
  error?: string | null;
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

  getRagStatus(
    courseId = 'IT2030',
    embeddingProvider?: EmbeddingProviderOption,
  ): Observable<RagStatus> {
    const params: Record<string, string> = { course_id: courseId };
    if (embeddingProvider) {
      params['embedding_provider'] = embeddingProvider;
    }
    return this.http
      .get<RawRagStatus>(`${this.aiUrl}/ai/rag/status`, { params })
      .pipe(
        map((res) => ({
          courseId: res.course_id,
          status: res.status,
          totalChunks: res.total_chunks,
          totalFiles: res.total_files,
          files: res.files || [],
          embeddingProvider: res.embedding_provider,
          embeddingModel: res.embedding_model,
          rerankerProvider: res.reranker_provider,
          rerankerModel: res.reranker_model,
          chunkingStrategy: res.chunking_strategy,
          hybridBm25Active: res.hybrid_bm25_active,
          searchModesAvailable: res.search_modes_available || [],
          features: res.features || [],
          error: res.error,
        })),
      );
  }

  updateCourseRagConfig(
    courseId: string,
    config: {
      embeddingProvider?: EmbeddingProviderOption;
      chunkingStrategy?: ChunkingStrategyOption;
      rerankerProvider?: RerankerProviderOption;
    },
  ): Observable<{
    courseId: string;
    embeddingProvider: EmbeddingProviderOption;
    chunkingStrategy: ChunkingStrategyOption;
    embeddingModel: string;
    rerankerProvider: RerankerProviderOption;
    rerankerModel: string;
  }> {
    return this.http
      .put<{
        course_id: string;
        embedding_provider: EmbeddingProviderOption;
        chunking_strategy: ChunkingStrategyOption;
        embedding_model: string;
        reranker_provider: RerankerProviderOption;
        reranker_model: string;
      }>(`${this.aiUrl}/ai/rag/courses/${encodeURIComponent(courseId)}/config`, {
        ...(config.embeddingProvider ? { embedding_provider: config.embeddingProvider } : {}),
        ...(config.chunkingStrategy ? { chunking_strategy: config.chunkingStrategy } : {}),
        ...(config.rerankerProvider ? { reranker_provider: config.rerankerProvider } : {}),
      })
      .pipe(
        map((res) => ({
          courseId: res.course_id,
          embeddingProvider: res.embedding_provider,
          chunkingStrategy: res.chunking_strategy,
          embeddingModel: res.embedding_model,
          rerankerProvider: res.reranker_provider,
          rerankerModel: res.reranker_model,
        })),
      );
  }

  indexCourseDocuments(
    courseId = 'IT2030',
    forceReindex = false,
    embeddingProvider?: EmbeddingProviderOption,
    chunkingStrategy?: ChunkingStrategyOption,
  ): Observable<{
    courseId: string;
    status: string;
    totalFiles: number;
    addedOrUpdatedChunks: number;
    totalChunks: number;
    embeddingModel: string;
    chunkingStrategy?: string;
  }> {
    return this.http
      .post<RawRagIndexResponse>(`${this.aiUrl}/ai/rag/index`, {
        course_id: courseId,
        force_reindex: forceReindex,
        ...(embeddingProvider ? { embedding_provider: embeddingProvider } : {}),
        ...(chunkingStrategy ? { chunking_strategy: chunkingStrategy } : {}),
      })
      .pipe(
        map((res) => ({
          courseId: res.course_id,
          status: res.status,
          totalFiles: res.total_files,
          addedOrUpdatedChunks: res.added_or_updated_chunks,
          totalChunks: res.total_chunks,
          embeddingModel: res.embedding_model,
          chunkingStrategy: res.chunking_strategy,
        })),
      );
  }

  private mapIndexJob(res: RawRagIndexJob): RagIndexJobStatus {
    return {
      jobId: res.job_id,
      courseId: res.course_id,
      status: res.status,
      phase: res.phase,
      percent: Number(res.percent) || 0,
      message: res.message || '',
      currentFile: res.current_file ?? null,
      processedFiles: Number(res.processed_files) || 0,
      totalFiles: Number(res.total_files) || 0,
      processedChunks: Number(res.processed_chunks) || 0,
      totalChunks: Number(res.total_chunks) || 0,
      embeddingProvider: res.embedding_provider,
      chunkingStrategy: res.chunking_strategy,
      elapsedSeconds: Number(res.elapsed_seconds) || 0,
      result: res.result
        ? {
            courseId: res.result.course_id,
            status: res.result.status,
            totalFiles: res.result.total_files,
            addedOrUpdatedChunks: res.result.added_or_updated_chunks,
            removedChunks: res.result.removed_chunks,
            totalChunks: res.result.total_chunks,
            embeddingModel: res.result.embedding_model,
            chunkingStrategy: res.result.chunking_strategy,
          }
        : null,
      error: res.error ?? null,
    };
  }

  startIndexCourseDocumentsJob(
    courseId = 'IT2030',
    forceReindex = false,
    embeddingProvider?: EmbeddingProviderOption,
    chunkingStrategy?: ChunkingStrategyOption,
  ): Observable<RagIndexJobStatus> {
    return this.http
      .post<RawRagIndexJob>(`${this.aiUrl}/ai/rag/index/start`, {
        course_id: courseId,
        force_reindex: forceReindex,
        ...(embeddingProvider ? { embedding_provider: embeddingProvider } : {}),
        ...(chunkingStrategy ? { chunking_strategy: chunkingStrategy } : {}),
      })
      .pipe(map((res) => this.mapIndexJob(res)));
  }

  getIndexJobStatus(jobId: string): Observable<RagIndexJobStatus> {
    return this.http
      .get<RawRagIndexJob>(`${this.aiUrl}/ai/rag/index/jobs/${encodeURIComponent(jobId)}`)
      .pipe(map((res) => this.mapIndexJob(res)));
  }

  getActiveIndexJob(
    courseId: string,
    embeddingProvider?: EmbeddingProviderOption,
  ): Observable<RagIndexJobStatus | null> {
    const params: Record<string, string> = { course_id: courseId };
    if (embeddingProvider) {
      params['embedding_provider'] = embeddingProvider;
    }
    return this.http
      .get<RawRagIndexJob | null>(`${this.aiUrl}/ai/rag/index/active`, { params })
      .pipe(map((res) => (res ? this.mapIndexJob(res) : null)));
  }

  uploadCourseDocument(
    courseId: string,
    file: File,
    forceReindex = false,
    embeddingProvider?: EmbeddingProviderOption,
    chunkingStrategy?: ChunkingStrategyOption,
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
    if (embeddingProvider) {
      formData.append('embedding_provider', embeddingProvider);
    }
    if (chunkingStrategy) {
      formData.append('chunking_strategy', chunkingStrategy);
    }
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

  uploadCourseDocumentWithProgress(
    courseId: string,
    file: File,
    forceReindex = false,
    embeddingProvider?: EmbeddingProviderOption,
    chunkingStrategy?: ChunkingStrategyOption,
  ): Observable<RagUploadProgressEvent> {
    const formData = new FormData();
    formData.append('course_id', courseId);
    formData.append('force_reindex', String(forceReindex));
    if (embeddingProvider) {
      formData.append('embedding_provider', embeddingProvider);
    }
    if (chunkingStrategy) {
      formData.append('chunking_strategy', chunkingStrategy);
    }
    formData.append('file', file, file.name);

    return this.http
      .post<RawRagIndexResponse>(`${this.aiUrl}/ai/rag/upload`, formData, {
        reportProgress: true,
        observe: 'events',
      })
      .pipe(
        map((event: HttpEvent<RawRagIndexResponse>): RagUploadProgressEvent | null => {
          if (event.type === HttpEventType.Sent) {
            return { phase: 'uploading', uploadPercent: 0 };
          }
          if (event.type === HttpEventType.UploadProgress) {
            const pct = event.total
              ? Math.min(100, Math.round((100 * event.loaded) / event.total))
              : 0;
            return {
              phase: pct >= 100 ? 'processing' : 'uploading',
              uploadPercent: pct,
            };
          }
          if (event.type === HttpEventType.Response && event.body) {
            const res = event.body;
            return {
              phase: 'done',
              uploadPercent: 100,
              result: {
                courseId: res.course_id,
                status: res.status,
                totalFiles: res.total_files,
                addedOrUpdatedChunks: res.added_or_updated_chunks,
                totalChunks: res.total_chunks,
              },
            };
          }
          return null;
        }),
        filter((ev): ev is RagUploadProgressEvent => ev !== null),
      );
  }

  getServerDocumentUrl(courseId: string, filename: string): string {
    return `${this.aiUrl}/ai/rag/documents/${encodeURIComponent(courseId)}/${encodeURIComponent(filename)}`;
  }

  previewCourseDocument(
    courseId: string,
    filename: string,
  ): Observable<{
    courseId: string;
    filename: string;
    sizeBytes: number;
    totalChars: number;
    content: string;
  }> {
    return this.http
      .get<{
        course_id: string;
        filename: string;
        size_bytes: number;
        total_chars: number;
        content: string;
      }>(
        `${this.aiUrl}/ai/rag/documents/${encodeURIComponent(courseId)}/${encodeURIComponent(filename)}/preview`,
      )
      .pipe(
        map((res) => ({
          courseId: res.course_id,
          filename: res.filename,
          sizeBytes: res.size_bytes,
          totalChars: res.total_chars,
          content: res.content,
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

  syncCourseFolder(
    courseCode: string,
    oldCode?: string,
    legacyId?: string,
  ): Observable<{
    course_code: string;
    folder_path: string;
    migrated_files: number;
    status: string;
  }> {
    return this.http.post<{
      course_code: string;
      folder_path: string;
      migrated_files: number;
      status: string;
    }>(`${this.aiUrl}/ai/rag/courses/sync-folder`, {
      course_code: courseCode,
      old_code: oldCode || null,
      legacy_id: legacyId || null,
    });
  }

  deleteCourseFolder(
    courseCode: string,
    legacyId?: string,
  ): Observable<{
    course_code: string;
    deleted_dirs: number;
    removed_chunks: number;
    status: string;
  }> {
    const params: Record<string, string> = {};
    if (legacyId) {
      params['legacy_id'] = legacyId;
    }
    return this.http.delete<{
      course_code: string;
      deleted_dirs: number;
      removed_chunks: number;
      status: string;
    }>(`${this.aiUrl}/ai/rag/courses/${encodeURIComponent(courseCode)}`, { params });
  }

  searchCourseDocuments(params: {
    courseId: string;
    queryText: string;
    topK?: number;
    searchMode?: 'hybrid' | 'dense' | 'bm25';
    useRerank?: boolean;
    embeddingProvider?: EmbeddingProviderOption;
  }): Observable<RagSearchResponse> {
    return this.http
      .post<RawRagSearchResponse>(`${this.aiUrl}/ai/rag/search`, {
        course_id: params.courseId,
        query_text: params.queryText,
        top_k: params.topK ?? 3,
        search_mode: params.searchMode ?? 'hybrid',
        use_rerank: params.useRerank ?? false,
        ...(params.embeddingProvider ? { embedding_provider: params.embeddingProvider } : {}),
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

  suggestReferenceAnswer(params: {
    courseId: string;
    question: string;
    topic?: string;
    referenceAnswer?: string;
    topK?: number;
    searchMode?: 'hybrid' | 'dense' | 'bm25';
    includeRubric?: boolean;
    selectedChunkIds?: string[];
    embeddingProvider?: EmbeddingProviderOption;
    rerankerProvider?: RerankerProviderOption;
  }): Observable<RagSuggestAnswerResponse> {
    return this.http
      .post<{
        course_id: string;
        sample_answer: string;
        suggested_criteria: {
          name: string;
          description: string;
          max_score: number;
        }[];
        rag_references: RawRagSearchResponse['results'];
        used_chunk_ids: string[];
        embedding_provider?: string;
        embedding_model?: string;
        reranker_provider?: string;
        reranker_model?: string;
        llm_model: string;
        status: 'ai_draft';
        notice: string;
      }>(`${this.aiUrl}/ai/rag/suggest-answer`, {
        course_id: params.courseId,
        question: params.question,
        topic: params.topic || null,
        reference_answer: params.referenceAnswer || null,
        top_k: params.topK ?? 4,
        search_mode: params.searchMode ?? 'hybrid',
        include_rubric: params.includeRubric ?? false,
        ...(params.selectedChunkIds !== undefined
          ? { selected_chunk_ids: params.selectedChunkIds }
          : {}),
        ...(params.embeddingProvider ? { embedding_provider: params.embeddingProvider } : {}),
        ...(params.rerankerProvider ? { reranker_provider: params.rerankerProvider } : {}),
      })
      .pipe(
        map((res) => ({
          courseId: res.course_id,
          sampleAnswer: res.sample_answer || '',
          suggestedCriteria: (res.suggested_criteria || []).map((c) => ({
            name: c.name,
            description: c.description || '',
            maxScore: Number(c.max_score) || 0,
          })),
          ragReferences: (res.rag_references || []).map(
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
          usedChunkIds: res.used_chunk_ids || [],
          embeddingProvider: res.embedding_provider,
          embeddingModel: res.embedding_model,
          rerankerProvider: res.reranker_provider,
          rerankerModel: res.reranker_model,
          llmModel: res.llm_model,
          status: res.status || 'ai_draft',
          notice: res.notice || '',
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
    embeddingProvider?: EmbeddingProviderOption;
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
          ...(params.embeddingProvider ? { embedding_provider: params.embeddingProvider } : {}),
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

