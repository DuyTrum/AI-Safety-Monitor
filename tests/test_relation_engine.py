"""Unit Tests for Safety Relation Engine & RelateAnything Integration.

Kiểm thử tự động cho:
1. SafetyRelationEngine: Khởi tạo, quản lý từ vựng quan hệ an toàn và cơ chế fallback.
2. classify_relation_hazard: Phân cấp mức độ nguy hiểm theo chuẩn OSHA (Điểm mù xe cơ giới, ngã cao, vật rơi).
3. infer_safety_relations: Suy luận các bộ ba quan hệ (Subject - Predicate - Object).
4. draw_relations_on_frame: Vẽ trực quan hóa liên kết quan hệ và nhãn HUD.
5. Tích hợp liên module với ScaffoldHarnessMonitor và RiskPredictor.
"""

import os
import sys
import unittest
import numpy as np

# Thêm đường dẫn gốc vào sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.modules.relation_engine import (
    SafetyRelationEngine,
    SafetyRelationTriplet,
    RelationHazardSeverity,
    DEFAULT_SAFETY_VOCABULARY,
)
from src.modules.scaffold_harness_monitor import ScaffoldHarnessMonitor, HeightViolationType
from src.modules.risk_predictor import RiskPredictor, RiskLevel


class TestSafetyRelationEngine(unittest.TestCase):
    """Kiểm thử tính năng của bộ máy suy luận quan hệ an toàn SafetyRelationEngine."""

    def setUp(self):
        # Khởi tạo engine ở chế độ CPU/Fallback an toàn cho môi trường test
        self.engine = SafetyRelationEngine(device="cpu")

    def test_vocabulary_initialization_and_update(self):
        """Kiểm tra khởi tạo từ vựng an toàn mặc định và cập nhật từ vựng tùy biến."""
        self.assertGreater(len(self.engine.vocabulary), 5)
        self.assertIn("hooked to", self.engine.vocabulary)
        self.assertIn("standing in blind spot of", self.engine.vocabulary)

        # Cập nhật từ vựng mới
        new_vocab = ["operating machine", "wearing ear protection", "spill near"]
        self.engine.set_vocabulary(new_vocab)
        self.assertEqual(len(self.engine.vocabulary), 3)
        self.assertIn("operating machine", self.engine.vocabulary)

    def test_hazard_classification_vehicle_conflict(self):
        """Kiểm tra phân loại nguy cơ va chạm phương tiện cơ giới & điểm mù (Struck-By)."""
        # Đứng trong điểm mù xe nâng -> NGUY CẤP (CRITICAL)
        is_haz, sev, desc = self.engine.classify_relation_hazard(
            subject_label="person",
            predicate="standing in blind spot of",
            object_label="forklift",
        )
        self.assertTrue(is_haz)
        self.assertEqual(sev, RelationHazardSeverity.CRITICAL)
        self.assertIn("ĐIỂM MÙ", desc)

        # Đi cắt ngang đầu xe tải -> NGUY HIỂM CAO (HIGH)
        is_haz, sev, _ = self.engine.classify_relation_hazard(
            subject_label="worker",
            predicate="walking in path of",
            object_label="truck",
        )
        self.assertTrue(is_haz)
        self.assertEqual(sev, RelationHazardSeverity.HIGH)

    def test_hazard_classification_heights_and_scaffold(self):
        """Kiểm tra phân loại nguy cơ ngã cao trên giàn giáo (Fall Hazards)."""
        # Trên giàn giáo nhưng chưa móc dây -> NGUY CẤP (CRITICAL)
        is_haz, sev, desc = self.engine.classify_relation_hazard(
            subject_label="worker",
            predicate="unhooked from",
            object_label="scaffold",
        )
        self.assertTrue(is_haz)
        self.assertEqual(sev, RelationHazardSeverity.CRITICAL)

        # Đã móc chốt an toàn -> AN TOÀN (LOW)
        is_haz, sev, desc = self.engine.classify_relation_hazard(
            subject_label="harness_hook",
            predicate="hooked to",
            object_label="scaffold_pipe",
        )
        self.assertFalse(is_haz)
        self.assertEqual(sev, RelationHazardSeverity.LOW)

    def test_hazard_classification_suspended_loads(self):
        """Kiểm tra cảnh báo đứng dưới vật tải cẩu treo lơ lửng."""
        is_haz, sev, desc = self.engine.classify_relation_hazard(
            subject_label="worker",
            predicate="working underneath",
            object_label="crane",
        )
        self.assertTrue(is_haz)
        self.assertEqual(sev, RelationHazardSeverity.CRITICAL)

    def test_infer_relations_fallback_mode(self):
        """Kiểm tra suy luận quan hệ trong chế độ hình học ngữ nghĩa (Fallback Mode)."""
        dummy_frame = np.zeros((600, 800, 3), dtype=np.uint8)

        # Giả lập 2 đối tượng: Công nhân #1 và Xe nâng #2 ở gần nhau
        detections = [
            (1, (100, 200, 160, 350), "person", 0.92),
            (2, (180, 220, 320, 360), "forklift", 0.88),
        ]

        triplets = self.engine.infer_safety_relations(dummy_frame, detections)
        self.assertIsInstance(triplets, list)
        self.assertGreater(len(triplets), 0)

        # Kiểm tra nội dung bộ ba quan hệ
        first_trip = triplets[0]
        self.assertIsInstance(first_trip, SafetyRelationTriplet)
        self.assertEqual(first_trip.subject_id, 1)
        self.assertEqual(first_trip.object_id, 2)
        self.assertIn("blind spot", first_trip.predicate)
        self.assertTrue(first_trip.is_hazard)

    def test_draw_relations_on_frame(self):
        """Kiểm tra hàm vẽ trực quan hóa quan hệ trên frame không làm thay đổi kích thước ảnh."""
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        trip = SafetyRelationTriplet(
            subject_id=1,
            subject_label="person",
            subject_bbox=(50, 50, 100, 150),
            predicate="standing in blind spot of",
            object_id=2,
            object_label="forklift",
            object_bbox=(150, 50, 250, 150),
            confidence=0.85,
            is_hazard=True,
            hazard_severity=RelationHazardSeverity.CRITICAL,
            hazard_description="Nguy hiểm điểm mù",
        )

        out_frame = self.engine.draw_relations_on_frame(dummy_frame, [trip])
        self.assertEqual(out_frame.shape, dummy_frame.shape)
        # Khung hình sau khi vẽ phải có pixel khác 0 (có đường nét vẽ)
        self.assertGreater(np.sum(out_frame), 0)

    def test_integration_with_scaffold_monitor(self):
        """Kiểm tra truyền relation_triplets vào ScaffoldHarnessMonitor."""
        scaffold_monitor = ScaffoldHarnessMonitor()
        worker_bbox = (100, 100, 150, 250)
        scaffold_boxes = [(1, (80, 150, 300, 400))]

        # Tạo triplet: worker unhooked from scaffold
        triplet = SafetyRelationTriplet(
            subject_id=10,
            subject_label="person",
            subject_bbox=worker_bbox,
            predicate="unhooked from",
            object_id=1,
            object_label="scaffold",
            object_bbox=(80, 150, 300, 400),
            confidence=0.90,
            is_hazard=True,
            hazard_severity=RelationHazardSeverity.CRITICAL,
        )

        status = scaffold_monitor.evaluate_worker_height_safety(
            track_id=10,
            worker_bbox=worker_bbox,
            associated_labels=["harness"],
            scaffold_bboxes=scaffold_boxes,
            relation_triplets=[triplet],
        )

        self.assertTrue(status.is_on_scaffold)
        self.assertFalse(status.is_hooked)
        self.assertEqual(status.violation_type, HeightViolationType.ON_SCAFFOLD_UNHOOKED)

    def test_integration_with_risk_predictor(self):
        """Kiểm tra truyền relation_triplets vào RiskPredictor nâng cao điểm WRI."""
        risk_predictor = RiskPredictor()
        worker_bbox = (100, 100, 150, 250)

        # Tạo triplet nguy hiểm nghiêm trọng (CRITICAL)
        hazard_trip = SafetyRelationTriplet(
            subject_id=5,
            subject_label="person",
            subject_bbox=worker_bbox,
            predicate="standing in blind spot of",
            object_id=2,
            object_label="forklift",
            object_bbox=(180, 100, 300, 250),
            confidence=0.95,
            is_hazard=True,
            hazard_severity=RelationHazardSeverity.CRITICAL,
        )

        result = risk_predictor.calculate_wri(
            track_id=5,
            worker_bbox=worker_bbox,
            missing_ppe_items=[],
            relation_triplets=[hazard_trip],
        )

        # Do có quan hệ nguy hiểm CRITICAL, WRI phải tăng vọt lên mức DANGER (>= 85)
        self.assertGreaterEqual(result.wri_score, 85.0)
        self.assertEqual(result.risk_level, RiskLevel.DANGER)
        self.assertIn("relation", result.breakdown)
        self.assertGreaterEqual(result.breakdown["relation"], 90.0)


if __name__ == "__main__":
    unittest.main()
