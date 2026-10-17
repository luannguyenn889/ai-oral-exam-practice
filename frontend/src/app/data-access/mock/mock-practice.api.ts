import { Injectable } from '@angular/core';
import { Observable, of, delay, throwError } from 'rxjs';
import { PracticeApi } from '../api/practice.api';
import { Course, Question, Rubric, PracticeSession, Evaluation } from '../../shared/models';

@Injectable({
  providedIn: 'root',
})
export class MockPracticeApi extends PracticeApi {
  private mockCourses: Course[] = [
    {
      id: 'course-1',
      code: 'CS101',
      name: 'Nhập môn Trí tuệ Nhân tạo',
      description:
        'Cung cấp kiến thức cơ bản về tìm kiếm heuristic, tri thức logic, học máy và mạng nơ-ron.',
      instructorName: 'TS. Nguyễn Văn A',
      questionCount: 4,
      semester: 'Học kỳ 1 - 2026',
      department: 'Khoa Khoa học Máy tính',
      topics: ['Tìm kiếm & Giải thuật', 'Học máy cơ bản', 'Mạng Nơ-ron & Deep Learning'],
    },
    {
      id: 'course-2',
      code: 'CS202',
      name: 'Kiến trúc Phần mềm',
      description:
        'Các mẫu thiết kế (Design Patterns), kiến trúc Microservices, Clean Architecture và hướng dịch vụ.',
      instructorName: 'ThS. Trần Thị B',
      questionCount: 3,
      semester: 'Học kỳ 1 - 2026',
      department: 'Khoa Kỹ thuật Phần mềm',
      topics: ['Design Patterns', 'SOLID Principles', 'Microservices Architecture'],
    },
    {
      id: 'course-3',
      code: 'CS303',
      name: 'Mạng máy tính nâng cao',
      description:
        'Giao thức truyền thông TCP/IP, phân tầng mạng, định tuyến OSPF/BGP và an toàn thông tin.',
      instructorName: 'PGS. TS. Lê Văn C',
      questionCount: 3,
      semester: 'Học kỳ 1 - 2026',
      department: 'Khoa Truyền thông & Mạng',
      topics: ['Giao thức mạng TCP/IP', 'Định tuyến & Chuyển tiếp', 'Bảo mật hạ tầng mạng'],
    },
    {
      id: 'course-4',
      code: 'CS404',
      name: 'Hệ Quản trị Cơ sở Dữ liệu',
      description:
        'Tối ưu hóa truy vấn SQL, chỉ mục (Index B-Tree), giao tác ACID và kiến trúc phân tán.',
      instructorName: 'TS. Phạm Minh D',
      questionCount: 2,
      semester: 'Học kỳ 1 - 2026',
      department: 'Khoa Hệ thống Thông tin',
      topics: ['Tối ưu truy vấn & Index', 'Giao tác & Khóa đồng thời'],
    },
  ];

  private mockQuestions: Question[] = [
    {
      id: 'q-1',
      courseId: 'course-1',
      topic: 'Học máy cơ bản',
      title: 'Phân biệt Học có giám sát và Học không giám sát',
      content:
        'Hãy trình bày định nghĩa, điểm khác biệt cốt lõi và lấy ít nhất 2 ví dụ minh họa thực tế cho Học có giám sát (Supervised Learning) và Học không giám sát (Unsupervised Learning).',
      sampleAnswer:
        'Học có giám sát dùng dữ liệu có nhãn để huấn luyện mô hình dự đoán. Học không giám sát dùng dữ liệu không gán nhãn để tìm cấu trúc ẩn như gom cụm (Clustering).',
      timeLimitSeconds: 180,
      difficulty: 'medium',
      tags: ['Machine Learning', 'Classification', 'Clustering'],
      rubric: {
        id: 'rubric-1',
        questionId: 'q-1',
        totalScore: 10,
        criteria: [
          {
            id: 'crit-1',
            name: 'Định nghĩa & Khái niệm',
            description: 'Nêu rõ ràng định nghĩa của cả hai phương pháp học.',
            maxScore: 3,
          },
          {
            id: 'crit-2',
            name: 'So sánh & Điểm khác biệt',
            description: 'Chỉ ra sự khác biệt về dữ liệu đầu vào, mục tiêu và hàm mất mát.',
            maxScore: 4,
          },
          {
            id: 'crit-3',
            name: 'Ví dụ thực tế',
            description: 'Đưa ra ít nhất 2 ví dụ thực tế cho mỗi loại.',
            maxScore: 3,
          },
        ],
      },
    },
    {
      id: 'q-2',
      courseId: 'course-1',
      topic: 'Tìm kiếm & Giải thuật',
      title: 'Thuật toán tìm kiếm A* và hàm Heuristic',
      content:
        'Giải thích nguyên lý hoạt động của giải thuật A*, công thức f(n) = g(n) + h(n) và điều kiện để Heuristic chấp nhận được (admissible) nhằm đảm bảo nghiệm tối ưu.',
      sampleAnswer:
        'A* kết hợp chi phí thực tế g(n) từ nút gốc và ước lượng h(n) tới đích. Heuristic admissible khi h(n) <= h*(n) với mọi n.',
      timeLimitSeconds: 240,
      difficulty: 'hard',
      tags: ['A-Star', 'Heuristic', 'Search Algorithms'],
      rubric: {
        id: 'rubric-2',
        questionId: 'q-2',
        totalScore: 10,
        criteria: [
          {
            id: 'crit-2-1',
            name: 'Nguyên lý và công thức f(n)',
            description: 'Giải thích đúng ý nghĩa của các thành phần g(n), h(n) và hàm f(n).',
            maxScore: 4,
          },
          {
            id: 'crit-2-2',
            name: 'Tính admissible & consistent',
            description: 'Phân tích điều kiện h(n) <= h*(n) và tính chất tam giác nhất quán.',
            maxScore: 4,
          },
          {
            id: 'crit-2-3',
            name: 'Trực giác không gian trạng thái',
            description:
              'Giải thích tại sao A* duyệt ít trạng thái hơn Dijkstra trong đồ thị có đích rõ ràng.',
            maxScore: 2,
          },
        ],
      },
    },
    {
      id: 'q-3',
      courseId: 'course-1',
      topic: 'Mạng Nơ-ron & Deep Learning',
      title: 'Vấn đề biến mất đạo hàm (Vanishing Gradient) trong Deep Neural Network',
      content:
        'Trình bày nguyên nhân gây ra hiện tượng biến mất đạo hàm khi huấn luyện mạng nơ-ron sâu với hàm Sigmoid/Tanh và các giải pháp khắc phục phổ biến (ReLU, ResNet, Batch Normalization).',
      sampleAnswer:
        'Đạo hàm của Sigmoid tối đa là 0.25, lan truyền ngược qua nhiều lớp khiến gradient tiến về 0. Khắc phục bằng ReLU, residual connection hoặc batch norm.',
      timeLimitSeconds: 200,
      difficulty: 'hard',
      tags: ['Deep Learning', 'Backpropagation', 'Activation Function'],
    },
    {
      id: 'q-4',
      courseId: 'course-1',
      topic: 'Học máy cơ bản',
      title: 'Hiện tượng Overfitting và các kỹ thuật Regularization',
      content:
        'Thế nào là Overfitting (quá khớp)? Nêu các dấu hiệu nhận biết trên tập Train/Validation và trình bày ít nhất 3 phương pháp chống overfitting.',
      timeLimitSeconds: 180,
      difficulty: 'easy',
      tags: ['Overfitting', 'Regularization', 'Dropout'],
    },
    {
      id: 'q-5',
      courseId: 'course-2',
      topic: 'SOLID Principles',
      title: 'Nguyên lý Đơn trách nhiệm (Single Responsibility Principle - SRP)',
      content:
        'Trình bày nguyên lý SRP trong bộ nguyên lý SOLID. Ý nghĩa của nguyên lý này trong việc giảm khớp nối (coupling) và tăng khả năng bảo trì phần mềm.',
      timeLimitSeconds: 150,
      difficulty: 'easy',
      tags: ['OOP', 'SOLID', 'Clean Code'],
    },
    {
      id: 'q-6',
      courseId: 'course-2',
      topic: 'Design Patterns',
      title: 'Mô hình thiết kế Observer và ứng dụng trong Event-Driven',
      content:
        'Giải thích cấu trúc mẫu thiết kế Observer (Subject, Observer). Khi nào nên áp dụng mẫu thiết kế này thay cho gọi hàm trực tiếp?',
      timeLimitSeconds: 180,
      difficulty: 'medium',
      tags: ['Design Patterns', 'Event-Driven', 'PubSub'],
    },
    {
      id: 'q-7',
      courseId: 'course-2',
      topic: 'Microservices Architecture',
      title: 'Tính nhất quán dữ liệu trong Microservices với Saga Pattern',
      content:
        'Tại sao không nên dùng Distributed Transaction (2PC) trong microservices? Phân tích cách Saga Pattern (Choreography vs Orchestration) giải quyết vấn đề này.',
      timeLimitSeconds: 240,
      difficulty: 'hard',
      tags: ['Microservices', 'Saga', 'Distributed Systems'],
    },
    {
      id: 'q-8',
      courseId: 'course-3',
      topic: 'Giao thức mạng TCP/IP',
      title: 'Cơ chế bắt tay 3 bước (Three-way Handshake) của giao thức TCP',
      content:
        'Mô tả chi tiết quá trình bắt tay 3 bước (SYN, SYN-ACK, ACK) khi thiết lập kết nối TCP. Mục đích của việc trao đổi Initial Sequence Number (ISN) là gì?',
      timeLimitSeconds: 180,
      difficulty: 'easy',
      tags: ['TCP', 'Handshake', 'Networking'],
    },
  ];

  private mockSessions: PracticeSession[] = [
    {
      id: 'session-demo-1',
      questionId: 'q-1',
      questionTitle: 'Phân biệt Học có giám sát và Học không giám sát',
      courseName: 'Nhập môn Trí tuệ Nhân tạo',
      userId: 'user-student-1',
      status: 'completed',
      audioDurationSeconds: 115,
      transcript:
        'Học có giám sát là phương pháp máy học trong đó tập dữ liệu huấn luyện đã được gán nhãn trước. Mục tiêu là tìm hàm ánh xạ từ đầu vào sang đầu ra. Ví dụ như phân loại email spam và dự đoán giá nhà. Còn học không giám sát thì dữ liệu không có nhãn, hệ thống tự phát hiện quy luật hoặc cụm dữ liệu, ví dụ phân khúc khách hàng bằng K-Means.',
      isTranscriptConfirmed: true,
      evaluation: {
        totalScore: 8.5,
        maxScore: 10,
        criteria: [
          {
            criterionId: 'crit-1',
            score: 3.0,
            maxScore: 3,
            evidence: 'Đã nêu chính xác định nghĩa học có giám sát và không giám sát.',
            missingOrIncorrect: [],
            feedback: 'Nắm vững khái niệm cơ bản.',
          },
          {
            criterionId: 'crit-2',
            score: 3.0,
            maxScore: 4,
            evidence: 'Đã phân biệt được về mặt nhãn dữ liệu và mục tiêu ánh xạ.',
            missingOrIncorrect: ['Chưa giải thích rõ về hàm mục tiêu hoặc hàm mất mát tương ứng.'],
            feedback: 'Cần phân tích sâu hơn khía cạnh toán học/thuật toán.',
          },
          {
            criterionId: 'crit-3',
            score: 2.5,
            maxScore: 3,
            evidence: 'Đã nêu ví dụ spam email, giá nhà, phân khúc khách hàng.',
            missingOrIncorrect: ['Cần bổ sung thêm ví dụ thứ hai cho học không giám sát.'],
            feedback: 'Ví dụ sát thực tế và đúng ngữ cảnh.',
          },
        ],
        strengths: ['Trình bày mạch lạc, tự tin.', 'Nắm đúng bản chất phân loại bài toán học máy.'],
        improvements: [
          'Bổ sung phân tích về hàm mất mát và tối ưu hóa.',
          'Nêu thêm các thuật toán tiêu biểu (SVM, Random Forest, PCA).',
        ],
        uncertaintyNotes: [],
        needsHumanReview: false,
      },
      createdAt: new Date(Date.now() - 3600 * 1000 * 24).toISOString(),
      updatedAt: new Date(Date.now() - 3600 * 1000 * 24).toISOString(),
    },
  ];

  override getCourses(): Observable<Course[]> {
    return of([...this.mockCourses]).pipe(delay(500));
  }

  override getQuestions(courseId?: string): Observable<Question[]> {
    const list = courseId
      ? this.mockQuestions.filter((q) => q.courseId === courseId)
      : this.mockQuestions;
    return of([...list]).pipe(delay(500));
  }

  override getQuestion(questionId: string): Observable<Question> {
    const q = this.mockQuestions.find((item) => item.id === questionId);
    if (!q) {
      return throwError(() => new Error('Không tìm thấy câu hỏi yêu cầu.'));
    }
    return of({ ...q }).pipe(delay(400));
  }

  override createPracticeSession(questionId: string): Observable<PracticeSession> {
    const q = this.mockQuestions.find((item) => item.id === questionId);
    const newSession: PracticeSession = {
      id: `session-${Date.now()}`,
      questionId,
      questionTitle: q?.title || 'Câu hỏi luyện tập',
      courseName: 'Khóa học ôn tập',
      userId: 'user-student-1',
      status: 'recording',
      isTranscriptConfirmed: false,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    this.mockSessions.unshift(newSession);
    return of(newSession).pipe(delay(300));
  }

  override getPracticeSession(sessionId: string): Observable<PracticeSession> {
    const s = this.mockSessions.find((item) => item.id === sessionId);
    if (!s) {
      return throwError(() => new Error('Không tìm thấy phiên luyện tập.'));
    }
    return of({ ...s }).pipe(delay(400));
  }

  override uploadAudio(sessionId: string, _audioFile: Blob): Observable<PracticeSession> {
    const s = this.mockSessions.find((item) => item.id === sessionId);
    if (s) {
      s.status = 'uploaded';
      s.updatedAt = new Date().toISOString();
    }
    return of({ ...(s || this.mockSessions[0]) }).pipe(delay(800));
  }

  override requestTranscription(sessionId: string): Observable<{ status: string; jobId?: string }> {
    const s = this.mockSessions.find((item) => item.id === sessionId);
    if (s) {
      s.status = 'transcript_review';
      s.transcript =
        'Đây là nội dung bản ghi âm mô phỏng do hệ thống STT tự động trích xuất. Sinh viên có thể chỉnh sửa lại trước khi gửi chấm.';
    }
    return of({ status: 'success', jobId: `job-stt-${Date.now()}` }).pipe(delay(600));
  }

  override saveConfirmedTranscript(
    sessionId: string,
    transcript: string,
  ): Observable<PracticeSession> {
    const s = this.mockSessions.find((item) => item.id === sessionId);
    if (s) {
      s.transcript = transcript;
      s.isTranscriptConfirmed = true;
      s.status = 'grading';
    }
    return of({ ...(s || this.mockSessions[0]) }).pipe(delay(400));
  }

  override requestEvaluation(sessionId: string): Observable<{ status: string; jobId?: string }> {
    const s = this.mockSessions.find((item) => item.id === sessionId);
    if (s) {
      s.status = 'completed';
      s.evaluation = this.mockSessions[0].evaluation;
    }
    return of({ status: 'success', jobId: `job-eval-${Date.now()}` }).pipe(delay(1000));
  }

  override getEvaluation(sessionId: string): Observable<Evaluation> {
    const s = this.mockSessions.find((item) => item.id === sessionId);
    if (s?.evaluation) {
      return of(s.evaluation).pipe(delay(400));
    }
    return of(this.mockSessions[0].evaluation!).pipe(delay(400));
  }

  override getPracticeHistory(_userId?: string): Observable<PracticeSession[]> {
    return of([...this.mockSessions]).pipe(delay(500));
  }

  override saveQuestion(question: Partial<Question>): Observable<Question> {
    const saved: Question = {
      id: question.id || `q-${Date.now()}`,
      courseId: question.courseId || 'course-1',
      title: question.title || 'Câu hỏi mới',
      content: question.content || '',
      sampleAnswer: question.sampleAnswer || '',
      timeLimitSeconds: question.timeLimitSeconds || 180,
      difficulty: question.difficulty || 'medium',
    };
    this.mockQuestions.push(saved);
    return of(saved).pipe(delay(500));
  }

  override saveRubric(questionId: string, rubric: Rubric): Observable<Rubric> {
    const q = this.mockQuestions.find((item) => item.id === questionId);
    if (q) {
      q.rubric = rubric;
    }
    return of(rubric).pipe(delay(500));
  }
}
