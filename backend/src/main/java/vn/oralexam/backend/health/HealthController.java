package vn.oralexam.backend.health;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/health")
public class HealthController {
    private final AiServiceHealthClient aiServiceHealthClient;

    public HealthController(AiServiceHealthClient aiServiceHealthClient) {
        this.aiServiceHealthClient = aiServiceHealthClient;
    }

    @GetMapping
    public HealthResponse health() {
        return new HealthResponse("UP", "backend", aiServiceHealthClient.isAvailable() ? "UP" : "DOWN");
    }

    public record HealthResponse(String status, String service, String aiService) {
    }
}
