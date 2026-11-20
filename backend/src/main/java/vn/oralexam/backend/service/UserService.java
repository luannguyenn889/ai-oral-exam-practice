package vn.oralexam.backend.service;

import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.Locale;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;

import com.google.api.client.googleapis.auth.oauth2.GoogleIdToken;
import com.google.api.client.googleapis.auth.oauth2.GoogleIdTokenVerifier;
import com.google.api.client.http.javanet.NetHttpTransport;
import com.google.api.client.json.gson.GsonFactory;
import vn.oralexam.backend.DTO.request.ChangePasswordRequest;
import vn.oralexam.backend.DTO.request.LoginRequest;
import vn.oralexam.backend.DTO.request.RegisterRequest;
import vn.oralexam.backend.DTO.request.UpdateProfileRequest;
import vn.oralexam.backend.entity.User;
import vn.oralexam.backend.repository.UserRepository;
import vn.oralexam.backend.security.JwtTokenService;
import org.springframework.beans.factory.annotation.Value;
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

    @Value("${app.auth.google-client-id:569426721711-6ub3hgomi74b201otif6cpe3oq53s5fj.apps.googleusercontent.com}")
    private String googleClientId;

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

    /**
     * Xác thực người dùng thông qua Google ID Token (OAuth2 / OpenID Connect).
     *
     * Luồng xử lý (Cách 3):
     * 1. Xác thực chữ ký số và Audience của token với Google qua GoogleIdTokenVerifier.
     * 2. Trích xuất thông tin người dùng từ payload (email, họ tên, ảnh đại diện).
     * 3. Đồng bộ User vào Database:
     *    - Nếu tài khoản ĐÃ TỒN TẠI: Đăng nhập thẳng với các quyền hiện có trong DB (bỏ qua requestedRole để bảo mật).
     *    - Nếu tài khoản CHƯA TỒN TẠI (lần đầu):
     *        + Nếu requestedRole chưa được chọn: Trả về cờ needsRoleSelection = true yêu cầu phía Frontend hiển thị giao diện chọn vai trò.
     *        + Nếu requestedRole đã được chọn ('student' hoặc 'instructor'): Tạo mới User với vai trò đó.
     * 4. Tạo JWT Access Token của hệ thống kèm theo Roles để người dùng sử dụng.
     *
     * @param tokenFromClient Chuỗi ID Token (JWT) do Google cấp cho phía Frontend Angular.
     * @param requestedRole Vai trò người dùng lựa chọn ('student' hoặc 'instructor') ở lần đầu đăng nhập.
     * @return AuthResponse chứa Access Token hệ thống hoặc thông báo yêu cầu chọn vai trò.
     */
    @Transactional
    public AuthResponse loginWithGoogle(String tokenFromClient, String requestedRole) {
        try {
            // Khởi tạo verifier với Client ID của dự án đã đăng ký trên Google Cloud Console
            GoogleIdTokenVerifier verifier = new GoogleIdTokenVerifier.Builder(
                    new NetHttpTransport(), new GsonFactory())
                    .setAudience(Collections.singletonList(googleClientId))
                    .build();

            // Xác thực token với máy chủ Google
            GoogleIdToken idToken = verifier.verify(tokenFromClient);
            if (idToken == null) {
                throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Google ID token không hợp lệ hoặc đã hết hạn.");
            }

            // Lấy thông tin cá nhân từ payload của Google
            GoogleIdToken.Payload payload = idToken.getPayload();
            String email = normalizeEmail(payload.getEmail());
            String name = (String) payload.get("name");
            String pictureUrl = (String) payload.get("picture");

            // 1. Kiểm tra xem người dùng đã từng đăng ký/đăng nhập trong DB chưa
            Optional<User> existingUserOpt = userRepository.findByEmailIgnoreCase(email);

            if (existingUserOpt.isEmpty()) {
                // Tài khoản mới lần đầu đăng nhập
                // Nếu chưa truyền vai trò -> yêu cầu người dùng chọn vai trò
                if (requestedRole == null || requestedRole.trim().isBlank()) {
                    return AuthResponse.requireRoleSelection(email, name, pictureUrl);
                }

                // Kiểm tra tính hợp lệ của vai trò được chọn (chỉ cho phép student hoặc instructor, chặn admin)
                String normalizedRole = requestedRole.trim().toLowerCase(Locale.ROOT);
                if (!Set.of("student", "instructor").contains(normalizedRole)) {
                    throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                            "Vai trò không hợp lệ. Chỉ chấp nhận 'student' hoặc 'instructor'.");
                }

                // Tạo tài khoản mới với vai trò đã chọn
                User newUser = new User();
                newUser.setEmail(email);
                newUser.setFullName(name != null && !name.isBlank() ? name.trim() : email.split("@")[0]);
                newUser.setAvatarUrl(pictureUrl);
                newUser.setPasswordHash(null); // Đăng nhập Google không cần mật khẩu cục bộ
                newUser.setRoles(Set.of(normalizedRole));
                User savedUser = userRepository.saveAndFlush(newUser);
                return createAuthResponse(savedUser);
            }

            // 2. Tài khoản đã tồn tại trong DB -> đăng nhập ngay
            User user = existingUserOpt.get();
            if (!user.isActive()) {
                throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Tài khoản của bạn đã bị khóa.");
            }

            // Đồng bộ cập nhật ảnh đại diện mới nhất từ Google nếu có thay đổi
            if (pictureUrl != null && !pictureUrl.equals(user.getAvatarUrl())) {
                user.setAvatarUrl(pictureUrl);
                user = userRepository.saveAndFlush(user);
            }

            // Cấp JWT Access Token của hệ thống và trả về kết quả
            return createAuthResponse(user);
        } catch (ResponseStatusException e) {
            throw e;
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "Lỗi xác thực Google: " + e.getMessage());
        }
    }

    @Transactional(readOnly = true)
    public UserProfile getProfile(UUID userId) {
        User user = findActiveUserById(userId);
        return toUserProfile(user);
    }

    @Transactional
    public UserProfile updateProfile(UUID userId, UpdateProfileRequest request) {
        User user = findActiveUserById(userId);
        user.setFullName(request.fullName().trim());
        user.setAvatarUrl(trimToNull(request.avatarUrl()));
        user.setStudentCode(trimToNull(request.studentCode()));
        user.setDepartment(trimToNull(request.department()));
        return toUserProfile(userRepository.saveAndFlush(user));
    }

    @Transactional
    public boolean changePassword(UUID userId, ChangePasswordRequest request) {
        if (request.newPassword().getBytes(StandardCharsets.UTF_8).length > 72) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "Mật khẩu mới không được vượt quá 72 bytes UTF-8.");
        }
        User user = findActiveUserById(userId);
        if (user.getPasswordHash() != null && !user.getPasswordHash().isBlank()) {
            if (request.currentPassword() == null || request.currentPassword().isBlank()) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                        "Vui lòng nhập mật khẩu hiện tại.");
            }
            if (!passwordEncoder.matches(request.currentPassword(), user.getPasswordHash())) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                        "Mật khẩu hiện tại không chính xác.");
            }
            if (passwordEncoder.matches(request.newPassword(), user.getPasswordHash())) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                        "Mật khẩu mới không được trùng với mật khẩu hiện tại.");
            }
        }
        user.setPasswordHash(passwordEncoder.encode(request.newPassword()));
        userRepository.saveAndFlush(user);
        return true;
    }

    private User findActiveUserById(UUID userId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND,
                        "Không tìm thấy tài khoản người dùng."));
        if (!user.isActive()) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN,
                    "Tài khoản của bạn đã bị khóa.");
        }
        return user;
    }

    private AuthResponse createAuthResponse(User user) {
        String token = jwtTokenService.createToken(user.getId(), user.getEmail(), user.getRoles());
        return AuthResponse.success(token, "Bearer", jwtTokenService.getExpirationSeconds(),
                toUserProfile(user));
    }

    private UserProfile toUserProfile(User user) {
        return new UserProfile(
                user.getId().toString(),
                user.getEmail(),
                user.getFullName(),
                user.getAvatarUrl(),
                user.getRoles(),
                user.getStudentCode(),
                user.getDepartment(),
                user.getPasswordHash() != null && !user.getPasswordHash().isBlank());
    }

    private String trimToNull(String value) {
        if (value == null) return null;
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }

    private String normalizeEmail(String email) {
        return email.trim().toLowerCase(Locale.ROOT);
    }

    public record AuthResponse(
            String accessToken,
            String tokenType,
            long expiresIn,
            UserProfile user,
            boolean needsRoleSelection
    ) {
        public static AuthResponse success(String token, String tokenType, long expiresIn, UserProfile user) {
            return new AuthResponse(token, tokenType, expiresIn, user, false);
        }

        public static AuthResponse requireRoleSelection(String email, String fullName, String avatarUrl) {
            return new AuthResponse(null, null, 0,
                    new UserProfile(null, email, fullName, avatarUrl, Collections.emptySet(), null, null, false),
                    true);
        }
    }

    public record UserProfile(
            String id,
            String email,
            String fullName,
            String avatarUrl,
            Set<String> roles,
            String studentCode,
            String department,
            boolean hasPassword) { }
}

