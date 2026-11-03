package vn.oralexam.backend.service;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.stream.Collectors;

import jakarta.annotation.PostConstruct;
import org.apache.poi.ss.usermodel.BorderStyle;
import org.apache.poi.ss.usermodel.Cell;
import org.apache.poi.ss.usermodel.CellStyle;
import org.apache.poi.ss.usermodel.DataValidation;
import org.apache.poi.ss.usermodel.DataValidationConstraint;
import org.apache.poi.ss.usermodel.DataValidationHelper;
import org.apache.poi.ss.usermodel.FillPatternType;
import org.apache.poi.ss.usermodel.Font;
import org.apache.poi.ss.usermodel.HorizontalAlignment;
import org.apache.poi.ss.usermodel.IndexedColors;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.ss.usermodel.VerticalAlignment;
import org.apache.poi.ss.usermodel.Workbook;
import org.apache.poi.ss.util.CellRangeAddressList;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import vn.oralexam.backend.DTO.request.BatchImportCommitRequest;
import vn.oralexam.backend.DTO.request.SaveCourseRequest;
import vn.oralexam.backend.DTO.request.SaveQuestionRequest;
import vn.oralexam.backend.DTO.request.SaveRubricRequest;
import vn.oralexam.backend.DTO.response.CourseResponse;
import vn.oralexam.backend.DTO.response.QuestionResponse;
import vn.oralexam.backend.DTO.response.RubricCriterionDto;
import vn.oralexam.backend.DTO.response.RubricDto;
import vn.oralexam.backend.entity.Course;
import vn.oralexam.backend.entity.Question;
import vn.oralexam.backend.entity.QuestionVersion;
import vn.oralexam.backend.entity.RubricCriterion;
import vn.oralexam.backend.entity.RubricVersion;
import vn.oralexam.backend.entity.User;
import vn.oralexam.backend.repository.CourseRepository;
import vn.oralexam.backend.repository.QuestionRepository;
import vn.oralexam.backend.repository.QuestionVersionRepository;
import vn.oralexam.backend.repository.RubricVersionRepository;
import vn.oralexam.backend.repository.UserRepository;

@Service
@Transactional
public class QuestionService {

    private final CourseRepository courseRepository;
    private final QuestionRepository questionRepository;
    private final QuestionVersionRepository questionVersionRepository;
    private final RubricVersionRepository rubricVersionRepository;
    private final UserRepository userRepository;

    public QuestionService(
            CourseRepository courseRepository,
            QuestionRepository questionRepository,
            QuestionVersionRepository questionVersionRepository,
            RubricVersionRepository rubricVersionRepository,
            UserRepository userRepository
    ) {
        this.courseRepository = courseRepository;
        this.questionRepository = questionRepository;
        this.questionVersionRepository = questionVersionRepository;
        this.rubricVersionRepository = rubricVersionRepository;
        this.userRepository = userRepository;
    }

    /**
     * Xác định chính xác UUID của người tạo (giảng viên)
     * Nếu không có userId từ JWT (ví dụ chạy offline/dev), tự động gán cho tài khoản giảng viên trong database
     */
    public UUID resolveUserId(UUID explicitUserId) {
        if (explicitUserId != null) {
            return explicitUserId;
        }
        return userRepository.findAll().stream()
                .filter(u -> u.getRoles().contains("instructor") || u.getRoles().contains("admin"))
                .map(User::getId)
                .findFirst()
                .orElseGet(() -> {
                    if (userRepository.count() == 0) {
                        User defaultInstructor = new User();
                        defaultInstructor.setEmail("giangvien@qnu.edu.vn");
                        defaultInstructor.setFullName("TS. Nguyễn Luân (Khoa CNTT - ĐH Quy Nhơn)");
                        defaultInstructor.getRoles().add("instructor");
                        defaultInstructor.setActive(true);
                        return userRepository.save(defaultInstructor).getId();
                    }
                    return userRepository.findAll().get(0).getId();
                });
    }

    /**
     * Phân giải học phần chuẩn xác: hỗ trợ cả UUID string hoặc mã môn học (ví dụ: 'IT2030')
     */
    public Course resolveCourse(String courseIdOrCode) {
        if (courseIdOrCode == null || courseIdOrCode.isBlank()) {
            throw new IllegalArgumentException("Mã môn học không được để trống");
        }
        String trimmed = courseIdOrCode.trim();
        try {
            UUID id = UUID.fromString(trimmed);
            Optional<Course> c = courseRepository.findById(id);
            if (c.isPresent()) return c.get();
        } catch (IllegalArgumentException ignored) {
        }
        return courseRepository.findByCodeIgnoreCase(trimmed)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy môn học với mã hoặc ID: " + trimmed));
    }

    /**
     * Tự động khởi tạo dữ liệu mẫu cho Course và Instructor nếu database trống
     */
    @PostConstruct
    public void seedInitialDataIfEmpty() {
        UUID instructorId = resolveUserId(null);

        if (courseRepository.count() == 0) {
            Course c1 = new Course(
                    "IT2030",
                    "Công nghệ Phần mềm (Software Engineering)",
                    "Môn học cốt lõi ngành CNTT về quy trình phát triển phần mềm, kiến trúc mẫu và kiểm thử.",
                    "Học kỳ 1 - 2026",
                    "Khoa Công nghệ Thông tin"
            );
            c1.setCreatedBy(instructorId);

            Course c2 = new Course(
                    "IT3020",
                    "Hệ Quản trị Cơ sở Dữ liệu (DBMS)",
                    "Nguyên lý cơ sở dữ liệu quan hệ, giao dịch ACID, tối ưu hóa truy vấn SQL và lập chỉ mục.",
                    "Học kỳ 1 - 2026",
                    "Khoa Công nghệ Thông tin"
            );
            c2.setCreatedBy(instructorId);

            Course c3 = new Course(
                    "IT3080",
                    "Mạng Máy tính & An toàn Mạng",
                    "Giao thức mạng mô hình OSI/TCP-IP, định tuyến, bảo mật SSL/TLS và phòng chống tấn công mạng.",
                    "Học kỳ 1 - 2026",
                    "Khoa Công nghệ Thông tin"
            );
            c3.setCreatedBy(instructorId);

            courseRepository.saveAll(List.of(c1, c2, c3));
        }
    }

    @Transactional(readOnly = true)
    public List<CourseResponse> getAllCourses() {
        List<Course> courses = courseRepository.findByActiveTrue();
        List<Question> allQuestions = questionRepository.findByActiveTrue();
        Map<UUID, User> userCache = userRepository.findAll().stream()
                .collect(Collectors.toMap(User::getId, u -> u, (a, b) -> a));

        return courses.stream().map(c -> {
            List<Question> courseQuestions = allQuestions.stream()
                    .filter(q -> q.getCourse() != null && q.getCourse().getId().equals(c.getId()))
                    .toList();

            List<String> topics = courseQuestions.stream()
                    .map(Question::getTopic)
                    .filter(t -> t != null && !t.isBlank())
                    .distinct()
                    .collect(Collectors.toList());

            String instructorName = "Khoa Công nghệ Thông tin";
            if (c.getCreatedBy() != null && userCache.containsKey(c.getCreatedBy())) {
                instructorName = userCache.get(c.getCreatedBy()).getFullName();
            }

            return new CourseResponse(
                    c.getId(),
                    c.getCode(),
                    c.getName(),
                    c.getDescription(),
                    c.getSemester(),
                    c.getDepartment(),
                    courseQuestions.size(),
                    topics,
                    c.getCreatedBy(),
                    instructorName
            );
        }).collect(Collectors.toList());
    }

    public CourseResponse saveCourse(SaveCourseRequest request, UUID userId) {
        UUID creatorId = resolveUserId(userId);
        Course course;
        if (request.id() != null) {
            course = courseRepository.findById(request.id())
                    .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy học phần: " + request.id()));
        } else {
            Optional<Course> existing = courseRepository.findByCodeIgnoreCase(request.code().trim());
            if (existing.isPresent()) {
                throw new IllegalArgumentException("Mã học phần '" + request.code().trim() + "' đã tồn tại trong hệ thống.");
            }
            course = new Course();
            course.setCreatedBy(creatorId);
        }

        course.setCode(request.code().trim().toUpperCase());
        course.setName(request.name().trim());
        course.setDescription(request.description() != null ? request.description().trim() : "");
        course.setSemester(request.semester() != null && !request.semester().isBlank() ? request.semester().trim() : "Học kỳ 1 - 2026");
        course.setDepartment(request.department() != null && !request.department().isBlank() ? request.department().trim() : "Khoa Công nghệ Thông tin");
        course.setActive(true);
        if (course.getCreatedBy() == null) {
            course.setCreatedBy(creatorId);
        }

        course = courseRepository.save(course);
        String instructorName = userRepository.findById(creatorId).map(User::getFullName).orElse("TS. Nguyễn Luân (Khoa CNTT - ĐH Quy Nhơn)");

        return new CourseResponse(
                course.getId(),
                course.getCode(),
                course.getName(),
                course.getDescription(),
                course.getSemester(),
                course.getDepartment(),
                0,
                List.of(),
                course.getCreatedBy(),
                instructorName
        );
    }

    @Transactional(readOnly = true)
    public List<QuestionResponse> getQuestions(String courseIdentifier) {
        List<Question> questions;
        if (courseIdentifier != null && !courseIdentifier.isBlank()) {
            Course course = resolveCourse(courseIdentifier);
            questions = questionRepository.findByCourseIdAndActiveTrue(course.getId());
        } else {
            questions = questionRepository.findByActiveTrue();
        }

        return questions.stream()
                .map(this::toQuestionResponse)
                .collect(Collectors.toList());
    }

    @Transactional(readOnly = true)
    public QuestionResponse getQuestionById(UUID id) {
        Question question = questionRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy câu hỏi với ID: " + id));
        return toQuestionResponse(question);
    }

    public QuestionResponse saveQuestion(SaveQuestionRequest request, UUID userId) {
        Course course = resolveCourse(request.courseId());
        UUID creatorId = resolveUserId(userId);

        Question question;
        boolean isNew = (request.id() == null);

        if (isNew) {
            question = new Question(course, request.topic(), creatorId);
            question.setParentQuestionId(request.parentQuestionId());
            question = questionRepository.save(question);

            QuestionVersion version = new QuestionVersion();
            version.setQuestion(question);
            version.setVersionNo(1);
            version.setTitle(request.title());
            version.setPrompt(request.content());
            version.setReferenceAnswer(request.sampleAnswer());
            version.setDifficulty(request.difficulty() != null ? request.difficulty() : "medium");
            version.setTimeLimitSeconds(request.timeLimitSeconds() != null ? request.timeLimitSeconds() : 180);
            version.setTags(request.tags() != null ? new ArrayList<>(request.tags()) : new ArrayList<>());
            version.setCreatedBy(creatorId);

            RubricVersion defaultRubric = createDefaultRubricVersion(version, creatorId);
            version.getRubricVersions().add(defaultRubric);

            question.getVersions().add(version);
            question = questionRepository.save(question);
        } else {
            question = questionRepository.findById(request.id())
                    .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy câu hỏi: " + request.id()));

            question.setCourse(course);
            question.setTopic(request.topic());
            question.setParentQuestionId(request.parentQuestionId());

            QuestionVersion latest = question.getLatestVersion();
            if (latest != null) {
                int nextVersionNo = latest.getVersionNo() + 1;
                QuestionVersion newVersion = new QuestionVersion();
                newVersion.setQuestion(question);
                newVersion.setVersionNo(nextVersionNo);
                newVersion.setTitle(request.title());
                newVersion.setPrompt(request.content());
                newVersion.setReferenceAnswer(request.sampleAnswer());
                newVersion.setDifficulty(request.difficulty() != null ? request.difficulty() : latest.getDifficulty());
                newVersion.setTimeLimitSeconds(request.timeLimitSeconds() != null ? request.timeLimitSeconds() : latest.getTimeLimitSeconds());
                newVersion.setTags(request.tags() != null ? new ArrayList<>(request.tags()) : new ArrayList<>(latest.getTags()));
                newVersion.setCreatedBy(userId);

                RubricVersion latestRubric = latest.getLatestRubricVersion();
                if (latestRubric != null) {
                    RubricVersion copiedRubric = new RubricVersion();
                    copiedRubric.setQuestionVersion(newVersion);
                    copiedRubric.setVersionNo(1);
                    copiedRubric.setTotalScore(latestRubric.getTotalScore());
                    copiedRubric.setGradingInstructions(latestRubric.getGradingInstructions());
                    copiedRubric.setCreatedBy(userId);

                    for (RubricCriterion c : latestRubric.getCriteria()) {
                        RubricCriterion newCriterion = new RubricCriterion(
                                c.getPosition(),
                                c.getName(),
                                c.getDescription(),
                                c.getMaxScore()
                        );
                        copiedRubric.addCriterion(newCriterion);
                    }
                    newVersion.getRubricVersions().add(copiedRubric);
                }

                question.getVersions().add(0, newVersion);
            }
            question = questionRepository.save(question);
        }

        return toQuestionResponse(question);
    }

    public RubricDto saveRubric(UUID questionId, SaveRubricRequest request, UUID userId) {
        Question question = questionRepository.findById(questionId)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy câu hỏi: " + questionId));

        QuestionVersion latestVersion = question.getLatestVersion();
        if (latestVersion == null) {
            throw new IllegalStateException("Câu hỏi chưa có phiên bản nội dung hợp lệ");
        }

        int nextRubricVersionNo = 1;
        RubricVersion currentLatestRubric = latestVersion.getLatestRubricVersion();
        if (currentLatestRubric != null) {
            nextRubricVersionNo = currentLatestRubric.getVersionNo() + 1;
        }

        RubricVersion newRubric = new RubricVersion();
        newRubric.setQuestionVersion(latestVersion);
        newRubric.setVersionNo(nextRubricVersionNo);
        newRubric.setTotalScore(request.totalScore() != null ? request.totalScore() : BigDecimal.valueOf(10.0));
        newRubric.setGradingInstructions(request.gradingInstructions());
        newRubric.setCreatedBy(userId);

        if (request.criteria() != null) {
            int pos = 1;
            for (SaveRubricRequest.CriterionItem item : request.criteria()) {
                RubricCriterion criterion = new RubricCriterion(
                        pos++,
                        item.name(),
                        item.description(),
                        item.maxScore() != null ? item.maxScore() : BigDecimal.valueOf(2.5)
                );
                newRubric.addCriterion(criterion);
            }
        }

        latestVersion.getRubricVersions().add(0, newRubric);
        questionRepository.save(question);

        return toRubricDto(newRubric, questionId);
    }

    public void deleteQuestion(UUID id) {
        Question question = questionRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("Không tìm thấy câu hỏi: " + id));
        question.setActive(false);
        questionRepository.save(question);
    }

    /**
     * Tạo file mẫu Excel (.xlsx) chuẩn hóa để giảng viên nhập hàng loạt câu hỏi và rubric
     */
    public byte[] generateExcelTemplate() throws IOException {
        try (Workbook workbook = new XSSFWorkbook(); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            Sheet sheet = workbook.createSheet("NganHangCauHoi");

            // Header Style
            CellStyle headerStyle = workbook.createCellStyle();
            Font headerFont = workbook.createFont();
            headerFont.setBold(true);
            headerFont.setColor(IndexedColors.WHITE.getIndex());
            headerStyle.setFont(headerFont);
            headerStyle.setFillForegroundColor(IndexedColors.ROYAL_BLUE.getIndex());
            headerStyle.setFillPattern(FillPatternType.SOLID_FOREGROUND);
            headerStyle.setAlignment(HorizontalAlignment.CENTER);
            headerStyle.setVerticalAlignment(VerticalAlignment.CENTER);
            headerStyle.setBorderBottom(BorderStyle.THIN);

            // Data Style
            CellStyle dataStyle = workbook.createCellStyle();
            dataStyle.setWrapText(true);
            dataStyle.setVerticalAlignment(VerticalAlignment.TOP);

            String[] headers = {
                    "Mã câu (*)",
                    "Chương / Chủ đề",
                    "Tiêu đề tóm tắt (*)",
                    "Nội dung phát vấn (*)",
                    "Đáp án tham chiếu (*)",
                    "Ý chính / Tiêu chí Rubric",
                    "Độ khó (easy/medium/hard)",
                    "Thời lượng (giây)",
                    "Mã câu hỏi cha (nếu có)"
            };

            Row headerRow = sheet.createRow(0);
            headerRow.setHeightInPoints(28);
            for (int i = 0; i < headers.length; i++) {
                Cell cell = headerRow.createCell(i);
                cell.setCellValue(headers[i]);
                cell.setCellStyle(headerStyle);
            }

            // Dòng ví dụ 1: Câu hỏi chính
            Row row1 = sheet.createRow(1);
            row1.createCell(0).setCellValue("Q1");
            row1.createCell(1).setCellValue("Thiết kế Hướng đối tượng & SOLID");
            row1.createCell(2).setCellValue("Nguyên lý Single Responsibility (SRP)");
            row1.createCell(3).setCellValue("Hãy trình bày định nghĩa và ý nghĩa của nguyên lý Single Responsibility Principle (SRP) trong thiết kế phần mềm?");
            row1.createCell(4).setCellValue("Nguyên lý đơn trách nhiệm (SRP) phát biểu rằng một lớp chỉ nên có một lý do duy nhất để thay đổi. Nghĩa là lớp đó chỉ đảm nhận một trách nhiệm duy nhất trong toàn hệ thống. Việc tuân thủ SRP giúp mã nguồn dễ bảo trì, giảm khớp nối (coupling) và dễ viết Unit Test.");
            row1.createCell(5).setCellValue("Khái niệm SRP (3đ); Lợi ích bảo trì & kiểm thử (3đ); Ví dụ minh họa (2.5đ); Kỹ năng trình bày (1.5đ)");
            row1.createCell(6).setCellValue("medium");
            row1.createCell(7).setCellValue(180);
            row1.createCell(8).setCellValue("");

            // Dòng ví dụ 2: Câu hỏi phụ (Follow-up subquestion gắn với Q1)
            Row row2 = sheet.createRow(2);
            row2.createCell(0).setCellValue("Q1.1");
            row2.createCell(1).setCellValue("Thiết kế Hướng đối tượng & SOLID");
            row2.createCell(2).setCellValue("Ví dụ vi phạm SRP và giải pháp refactor (Câu hỏi phụ)");
            row2.createCell(3).setCellValue("Trong dự án thực tế, bạn hãy nêu một ví dụ về một lớp thường hay vi phạm SRP và đề xuất phương án tách lớp để tuân thủ nguyên lý này?");
            row2.createCell(4).setCellValue("Ví dụ lớp UserAccount vừa lưu dữ liệu người dùng, vừa gửi email kích hoạt, vừa ghi log giao dịch. Cách refactor: Tách thành UserAccount (thực thể), EmailNotificationService (gửi mail) và ActivityAuditLogger (ghi log).");
            row2.createCell(5).setCellValue("Chỉ rõ vi phạm đa trách nhiệm (4đ); Phương án tách lớp chuẩn (4đ); Phản xạ nhanh (2đ)");
            row2.createCell(6).setCellValue("hard");
            row2.createCell(7).setCellValue(120);
            row2.createCell(8).setCellValue("Q1");

            // Dropdown validation cho cột Độ khó (Cột F = index 6)
            DataValidationHelper validationHelper = sheet.getDataValidationHelper();
            DataValidationConstraint constraint = validationHelper.createExplicitListConstraint(new String[]{"easy", "medium", "hard"});
            CellRangeAddressList addressList = new CellRangeAddressList(1, 1000, 6, 6);
            DataValidation validation = validationHelper.createValidation(constraint, addressList);
            validation.setSuppressDropDownArrow(true);
            sheet.addValidationData(validation);

            // Tự động căn chỉnh độ rộng cột
            sheet.setColumnWidth(0, 12 * 256);
            sheet.setColumnWidth(1, 28 * 256);
            sheet.setColumnWidth(2, 32 * 256);
            sheet.setColumnWidth(3, 45 * 256);
            sheet.setColumnWidth(4, 50 * 256);
            sheet.setColumnWidth(5, 38 * 256);
            sheet.setColumnWidth(6, 22 * 256);
            sheet.setColumnWidth(7, 18 * 256);
            sheet.setColumnWidth(8, 22 * 256);

            workbook.write(out);
            return out.toByteArray();
        }
    }

    /**
     * Nhập hàng loạt câu hỏi và Rubric đã qua kiểm duyệt vào database
     */
    public int commitBatchQuestions(BatchImportCommitRequest request, UUID userId) {
        Course course = resolveCourse(request.courseId());
        UUID creatorId = resolveUserId(userId);

        if (request.questions() == null || request.questions().isEmpty()) {
            return 0;
        }

        Map<String, Question> codeToQuestionMap = new HashMap<>();
        List<BatchImportCommitRequest.ImportQuestionDto> pendingFollowups = new ArrayList<>();

        // Vòng 1: Tạo câu hỏi và Rubric
        for (BatchImportCommitRequest.ImportQuestionDto dto : request.questions()) {
            Question question = new Question(course, dto.topic() != null ? dto.topic() : "Chung", creatorId);
            question = questionRepository.save(question);

            QuestionVersion version = new QuestionVersion();
            version.setQuestion(question);
            version.setVersionNo(1);
            version.setTitle(dto.title() != null && !dto.title().isBlank() ? dto.title() : "Câu hỏi mới");
            version.setPrompt(dto.content() != null ? dto.content() : "");
            version.setReferenceAnswer(dto.sampleAnswer() != null ? dto.sampleAnswer() : "");
            version.setDifficulty(dto.difficulty() != null ? dto.difficulty() : "medium");
            version.setTimeLimitSeconds(dto.timeLimitSeconds() != null ? dto.timeLimitSeconds() : 180);
            version.setTags(dto.tags() != null ? new ArrayList<>(dto.tags()) : List.of("CNPM"));
            version.setCreatedBy(creatorId);

            RubricVersion rubric = new RubricVersion();
            rubric.setQuestionVersion(version);
            rubric.setVersionNo(1);
            rubric.setTotalScore(BigDecimal.valueOf(10.0));
            rubric.setCreatedBy(creatorId);
            rubric.setGradingInstructions("Chấm điểm dựa trên tính chính xác của kiến thức chuyên ngành, chiều sâu phân tích và tính ứng dụng thực tế.");

            if (dto.criteria() != null && !dto.criteria().isEmpty()) {
                int pos = 1;
                for (BatchImportCommitRequest.CriterionDto c : dto.criteria()) {
                    RubricCriterion criterion = new RubricCriterion(
                            pos++,
                            c.name(),
                            c.description(),
                            c.maxScore() != null ? c.maxScore() : BigDecimal.valueOf(2.5)
                    );
                    rubric.addCriterion(criterion);
                }
            } else {
                RubricVersion def = createDefaultRubricVersion(version, creatorId);
                for (RubricCriterion c : def.getCriteria()) {
                    rubric.addCriterion(new RubricCriterion(c.getPosition(), c.getName(), c.getDescription(), c.getMaxScore()));
                }
            }

            version.getRubricVersions().add(rubric);
            question.getVersions().add(version);
            question = questionRepository.save(question);

            if (dto.code() != null && !dto.code().isBlank()) {
                codeToQuestionMap.put(dto.code().trim().toUpperCase(), question);
            }

            if (dto.parentCode() != null && !dto.parentCode().isBlank()) {
                pendingFollowups.add(dto);
            }
        }

        // Vòng 2: Cập nhật liên kết câu hỏi cha - con (Follow-up branch)
        for (BatchImportCommitRequest.ImportQuestionDto dto : pendingFollowups) {
            String childCode = dto.code() != null ? dto.code().trim().toUpperCase() : "";
            String parentCode = dto.parentCode().trim().toUpperCase();

            Question childQuestion = codeToQuestionMap.get(childCode);
            Question parentQuestion = codeToQuestionMap.get(parentCode);

            if (childQuestion != null && parentQuestion != null && !childQuestion.getId().equals(parentQuestion.getId())) {
                childQuestion.setParentQuestionId(parentQuestion.getId());
                questionRepository.save(childQuestion);
            }
        }

        return request.questions().size();
    }

    private RubricVersion createDefaultRubricVersion(QuestionVersion questionVersion, UUID userId) {
        RubricVersion rubric = new RubricVersion();
        rubric.setQuestionVersion(questionVersion);
        rubric.setVersionNo(1);
        rubric.setTotalScore(BigDecimal.valueOf(10.0));
        rubric.setGradingInstructions("Chấm điểm dựa trên sự chính xác của kiến thức chuyên ngành, khả năng diễn đạt logic và các ví dụ minh họa.");
        rubric.setCreatedBy(userId);

        rubric.addCriterion(new RubricCriterion(
                1,
                "Khái niệm & Kiến thức cốt lõi",
                "Trình bày chính xác và đầy đủ các định nghĩa, thuật ngữ chuyên môn trọng tâm.",
                BigDecimal.valueOf(3.0)
        ));
        rubric.addCriterion(new RubricCriterion(
                2,
                "Phân tích & So sánh chuyên sâu",
                "Phân tích rõ cơ chế hoạt động, sự khác biệt và ưu nhược điểm liên quan.",
                BigDecimal.valueOf(3.0)
        ));
        rubric.addCriterion(new RubricCriterion(
                3,
                "Ví dụ thực tế & Tính ứng dụng",
                "Đưa ra được ví dụ mã nguồn hoặc tình huống thực tế minh họa đúng bản chất.",
                BigDecimal.valueOf(2.5)
        ));
        rubric.addCriterion(new RubricCriterion(
                4,
                "Phản xạ & Kỹ năng trình bày",
                "Diễn đạt mạch lạc, phản xạ tự tin, dùng thuật ngữ chuyên ngành chuẩn xác.",
                BigDecimal.valueOf(1.5)
        ));

        return rubric;
    }

    private QuestionResponse toQuestionResponse(Question question) {
        QuestionVersion v = question.getLatestVersion();
        RubricDto rubricDto = null;

        if (v != null) {
            RubricVersion rv = v.getLatestRubricVersion();
            if (rv != null) {
                rubricDto = toRubricDto(rv, question.getId());
            }
        }

        return new QuestionResponse(
                question.getId(),
                question.getCourse() != null ? question.getCourse().getId() : null,
                question.getTopic(),
                v != null ? v.getTitle() : "Chưa có tiêu đề",
                v != null ? v.getPrompt() : "",
                v != null ? v.getReferenceAnswer() : "",
                v != null ? v.getDifficulty() : "medium",
                v != null ? v.getTimeLimitSeconds() : 180,
                v != null && v.getTags() != null ? v.getTags() : List.of(),
                rubricDto,
                question.getParentQuestionId()
        );
    }

    private RubricDto toRubricDto(RubricVersion rv, UUID questionId) {
        List<RubricCriterionDto> criteriaDtos = (rv.getCriteria() != null)
                ? rv.getCriteria().stream()
                .map(c -> new RubricCriterionDto(c.getId(), c.getName(), c.getDescription(), c.getMaxScore()))
                .collect(Collectors.toList())
                : List.of();

        return new RubricDto(
                rv.getId(),
                questionId,
                criteriaDtos,
                rv.getTotalScore(),
                rv.getGradingInstructions()
        );
    }
}
