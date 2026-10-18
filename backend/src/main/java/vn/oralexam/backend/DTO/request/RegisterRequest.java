package vn.oralexam.backend.DTO.request;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record RegisterRequest(
        @NotBlank @Email @Size(max = 320) String email,
        @NotBlank @Size(min = 2, max = 160) String fullName,
        @NotBlank @Size(min = 8, max = 72) String password,
        @NotBlank @Pattern(regexp = "(?i)student|instructor|admin") String role) {
}
