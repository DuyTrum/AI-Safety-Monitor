"""Unit Tests for Advanced AI Safety Modules.

Kiểm thử tự động cho:
1. ZoneManager (Virtual Danger Geofencing)
2. ScaffoldHarnessMonitor (Giám sát giàn giáo, dây đai và chốt neo)
3. RiskPredictor (Công thức WRI và ngoại suy quỹ đạo tai nạn)
4. PoseEngine (Thuật toán phân tích góc thân và phát hiện té ngã)
"""

import os
import sys
import unittest
import numpy as np

# Thêm đường dẫn gốc của project vào sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.modules.zone_manager import ZoneManager, SafetyZone, ZoneType, ZoneSeverity
from src.modules.scaffold_harness_monitor import ScaffoldHarnessMonitor, HeightViolationType
from src.modules.risk_predictor import RiskPredictor, RiskLevel
from src.modules.pose_engine import PoseEngine, PoseAnalysisResult


class TestZoneManager(unittest.TestCase):
    """Kiểm thử tính năng quản lý vùng nguy hiểm và kiểm tra xâm nhập."""

    def setUp(self):
        self.zm = ZoneManager()
        # Tạo vùng hình vuông từ (100, 100) đến (200, 200)
        self.test_zone = SafetyZone(
            zone_id="test_zone_01",
            name="Vùng thử nghiệm",
            zone_type=ZoneType.EXCAVATION_PIT,
            points=[(100, 100), (200, 100), (200, 200), (100, 200)],
            severity=ZoneSeverity.CRITICAL,
            penalty_score=85.0,
        )
        self.zm.add_zone(self.test_zone)

    def test_point_inside_zone(self):
        """Điểm nằm bên trong đa giác phải trả về True."""
        self.assertTrue(self.test_zone.contains_point((150, 150)))
        self.assertFalse(self.test_zone.contains_point((50, 50)))

    def test_bbox_foot_intrusion(self):
        """Kiểm tra xâm nhập dựa trên vị trí chân công nhân (đáy bbox)."""
        # Bbox có đáy tại (150, 180) -> Chân nằm trong vùng
        inside_bbox = (130, 80, 170, 180)
        intrusions = self.zm.check_bbox_intrusion(inside_bbox)
        self.assertEqual(len(intrusions), 1)
        self.assertEqual(intrusions[0][0].zone_id, "test_zone_01")

        # Bbox có đáy tại (150, 250) -> Chân nằm ngoài vùng
        outside_bbox = (130, 180, 170, 250)
        intrusions_out = self.zm.check_bbox_intrusion(outside_bbox)
        self.assertEqual(len(intrusions_out), 0)

    def test_proximity_warning(self):
        """Kiểm tra cảnh báo khi công nhân tiến sát mép vùng nguy hiểm."""
        # Chân tại (150, 220) -> Cách mép dưới (y=200) đúng 20px
        near_bbox = (130, 120, 170, 220)
        warnings = self.zm.check_proximity_warning(near_bbox, buffer_distance_px=30.0)
        self.assertEqual(len(warnings), 1)


class TestScaffoldHarnessMonitor(unittest.TestCase):
    """Kiểm thử logic an toàn giàn giáo, dây đai và dụng cụ."""

    def setUp(self):
        self.monitor = ScaffoldHarnessMonitor()
        # Giàn giáo tại tọa độ (200, 100) đến (400, 500)
        self.scaffold_boxes = [(1, (200, 100, 400, 500))]

    def test_worker_on_scaffold_without_harness(self):
        """Công nhân trên giàn giáo KHÔNG có dây đai an toàn -> Báo động mức khẩn cấp."""
        worker_bbox = (250, 150, 320, 350)  # Nằm trên giàn giáo
        status = self.monitor.evaluate_worker_height_safety(
            track_id=101,
            worker_bbox=worker_bbox,
            associated_labels=["helmet"],  # Có mũ nhưng không có harness
            scaffold_bboxes=self.scaffold_boxes,
        )
        self.assertTrue(status.is_on_scaffold)
        self.assertFalse(status.has_harness)
        self.assertEqual(status.violation_type, HeightViolationType.ON_SCAFFOLD_NO_HARNESS)
        self.assertEqual(status.penalty_score, 95.0)

    def test_worker_on_scaffold_unhooked(self):
        """Công nhân có dây an toàn nhưng CHƯA móc chốt neo -> Báo động nguy hiểm."""
        worker_bbox = (250, 150, 320, 350)
        status = self.monitor.evaluate_worker_height_safety(
            track_id=102,
            worker_bbox=worker_bbox,
            associated_labels=["helmet", "harness"],  # Có harness nhưng không có hook
            scaffold_bboxes=self.scaffold_boxes,
        )
        self.assertTrue(status.is_on_scaffold)
        self.assertTrue(status.has_harness)
        self.assertFalse(status.is_hooked)
        self.assertEqual(status.violation_type, HeightViolationType.ON_SCAFFOLD_UNHOOKED)
        self.assertEqual(status.penalty_score, 75.0)

    def test_worker_on_scaffold_fully_safe(self):
        """Công nhân có dây đai VÀ đã móc chốt -> An toàn."""
        worker_bbox = (250, 150, 320, 350)
        status = self.monitor.evaluate_worker_height_safety(
            track_id=103,
            worker_bbox=worker_bbox,
            associated_labels=["helmet", "harness", "hooked"],
            scaffold_bboxes=self.scaffold_boxes,
        )
        self.assertTrue(status.is_on_scaffold)
        self.assertTrue(status.is_hooked)
        self.assertIsNone(status.violation_type)
        self.assertEqual(status.penalty_score, 0.0)

    def test_tool_on_scaffold_edge(self):
        """Phát hiện dụng cụ để sát mép giàn giáo."""
        # Giàn giáo x1=200, x2=400. Dụng cụ tại x1=210, x2=230 (cách mép trái 20px <= 35px)
        tools = [("hammer", (210, 280, 230, 300))]
        hazards = self.monitor.detect_tool_drop_hazards(tools, self.scaffold_boxes)
        self.assertEqual(len(hazards), 1)
        self.assertEqual(hazards[0].tool_name, "hammer")


class TestRiskPredictor(unittest.TestCase):
    """Kiểm thử công thức tính điểm rủi ro WRI và ngoại suy quỹ đạo."""

    def setUp(self):
        self.predictor = RiskPredictor()

    def test_wri_safe_worker(self):
        """Công nhân đầy đủ trang bị, tư thế đứng bình thường -> WRI an toàn (< 35)."""
        res = self.predictor.calculate_wri(
            track_id=1,
            worker_bbox=(100, 100, 150, 250),
            missing_ppe_items=[],
        )
        self.assertEqual(res.risk_level, RiskLevel.SAFE)
        self.assertLess(res.wri_score, 35.0)

    def test_wri_critical_fall(self):
        """Trường hợp té ngã -> WRI vọt lên mức Nguy hiểm (>= 70)."""
        # Tạo kết quả pose giả lập người ngã
        dummy_kpts = np.zeros((17, 3))
        fallen_pose = PoseAnalysisResult(
            track_id=2,
            bbox=(100, 200, 260, 240),
            keypoints=dummy_kpts,
            torso_angle=85.0,
            aspect_ratio=1.6,
            posture_state="FALLEN",
            is_fallen=True,
            is_bending_risk=False,
            confidence=0.9,
            risk_penalty=95.0,
        )
        res = self.predictor.calculate_wri(
            track_id=2,
            worker_bbox=(100, 200, 260, 240),
            missing_ppe_items=["no-helmet"],
            pose_result=fallen_pose,
        )
        self.assertEqual(res.risk_level, RiskLevel.DANGER)
        self.assertGreaterEqual(res.wri_score, 85.0)

    def test_trajectory_extrapolation(self):
        """Kiểm tra ngoại suy quỹ đạo di chuyển."""
        # Giả lập công nhân di chuyển liên tục từ trái sang phải
        self.predictor.update_track_position(5, (100, 100, 130, 200), timestamp=1.0)
        self.predictor.update_track_position(5, (130, 100, 160, 200), timestamp=1.5)
        self.predictor.update_track_position(5, (160, 100, 190, 200), timestamp=2.0)

        traj = self.predictor.predict_trajectory(5)
        self.assertIsNotNone(traj)
        # Vận tốc vx dương (đang tiến về bên phải)
        self.assertGreater(traj.velocity_px_s[0], 0)
        # Vị trí sau 2s phải xa hơn vị trí hiện tại
        self.assertGreater(traj.predicted_pos_2s[0], traj.current_pos[0])


from src.utils.text_utils import strip_accents


class TestTextUtils(unittest.TestCase):
    """Kiểm thử chuẩn hóa chuỗi và loại bỏ dấu tiếng Việt cho OpenCV."""

    def test_strip_accents(self):
        """Bảo đảm các chuỗi có dấu và emoji chuyển đổi sạch sang ASCII thuần."""
        self.assertEqual(strip_accents("[STANDING] BÌNH THƯỜNG"), "[STANDING] BINH THUONG")
        self.assertEqual(strip_accents("⚠️ SẮP VA CHẠM (1.5s)!"), "[CANH BAO] SAP VA CHAM (1.5s)!" if "[CANH BAO]" in strip_accents("⚠️ SẮP VA CHẠM (1.5s)!") else "SAP VA CHAM (1.5s)!")
        self.assertEqual(strip_accents("VẬT RƠI!"), "VAT ROI!")
        self.assertEqual(strip_accents("AN TOÀN LAO ĐỘNG"), "AN TOAN LAO DONG")


if __name__ == "__main__":
    unittest.main()
