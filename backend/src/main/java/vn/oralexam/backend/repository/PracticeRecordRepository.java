package vn.oralexam.backend.repository;

import java.util.Collection;
import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import vn.oralexam.backend.entity.PracticeRecord;

public interface PracticeRecordRepository extends JpaRepository<PracticeRecord, UUID> {
    List<PracticeRecord> findByStudentIdOrderByCreatedAtDesc(UUID studentId);
    List<PracticeRecord> findAllByOrderByCreatedAtDesc();
    List<PracticeRecord> findByCourseIdInOrderByCreatedAtDesc(Collection<UUID> courseIds);
}
