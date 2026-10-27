package vn.oralexam.backend.DTO.request;

import java.util.List;
import java.util.UUID;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

public record SaveQuestionRequest(
        UUID id,
        @NotBlank(message = "Mã môn học không được để trống")
        String courseId,
        String topic,
        @NotBlank(message = "Tiêu đề câu hỏi không được để trống")
        String title,
        @NotBlank(message = "Nội dung câu hỏi không được để trống")
        String content,
        String sampleAnswer,
        String difficulty,
        Integer timeLimitSeconds,
        List<String> tags,
        UUID parentQuestionId
) {
}
