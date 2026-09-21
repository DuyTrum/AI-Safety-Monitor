"""Unit Tests for Accident Physics Simulation & What-If Safety Auditor.

Kiểm thử tự động cho:
1. PhysicsSimulator: Động học rơi tự do, tính toán Joule, nón nguy hiểm rơi (Drop Cone),
   va chạm công nhân và bóng ma ngã (Ghost Fall).
2. WhatIfAuditor: Sinh kịch bản giả định tai nạn What-If theo chuẩn OSHA & QCVN 18:2021/BXD.
"""

import math
import os
import sys
import unittest
import numpy as np

# Thêm đường dẫn gốc vào sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.modules.physics_simulator import (
    PhysicsSimulator,
    ImpactSeverity,
    DroppedObjectSimulation,
    GhostFallSimulation,
)
from src.modules.whatif_auditor import (
    WhatIfAuditor,
    WhatIfScenario,
    ScenarioSeverity,
)


class TestPhysicsSimulator(unittest.TestCase):
    """Kiểm thử bộ mô phỏng vật lý tai nạn công trường."""

    def setUp(self):
        self.sim = PhysicsSimulator(pixel_to_meter_ratio=0.02, worker_mass_kg=70.0)

    def test_free_fall_kinematics(self):
        """Kiểm tra tính toán vận tốc, thời gian rơi và động năng theo định luật Newton."""
        h = 10.0  # 10m
        m = 2.0   # 2kg búa tạ
        v, t, joules, severity = self.sim.calculate_free_fall(height_meters=h, mass_kg=m)

        # v = sqrt(2 * 9.80665 * 10) ~ 14.0 m/s
        self.assertAlmostEqual(v, math.sqrt(2 * 9.80665 * 10.0), places=2)
        # t = sqrt(2 * 10 / 9.80665) ~ 1.428s
        self.assertAlmostEqual(t, math.sqrt(20.0 / 9.80665), places=2)
        # E_k = m * g * h = 2 * 9.80665 * 10 ~ 196.13 Joules
        self.assertAlmostEqual(joules, 2.0 * 9.80665 * 10.0, places=2)
        # Với > 100 Joules, mức độ thương tích phải là FATAL
        self.assertEqual(severity, ImpactSeverity.FATAL)

    def test_impact_severity_tiers(self):
        """Kiểm tra các ngưỡng phân cấp thương tật theo Joule."""
        # Nhẹ: 1m, 1kg -> ~9.8J (< 20J) -> MINOR
        _, _, j_minor, sev_minor = self.sim.calculate_free_fall(1.0, 1.0)
        self.assertEqual(sev_minor, ImpactSeverity.MINOR)

        # Vừa: 3m, 1kg -> ~29.4J (20-50J) -> MODERATE
        _, _, j_mod, sev_mod = self.sim.calculate_free_fall(3.0, 1.0)
        self.assertEqual(sev_mod, ImpactSeverity.MODERATE)

        # Nặng: 7m, 1kg -> ~68.6J (50-100J) -> SEVERE
        _, _, j_sev, sev_sev = self.sim.calculate_free_fall(7.0, 1.0)
        self.assertEqual(sev_sev, ImpactSeverity.SEVERE)

    def test_dropped_tool_and_cone_collision(self):
        """Kiểm tra việc chiếu nón rơi và phát hiện công nhân đứng trong vùng nguy hiểm."""
        tool_bbox = (300, 100, 340, 130)  # Dụng cụ ở độ cao y=130
        frame_height = 600
        ground_y = 500

        # Công nhân A: đứng ngay dưới tâm nón (x=320, chân tại y=500)
        worker_a = (1, (300, 350, 340, 500))
        # Công nhân B: đứng xa an toàn (x=100, chân tại y=500)
        worker_b = (2, (80, 350, 120, 500))

        sim_res = self.sim.simulate_dropped_tool(
            tool_bbox=tool_bbox,
            frame_height=frame_height,
            tool_name="hammer",
            ground_y=ground_y,
            custom_mass_kg=1.5,
            worker_bboxes=[worker_a, worker_b],
        )

        self.assertEqual(sim_res.source_label, "hammer")
        self.assertGreater(sim_res.impact_energy_joules, 0.0)
        self.assertEqual(sim_res.drop_cone_ellipse[0], (320, 500))  # Tâm nón rơi
        # Công nhân A phải bị phát hiện nằm trong nón rơi nguy hiểm
        self.assertIn(1, sim_res.workers_at_risk)
        # Công nhân B ở xa không bị nguy hiểm
        self.assertNotIn(2, sim_res.workers_at_risk)

    def test_ghost_fall_trajectory(self):
        """Kiểm tra ngoại suy bóng ma trượt ngã (Ghost Fall)."""
        worker_bbox = (200, 200, 260, 350)
        ghost = self.sim.simulate_worker_ghost_fall(
            track_id=10,
            worker_bbox=worker_bbox,
            frame_height=720,
            fall_cause="POSTURE_LOSS",
            horizontal_velocity_px_s=30.0,
            height_offset_m=3.0,
        )

        self.assertEqual(ghost.track_id, 10)
        self.assertEqual(ghost.fall_cause, "POSTURE_LOSS")
        self.assertEqual(len(ghost.trajectory_points), 4)
        # Đáy bóng ma sau 2s phải thấp hơn hoặc bằng vị trí ban đầu
        self.assertGreaterEqual(ghost.ghost_bbox_2s[3], worker_bbox[3])
        self.assertGreater(ghost.simulated_impact_joules, 1000.0)


    def test_draw_hud_does_not_crash(self):
        """Đảm bảo hàm vẽ HUD mô phỏng chạy trơn tru trên khung hình OpenCV."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        tool_bbox = (300, 100, 330, 120)
        drop_sim = self.sim.simulate_dropped_tool(tool_bbox=tool_bbox, frame_height=480)
        ghost_sim = self.sim.simulate_worker_ghost_fall(
            track_id=1, worker_bbox=(200, 150, 250, 280), frame_height=480
        )

        out_frame = self.sim.draw_physics_hud(frame, [drop_sim], [ghost_sim])
        self.assertEqual(out_frame.shape, frame.shape)


class TestWhatIfAuditor(unittest.TestCase):
    """Kiểm thử Trợ lý AI Phân tích Kịch bản Tai nạn What-If."""

    def setUp(self):
        self.auditor = WhatIfAuditor(gemini_api_key="")  # Chạy ở chế độ Offline Expert System

    def test_tool_drop_scenario(self):
        """Kịch bản rơi dụng cụ phải có chuỗi nguyên nhân và chuẩn OSHA/QCVN phù hợp."""
        scenario = self.auditor.generate_scenario(
            violation_type="tool_drop_hazard",
            context_data={"height_m": 8.0, "mass_kg": 2.0},
        )

        self.assertIsInstance(scenario, WhatIfScenario)
        self.assertEqual(scenario.source_mode, "OFFLINE_EXPERT_SYSTEM")
        self.assertIn("Rơi Dụng Cụ", scenario.title)
        self.assertGreaterEqual(scenario.probability_pct, 70.0)
        self.assertGreater(len(scenario.root_cause_chain), 2)
        self.assertGreater(len(scenario.immediate_actions), 0)
        self.assertIn("18:2021/BXD", scenario.osha_standard)

    def test_scaffold_unhooked_scenario(self):
        """Kịch bản không neo dây an toàn trên giàn giáo."""
        scenario = self.auditor.generate_scenario(
            violation_type="on_scaffold_unhooked",
            context_data={"worker_id": 5},
        )

        self.assertEqual(scenario.severity_level, ScenarioSeverity.CRITICAL)
        self.assertIn("Dây An Toàn", scenario.title)
        self.assertGreater(len(scenario.simulated_consequences), 1)

    def test_fall_detected_scenario(self):
        """Kịch bản té ngã bất động."""
        scenario = self.auditor.generate_scenario(
            violation_type="fall_detected",
            context_data={"worker_id": 2},
        )

        self.assertEqual(scenario.severity_level, ScenarioSeverity.CRITICAL)
        self.assertIn("Té Ngã", scenario.title)

    def test_to_dict_serialization(self):
        """Kiểm tra tuần tự hóa dữ liệu JSON cho API phản hồi."""
        scenario = self.auditor.generate_scenario("no-helmet")
        d = scenario.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["hazard_type"], "no-helmet")
        self.assertIn("scenario_id", d)
        self.assertIn("immediate_actions", d)
        self.assertIn("statistical_basis", d)

    def test_dynamic_probability_calculation(self):
        """Kiểm tra tính toán xác suất rủi ro động theo hàm Logit FMEA."""
        # Trường hợp rủi ro cực cao: đứng sát mép (0.5m), độ cao lớn (10m), nghiêng người (45 độ)
        high_prob, high_lvl, high_desc = WhatIfAuditor.calculate_dynamic_probability(
            "on_scaffold_unhooked",
            ctx={"height_m": 10.0, "torso_angle": 45.0, "distance_to_edge_m": 0.5},
        )
        # Trường hợp rủi ro thấp hơn: đứng xa mép (2.5m), độ cao thấp (2m), đứng thẳng (10 độ)
        low_prob, low_lvl, low_desc = WhatIfAuditor.calculate_dynamic_probability(
            "on_scaffold_unhooked",
            ctx={"height_m": 2.0, "torso_angle": 10.0, "distance_to_edge_m": 2.5},
        )

        self.assertGreater(high_prob, low_prob)
        self.assertIn("FMEA", high_desc)


if __name__ == "__main__":
    unittest.main()

