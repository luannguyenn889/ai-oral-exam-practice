package vn.oralexam.backend.DTO.request;

import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;

import jakarta.validation.constraints.NotBlank;

public record BatchImportCommitRequest(
        @NotBlank(message = "Mã môn học không được để trống")
        String courseId,
        List<ImportQuestionDto> questions
) {
    public record CriterionDto(
            String name,
            String description,
            BigDecimal maxScore
    ) {
    }

    public record ImportQuestionDto(
            String code,
            String topic,
            String title,
            String content,
            String sampleAnswer,
            String difficulty,
            Integer timeLimitSeconds,
            String parentCode,
            List<String> tags,
            List<CriterionDto> criteria
    ) {
    }
}

