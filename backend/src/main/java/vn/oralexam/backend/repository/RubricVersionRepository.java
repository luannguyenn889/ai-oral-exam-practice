package vn.oralexam.backend.repository;

import java.util.Optional;
import java.util.UUID;

import vn.oralexam.backend.entity.RubricVersion;
import org.springframework.data.jpa.repository.JpaRepository;

public interface RubricVersionRepository extends JpaRepository<RubricVersion, UUID> {
    Optional<RubricVersion> findTopByQuestionVersionIdOrderByVersionNoDesc(UUID questionVersionId);
}

