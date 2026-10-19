package vn.oralexam.backend.DTO.request;

import jakarta.validation.constraints.NotBlank;

/**
 * DTO nhận yêu cầu đăng nhập bằng Google từ Frontend.
 *
 * @param idToken Chuỗi JWT do Google Identity Services cấp khi người dùng hoàn tất đăng nhập.
 * @param role Vai trò người dùng chọn ('student' hoặc 'instructor') khi đăng nhập lần đầu tiên.
 */
public record GoogleLoginRequest(
    @NotBlank(message = "Google ID token không được để trống")
    String idToken,
    String role
) {}


