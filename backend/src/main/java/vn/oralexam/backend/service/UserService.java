package vn.oralexam.backend.service;

import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.Set;

import vn.oralexam.backend.DTO.request.LoginRequest;
import vn.oralexam.backend.DTO.request.RegisterRequest;
import vn.oralexam.backend.entity.User;
import vn.oralexam.backend.repository.UserRepository;
import vn.oralexam.backend.security.JwtTokenService;
import org.springframework.http.HttpStatus;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@Service
public class UserService {
    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenService jwtTokenService;

    public UserService(UserRepository userRepository, PasswordEncoder passwordEncoder,
                       JwtTokenService jwtTokenService) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtTokenService = jwtTokenService;
    }

    @Transactional
    public AuthResponse register(RegisterRequest request) {
        if (request.password().getBytes(StandardCharsets.UTF_8).length > 72) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "Mật khẩu không được vượt quá 72 bytes UTF-8.");
        }
        String email = normalizeEmail(request.email());
        if (userRepository.existsByEmailIgnoreCase(email)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Email đã được sử dụng.");
        }

        User user = new User();
        user.setEmail(email);
        user.setFullName(request.fullName().trim());
        user.setPasswordHash(passwordEncoder.encode(request.password()));
        user.setRoles(Set.of(request.role().trim().toLowerCase(Locale.ROOT)));
        try {
            return createAuthResponse(userRepository.saveAndFlush(user));
        } catch (DataIntegrityViolationException exception) {
            // Handles simultaneous registrations that pass the pre-check together.
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Email đã được sử dụng.");
        }
    }

    @Transactional(readOnly = true)
    public AuthResponse login(LoginRequest request) {
        if (request.password().getBytes(StandardCharsets.UTF_8).length > 72) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED,
                    "Email hoặc mật khẩu không chính xác.");
        }
        User user = userRepository.findByEmailIgnoreCase(normalizeEmail(request.email()))
                .filter(User::isActive)
                .filter(candidate -> candidate.getPasswordHash() != null
                        && passwordEncoder.matches(request.password(), candidate.getPasswordHash()))
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.UNAUTHORIZED, "Email hoặc mật khẩu không chính xác."));
        return createAuthResponse(user);
    }

    private AuthResponse createAuthResponse(User user) {
        String token = jwtTokenService.createToken(user.getId(), user.getEmail(), user.getRoles());
        return new AuthResponse(token, "Bearer", jwtTokenService.getExpirationSeconds(),
                new UserProfile(user.getId().toString(), user.getEmail(), user.getFullName(),
                        user.getAvatarUrl(), user.getRoles()));
    }

    private String normalizeEmail(String email) {
        return email.trim().toLowerCase(Locale.ROOT);
    }

    public record AuthResponse(String accessToken, String tokenType, long expiresIn, UserProfile user) { }
    public record UserProfile(String id, String email, String fullName, String avatarUrl, Set<String> roles) { }
}
