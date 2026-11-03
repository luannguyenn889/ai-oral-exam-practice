package vn.oralexam.backend.DTO.request;

import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;

public record SaveRubricRequest(
        UUID id,
        UUID questionId,
        List<CriterionItem> criteria,
        BigDecimal totalScore,
        String gradingInstructions
) {
    public record CriterionItem(
            UUID id,
            String name,
            String description,
            BigDecimal maxScore
    ) {
    }
}

