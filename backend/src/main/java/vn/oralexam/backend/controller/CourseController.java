package vn.oralexam.backend.controller;

import java.util.List;
import java.util.Map;
import java.util.UUID;

import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;
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
     * Lấy danh sách môn học khả dụng (hỗ trợ lọc riêng theo giảng viên tạo nếu mineOnly=true)
     */
    @GetMapping
    public List<CourseResponse> getAllCourses(
            @RequestParam(name = "mineOnly", defaultValue = "false") boolean mineOnly,
            Authentication authentication
    ) {
        UUID ownerFilter = mineOnly ? requireUserId(authentication) : null;
        return questionService.getAllCourses(ownerFilter);
    }

    /**
     * Thêm mới một học phần / môn học (gắn với giảng viên đang đăng nhập)
     */
    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public CourseResponse createCourse(
            @Valid @RequestBody SaveCourseRequest request,
            Authentication authentication
    ) {
        UUID userId = requireUserId(authentication);
        return questionService.saveCourse(request, userId, hasAdminRole(authentication));
    }

    /**
     * Cập nhật thông tin học phần (chỉ chủ sở hữu hoặc Admin)
     */
    @PutMapping("/{id}")
    public CourseResponse updateCourse(
            @PathVariable String id,
            @Valid @RequestBody SaveCourseRequest request,
            Authentication authentication
    ) {
        UUID userId = requireUserId(authentication);
        UUID resolvedId = questionService.resolveCourse(id).getId();
        SaveCourseRequest syncedRequest = new SaveCourseRequest(
                resolvedId,
                request.code(),
                request.name(),
                request.description(),
                request.semester(),
                request.department()
        );
        return questionService.saveCourse(syncedRequest, userId, hasAdminRole(authentication));
    }

    /**
     * Xóa mềm học phần, giải phóng mã học phần và dọn thư mục tài liệu RAG (chỉ chủ sở hữu hoặc Admin)
     */
    @DeleteMapping("/{id}")
    public Map<String, Object> deleteCourse(
            @PathVariable String id,
            Authentication authentication
    ) {
        UUID userId = requireUserId(authentication);
        questionService.deleteCourse(id, userId, hasAdminRole(authentication));
        return Map.of("success", true, "message", "Đã xóa học phần thành công.");
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, String>> handleIllegalArgument(IllegalArgumentException ex) {
        return ResponseEntity.badRequest().body(Map.of("message", ex.getMessage() != null ? ex.getMessage() : "Yêu cầu không hợp lệ."));
    }

    private UUID requireUserId(Authentication authentication) {
        if (authentication == null || authentication.getName() == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Bạn cần đăng nhập để thực hiện thao tác này.");
        }
        try {
            return UUID.fromString(authentication.getName());
        } catch (IllegalArgumentException exception) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Phiên đăng nhập không hợp lệ.");
        }
    }

    private boolean hasAdminRole(Authentication authentication) {
        return authentication != null && authentication.getAuthorities().stream()
                .anyMatch(a -> "ROLE_ADMIN".equalsIgnoreCase(a.getAuthority()));
    }
}
