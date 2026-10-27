package vn.oralexam.backend.controller;

import java.util.List;
import java.util.UUID;

import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import vn.oralexam.backend.DTO.request.SaveCourseRequest;
import vn.oralexam.backend.DTO.response.CourseResponse;
import vn.oralexam.backend.service.QuestionService;

@RestController
@RequestMapping("/api/courses")
public class CourseController {

    private final QuestionService questionService;

    public CourseController(QuestionService questionService) {
        this.questionService = questionService;
    }

    /**
     * Lấy danh sách tất cả môn học khả dụng kèm số lượng câu hỏi và chủ đề
     */
    @GetMapping
    public List<CourseResponse> getAllCourses() {
        return questionService.getAllCourses();
    }

    /**
     * Thêm mới một học phần / môn học
     */
    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public CourseResponse createCourse(
            @Valid @RequestBody SaveCourseRequest request,
            Authentication authentication
    ) {
        UUID userId = extractUserId(authentication);
        return questionService.saveCourse(request, userId);
    }

    /**
     * Cập nhật thông tin học phần
     */
    @PutMapping("/{id}")
    public CourseResponse updateCourse(
            @PathVariable UUID id,
            @Valid @RequestBody SaveCourseRequest request,
            Authentication authentication
    ) {
        UUID userId = extractUserId(authentication);
        SaveCourseRequest syncedRequest = new SaveCourseRequest(
                id,
                request.code(),
                request.name(),
                request.description(),
                request.semester(),
                request.department()
        );
        return questionService.saveCourse(syncedRequest, userId);
    }

    private UUID extractUserId(Authentication authentication) {
        if (authentication != null && authentication.getName() != null) {
            try {
                return UUID.fromString(authentication.getName());
            } catch (IllegalArgumentException ignored) {
            }
        }
        return null;
    }
}
