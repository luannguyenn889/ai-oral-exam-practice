package vn.oralexam.backend.DTO.request;

public record SavePracticeRecordRequest(
        String courseId,
        String courseCode,
        String questionId,
        String questionTitle,
        String transcript,
        String audioUrl,
        Double totalScore,
        Double maxScore,
        Boolean needsHumanReview,
        String evaluationJson
) {
}
