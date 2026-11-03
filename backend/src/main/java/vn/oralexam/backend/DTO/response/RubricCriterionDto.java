package vn.oralexam.backend.DTO.response;

import java.math.BigDecimal;
import java.util.UUID;

public record RubricCriterionDto(
        UUID id,
        String name,
        String description,
        BigDecimal maxScore
) {
}

