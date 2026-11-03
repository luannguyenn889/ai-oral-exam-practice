package vn.oralexam.backend.DTO.request;

import java.util.UUID;

import jakarta.validation.constraints.NotBlank;

public record SaveCourseRequest(
        UUID id,
        @NotBlank(message = "Mã học phần không được để trống")
        String code,
        @NotBlank(message = "Tên môn học không được để trống")
        String name,
        String description,
        String semester,
        String department
) {
}

