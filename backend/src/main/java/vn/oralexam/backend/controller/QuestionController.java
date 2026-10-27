package vn.oralexam.backend.controller;

import java.io.IOException;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import jakarta.validation.Valid;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import vn.oralexam.backend.DTO.request.BatchImportCommitRequest;
import vn.oralexam.backend.DTO.request.SaveQuestionRequest;
import vn.oralexam.backend.DTO.request.SaveRubricRequest;
import vn.oralexam.backend.DTO.response.QuestionResponse;
import vn.oralexam.backend.DTO.response.RubricDto;
import vn.oralexam.backend.service.QuestionService;

@RestController
@RequestMapping("/api")
public class QuestionController {

    private final QuestionService questionService;

    public QuestionController(QuestionService questionService) {
        this.questionService = questionService;
    }

    /**
     * Lấy danh sách câu hỏi theo môn học hoặc toàn bộ
     */
    @GetMapping("/questions")
    public List<QuestionResponse> getQuestions(@RequestParam(name = "courseId", required = false) String courseId) {
        return questionService.getQuestions(courseId);
    }

    /**
     * Lấy danh sách câu hỏi của một môn học cụ thể
     */
    @GetMapping("/courses/{courseId}/questions")
    public List<QuestionResponse> getQuestionsByCourse(@PathVariable String courseId) {
        return questionService.getQuestions(courseId);
    }

    /**
     * Lấy chi tiết câu hỏi kèm Rubric chấm điểm
     */
    @GetMapping("/questions/{id}")
    public QuestionResponse getQuestionById(@PathVariable UUID id) {
        return questionService.getQuestionById(id);
    }

    /**
     * Tạo mới câu hỏi vấn đáp
     */
    @PostMapping("/questions")
    @ResponseStatus(HttpStatus.CREATED)
    public QuestionResponse createQuestion(
            @Valid @RequestBody SaveQuestionRequest request,
            Authentication authentication
    ) {
        UUID userId = extractUserId(authentication);
        return questionService.saveQuestion(request, userId);
    }

    /**
     * Cập nhật thông tin câu hỏi
     */
    @PutMapping("/questions/{id}")
    public QuestionResponse updateQuestion(
            @PathVariable UUID id,
            @Valid @RequestBody SaveQuestionRequest request,
            Authentication authentication
    ) {
        UUID userId = extractUserId(authentication);
        SaveQuestionRequest syncedRequest = new SaveQuestionRequest(
                id,
                request.courseId(),
                request.topic(),
                request.title(),
                request.content(),
                request.sampleAnswer(),
                request.difficulty(),
                request.timeLimitSeconds(),
                request.tags(),
                request.parentQuestionId()
        );
        return questionService.saveQuestion(syncedRequest, userId);
    }

    /**
     * Cập nhật hoặc lưu phiên bản mới của Rubric chấm điểm
     */
    @PutMapping("/questions/{id}/rubric")
    public RubricDto saveRubric(
            @PathVariable UUID id,
            @RequestBody SaveRubricRequest request,
            Authentication authentication
    ) {
        UUID userId = extractUserId(authentication);
        return questionService.saveRubric(id, request, userId);
    }

    /**
     * Xóa mềm câu hỏi
     */
    @DeleteMapping("/questions/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void deleteQuestion(@PathVariable UUID id) {
        questionService.deleteQuestion(id);
    }

    /**
     * Tải xuống file mẫu Excel (.xlsx) chuẩn hóa cho việc nhập hàng loạt câu hỏi và Rubric
     */
    @GetMapping("/questions/import/template")
    public ResponseEntity<byte[]> downloadExcelTemplate() throws IOException {
        byte[] fileBytes = questionService.generateExcelTemplate();
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"Mau_Ngan_Hang_Cau_Hoi_Van_Dap.xlsx\"")
                .contentType(MediaType.parseMediaType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
                .body(fileBytes);
    }

    /**
     * Lưu hàng loạt câu hỏi và Rubric đã qua kiểm duyệt / chỉnh sửa trên bảng Preview
     */
    @PostMapping("/questions/import/commit")
    public Map<String, Object> commitBatchQuestions(
            @Valid @RequestBody BatchImportCommitRequest request,
            Authentication authentication
    ) {
        UUID userId = extractUserId(authentication);
        int count = questionService.commitBatchQuestions(request, userId);
        return Map.of(
                "success", true,
                "importedCount", count,
                "message", "Đã nhập thành công " + count + " câu hỏi và Rubric vào ngân hàng!"
        );
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
