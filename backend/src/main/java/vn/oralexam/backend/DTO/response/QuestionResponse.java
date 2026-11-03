package vn.oralexam.backend.DTO.response;

import java.util.List;
import java.util.UUID;

public record QuestionResponse(
        UUID id,
        UUID courseId,
        String topic,
        String title,
        String content,
        String sampleAnswer,
        String difficulty,
        Integer timeLimitSeconds,
        List<String> tags,
        RubricDto rubric,
        UUID parentQuestionId
) {
}
