import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of, delay, throwError, catchError, map } from 'rxjs';
import { environment } from '../../../environments/environment';
import { PracticeApi } from '../api/practice.api';
import {
  Course,
  Question,
  Rubric,
  PracticeSession,
  Evaluation,
  ExtractedQuestion,
  QuestionExtractResult,
} from '../../shared/models';
import { AiRagService } from '../../core/services/ai-rag.service';

@Injectable({
  providedIn: 'root',
})
export class MockPracticeApi extends PracticeApi {
  private http = inject(HttpClient);
  private aiRagService = inject(AiRagService);
  private sessionAudioBlobs = new Map<string, Blob>();

  private mockCourses: Course[] = [
    {
      id: 'IT2030',
      code: 'IT2030',
      name: 'Nhập môn Công nghệ phần mềm (QNU)',
      description:
        'Học phần chuẩn tích hợp kho giáo trình Hybrid RAG (Dense + BM25 + RRF): Quy trình phát triển phần mềm, Scrum, Kỹ nghệ yêu cầu, Kiến trúc, TDD và Kiểm thử phần mềm.',
      instructorName: 'TS. Nguyễn Luân (Khoa CNTT - ĐH Quy Nhơn)',
      questionCount: 8,
      semester: 'Học kỳ 1 - 2026',
      department: 'Khoa Công nghệ Thông tin',
      topics: [
        'Lập trình Hướng đối tượng (OOP)',
        'Quy trình Phần mềm & Scrum',
        'Kỹ nghệ Yêu cầu (SRS)',
        'Thiết kế & Kiến trúc Phần mềm',
        'Kiểm thử Phần mềm & TDD',
      ],
    },
    {
      id: 'course-1',
      code: 'CS101',
      name: 'Nhập môn Trí tuệ Nhân tạo',
      description:
        'Cung cấp kiến thức cơ bản về tìm kiếm heuristic, tri thức logic, học máy và mạng nơ-ron.',
      instructorName: 'TS. Nguyễn Văn A',
      questionCount: 2,
      semester: 'Học kỳ 1 - 2026',
      department: 'Khoa Khoa học Máy tính',
      topics: ['Tìm kiếm & Giải thuật', 'Học máy cơ bản'],
    },
  ];

  // Bộ câu hỏi và Rubric trích xuất trực tiếp từ BỘ ĐỀ THI.txt của speed-to-text-demo
  private mockQuestions: Question[] = [
    {
      id: 'q-se-1',
      courseId: 'IT2030',
      topic: 'Lập trình Hướng đối tượng (OOP)',
      title: 'Khái niệm, Vai trò và 4 tính chất cơ bản của OOP',
      content:
        'Trình bày khái niệm và vai trò của lập trình hướng đối tượng (OOP). Nêu 4 tính chất cơ bản của OOP và cho ví dụ minh họa thực tế.',
      sampleAnswer:
        'OOP là phương pháp lập trình dựa trên các đối tượng (objects) chứa thuộc tính và phương thức, giúp mô hình hóa bài toán trực quan, dễ bảo trì và tái sử dụng. 4 tính chất cơ bản gồm: Đóng gói (Encapsulation), Kế thừa (Inheritance), Đa hình (Polymorphism) và Trừu tượng (Abstraction).',
      timeLimitSeconds: 180,
      difficulty: 'easy',
      tags: ['OOP', 'Encapsulation', 'Inheritance', 'Polymorphism', 'Abstraction'],
      rubric: {
        id: 'rubric-se-1',
        questionId: 'q-se-1',
        totalScore: 10,
        criteria: [
          {
            id: 'c1',
            name: 'Định nghĩa và Vai trò của OOP',
            description:
              'Định nghĩa đúng OOP dựa trên đối tượng (thuộc tính + phương thức) (1.5đ); nêu vai trò mô hình hóa trực quan, tăng khả năng bảo trì và tái sử dụng (1.0đ).',
            maxScore: 2.5,
          },
          {
            id: 'c2',
            name: 'Nêu đúng tên và giải thích 4 tính chất cơ bản',
            description:
              'Giải thích đúng 4 tính chất: Đóng gói - Encapsulation (1.5đ), Kế thừa - Inheritance (1.5đ), Đa hình - Polymorphism (1.5đ), Trừu tượng - Abstraction (1.5đ).',
            maxScore: 6.0,
          },
          {
            id: 'c3',
            name: 'Ví dụ minh họa thực tế',
            description:
              'Lấy được ví dụ cụ thể (như lớp Xe Hơi và lớp con kế thừa, ghi đè phương thức) dễ hiểu.',
            maxScore: 1.5,
          },
        ],
      },
    },
    {
      id: 'q-se-2',
      courseId: 'IT2030',
      topic: 'Quy trình Phần mềm & Scrum',
      title: 'Các sự kiện và Vai trò trong khung quy trình Scrum',
      content:
        'Khung quy trình phát triển phần mềm Scrum gồm những sự kiện (events) chính nào? Hãy trình bày mục đích của các sự kiện đó. Đồng thời, phân biệt vai trò của Scrum Master và Product Owner trong đội ngũ Scrum.',
      sampleAnswer:
        '4 sự kiện chính trong Scrum gồm: Sprint Planning (lập kế hoạch Sprint), Daily Scrum (họp 15 phút hằng ngày), Sprint Review (demo sản phẩm cuối Sprint) và Sprint Retrospective (họp cải tiến quy trình). Product Owner quản lý Product Backlog và tối ưu giá trị sản phẩm; Scrum Master hỗ trợ quy trình Scrum và gỡ bỏ trở ngại (impediments) cho đội phát triển.',
      timeLimitSeconds: 240,
      difficulty: 'medium',
      tags: ['Scrum', 'Agile', 'Product Owner', 'Scrum Master', 'Sprint'],
      rubric: {
        id: 'rubric-se-2',
        questionId: 'q-se-2',
        totalScore: 10,
        criteria: [
          {
            id: 'c1',
            name: 'Các sự kiện chính trong Scrum',
            description:
              'Nêu và giải thích đúng 4 sự kiện cốt lõi: Sprint Planning (1.0đ), Daily Scrum (1.0đ), Sprint Review (1.0đ), Sprint Retrospective (1.0đ).',
            maxScore: 4.0,
          },
          {
            id: 'c2',
            name: 'Vai trò của Product Owner (PO)',
            description:
              'Tối ưu hóa giá trị sản phẩm, sắp xếp độ ưu tiên Product Backlog (1.0đ) và đại diện tiếng nói khách hàng (1.0đ).',
            maxScore: 2.0,
          },
          {
            id: 'c3',
            name: 'Vai trò của Scrum Master (SM)',
            description:
              'Đảm bảo đội ngũ hiểu và vận hành đúng Scrum (1.0đ); loại bỏ các trở ngại (impediments) cản trở tiến độ (1.0đ).',
            maxScore: 2.0,
          },
          {
            id: 'c4',
            name: 'Kỹ năng diễn đạt & Thuật ngữ chuyên ngành',
            description:
              'Trình bày logic, sử dụng chính xác các thuật ngữ Sprint, Backlog, Impediments.',
            maxScore: 2.0,
          },
        ],
      },
    },
    {
      id: 'q-se-3',
      courseId: 'IT2030',
      topic: 'Kỹ nghệ Yêu cầu (SRS)',
      title: 'Phân biệt Yêu cầu chức năng và Yêu cầu phi chức năng',
      content:
        'Yêu cầu phần mềm là gì? Hãy phân biệt và cho ví dụ cụ thể minh họa sự khác nhau giữa Yêu cầu chức năng (Functional requirements) và Yêu cầu phi chức năng (Non-functional requirements).',
      sampleAnswer:
        'Yêu cầu phần mềm mô tả các dịch vụ hệ thống phải cung cấp và các ràng buộc vận hành. Yêu cầu chức năng mô tả hệ thống làm gì (ví dụ: đăng nhập, thanh toán, xuất báo cáo PDF). Yêu cầu phi chức năng đặt ra ràng buộc về chất lượng như hiệu năng, bảo mật, độ tin cậy (ví dụ: phản hồi dưới 2 giây, chịu tải 10.000 người dùng đồng thời).',
      timeLimitSeconds: 180,
      difficulty: 'easy',
      tags: ['SRS', 'Functional Requirements', 'Non-functional Requirements'],
      rubric: {
        id: 'rubric-se-3',
        questionId: 'q-se-3',
        totalScore: 10,
        criteria: [
          {
            id: 'c1',
            name: 'Định nghĩa Yêu cầu phần mềm',
            description:
              'Giải thích được yêu cầu phần mềm là mô tả các dịch vụ/tính năng hệ thống phải cung cấp và các ràng buộc đi kèm.',
            maxScore: 2.0,
          },
          {
            id: 'c2',
            name: 'Yêu cầu chức năng (Functional Requirements)',
            description:
              'Định nghĩa đúng chức năng/nghiệp vụ trực tiếp (1.5đ) và lấy ví dụ thực tế chính xác (1.5đ).',
            maxScore: 3.0,
          },
          {
            id: 'c3',
            name: 'Yêu cầu phi chức năng (Non-functional Requirements)',
            description:
              'Định nghĩa đúng ràng buộc chất lượng/hiệu năng/bảo mật (1.5đ) và lấy ví dụ có số liệu cụ thể (1.5đ).',
            maxScore: 3.0,
          },
          {
            id: 'c4',
            name: 'So sánh bản chất & Diễn đạt',
            description:
              'Phân biệt rõ "Hệ thống làm cái gì" (Chức năng) và "Hệ thống đạt tiêu chuẩn gì" (Phi chức năng).',
            maxScore: 2.0,
          },
        ],
      },
    },
    {
      id: 'q-se-4',
      courseId: 'IT2030',
      topic: 'Thiết kế & Kiến trúc Phần mềm',
      title: 'Độ đo Coupling (Độ liên kết) và Cohesion (Độ gắn kết)',
      content:
        'Trong thiết kế kiến trúc phần mềm, hai độ đo Coupling (Độ liên kết) và Cohesion (Độ gắn kết) phản ánh điều gì? Người thiết kế mong muốn các độ đo này ở mức cao hay thấp để đạt chất lượng tốt? Hãy giải thích lý do tại sao.',
      sampleAnswer:
        'Coupling đo mức độ phụ thuộc lẫn nhau giữa các mô-đun; Cohesion đo mức độ tập trung của các chức năng bên trong cùng một mô-đun. Thiết kế tốt hướng tới Loose Coupling (Coupling thấp) và High Cohesion (Cohesion cao) để dễ bảo trì (Maintainability), dễ tái sử dụng (Reusability) và dễ kiểm thử độc lập (Testability).',
      timeLimitSeconds: 210,
      difficulty: 'medium',
      tags: ['Coupling', 'Cohesion', 'Software Design', 'Maintainability'],
      rubric: {
        id: 'rubric-se-4',
        questionId: 'q-se-4',
        totalScore: 10,
        criteria: [
          {
            id: 'c1',
            name: 'Khái niệm Coupling & Mức mong muốn',
            description:
              'Định nghĩa mức độ phụ thuộc giữa các mô-đun (1.5đ) và nêu mong muốn Coupling thấp - Loose Coupling (1.0đ).',
            maxScore: 2.5,
          },
          {
            id: 'c2',
            name: 'Khái niệm Cohesion & Mức mong muốn',
            description:
              'Định nghĩa mức độ gắn kết nội bộ trong mô-đun (1.5đ) và nêu mong muốn Cohesion cao - High Cohesion (1.0đ).',
            maxScore: 2.5,
          },
          {
            id: 'c3',
            name: 'Giải thích lý do (Bảo trì, Tái sử dụng, Kiểm thử)',
            description:
              'Giải thích tác động tới tính dễ bảo trì (1.0đ), khả năng tái sử dụng (1.0đ) và dễ kiểm thử Unit Test (1.0đ).',
            maxScore: 3.0,
          },
          {
            id: 'c4',
            name: 'Thuật ngữ chuyên ngành & Ví dụ',
            description:
              'Dùng chuẩn thuật ngữ Loosely coupled, Highly cohesive và lấy ví dụ minh họa.',
            maxScore: 2.0,
          },
        ],
      },
    },
    {
      id: 'q-se-5',
      courseId: 'IT2030',
      topic: 'Kiểm thử Phần mềm & TDD',
      title: 'Quy trình viết mã hướng kiểm thử (Test-Driven Development - TDD)',
      content:
        'Hãy trình bày các bước trong quy trình viết mã hướng kiểm thử (Test-Driven Development - TDD). So sánh sự khác nhau cơ bản giữa TDD và quy trình viết mã tăng dần thông thường (Incremental Coding).',
      sampleAnswer:
        'Chu trình TDD gồm 3 bước Red - Green - Refactor: (1) Red: Viết Unit Test trước cho tính năng mới và chạy thấy báo đỏ; (2) Green: Viết mã nguồn tối thiểu để vượt qua bài test; (3) Refactor: Tối ưu và làm sạch mã nguồn mà vẫn giữ test xanh. Khác với Incremental Coding (viết code trước, test sau), TDD viết test tự động trước khi viết code thực thi.',
      timeLimitSeconds: 200,
      difficulty: 'hard',
      tags: ['TDD', 'Red-Green-Refactor', 'Unit Test', 'Incremental Coding'],
      rubric: {
        id: 'rubric-se-5',
        questionId: 'q-se-5',
        totalScore: 10,
        criteria: [
          {
            id: 'c1',
            name: 'Chu trình 3 bước Red - Green - Refactor',
            description:
              'Trình bày đúng Bước 1: Viết Test trước - Red (1.5đ), Bước 2: Viết code tối thiểu qua test - Green (1.5đ), Bước 3: Tái cấu trúc mã - Refactor (1.0đ).',
            maxScore: 4.0,
          },
          {
            id: 'c2',
            name: 'So sánh với Incremental Coding',
            description:
              'Chỉ rõ sự ngược nhau về thứ tự: TDD viết test trước -> code sau; Incremental Coding viết code trước -> test sau.',
            maxScore: 2.0,
          },
          {
            id: 'c3',
            name: 'Lợi ích của TDD',
            description:
              'Nêu được ít nhất 2 lợi ích: tăng độ bao phủ kiểm thử (Test Coverage), thiết kế interface rõ ràng, phát hiện lỗi sớm.',
            maxScore: 2.0,
          },
          {
            id: 'c4',
            name: 'Diễn đạt & Tính logic',
            description: 'Lập luận mạch lạc, giải thích rõ chu trình lặp Red-Green-Refactor.',
            maxScore: 2.0,
          },
        ],
      },
    },
    {
      id: 'q-se-6',
      courseId: 'IT2030',
      topic: 'Kiểm thử Phần mềm & TDD',
      title: 'Phân biệt Kiểm thử hộp đen (Black-box) và Kiểm thử hộp trắng (White-box)',
      content:
        'Hãy phân biệt phương pháp kiểm thử hộp đen (Black-box testing) và kiểm thử hộp trắng (White-box testing). Cho biết phạm vi ứng dụng và đối tượng thực hiện chính của từng phương pháp.',
      sampleAnswer:
        'Kiểm thử hộp đen kiểm tra chức năng dựa trên đặc tả đầu vào/đầu ra mà không cần nhìn mã nguồn, thường do Tester hoặc khách hàng thực hiện ở mức System/Acceptance Test. Kiểm thử hộp trắng kiểm tra luồng logic, nhánh rẽ và câu lệnh bên trong mã nguồn, thường do Developer thực hiện ở mức Unit/Integration Test.',
      timeLimitSeconds: 180,
      difficulty: 'medium',
      tags: ['Black-box Testing', 'White-box Testing', 'Unit Test', 'System Test'],
      rubric: {
        id: 'rubric-se-6',
        questionId: 'q-se-6',
        totalScore: 10,
        criteria: [
          {
            id: 'c1',
            name: 'Kiểm thử hộp đen (Black-box testing)',
            description:
              'Định nghĩa kiểm thử theo đặc tả chức năng/giao diện (1.5đ); đối tượng thực hiện là Tester/Khách hàng ở System/Acceptance Test (1.5đ).',
            maxScore: 3.0,
          },
          {
            id: 'c2',
            name: 'Kiểm thử hộp trắng (White-box testing)',
            description:
              'Định nghĩa kiểm thử dựa trên cấu trúc mã nguồn/nhánh rẽ (1.5đ); đối tượng thực hiện là Developer ở Unit/Integration Test (1.5đ).',
            maxScore: 3.0,
          },
          {
            id: 'c3',
            name: 'So sánh ưu/nhược điểm',
            description:
              'So sánh ưu nhược điểm của cả hai phương pháp về góc nhìn người dùng và độ phủ đường đi trong code.',
            maxScore: 2.0,
          },
          {
            id: 'c4',
            name: 'Cấu trúc trình bày đối chiếu',
            description: 'Trình bày rõ ràng theo từng tiêu chí đối chiếu.',
            maxScore: 2.0,
          },
        ],
      },
    },
    {
      id: 'q-se-7',
      courseId: 'IT2030',
      topic: 'Quy trình Phần mềm & Scrum',
      title: '4 hoạt động cơ bản trong Quy trình phát triển phần mềm',
      content:
        'Quy trình phát triển phần mềm là gì? Trình bày 4 hoạt động cơ bản trong quy trình phát triển phần mềm và lấy ví dụ minh họa.',
      sampleAnswer:
        'Quy trình phát triển phần mềm là tập hợp các hoạt động có cấu trúc nhằm tạo ra và duy trì hệ thống phần mềm. 4 hoạt động cơ bản gồm: (1) Đặc tả phần mềm (Software specification), (2) Phát triển phần mềm (Software development - thiết kế & lập trình), (3) Thẩm định phần mềm (Software validation), và (4) Tiến hóa phần mềm (Software evolution).',
      timeLimitSeconds: 180,
      difficulty: 'easy',
      tags: ['Software Process', 'Specification', 'Validation', 'Evolution'],
      rubric: {
        id: 'rubric-se-7',
        questionId: 'q-se-7',
        totalScore: 10,
        criteria: [
          {
            id: 'c1',
            name: 'Định nghĩa quy trình phát triển phần mềm',
            description:
              'Nêu đúng quy trình phần mềm là tập hợp các hoạt động liên quan để xây dựng và bảo trì phần mềm.',
            maxScore: 2.0,
          },
          {
            id: 'c2',
            name: '4 hoạt động cơ bản',
            description:
              'Giải thích đủ 4 hoạt động: Đặc tả (Specification - 1.5đ), Phát triển (Development - 1.5đ), Thẩm định (Validation - 1.5đ), Tiến hóa (Evolution - 1.5đ).',
            maxScore: 6.0,
          },
          {
            id: 'c3',
            name: 'Ví dụ minh họa thực tế',
            description:
              'Lấy ví dụ một hệ thống cụ thể (như quản lý sinh viên) và gắn với 4 hoạt động trên.',
            maxScore: 2.0,
          },
        ],
      },
    },
    {
      id: 'q-se-8',
      courseId: 'IT2030',
      topic: 'Quy trình Phần mềm & Scrum',
      title: 'So sánh mô hình Thác nước (Waterfall) và Phát triển tăng dần (Incremental)',
      content:
        'So sánh mô hình Thác nước (Waterfall Model) và mô hình Phát triển tăng dần (Incremental Development). Nêu trường hợp áp dụng phù hợp cho từng mô hình.',
      sampleAnswer:
        'Mô hình Thác nước tổ chức phát triển theo các giai đoạn tuần tự, bàn giao sản phẩm hoàn chỉnh ở cuối dự án, phù hợp khi yêu cầu đã rõ ràng và ổn định. Mô hình Phát triển tăng dần chia hệ thống thành nhiều phiên bản (increments), bàn giao sớm các tính năng cốt lõi và dễ tiếp nhận phản hồi thay đổi từ khách hàng.',
      timeLimitSeconds: 210,
      difficulty: 'medium',
      tags: ['Waterfall', 'Incremental Development', 'SDLC'],
      rubric: {
        id: 'rubric-se-8',
        questionId: 'q-se-8',
        totalScore: 10,
        criteria: [
          {
            id: 'c1',
            name: 'Khái niệm hai mô hình',
            description:
              'Nêu đúng khái niệm mô hình Thác nước tuần tự (1.0đ) và Phát triển tăng dần theo phiên bản (1.0đ).',
            maxScore: 2.0,
          },
          {
            id: 'c2',
            name: 'So sánh 4 đặc điểm cốt lõi',
            description:
              'So sánh về: Cách tổ chức quy trình (1.5đ), Thời điểm bàn giao (1.5đ), Khả năng đáp ứng thay đổi (1.5đ), và Phản hồi người dùng (1.5đ).',
            maxScore: 6.0,
          },
          {
            id: 'c3',
            name: 'Trường hợp áp dụng',
            description:
              'Chỉ rõ khi nào nên dùng Waterfall (yêu cầu ổn định) và khi nào nên dùng Incremental (cần bàn giao sớm, yêu cầu linh hoạt).',
            maxScore: 2.0,
          },
        ],
      },
    },
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
  ];

  private readonly defaultFallbackEvaluation: Evaluation = {
    totalScore: 8.0,
    maxScore: 10,
    summary:
      'Sinh viên nắm vững định nghĩa OOP và nêu chính xác 4 tính chất cơ bản theo đúng giáo trình, tuy nhiên chưa nêu ví dụ thực tế minh họa.',
    criteria: [
      {
        criterionId: 'c1',
        score: 2.0,
        maxScore: 2.5,
        evidence:
          'lập trình hướng đối tượng (OOP) là phương pháp lập trình dựa trên các đối tượng có thuộc tính và phương thức',
        missingOrIncorrect: ['Chưa phân tích sâu vai trò tăng khả năng bảo trì và tái sử dụng'],
        feedback: 'Nêu đúng định nghĩa cốt lõi của OOP.',
      },
      {
        criterionId: 'c2',
        score: 6.0,
        maxScore: 6.0,
        evidence:
          'Bốn tính chất cơ bản của OOP là Đóng gói (Encapsulation), Kế thừa (Inheritance), Đa hình (Polymorphism) và Trừu tượng (Abstraction)',
        missingOrIncorrect: [],
        feedback: 'Nêu đầy đủ và chính xác 4 tính chất cơ bản của OOP.',
      },
      {
        criterionId: 'c3',
        score: 0.0,
        maxScore: 1.5,
        evidence: '',
        missingOrIncorrect: ['Chưa lấy ví dụ thực tế minh họa cho lớp và đối tượng'],
        feedback: 'Cần bổ sung 1 ví dụ cụ thể (như lớp Xe Hơi, lớp Sinh Viên) để đạt điểm tối đa.',
      },
    ],
    strengths: [
      'Nắm vững khái niệm đối tượng gồm thuộc tính và phương thức.',
      'Nêu chính xác cả 4 tính chất nền tảng của OOP.',
      'Trình bày ngắn gọn, đúng trọng tâm câu hỏi.',
    ],
    weaknesses: [
      'Chưa đưa ra ví dụ thực tế minh họa.',
      'Chưa giải thích chi tiết cơ chế nạp chồng (overloading) và ghi đè (overriding) trong tính đa hình.',
    ],
    improvements: [
      'Luôn kèm theo 1 ví dụ thực tế sau khi nêu lý thuyết để đạt trọn vẹn 1.5 điểm ví dụ.',
      'Giải thích thêm 1 câu ngắn cho mỗi tính chất thay vì chỉ liệt kê tên.',
    ],
    uncertaintyNotes: [],
    needsHumanReview: false,
    ragReferences: [
      {
        chunkId: 'IT2030::Bộ câu hỏi ôn tập CNPM.docx_chunk_1',
        source: 'Bộ câu hỏi ôn tập CNPM.docx',
        retrievedBy: 'dense + BM25',
        denseSim: 0.8412,
        rrfScore: 0.03279,
        textPreview:
          'Lập trình hướng đối tượng (OOP) tổ chức phần mềm xoay quanh các đối tượng (Objects) kết hợp dữ liệu và hành vi, dựa trên 4 tính chất: Encapsulation, Inheritance, Polymorphism và Abstraction...',
      },
    ],
    llmModel: 'gemini-2.5-flash',
    embeddingModel: 'paraphrase-multilingual-MiniLM-L12-v2',
    processingTimeMs: 2150,
  };

  private mockSessions: PracticeSession[] = [
    {
      id: 'session-demo-1',
      questionId: 'q-se-1',
      courseId: 'IT2030',
      questionTitle: 'Khái niệm, Vai trò và 4 tính chất cơ bản của OOP',
      courseName: 'Nhập môn Công nghệ phần mềm (QNU)',
      userId: 'user-student-1',
      status: 'completed',
      audioDurationSeconds: 95,
      rawTranscript:
        'dạ thưa thầy lập trình hướng đối tượng úp là phương pháp lập trình dựa trên các đối tượng có thuộc tính và phân thức bốn tính chất của úp là đóng gói kế thừa đa hình và chư tượng ạ',
      transcript:
        'Dạ thưa thầy, lập trình hướng đối tượng (OOP) là phương pháp lập trình dựa trên các đối tượng có thuộc tính và phương thức. Bốn tính chất cơ bản của OOP là Đóng gói (Encapsulation), Kế thừa (Inheritance), Đa hình (Polymorphism) và Trừu tượng (Abstraction) ạ.',
      sttModel: 'whisper-large-v3 (groq)',
      correctionModel: 'gemini-2.5-flash',
      isTranscriptConfirmed: true,
      evaluation: this.defaultFallbackEvaluation,
      createdAt: new Date(Date.now() - 3600 * 1000 * 12).toISOString(),
      updatedAt: new Date(Date.now() - 3600 * 1000 * 12).toISOString(),
    },
  ];

  constructor() {
    super();
    this.restoreSessionsFromStorage();
  }

  private restoreSessionsFromStorage(): void {
    try {
      const raw = sessionStorage.getItem('oral_exam_practice_sessions_v1');
      if (raw) {
        const parsed = JSON.parse(raw) as PracticeSession[];
        if (Array.isArray(parsed) && parsed.length > 0) {
          this.mockSessions = parsed;
        }
      }
    } catch {
      // Ignore storage read errors
    }
  }

  private persistSessionsToStorage(): void {
    try {
      sessionStorage.setItem('oral_exam_practice_sessions_v1', JSON.stringify(this.mockSessions));
    } catch {
      // Ignore storage write errors
    }
  }

  private ensureSession(sessionId: string): PracticeSession {
    let s = this.mockSessions.find((item) => item.id === sessionId);
    if (!s) {
      const q = this.mockQuestions[0];
      const course = this.mockCourses[0];
      s = {
        id: sessionId,
        questionId: q.id,
        courseId: q.courseId,
        questionTitle: q.title,
        courseName: course.name,
        userId: 'user-student-1',
        status: 'transcript_review',
        rawTranscript:
          'dạ thưa thầy lập trình hướng đối tượng úp là phương pháp lập trình dựa trên các đối tượng có thuộc tính và phân thức bốn tính chất của úp là đóng gói kế thừa đa hình và chư tượng ạ',
        transcript: q.sampleAnswer || 'Lập trình hướng đối tượng gồm 4 tính chất cơ bản.',
        isTranscriptConfirmed: true,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };
      this.mockSessions.unshift(s);
      this.persistSessionsToStorage();
    }
    return s;
  }

  override getCourses(): Observable<Course[]> {
    return this.http.get<Course[]>(`${environment.apiBaseUrl}/courses`).pipe(
      map((courses) => {
        if (courses && courses.length > 0) {
          courses.forEach((c) => {
            const idx = this.mockCourses.findIndex((mc) => mc.id === c.id || mc.code === c.code);
            if (idx === -1) {
              this.mockCourses.push(c);
            } else {
              this.mockCourses[idx] = c;
            }
          });
          return courses;
        }
        return this.mockCourses;
      }),
      catchError(() => of([...this.mockCourses])),
    );
  }

  private mapServerQuestion(res: any): Question {
    return {
      id: String(res.id),
      courseId: String(res.courseId || ''),
      topic: res.topic || '',
      title: res.title || '',
      content: res.content || '',
      sampleAnswer: res.sampleAnswer || '',
      difficulty: res.difficulty || 'medium',
      timeLimitSeconds: res.timeLimitSeconds || 180,
      tags: res.tags || [],
      parentQuestionId: res.parentQuestionId ? String(res.parentQuestionId) : null,
      rubric: res.rubric
        ? {
            id: String(res.rubric.id),
            questionId: String(res.id),
            totalScore: Number(res.rubric.totalScore) || 10.0,
            gradingInstructions: res.rubric.gradingInstructions,
            criteria: (res.rubric.criteria || []).map((c: any) => ({
              id: String(c.id),
              name: c.name,
              description: c.description,
              maxScore: Number(c.maxScore) || 2.5,
            })),
          }
        : undefined,
    };
  }

  override getQuestions(courseId?: string): Observable<Question[]> {
    const url = courseId
      ? `${environment.apiBaseUrl}/courses/${courseId}/questions`
      : `${environment.apiBaseUrl}/questions`;

    return this.http.get<any[]>(url).pipe(
      map((serverList) => {
        const questions = (serverList || []).map((q) => this.mapServerQuestion(q));
        questions.forEach((q) => {
          const idx = this.mockQuestions.findIndex((item) => item.id === q.id);
          if (idx !== -1) {
            this.mockQuestions[idx] = q;
          } else {
            this.mockQuestions.push(q);
          }
        });
        return questions;
      }),
      catchError((err) => {
        console.warn('Lấy câu hỏi từ Backend không thành công, dùng danh sách đệm:', err);
        const list = courseId
          ? this.mockQuestions.filter((q) => q.courseId === courseId)
          : this.mockQuestions;
        return of([...list]);
      }),
    );
  }

  override getQuestion(questionId: string): Observable<Question> {
    return this.http.get<any>(`${environment.apiBaseUrl}/questions/${questionId}`).pipe(
      map((serverQ) => {
        const q = this.mapServerQuestion(serverQ);
        const idx = this.mockQuestions.findIndex((item) => item.id === q.id);
        if (idx !== -1) {
          this.mockQuestions[idx] = q;
        } else {
          this.mockQuestions.unshift(q);
        }
        return q;
      }),
      catchError((err) => {
        console.warn('Lấy chi tiết câu hỏi từ Backend không thành công, dùng câu hỏi đệm:', err);
        const q =
          this.mockQuestions.find((item) => item.id === questionId) || this.mockQuestions[0];
        return of({ ...q });
      }),
    );
  }

  override createPracticeSession(questionId: string): Observable<PracticeSession> {
    return this.getQuestion(questionId).pipe(
      map((q) => {
        const course = this.mockCourses.find((c) => c.id === q.courseId);
        const newSession: PracticeSession = {
          id: `session-${Date.now()}`,
          questionId: q.id,
          courseId: q.courseId || 'IT2030',
          questionTitle: q.title || 'Câu hỏi luyện tập',
          courseName: course?.name || 'Học phần vấn đáp',
          userId: 'user-student-1',
          status: 'recording',
          isTranscriptConfirmed: false,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        };
        (newSession as any)._question = q;
        this.mockSessions.unshift(newSession);
        this.persistSessionsToStorage();
        return newSession;
      }),
    );
  }

  override getPracticeSession(sessionId: string): Observable<PracticeSession> {
    const s = this.ensureSession(sessionId);
    return of({ ...s }).pipe(delay(50));
  }

  override uploadAudio(sessionId: string, audioFile: Blob): Observable<PracticeSession> {
    const s = this.ensureSession(sessionId);
    this.sessionAudioBlobs.set(sessionId, audioFile);
    s.status = 'uploaded';
    if (audioFile.size > 50) {
      s.audioUrl = URL.createObjectURL(audioFile);
    }
    s.updatedAt = new Date().toISOString();
    this.persistSessionsToStorage();
    return of({ ...s }).pipe(delay(50));
  }

  override requestTranscription(sessionId: string): Observable<{ status: string; jobId?: string }> {
    const s = this.ensureSession(sessionId);
    const q = (s as any)._question || this.mockQuestions.find((item) => item.id === s.questionId) || this.mockQuestions[0];
    const audioBlob = this.sessionAudioBlobs.get(sessionId);

    if (!audioBlob || audioBlob.size < 50) {
      return throwError(() => new Error('Không tìm thấy file ghi âm giọng nói của bạn. Vui lòng ghi âm lại trước khi chuyển văn bản.'));
    }

    const rubricSummary = (q.rubric?.criteria || [])
      .map((c: any) => `${c.name}: ${c.description}`)
      .join('; ');

    return this.aiRagService
      .transcribeUploadedAudio(
        audioBlob,
        q.content || s.questionTitle || '',
        rubricSummary,
        'groq',
        true,
      )
      .pipe(
        map((res) => {
          s.status = 'transcript_review';
          s.rawTranscript = res.rawTranscript;
          s.transcript = res.correctedTranscript || res.rawTranscript;
          s.audioDurationSeconds = res.durationSeconds || s.audioDurationSeconds;
          s.sttModel = res.sttModel;
          s.correctionModel = res.correctionModel;
          s.updatedAt = new Date().toISOString();
          this.persistSessionsToStorage();
          return { status: 'success', jobId: `job-stt-${Date.now()}` };
        }),
        catchError((err) => {
          console.error('Lỗi khi nhận diện giọng nói (STT):', err);
          return throwError(
            () =>
              new Error(
                `Lỗi khi chuyển đổi giọng nói thành văn bản: ${err?.message || 'Không thể kết nối đến AI Speech-to-Text service'}. Vui lòng kiểm tra AI Service.`,
              ),
          );
        }),
      );
  }

  override saveConfirmedTranscript(
    sessionId: string,
    transcript: string,
  ): Observable<PracticeSession> {
    const s = this.ensureSession(sessionId);
    s.transcript = transcript;
    s.isTranscriptConfirmed = true;
    s.status = 'grading';
    s.updatedAt = new Date().toISOString();
    this.persistSessionsToStorage();
    return of({ ...s }).pipe(delay(50));
  }

  override requestEvaluation(sessionId: string): Observable<{ status: string; jobId?: string }> {
    const s = this.ensureSession(sessionId);
    const q = (s as any)._question || this.mockQuestions.find((item) => item.id === s.questionId) || this.mockQuestions[0];
    const transcriptToGrade = s.transcript && s.transcript.trim();

    if (!transcriptToGrade) {
      return throwError(
        () => new Error('Chưa có nội dung câu trả lời của sinh viên. Vui lòng nói hoặc xác nhận câu trả lời trước khi gửi chấm điểm.'),
      );
    }

    return this.aiRagService
      .evaluateSubmission({
        sessionId: s.id,
        courseId: s.courseId || q.courseId || 'IT2030',
        question: q,
        transcript: transcriptToGrade,
        enableRag: true,
        searchMode: 'hybrid',
        topK: 3,
      })
      .pipe(
        map((evalResult) => {
          s.status = 'completed';
          s.transcript = transcriptToGrade;
          s.evaluation = evalResult;
          s.updatedAt = new Date().toISOString();
          this.persistSessionsToStorage();
          return { status: 'success', jobId: `job-eval-${Date.now()}` };
        }),
        catchError((err) => {
          console.error('Lỗi khi AI chấm điểm câu trả lời:', err);
          return throwError(
            () =>
              new Error(
                `Lỗi khi AI chấm điểm: ${err?.message || 'Không thể kết nối đến AI Evaluation Service'}. Vui lòng kiểm tra AI Service.`,
              ),
          );
        }),
      );
  }

  override getEvaluation(sessionId: string): Observable<Evaluation> {
    const s = this.ensureSession(sessionId);
    if (s.evaluation) {
      return of(s.evaluation).pipe(delay(50));
    }
    return throwError(() => new Error('Chưa có kết quả đánh giá cho phiên luyện tập này.'));
  }

  override getPracticeHistory(_userId?: string): Observable<PracticeSession[]> {
    return of([...this.mockSessions]).pipe(delay(200));
  }

  override saveCourse(course: Partial<Course>): Observable<Course> {
    const backendUrl = `${environment.apiBaseUrl}/courses`;
    const isUuid = course.id && course.id.includes('-') && course.id.length > 20;
    const payload = {
      id: isUuid ? course.id : null,
      code: (course.code || 'IT-NEW').toUpperCase().trim(),
      name: (course.name || 'Học phần mới').trim(),
      description: (course.description || '').trim(),
      semester: (course.semester || 'Học kỳ 1 - 2026').trim(),
      department: (course.department || 'Khoa Công nghệ Thông tin').trim(),
    };

    const req$ = isUuid
      ? this.http.put<any>(`${backendUrl}/${course.id}`, payload)
      : this.http.post<any>(backendUrl, payload);

    return req$.pipe(
      map((saved) => {
        const courseObj: Course = {
          id: String(saved.id),
          code: saved.code,
          name: saved.name,
          description: saved.description || '',
          semester: saved.semester || 'Học kỳ 1 - 2026',
          department: saved.department || 'Khoa Công nghệ Thông tin',
          questionCount: saved.questionCount || 0,
          topics: saved.topics || [],
          createdBy: saved.createdBy ? String(saved.createdBy) : undefined,
          instructorName: saved.instructorName || 'TS. Nguyễn Luân (Khoa CNTT - ĐH Quy Nhơn)',
        };
        const idx = this.mockCourses.findIndex(
          (c) => c.id === courseObj.id || c.code.toUpperCase() === courseObj.code.toUpperCase(),
        );
        if (idx !== -1) {
          this.mockCourses[idx] = courseObj;
        } else {
          this.mockCourses.unshift(courseObj);
        }
        return courseObj;
      }),
      catchError((err) => {
        console.error('Lỗi khi lưu học phần vào Backend Database:', err);
        const errorMsg =
          err?.error?.message ||
          err?.message ||
          'Không thể kết nối đến Backend Database (http://localhost:8080/api/courses). Vui lòng đảm bảo Backend đã chạy.';
        return throwError(() => new Error(errorMsg));
      }),
    );
  }

  override saveQuestion(question: Partial<Question>): Observable<Question> {
    const isUuid = question.id && question.id.includes('-') && question.id.length > 20;
    const backendUrl = `${environment.apiBaseUrl}/questions`;
    const payload = {
      id: isUuid ? question.id : null,
      courseId: question.courseId,
      topic: question.topic || 'Chủ đề chung',
      title: question.title || (question.content ? question.content.substring(0, 60) + '...' : 'Câu hỏi'),
      content: question.content || '',
      sampleAnswer: question.sampleAnswer || '',
      difficulty: question.difficulty || 'medium',
      timeLimitSeconds: question.timeLimitSeconds || 180,
      tags: question.tags || [],
      parentQuestionId: question.parentQuestionId || null,
    };

    const req$ = isUuid
      ? this.http.put<any>(`${backendUrl}/${question.id}`, payload)
      : this.http.post<any>(backendUrl, payload);

    return req$.pipe(
      map((saved) => {
        const q = this.mapServerQuestion(saved);
        const idx = this.mockQuestions.findIndex((item) => item.id === q.id);
        if (idx !== -1) {
          this.mockQuestions[idx] = q;
        } else {
          this.mockQuestions.unshift(q);
        }
        return q;
      }),
      catchError((err) => {
        console.error('Lỗi khi lưu câu hỏi vào Backend Database:', err);
        const errorMsg =
          err?.error?.message ||
          err?.message ||
          'Không thể lưu câu hỏi vào Backend Database. Vui lòng kiểm tra kết nối Backend.';
        return throwError(() => new Error(errorMsg));
      }),
    );
  }

  override saveRubric(questionId: string, rubric: Rubric): Observable<Rubric> {
    const payload = {
      criteria: rubric.criteria.map((c) => ({
        name: c.name,
        description: c.description,
        maxScore: c.maxScore,
      })),
      totalScore: rubric.totalScore,
      gradingInstructions: rubric.gradingInstructions || '',
    };

    return this.http
      .put<any>(`${environment.apiBaseUrl}/questions/${questionId}/rubric`, payload)
      .pipe(
        map((res) => {
          const updatedRubric: Rubric = {
            id: String(res.id),
            questionId,
            totalScore: Number(res.totalScore) || 10.0,
            gradingInstructions: res.gradingInstructions,
            criteria: (res.criteria || []).map((c: any) => ({
              id: String(c.id),
              name: c.name,
              description: c.description,
              maxScore: Number(c.maxScore),
            })),
          };
          const q = this.mockQuestions.find((item) => item.id === questionId);
          if (q) {
            q.rubric = updatedRubric;
          }
          return updatedRubric;
        }),
        catchError((err) => {
          console.error('Lỗi khi lưu Rubric vào Backend Database:', err);
          const errorMsg =
            err?.error?.message ||
            err?.message ||
            'Không thể lưu Rubric vào Backend Database. Vui lòng kiểm tra kết nối Backend.';
          return throwError(() => new Error(errorMsg));
        }),
      );
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
          title: q.title || (q.content ? q.content.substring(0, 60) + '...' : 'Câu hỏi'),
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
      catchError((err) => {
        console.error('Lỗi khi gọi AI service trích xuất tài liệu:', err);
        return throwError(
          () =>
            new Error(
              `Không thể kết nối đến AI Service (${aiUrl}). Vui lòng đảm bảo AI service đang chạy tại cổng 8000 (uvicorn app.main:app --port 8000). Chi tiết: ${err.message || 'Lỗi kết nối mạng'}`,
            ),
        );
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
        tags: q.tags || [],
        criteria: (q.criteria || []).map((c) => ({
          name: c.name,
          description: c.description,
          maxScore: c.maxScore,
        })),
      })),
    };

    return this.http
      .post<{ success: boolean; importedCount: number; message: string }>(
        `${environment.apiBaseUrl}/questions/import/commit`,
        payload,
      )
      .pipe(
        map((res) => {
          // Tự động đồng bộ lại danh sách câu hỏi từ database
          this.getQuestions(courseId).subscribe();
          return res;
        }),
        catchError((err) => {
          console.error('Lỗi khi commit câu hỏi vào Backend DB:', err);
          const errorMsg =
            err?.error?.message ||
            err?.message ||
            'Không thể kết nối đến Backend Database (http://localhost:8080/api/questions/import/commit). Vui lòng đảm bảo Backend đã chạy.';
          return throwError(() => new Error(errorMsg));
        }),
      );
  }

  override downloadExcelTemplate(): Observable<Blob> {
    return this.http
      .get('http://localhost:8080/api/questions/import/template', {
        responseType: 'blob',
      })
      .pipe(
        catchError(() => {
          const fallback = new Blob(
            ['Mã câu,Chương / Chủ đề,Tiêu đề tóm tắt,Nội dung câu hỏi,Câu trả lời mẫu,Độ khó,Thời gian (giây),Mã câu hỏi cha,Tiêu chí 1,Mô tả tiêu chí 1,Điểm tiêu chí 1,Tiêu chí 2,Mô tả tiêu chí 2,Điểm tiêu chí 2,Tiêu chí 3,Mô tả tiêu chí 3,Điểm tiêu chí 3\n'],
            { type: 'text/csv;charset=utf-8;' },
          );
          return of(fallback);
        }),
      );
  }
}
