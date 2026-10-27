package vn.oralexam.backend.repository;

import java.util.List;
import java.util.UUID;

import vn.oralexam.backend.entity.Question;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface QuestionRepository extends JpaRepository<Question, UUID> {
    List<Question> findByCourseIdAndActiveTrue(UUID courseId);
    List<Question> findByActiveTrue();

    @Query("SELECT q FROM Question q LEFT JOIN FETCH q.versions v LEFT JOIN FETCH v.rubricVersions rv LEFT JOIN FETCH rv.criteria WHERE q.id = :id")
    Question findDetailedById(@Param("id") UUID id);
}

