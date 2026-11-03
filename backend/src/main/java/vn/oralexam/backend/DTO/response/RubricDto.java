package vn.oralexam.backend.DTO.response;

import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;

public record RubricDto(
        UUID id,
        UUID questionId,
        List<RubricCriterionDto> criteria,
        BigDecimal totalScore,
        String gradingInstructions
) {
}

