package vn.oralexam.backend.service;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;
import vn.oralexam.backend.DTO.request.ReviewPracticeRecordRequest;
import vn.oralexam.backend.DTO.request.SavePracticeRecordRequest;
import vn.oralexam.backend.DTO.response.PracticeRecordResponse;
import vn.oralexam.backend.entity.Course;
import vn.oralexam.backend.entity.PracticeRecord;
import vn.oralexam.backend.entity.Question;
import vn.oralexam.backend.entity.User;
import vn.oralexam.backend.repository.CourseRepository;
import vn.oralexam.backend.repository.PracticeRecordRepository;
import vn.oralexam.backend.repository.QuestionRepository;
import vn.oralexam.backend.repository.UserRepository;

@Service
@Transactional
public class PracticeRecordService {

    private static final long MAX_AUDIO_BYTES = 20L * 1024L * 1024L;
    private static final Set<String> ALLOWED_AUDIO_EXTS = Set.of(".webm", ".wav", ".mp3", ".m4a", ".ogg");
    private static final Path AUDIO_STORAGE_DIR = Paths.get("data", "audio").toAbsolutePath().normalize();

    private final PracticeRecordRepository practiceRecordRepository;
    private final CourseRepository courseRepository;
    private final QuestionRepository questionRepository;
    private final UserRepository userRepository;

    public PracticeRecordService(
            PracticeRecordRepository practiceRecordRepository,
            CourseRepository courseRepository,
            QuestionRepository questionRepository,
            UserRepository userRepository
    ) {
        this.practiceRecordRepository = practiceRecordRepository;
        this.courseRepository = courseRepository;
        this.questionRepository = questionRepository;
        this.userRepository = userRepository;
    }

    public PracticeRecordResponse saveStudentRecord(SavePracticeRecordRequest request, UUID studentId) {
        if (studentId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Bạn cần đăng nhập để lưu kết quả luyện tập.");
        }

        PracticeRecord record = new PracticeRecord();
        record.setStudentId(studentId);

        Question resolvedQuestion = resolveQuestion(request.questionId()).orElse(null);
        Course resolvedCourse = null;
        if (resolvedQuestion != null && resolvedQuestion.getCourse() != null) {
            resolvedCourse = resolvedQuestion.getCourse();
        } else {
            resolvedCourse = resolveCourse(request.courseId(), request.courseCode()).orElse(null);
        }

        if (resolvedCourse != null) {
            record.setCourseId(resolvedCourse.getId());
            record.setCourseCode(resolvedCourse.getCode());
            record.setCourseName(resolvedCourse.getName());
        } else {
            record.setCourseCode(request.courseCode() != null ? request.courseCode().trim().toUpperCase() : null);
            record.setCourseName(request.courseCode());
        }

        if (resolvedQuestion != null) {
            record.setQuestionId(resolvedQuestion.getId());
        }
        String title = request.questionTitle() != null && !request.questionTitle().isBlank()
                ? request.questionTitle().trim()
                : "Câu hỏi luyện tập vấn đáp";
        record.setQuestionTitle(title);
        record.setStatus("completed");
        record.setTranscript(request.transcript());
        if (request.audioUrl() != null && !request.audioUrl().isBlank()) {
            record.setAudioUrl(request.audioUrl().trim());
        }
        record.setTotalScore(request.totalScore() != null ? request.totalScore() : 0.0);
        record.setMaxScore(request.maxScore() != null && request.maxScore() > 0 ? request.maxScore() : 10.0);
        record.setNeedsHumanReview(Boolean.TRUE.equals(request.needsHumanReview()));
        record.setEvaluationJson(request.evaluationJson());
        OffsetDateTime now = OffsetDateTime.now();
        record.setCreatedAt(now);
        record.setUpdatedAt(now);

        PracticeRecord saved = practiceRecordRepository.save(record);
        Map<UUID, User> users = loadUserMap();
        return toResponse(saved, users);
    }

    @Transactional(readOnly = true)
    public List<PracticeRecordResponse> getMyRecords(UUID studentId) {
        if (studentId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Bạn cần đăng nhập để xem lịch sử luyện tập.");
        }
        Map<UUID, User> users = loadUserMap();
        return practiceRecordRepository.findByStudentIdOrderByCreatedAtDesc(studentId).stream()
                .map(r -> toResponse(r, users))
                .toList();
    }

    @Transactional(readOnly = true)
    public PracticeRecordResponse getRecordById(UUID recordId, UUID requesterId, boolean isAdmin) {
        if (requesterId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Bạn cần đăng nhập để xem chi tiết phiên luyện tập.");
        }
        PracticeRecord record = practiceRecordRepository.findById(recordId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Không tìm thấy phiên luyện tập này."));

        boolean isOwner = requesterId.equals(record.getStudentId());
        boolean isCourseInstructor = false;
        if (!isOwner && !isAdmin && record.getCourseId() != null) {
            isCourseInstructor = courseRepository.findById(record.getCourseId())
                    .map(c -> requesterId.equals(c.getCreatedBy()))
                    .orElse(false);
        }
        if (!isOwner && !isAdmin && !isCourseInstructor) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Bạn không có quyền xem phiên luyện tập này.");
        }

        Map<UUID, User> users = loadUserMap();
        return toResponse(record, users);
    }

    public Map<String, Object> storeAudioFile(MultipartFile file, UUID studentId) {
        if (studentId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Bạn cần đăng nhập để tải lên bản ghi âm.");
        }
        if (file == null || file.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "File ghi âm đang rỗng.");
        }
        if (file.getSize() > MAX_AUDIO_BYTES) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "File ghi âm vượt quá giới hạn 20MB.");
        }

        String originalName = file.getOriginalFilename() != null ? file.getOriginalFilename() : "recording.webm";
        String ext = ".webm";
        int dotIdx = originalName.lastIndexOf('.');
        if (dotIdx >= 0 && dotIdx < originalName.length() - 1) {
            ext = originalName.substring(dotIdx).toLowerCase(Locale.ROOT);
        }
        if (!ALLOWED_AUDIO_EXTS.contains(ext)) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "Định dạng âm thanh không được hỗ trợ. Chỉ chấp nhận .webm, .wav, .mp3, .m4a, .ogg.");
        }

        String storedFileName = studentId + "_" + UUID.randomUUID() + ext;
        try {
            Files.createDirectories(AUDIO_STORAGE_DIR);
            Path target = AUDIO_STORAGE_DIR.resolve(storedFileName).normalize();
            if (!target.startsWith(AUDIO_STORAGE_DIR)) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Tên file không hợp lệ.");
            }
            Files.copy(file.getInputStream(), target, StandardCopyOption.REPLACE_EXISTING);
            String audioUrl = "/api/practice-records/audio/" + storedFileName;
            return Map.of(
                    "audioUrl", audioUrl,
                    "fileName", storedFileName,
                    "sizeBytes", file.getSize()
            );
        } catch (IOException ex) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "Không thể lưu file ghi âm trên máy chủ.");
        }
    }

    @Transactional(readOnly = true)
    public Path resolveAudioFile(String fileName, UUID requesterId, boolean isAdmin, boolean isInstructor) {
        if (requesterId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Bạn cần đăng nhập để nghe bản ghi âm.");
        }
        if (fileName == null || fileName.isBlank() || fileName.contains("..") || fileName.contains("/") || fileName.contains("\\")) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Tên file ghi âm không hợp lệ.");
        }
        boolean ownsByPrefix = fileName.startsWith(requesterId + "_");
        if (!ownsByPrefix && !isAdmin && !isInstructor) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Bạn không có quyền truy cập file ghi âm này.");
        }
        Path target = AUDIO_STORAGE_DIR.resolve(fileName).normalize();
        if (!target.startsWith(AUDIO_STORAGE_DIR) || !Files.isRegularFile(target)) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Không tìm thấy file ghi âm.");
        }
        return target;
    }

    @Transactional(readOnly = true)
    public List<PracticeRecordResponse> getInstructorRecords(
            UUID instructorId,
            boolean isAdmin,
            UUID courseIdFilter,
            Boolean needsReviewOnly
    ) {
        if (instructorId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Bạn cần đăng nhập để xem kết quả sinh viên.");
        }

        List<PracticeRecord> records;
        if (isAdmin) {
            records = practiceRecordRepository.findAllByOrderByCreatedAtDesc();
        } else {
            Set<UUID> ownedCourseIds = courseRepository.findByActiveTrue().stream()
                    .filter(c -> instructorId.equals(c.getCreatedBy()))
                    .map(Course::getId)
                    .collect(Collectors.toSet());
            if (ownedCourseIds.isEmpty()) {
                return List.of();
            }
            records = practiceRecordRepository.findByCourseIdInOrderByCreatedAtDesc(ownedCourseIds);
        }

        Map<UUID, User> users = loadUserMap();
        return records.stream()
                .filter(r -> courseIdFilter == null || courseIdFilter.equals(r.getCourseId()))
                .filter(r -> !Boolean.TRUE.equals(needsReviewOnly) || r.isNeedsHumanReview())
                .map(r -> toResponse(r, users))
                .toList();
    }

    public PracticeRecordResponse reviewRecord(
            UUID recordId,
            ReviewPracticeRecordRequest request,
            UUID reviewerId,
            boolean isAdmin
    ) {
        if (reviewerId == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Bạn cần đăng nhập để duyệt bài.");
        }

        PracticeRecord record = practiceRecordRepository.findById(recordId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Không tìm thấy phiên luyện tập này."));

        if (!isAdmin) {
            if (record.getCourseId() == null) {
                throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Bạn không có quyền duyệt phiên luyện tập này.");
            }
            Course course = courseRepository.findById(record.getCourseId())
                    .orElseThrow(() -> new ResponseStatusException(HttpStatus.FORBIDDEN, "Không tìm thấy học phần của phiên luyện tập."));
            if (course.getCreatedBy() == null || !course.getCreatedBy().equals(reviewerId)) {
                throw new ResponseStatusException(
                        HttpStatus.FORBIDDEN,
                        "Bạn chỉ được duyệt bài luyện tập thuộc học phần do chính mình phụ trách.");
            }
        }

        double maxScore = record.getMaxScore() != null && record.getMaxScore() > 0 ? record.getMaxScore() : 10.0;
        if (request.instructorScore() == null || request.instructorScore() < 0 || request.instructorScore() > maxScore) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "Điểm chốt của giảng viên phải nằm trong khoảng từ 0 đến " + maxScore + ".");
        }

        double roundedScore = Math.round(request.instructorScore() * 100.0) / 100.0;
        record.setReviewedByInstructor(true);
        record.setNeedsHumanReview(false);
        record.setInstructorScore(roundedScore);
        record.setInstructorNotes(request.instructorNotes() != null ? request.instructorNotes().trim() : "");
        record.setReviewedBy(reviewerId);
        OffsetDateTime now = OffsetDateTime.now();
        record.setReviewedAt(now);
        record.setUpdatedAt(now);

        PracticeRecord saved = practiceRecordRepository.save(record);
        Map<UUID, User> users = loadUserMap();
        return toResponse(saved, users);
    }

    private Optional<Question> resolveQuestion(String rawId) {
        if (rawId == null || rawId.isBlank()) {
            return Optional.empty();
        }
        try {
            return questionRepository.findById(UUID.fromString(rawId.trim()));
        } catch (IllegalArgumentException e) {
            return Optional.empty();
        }
    }

    private Optional<Course> resolveCourse(String rawCourseId, String rawCourseCode) {
        if (rawCourseId != null && !rawCourseId.isBlank()) {
            try {
                Optional<Course> byUuid = courseRepository.findById(UUID.fromString(rawCourseId.trim()));
                if (byUuid.isPresent()) {
                    return byUuid;
                }
            } catch (IllegalArgumentException ignored) {
                Optional<Course> byCode = courseRepository.findByCodeIgnoreCase(rawCourseId.trim());
                if (byCode.isPresent()) {
                    return byCode;
                }
            }
        }
        if (rawCourseCode != null && !rawCourseCode.isBlank()) {
            return courseRepository.findByCodeIgnoreCase(rawCourseCode.trim());
        }
        return Optional.empty();
    }

    private Map<UUID, User> loadUserMap() {
        return userRepository.findAll().stream()
                .collect(Collectors.toMap(User::getId, u -> u, (a, b) -> a));
    }

    private PracticeRecordResponse toResponse(PracticeRecord record, Map<UUID, User> users) {
        User student = users.get(record.getStudentId());
        User reviewer = record.getReviewedBy() != null ? users.get(record.getReviewedBy()) : null;
        return new PracticeRecordResponse(
                record.getId(),
                record.getStudentId(),
                student != null ? student.getFullName() : "Sinh viên",
                student != null ? student.getEmail() : "",
                student != null ? student.getStudentCode() : null,
                student != null ? student.getDepartment() : null,
                record.getCourseId(),
                record.getCourseCode(),
                record.getCourseName(),
                record.getQuestionId(),
                record.getQuestionTitle(),
                record.getStatus(),
                record.getTranscript(),
                record.getAudioUrl(),
                record.getTotalScore(),
                record.getMaxScore(),
                record.isNeedsHumanReview(),
                record.getEvaluationJson(),
                record.isReviewedByInstructor(),
                record.getInstructorScore(),
                record.getInstructorNotes(),
                reviewer != null ? reviewer.getFullName() : null,
                record.getReviewedAt(),
                record.getCreatedAt()
        );
    }
}
