package vn.oralexam.backend.DTO.response;

import java.time.OffsetDateTime;
import java.util.UUID;

public record PracticeRecordResponse(
        UUID id,
        UUID studentId,
        String studentName,
        String studentEmail,
        String studentCode,
        String studentDepartment,
        UUID courseId,
        String courseCode,
        String courseName,
        UUID questionId,
        String questionTitle,
        String status,
        String transcript,
        String audioUrl,
        Double totalScore,
        Double maxScore,
        boolean needsHumanReview,
        String evaluationJson,
        boolean reviewedByInstructor,
        Double instructorScore,
        String instructorNotes,
        String reviewerName,
        OffsetDateTime reviewedAt,
        OffsetDateTime createdAt
) {
}
