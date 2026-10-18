package vn.oralexam.backend.security;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Base64;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class JwtTokenService {
    private static final long EXPIRATION_SECONDS = 60 * 60;
    private static final Base64.Encoder ENCODER = Base64.getUrlEncoder().withoutPadding();
    private static final Base64.Decoder DECODER = Base64.getUrlDecoder();
    private final byte[] secret;
    private final ObjectMapper objectMapper;

    public JwtTokenService(@Value("${app.auth.jwt-secret}") String secret, ObjectMapper objectMapper) {
        this.secret = secret.getBytes(StandardCharsets.UTF_8);
        if (this.secret.length < 32) {
            throw new IllegalArgumentException("app.auth.jwt-secret phải có ít nhất 32 bytes.");
        }
        this.objectMapper = objectMapper;
    }

    public String createToken(UUID userId, String email, Set<String> roles) {
        try {
            String header = ENCODER.encodeToString(objectMapper.writeValueAsBytes(
                    new TokenHeader("HS256", "JWT")));
            String payload = ENCODER.encodeToString(objectMapper.writeValueAsBytes(
                    new TokenPayload(userId.toString(), email, List.copyOf(roles),
                            Instant.now().getEpochSecond() + EXPIRATION_SECONDS)));
            String content = header + "." + payload;
            return content + "." + ENCODER.encodeToString(sign(content));
        } catch (Exception exception) {
            throw new IllegalStateException("Không thể tạo access token.", exception);
        }
    }

    public TokenClaims verify(String token) {
        try {
            String[] parts = token.split("\\.");
            if (parts.length != 3) return null;
            String content = parts[0] + "." + parts[1];
            if (!java.security.MessageDigest.isEqual(sign(content), DECODER.decode(parts[2]))) return null;
            TokenHeader header = objectMapper.readValue(DECODER.decode(parts[0]), TokenHeader.class);
            TokenPayload payload = objectMapper.readValue(DECODER.decode(parts[1]), TokenPayload.class);
            if (!"HS256".equals(header.alg()) || payload.exp() <= Instant.now().getEpochSecond()) return null;
            UUID.fromString(payload.sub());
            return new TokenClaims(payload.sub(), payload.email(), payload.roles());
        } catch (Exception exception) {
            return null;
        }
    }

    public long getExpirationSeconds() {
        return EXPIRATION_SECONDS;
    }

    private byte[] sign(String content) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(secret, "HmacSHA256"));
        return mac.doFinal(content.getBytes(StandardCharsets.US_ASCII));
    }

    public record TokenClaims(String subject, String email, List<String> roles) { }
    private record TokenHeader(String alg, String typ) { }
    private record TokenPayload(String sub, String email, List<String> roles, long exp) { }
}
