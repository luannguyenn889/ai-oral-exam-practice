package vn.oralexam.backend.controller;

import org.springframework.http.*;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.multipart.MultipartFile;

import java.util.Map;

@RestController
@RequestMapping("/api/drive")
public class DriveSyncController {

    @PostMapping("/upload")
    public ResponseEntity<?> uploadFromDrive(
            @RequestParam("file") MultipartFile file,
            @RequestParam("courseId") String courseId) {
        try {
            RestTemplate restTemplate = new RestTemplate();
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.MULTIPART_FORM_DATA);

            MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
            body.add("course_id", courseId);
            body.add("force_reindex", "false");
            body.add("file", new org.springframework.core.io.ByteArrayResource(file.getBytes()) {
                @Override
                public String getFilename() {
                    return file.getOriginalFilename();
                }
            });

            HttpEntity<MultiValueMap<String, Object>> requestEntity = new HttpEntity<>(body, headers);
            String aiResponse = restTemplate.postForObject("http://localhost:8000/ai/rag/upload", requestEntity, String.class);

            return ResponseEntity.ok(Map.of("message", "Đồng bộ thành công", "aiResponse", aiResponse));
        } catch (Exception e) {
            return ResponseEntity.internalServerError().body("Lỗi: " + e.getMessage());
        }
    }
}