package vn.oralexam.backend.repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

import vn.oralexam.backend.entity.Course;
import org.springframework.data.jpa.repository.JpaRepository;

public interface CourseRepository extends JpaRepository<Course, UUID> {
    Optional<Course> findByCodeIgnoreCase(String code);
    List<Course> findByActiveTrue();
}

