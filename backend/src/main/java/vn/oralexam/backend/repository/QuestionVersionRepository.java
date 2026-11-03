package vn.oralexam.backend.repository;

import java.util.Optional;
import java.util.UUID;

import vn.oralexam.backend.entity.QuestionVersion;
import org.springframework.data.jpa.repository.JpaRepository;

public interface QuestionVersionRepository extends JpaRepository<QuestionVersion, UUID> {
    Optional<QuestionVersion> findTopByQuestionIdOrderByVersionNoDesc(UUID questionId);
}

