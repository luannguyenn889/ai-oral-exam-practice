package vn.oralexam.backend.DTO.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record UpdateProfileRequest(
        @NotBlank(message = "Họ và tên không được để trống.")
        @Size(min = 2, max = 160, message = "Họ và tên phải từ 2 đến 160 ký tự.")
        String fullName,
        @Size(max = 1000, message = "Đường dẫn ảnh đại diện tối đa 1000 ký tự.")
        String avatarUrl,
        @Size(max = 50, message = "Mã sinh viên tối đa 50 ký tự.")
        String studentCode,
        @Size(max = 160, message = "Tên khoa tối đa 160 ký tự.")
        String department) {
}
