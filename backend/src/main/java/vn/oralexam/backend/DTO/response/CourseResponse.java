package vn.oralexam.backend.DTO.response;

import java.util.List;
import java.util.UUID;

public record CourseResponse(
        UUID id,
        String code,
        String name,
        String description,
        String semester,
        String department,
        int questionCount,
        List<String> topics,
        UUID createdBy,
        String instructorName
) {
}

