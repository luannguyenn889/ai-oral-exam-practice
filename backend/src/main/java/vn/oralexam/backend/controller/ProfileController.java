package vn.oralexam.backend.controller;

import java.util.Map;
import java.util.UUID;

import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;
import vn.oralexam.backend.DTO.request.ChangePasswordRequest;
import vn.oralexam.backend.DTO.request.UpdateProfileRequest;
import vn.oralexam.backend.service.UserService;
import vn.oralexam.backend.service.UserService.UserProfile;

@RestController
@RequestMapping("/api/users")
public class ProfileController {
    private final UserService userService;

    public ProfileController(UserService userService) {
        this.userService = userService;
    }

    @GetMapping("/me")
    public UserProfile getMyProfile(Authentication authentication) {
        return userService.getProfile(extractUserId(authentication));
    }

    @PutMapping("/me")
    public UserProfile updateMyProfile(
            Authentication authentication,
            @Valid @RequestBody UpdateProfileRequest request) {
        return userService.updateProfile(extractUserId(authentication), request);
    }

    @PutMapping("/me/password")
    public Map<String, Object> changeMyPassword(
            Authentication authentication,
            @Valid @RequestBody ChangePasswordRequest request) {
        boolean hasPassword = userService.changePassword(extractUserId(authentication), request);
        return Map.of(
                "message", "Đổi mật khẩu thành công.",
                "hasPassword", hasPassword);
    }

    private UUID extractUserId(Authentication authentication) {
        if (authentication == null || authentication.getPrincipal() == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Bạn chưa đăng nhập.");
        }
        try {
            return UUID.fromString(authentication.getPrincipal().toString());
        } catch (IllegalArgumentException exception) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Phiên đăng nhập không hợp lệ.");
        }
    }
}
