package vn.oralexam.backend.controller;

import java.nio.file.Path;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;
import vn.oralexam.backend.DTO.request.ReviewPracticeRecordRequest;
import vn.oralexam.backend.DTO.request.SavePracticeRecordRequest;
import vn.oralexam.backend.DTO.response.PracticeRecordResponse;
import vn.oralexam.backend.service.PracticeRecordService;

@RestController
@RequestMapping("/api/practice-records")
public class PracticeRecordController {

    private final PracticeRecordService practiceRecordService;

    public PracticeRecordController(PracticeRecordService practiceRecordService) {
        this.practiceRecordService = practiceRecordService;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public PracticeRecordResponse saveMyRecord(
            @RequestBody SavePracticeRecordRequest request,
            Authentication authentication
    ) {
        UUID userId = requireUserId(authentication);
        return practiceRecordService.saveStudentRecord(request, userId);
    }

    @GetMapping("/me")
    public List<PracticeRecordResponse> getMyRecords(Authentication authentication) {
        UUID userId = requireUserId(authentication);
        return practiceRecordService.getMyRecords(userId);
    }

    @PostMapping(value = "/audio", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    @ResponseStatus(HttpStatus.CREATED)
    public Map<String, Object> uploadAudio(
            @RequestParam("file") MultipartFile file,
            Authentication authentication
    ) {
        UUID userId = requireUserId(authentication);
        return practiceRecordService.storeAudioFile(file, userId);
    }

    @GetMapping("/audio/{fileName:.+}")
    public ResponseEntity<Resource> streamAudio(
            @PathVariable String fileName,
            Authentication authentication
    ) {
        UUID userId = requireUserId(authentication);
        Path audioPath = practiceRecordService.resolveAudioFile(
                fileName,
                userId,
                hasRole(authentication, "ROLE_ADMIN"),
                hasRole(authentication, "ROLE_INSTRUCTOR")
        );
        MediaType mediaType = resolveAudioMediaType(fileName);
        return ResponseEntity.ok()
                .contentType(mediaType)
                .header(HttpHeaders.CONTENT_DISPOSITION, "inline; filename=\"" + audioPath.getFileName() + "\"")
                .body(new FileSystemResource(audioPath));
    }

    @GetMapping("/{id}")
    public PracticeRecordResponse getRecordById(
            @PathVariable UUID id,
            Authentication authentication
    ) {
        UUID userId = requireUserId(authentication);
        return practiceRecordService.getRecordById(id, userId, hasAdminRole(authentication));
    }

    @GetMapping("/instructor")
    public List<PracticeRecordResponse> getInstructorRecords(
            @RequestParam(name = "courseId", required = false) UUID courseId,
            @RequestParam(name = "needsReviewOnly", required = false) Boolean needsReviewOnly,
            Authentication authentication
    ) {
        UUID userId = requireUserId(authentication);
        return practiceRecordService.getInstructorRecords(
                userId,
                hasAdminRole(authentication),
                courseId,
                needsReviewOnly
        );
    }

    @PutMapping("/{id}/review")
    public PracticeRecordResponse reviewRecord(
            @PathVariable UUID id,
            @RequestBody ReviewPracticeRecordRequest request,
            Authentication authentication
    ) {
        UUID userId = requireUserId(authentication);
        return practiceRecordService.reviewRecord(id, request, userId, hasAdminRole(authentication));
    }

    private UUID requireUserId(Authentication authentication) {
        if (authentication == null || authentication.getName() == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Bạn cần đăng nhập để thực hiện thao tác này.");
        }
        try {
            return UUID.fromString(authentication.getName());
        } catch (IllegalArgumentException e) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Phiên đăng nhập không hợp lệ.");
        }
    }

    private boolean hasAdminRole(Authentication authentication) {
        return hasRole(authentication, "ROLE_ADMIN");
    }

    private boolean hasRole(Authentication authentication, String role) {
        if (authentication == null || authentication.getAuthorities() == null) {
            return false;
        }
        return authentication.getAuthorities().stream()
                .anyMatch(a -> role.equalsIgnoreCase(a.getAuthority()));
    }

    private MediaType resolveAudioMediaType(String fileName) {
        String lower = fileName.toLowerCase(Locale.ROOT);
        if (lower.endsWith(".wav")) return MediaType.parseMediaType("audio/wav");
        if (lower.endsWith(".mp3")) return MediaType.parseMediaType("audio/mpeg");
        if (lower.endsWith(".m4a")) return MediaType.parseMediaType("audio/mp4");
        if (lower.endsWith(".ogg")) return MediaType.parseMediaType("audio/ogg");
        return MediaType.parseMediaType("audio/webm");
    }
}
