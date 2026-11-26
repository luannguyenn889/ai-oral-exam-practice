/// <reference types="cypress" />

export type TestRole = 'student' | 'instructor' | 'admin';

declare global {
  namespace Cypress {
    interface Chainable {
      loginAs(role: TestRole): Chainable<void>;
      stubBackendApis(): Chainable<void>;
      stubAiServiceApis(): Chainable<void>;
      mockMicrophone(): Chainable<void>;
    }
  }
}

const TEST_USERS: Record<
  TestRole,
  {
    id: string;
    name: string;
    email: string;
    role: TestRole;
    studentCode?: string;
    department?: string;
    hasPassword: boolean;
  }
> = {
  student: {
    id: 'stu-e2e-1',
    name: 'Nguyễn Văn Sinh Viên',
    email: 'student.e2e@qnu.edu.vn',
    role: 'student',
    studentCode: '4551050001',
    department: 'Công nghệ thông tin',
    hasPassword: true,
  },
  instructor: {
    id: 'inst-e2e-1',
    name: 'TS. Trần Giảng Viên',
    email: 'instructor.e2e@qnu.edu.vn',
    role: 'instructor',
    department: 'Công nghệ phần mềm',
    hasPassword: true,
  },
  admin: {
    id: 'admin-e2e-1',
    name: 'Quản trị Hệ thống',
    email: 'admin.e2e@qnu.edu.vn',
    role: 'admin',
    hasPassword: true,
  },
};

Cypress.Commands.add('loginAs', (role: TestRole) => {
  const user = TEST_USERS[role];
  cy.window().then((win) => {
    win.localStorage.setItem('oral_exam_user', JSON.stringify(user));
    win.localStorage.setItem('oral_exam_access_token', `cypress-token-${role}`);
  });
});

Cypress.Commands.add('stubBackendApis', () => {
  const apiUrl = (Cypress.expose('apiUrl') as string) || 'http://localhost:8080/api';

  cy.fixture('practice_data.json').then((pdata) => {
    cy.intercept('GET', `${apiUrl}/users/me`, (req) => {
      const auth = req.headers['authorization'] || '';
      const role: TestRole = auth.includes('instructor')
        ? 'instructor'
        : auth.includes('admin')
          ? 'admin'
          : 'student';
      const u = TEST_USERS[role];
      req.reply({
        statusCode: 200,
        body: {
          id: u.id,
          email: u.email,
          fullName: u.name,
          avatarUrl: null,
          roles: [u.role],
          studentCode: u.studentCode ?? null,
          department: u.department ?? null,
          hasPassword: true,
        },
      });
    }).as('getMe');

    cy.intercept('GET', `${apiUrl}/courses*`, {
      statusCode: 200,
      body: pdata.courses,
    }).as('getCourses');

    cy.intercept('GET', `${apiUrl}/courses/*/questions`, {
      statusCode: 200,
      body: pdata.questions,
    }).as('getCourseQuestions');

    cy.intercept('GET', `${apiUrl}/questions`, {
      statusCode: 200,
      body: pdata.questions,
    }).as('getAllQuestions');

    cy.intercept('GET', `${apiUrl}/questions/*`, (req) => {
      const id = req.url.split('/').pop()?.split('?')[0];
      const found = pdata.questions.find((q: any) => q.id === id) || pdata.questions[0];
      req.reply({ statusCode: 200, body: found });
    }).as('getQuestion');

    cy.intercept('POST', `${apiUrl}/questions`, (req) => {
      req.reply({
        statusCode: 200,
        body: {
          ...req.body,
          id: req.body?.id || 'q-created-e2e',
          createdAt: new Date().toISOString(),
        },
      });
    }).as('saveQuestion');

    cy.intercept('PUT', `${apiUrl}/questions/*`, (req) => {
      req.reply({
        statusCode: 200,
        body: { ...req.body, id: req.url.split('/').pop() },
      });
    }).as('updateQuestion');

    cy.intercept('PUT', `${apiUrl}/questions/*/rubric`, {
      statusCode: 200,
      body: { ok: true },
    }).as('saveRubric');

    cy.intercept('POST', `${apiUrl}/questions/batch`, {
      statusCode: 200,
      body: pdata.questions,
    }).as('batchImportQuestions');

    cy.intercept('POST', `${apiUrl}/practice-records/audio`, {
      statusCode: 200,
      body: { audioUrl: '/api/practice-records/audio/e2e_sample.webm' },
    }).as('uploadAudio');

    cy.intercept('POST', `${apiUrl}/practice-records`, (req) => {
      req.reply({
        statusCode: 200,
        body: {
          ...pdata.practiceRecords[0],
          ...req.body,
          id: req.body?.id || 'sess-e2e-1',
        },
      });
    }).as('createPracticeRecord');

    cy.intercept('GET', `${apiUrl}/practice-records/*`, (req) => {
      const id = req.url.split('/').pop()?.split('?')[0];
      const found =
        pdata.practiceRecords.find((r: any) => r.id === id) || pdata.practiceRecords[0];
      req.reply({ statusCode: 200, body: found });
    }).as('getPracticeRecordById');

    cy.intercept('GET', `${apiUrl}/practice-records/instructor*`, {
      statusCode: 200,
      body: pdata.practiceRecords,
    }).as('getInstructorPracticeRecords');

    cy.intercept('GET', `${apiUrl}/practice-records`, {
      statusCode: 200,
      body: pdata.practiceRecords,
    }).as('getPracticeRecords');

    cy.intercept('GET', `${apiUrl}/practice-records/me`, {
      statusCode: 200,
      body: pdata.practiceRecords,
    }).as('getMyPracticeRecords');

    cy.intercept('PUT', `${apiUrl}/practice-records/*/review`, (req) => {
      req.reply({
        statusCode: 200,
        body: {
          ...pdata.practiceRecords[0],
          reviewedByInstructor: true,
          instructorScore: req.body?.instructorScore ?? 9.0,
          instructorNotes: req.body?.instructorNotes ?? 'Tốt',
          reviewerName: 'TS. Trần Giảng Viên',
          reviewedAt: new Date().toISOString(),
        },
      });
    }).as('reviewPracticeRecord');

    cy.intercept('GET', `${apiUrl}/instructor/analytics*`, {
      statusCode: 200,
      body: pdata.instructorAnalytics,
    }).as('getInstructorAnalytics');

    cy.intercept('GET', `${apiUrl}/admin/users*`, {
      statusCode: 200,
      body: pdata.adminUsers,
    }).as('getAdminUsers');

    cy.intercept('GET', `${apiUrl}/admin/overview*`, {
      statusCode: 200,
      body: pdata.adminOverview,
    }).as('getAdminOverview');
  });
});

Cypress.Commands.add('stubAiServiceApis', () => {
  const aiUrl = (Cypress.expose('aiUrl') as string) || 'http://localhost:8000';

  cy.fixture('rag_data.json').then((rdata) => {
    cy.intercept('GET', `${aiUrl}/ai/health`, {
      statusCode: 200,
      body: {
        status: 'ok',
        service: 'ai-service',
        version: '1.0.0',
        default_stt_provider: 'groq',
        default_llm_model: 'gemini-2.5-flash',
        embedding_provider: 'e5-small',
        embedding_model: 'intfloat/multilingual-e5-small',
        gemini_key_configured: true,
        groq_key_configured: true,
      },
    }).as('aiHealth');

    cy.intercept('POST', `${aiUrl}/ai/rag/courses/sync-folder`, {
      statusCode: 200,
      body: { course_code: 'IT2030', folder_path: 'data/documents/IT2030', migrated_files: 0, status: 'ok' },
    }).as('syncCourseFolder');

    cy.intercept('GET', `${aiUrl}/ai/rag/status*`, {
      statusCode: 200,
      body: rdata.ragStatus,
    }).as('getRagStatus');

    cy.intercept('GET', `${aiUrl}/ai/rag/index/active*`, {
      statusCode: 200,
      body: null,
    }).as('getActiveIndexJob');

    cy.intercept('PUT', `${aiUrl}/ai/rag/courses/*/config`, (req) => {
      req.reply({
        statusCode: 200,
        body: {
          course_id: 'IT2030',
          embedding_provider: req.body?.embedding_provider || 'e5-small',
          chunking_strategy: req.body?.chunking_strategy || 'recursive',
          embedding_model:
            req.body?.embedding_provider === 'gemini'
              ? 'gemini-embedding-2'
              : req.body?.embedding_provider === 'e5-small'
                ? 'intfloat/multilingual-e5-small'
                : 'paraphrase-multilingual-MiniLM-L12-v2',
          reranker_provider: req.body?.reranker_provider || 'bge-m3',
          reranker_model:
            req.body?.reranker_provider === 'bge-m3'
              ? 'BAAI/bge-reranker-v2-m3'
              : 'cross-encoder/ms-marco-MiniLM-L-6-v2',
        },
      });
    }).as('updateCourseRagConfig');

    cy.intercept('POST', `${aiUrl}/ai/rag/search`, {
      statusCode: 200,
      body: rdata.searchResponse,
    }).as('ragSearch');

    cy.intercept('POST', `${aiUrl}/ai/rag/suggest-answer`, (req) => {
      const includeRubric = Boolean(req.body?.include_rubric);
      req.reply({
        statusCode: 200,
        body: {
          ...rdata.suggestAnswerResponse,
          suggested_criteria: includeRubric ? rdata.suggestRubricCriteria : [],
          used_chunk_ids:
            req.body?.selected_chunk_ids || rdata.suggestAnswerResponse.used_chunk_ids,
        },
      });
    }).as('ragSuggestAnswer');

    cy.intercept('POST', `${aiUrl}/ai/transcriptions/upload`, {
      statusCode: 200,
      body: rdata.sttResponse,
    }).as('sttUpload');

    cy.intercept('POST', `${aiUrl}/ai/transcriptions/correct`, {
      statusCode: 200,
      body: {
        raw_transcript: rdata.sttResponse.raw_transcript,
        corrected_transcript: rdata.sttResponse.corrected_transcript,
        correction_model: 'gemini-2.5-flash',
      },
    }).as('sttCorrect');

    cy.intercept('POST', `${aiUrl}/ai/evaluations`, {
      statusCode: 200,
      body: rdata.evaluationResponse,
    }).as('evaluateAnswer');

    cy.intercept('POST', `${aiUrl}/ai/questions/extract`, {
      statusCode: 200,
      body: rdata.extractQuestionsResponse,
    }).as('extractQuestions');
  });
});

Cypress.Commands.add('mockMicrophone', () => {
  cy.window().then((win) => {
    const fakeTrack = { stop: () => {}, kind: 'audio', enabled: true };
    const fakeStream = {
      getTracks: () => [fakeTrack],
      getAudioTracks: () => [fakeTrack],
    };

    Object.defineProperty(win.navigator, 'mediaDevices', {
      configurable: true,
      value: {
        getUserMedia: () => Promise.resolve(fakeStream),
      },
    });

    class FakeMediaRecorder {
      state = 'inactive';
      mimeType = 'audio/webm';
      ondataavailable: ((e: { data: Blob }) => void) | null = null;
      onstop: (() => void) | null = null;

      start() {
        this.state = 'recording';
      }

      stop() {
        this.state = 'inactive';
        const blob = new Blob([new Uint8Array(256)], { type: 'audio/webm' });
        if (this.ondataavailable) {
          this.ondataavailable({ data: blob });
        }
        if (this.onstop) {
          this.onstop();
        }
      }
    }

    (win as any).MediaRecorder = FakeMediaRecorder;
  });
});
