package vn.oralexam.backend.DTO.request;

public record ReviewPracticeRecordRequest(
        Double instructorScore,
        String instructorNotes
) {
}
