package vn.oralexam.backend.DTO.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record ChangePasswordRequest(
        String currentPassword,
        @NotBlank(message = "Mật khẩu mới không được để trống.")
        @Size(min = 8, max = 72, message = "Mật khẩu mới phải từ 8 đến 72 ký tự.")
        String newPassword) {
}
