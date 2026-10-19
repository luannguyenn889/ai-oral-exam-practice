package vn.oralexam.backend.controller;

import jakarta.validation.Valid;
import vn.oralexam.backend.DTO.request.GoogleLoginRequest;
import vn.oralexam.backend.DTO.request.LoginRequest;
import vn.oralexam.backend.DTO.request.RegisterRequest;
import vn.oralexam.backend.service.UserService;
import vn.oralexam.backend.service.UserService.AuthResponse;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/auth")
public class UserController {
    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    /**
     * Đăng ký tài khoản người dùng mới bằng email và mật khẩu
     */
    @PostMapping("/register")
    @ResponseStatus(HttpStatus.CREATED)
    public AuthResponse register(@Valid @RequestBody RegisterRequest request) {
        return userService.register(request);
    }

    /**
     * Đăng nhập truyền thống bằng email và mật khẩu
     */
    @PostMapping("/login")
    public AuthResponse login(@Valid @RequestBody LoginRequest request) {
        return userService.login(request);
    }

    /**
     * Đăng nhập / Đăng ký nhanh qua Google ID Token (OAuth2)
     */
    @PostMapping("/google")
    public AuthResponse googleLogin(@Valid @RequestBody GoogleLoginRequest request) {
        return userService.loginWithGoogle(request.idToken(), request.role());
    }
}


