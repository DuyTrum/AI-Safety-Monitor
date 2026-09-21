"""Dynamic Accident Risk Prediction & Trajectory Forecasting Engine Module.

Triển khai:
1. Mô hình ngoại suy quỹ đạo di chuyển (Trajectory Forecasting & Early Warning) qua Kalman / Velocity vector.
2. Công thức Chỉ số Rủi ro Công nhân Động (Dynamic Worker Risk Index - WRI v2.0) tổng hợp 5 nhóm yếu tố.
3. Dự báo trước nguy cơ va chạm / rơi ngã trong khoảng 2 - 4 giây tiếp theo (Time-To-Danger - TTD).
"""

import collections
import logging
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Deque, Dict, List, Optional, Tuple, Any

import cv2
import numpy as np

from .zone_manager import ZoneManager, SafetyZone
from .pose_engine import PoseAnalysisResult
from .scaffold_harness_monitor import HeightSafetyStatus
from src.utils.text_utils import strip_accents

logger = logging.getLogger("RiskPredictor")


class RiskLevel(str, Enum):
    """Cấp độ rủi ro tai nạn."""

    SAFE = "safe"  # 0 - 34: An toàn
    WARNING = "warning"  # 35 - 69: Cảnh giác / Có yếu tố rủi ro
    DANGER = "danger"  # 70 - 100: Nguy cấp / Nguy cơ tai nạn sắp xảy ra


@dataclass
class TrajectoryPrediction:
    """Dự báo vị trí và quỹ đạo di chuyển tương lai."""

    track_id: int
    current_pos: Tuple[float, float]
    velocity_px_s: Tuple[float, float]  # (vx, vy) pixel / giây
    speed_px_s: float
    predicted_pos_2s: Tuple[float, float]
    predicted_pos_3s: Tuple[float, float]
    imminent_zone_collision: Optional[SafetyZone] = None
    time_to_danger_seconds: Optional[float] = None


@dataclass
class RiskAssessmentResult:
    """Kết quả đánh giá rủi ro tổng hợp cho một công nhân."""

    track_id: int
    bbox: Tuple[int, int, int, int]
    wri_score: float  # Điểm rủi ro từ 0.0 đến 100.0%
    risk_level: RiskLevel
    breakdown: Dict[str, float]  # Chi tiết điểm từng thành phần
    active_hazard_tags: List[str]  # Danh sách các thẻ nguy cơ (vd: "NO_HELMET", "UNHOOKED_SCAFFOLD")
    trajectory: Optional[TrajectoryPrediction] = None
    recommendation: str = "Tiếp tục quan sát"


class RiskPredictor:
    """Bộ máy dự đoán rủi ro và ngoại suy quỹ đạo tai nạn."""

    def __init__(
        self,
        history_len: int = 25,
        w_ppe: float = 0.20,
        w_pose: float = 0.25,
        w_height: float = 0.25,
        w_zone: float = 0.15,
        w_traj: float = 0.15,
    ) -> None:
        """Khởi tạo bộ dự đoán rủi ro.

        Args:
            history_len: Số lượng khung hình lưu vết quỹ đạo gần nhất.
            w_ppe: Trọng số rủi ro vi phạm trang bị bảo hộ (PPE).
            w_pose: Trọng số rủi ro tư thế và té ngã.
            w_height: Trọng số rủi ro làm việc trên cao và giàn giáo.
            w_zone: Trọng số rủi ro xâm nhập vùng cấm hiện tại.
            w_traj: Trọng số rủi ro quỹ đạo di chuyển hướng vào vùng nguy hiểm.
        """
        self.history_len = history_len
        self.w_ppe = w_ppe
        self.w_pose = w_pose
        self.w_height = w_height
        self.w_zone = w_zone
        self.w_traj = w_traj

        # Lưu vết quỹ đạo: track_id -> Deque[(x, y, timestamp)]
        self.track_histories: Dict[int, Deque[Tuple[float, float, float]]] = {}

    def update_track_position(self, track_id: int, bbox: Tuple[int, int, int, int], timestamp: Optional[float] = None) -> None:
        """Cập nhật tọa độ chân công nhân vào lịch sử quỹ đạo.

        Args:
            track_id: Mã định danh đối tượng.
            bbox: Tọa độ bounding box (x1, y1, x2, y2).
            timestamp: Mốc thời gian (mặc định time.time()).
        """
        if timestamp is None:
            timestamp = time.time()

        if track_id not in self.track_histories:
            self.track_histories[track_id] = collections.deque(maxlen=self.history_len)

        # Sử dụng tâm đáy (chân) của công nhân
        foot_x = (bbox[0] + bbox[2]) / 2.0
        foot_y = float(bbox[3])
        self.track_histories[track_id].append((foot_x, foot_y, timestamp))

    def predict_trajectory(
        self, track_id: int, zone_manager: Optional[ZoneManager] = None
    ) -> Optional[TrajectoryPrediction]:
        """Ngoại suy vị trí tương lai và kiểm tra va chạm vùng nguy hiểm trong 2 - 3s tới.

        Args:
            track_id: Mã định danh đối tượng.
            zone_manager: Bộ quản lý vùng nguy hiểm để đối chiếu.

        Returns:
            Optional[TrajectoryPrediction]: Thông tin dự báo quỹ đạo.
        """
        hist = self.track_histories.get(track_id)
        if not hist or len(hist) < 3:
            return None

        # Tính toán vector vận tốc dựa trên 5-10 khung hình gần nhất
        curr_x, curr_y, curr_t = hist[-1]
        past_idx = max(0, len(hist) - 8)
        past_x, past_y, past_t = hist[past_idx]

        dt = curr_t - past_t
        if dt <= 0.05:
            vx, vy = 0.0, 0.0
        else:
            vx = (curr_x - past_x) / dt
            vy = (curr_y - past_y) / dt

        speed = math.sqrt(vx * vx + vy * vy)

        # Ngoại suy vị trí tại t = 1.5s và t = 3.0s
        pred_x_2s = curr_x + vx * 1.5
        pred_y_2s = curr_y + vy * 1.5
        pred_x_3s = curr_x + vx * 3.0
        pred_y_3s = curr_y + vy * 3.0

        # Kiểm tra quỹ đạo tương lai có đi vào vùng nguy hiểm không
        imminent_zone = None
        ttd = None

        if zone_manager and speed > 15.0:  # Chỉ xét khi đối tượng đang chuyển động
            # Kiểm tra các điểm nội suy dọc theo tia chuyển động
            for step_sec in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]:
                test_pt = (curr_x + vx * step_sec, curr_y + vy * step_sec)
                for zone in zone_manager.list_zones():
                    if zone.is_active and zone.contains_point(test_pt):
                        imminent_zone = zone
                        ttd = step_sec
                        break
                if imminent_zone:
                    break

        return TrajectoryPrediction(
            track_id=track_id,
            current_pos=(curr_x, curr_y),
            velocity_px_s=(vx, vy),
            speed_px_s=speed,
            predicted_pos_2s=(pred_x_2s, pred_y_2s),
            predicted_pos_3s=(pred_x_3s, pred_y_3s),
            imminent_zone_collision=imminent_zone,
            time_to_danger_seconds=ttd,
        )

    def calculate_wri(
        self,
        track_id: int,
        worker_bbox: Tuple[int, int, int, int],
        missing_ppe_items: List[str],
        pose_result: Optional[PoseAnalysisResult] = None,
        height_status: Optional[HeightSafetyStatus] = None,
        intrusions: Optional[List[Tuple[SafetyZone, float]]] = None,
        zone_manager: Optional[ZoneManager] = None,
        relation_triplets: Optional[List[Any]] = None,
    ) -> RiskAssessmentResult:
        """Tính toán Chỉ số Rủi ro Công nhân Động (Dynamic Worker Risk Index - WRI).

        Args:
            track_id: Mã định danh công nhân.
            worker_bbox: Tọa độ bounding box của công nhân.
            missing_ppe_items: Danh sách các trang bị bảo hộ còn thiếu (vd: ["no-helmet"]).
            pose_result: Kết quả phân tích tư thế khớp xương.
            height_status: Trạng thái an toàn làm việc trên giàn giáo.
            intrusions: Danh sách các vùng nguy hiểm đang xâm nhập hiện tại.
            zone_manager: Bộ quản lý vùng nguy hiểm để kiểm tra quỹ đạo.
            relation_triplets: Bộ ba quan hệ thị giác từ SafetyRelationEngine.

        Returns:
            RiskAssessmentResult: Kết quả đánh giá rủi ro đa nhân tố.
        """
        hazard_tags: List[str] = []

        # 1. Điểm rủi ro Trang bị Bảo hộ (PPE Score: 0 - 100)
        s_ppe = 0.0
        for item in missing_ppe_items:
            if item in ["no-helmet", "no_helmet"]:
                s_ppe += 50.0
                hazard_tags.append("THIẾU_MŨ_BẢO_HỘ")
            elif item in ["no-vest", "no_vest"]:
                s_ppe += 35.0
                hazard_tags.append("THIẾU_ÁO_PHẢN_QUANG")
            elif item in ["no-boots", "no-gloves", "no-goggles"]:
                s_ppe += 15.0
                hazard_tags.append(f"THIẾU_{item.upper().replace('-', '_')}")
        s_ppe = min(100.0, s_ppe)

        # 2. Điểm rủi ro Tư thế & Té ngã (Pose Score: 0 - 100)
        s_pose = 0.0
        if pose_result:
            s_pose = pose_result.risk_penalty
            if pose_result.is_fallen:
                hazard_tags.append("🚨_PHÁT_HIỆN_TÉ_NGÃ")
            elif pose_result.is_bending_risk:
                hazard_tags.append("CÚI_GẬP_LƯNG_NGUY_HIỂM")

        # 3. Điểm rủi ro Giàn giáo & Độ cao (Height Score: 0 - 100)
        s_height = 0.0
        if height_status:
            s_height = height_status.penalty_score
            if height_status.violation_type:
                hazard_tags.append(height_status.violation_type.value.upper())

        # 4. Điểm rủi ro Vùng nguy hiểm Hiện tại (Zone Intrusion Score: 0 - 100)
        s_zone = 0.0
        if intrusions and len(intrusions) > 0:
            # Lấy điểm phạt cao nhất trong số các vùng đang xâm nhập
            max_penalty = max(zone.penalty_score for zone, _ in intrusions)
            s_zone = max_penalty
            for zone, _ in intrusions:
                hazard_tags.append(f"XÂM_NHẬP_{zone.zone_type.value.upper()}")

        # 5. Điểm dự báo Quỹ đạo Tai nạn (Trajectory Early Warning Score: 0 - 100)
        self.update_track_position(track_id, worker_bbox)
        trajectory = self.predict_trajectory(track_id, zone_manager)
        s_traj = 0.0
        if trajectory and trajectory.imminent_zone_collision:
            ttd = trajectory.time_to_danger_seconds or 3.0
            # Càng gần thời gian va chạm thì điểm phạt càng cao
            s_traj = max(60.0, 100.0 - (ttd * 12.0))
            hazard_tags.append(f"DỰ_BÁO_RƠI_NGÃ_TRONG_{ttd:.1f}S")

        # 6. Điểm rủi ro Tương tác Ngữ cảnh Thị giác (Scene Graph Relation Hazards: 0 - 100)
        s_relation = 0.0
        if relation_triplets:
            for trip in relation_triplets:
                t_sid = getattr(trip, "subject_id", None)
                t_oid = getattr(trip, "object_id", None)
                if t_sid == track_id or t_oid == track_id:
                    if getattr(trip, "is_hazard", False):
                        sev = getattr(trip, "hazard_severity", None)
                        sev_val = sev.value if hasattr(sev, "value") else str(sev)
                        if sev_val == "CRITICAL":
                            s_relation = max(s_relation, 95.0)
                        elif sev_val == "HIGH":
                            s_relation = max(s_relation, 75.0)
                        elif sev_val == "MEDIUM":
                            s_relation = max(s_relation, 50.0)
                        else:
                            s_relation = max(s_relation, 30.0)

                        pred_tag = getattr(trip, "predicate", "HAZARD").upper().replace(" ", "_")
                        hazard_tags.append(f"QUAN_HỆ_NGUY_HIỂM_{pred_tag}")

        # TỔNG HỢP CÔNG THỨC WRI ĐỘNG:
        total_wri = (
            self.w_ppe * s_ppe
            + self.w_pose * s_pose
            + self.w_height * s_height
            + self.w_zone * s_zone
            + self.w_traj * s_traj
        )

        # Nếu có quan hệ rủi ro nghiêm trọng (ví dụ: đứng trong điểm mù xe nâng, dưới tải cẩu)
        if s_relation > 0:
            # Gia tăng rủi ro tương tác theo hệ số tỷ lệ
            total_wri = max(total_wri, total_wri * 0.7 + s_relation * 0.4)

        # Trường hợp ngoại lệ khẩn cấp: Nếu Té ngã hoặc Giàn giáo không đai bảo hộ -> Kéo WRI lên thẳng >= 85
        if (pose_result and pose_result.is_fallen) or (height_status and height_status.penalty_score >= 90) or s_relation >= 90:
            total_wri = max(total_wri, 90.0)

        total_wri = min(100.0, round(total_wri, 1))

        # Phân cấp mức độ rủi ro
        if total_wri >= 70.0:
            risk_level = RiskLevel.DANGER
            recommendation = "🚨 BÁO ĐỘNG ĐỎ: Can thiệp dừng thi công khẩn cấp!"
        elif total_wri >= 35.0:
            risk_level = RiskLevel.WARNING
            recommendation = "⚠️ CẢNH BÁO VÀNG: Nhắc nhở an toàn viên kiểm tra."
        else:
            risk_level = RiskLevel.SAFE
            recommendation = "🟢 AN TOÀN: Tiếp tục giám sát định kỳ."

        return RiskAssessmentResult(
            track_id=track_id,
            bbox=worker_bbox,
            wri_score=total_wri,
            risk_level=risk_level,
            breakdown={
                "ppe": round(s_ppe, 1),
                "pose": round(s_pose, 1),
                "height": round(s_height, 1),
                "zone": round(s_zone, 1),
                "trajectory": round(s_traj, 1),
                "relation": round(s_relation, 1),
            },
            active_hazard_tags=hazard_tags,
            trajectory=trajectory,
            recommendation=recommendation,
        )

    def draw_risk_hud(
        self,
        frame: np.ndarray,
        assessments: List[RiskAssessmentResult],
        draw_trajectory_arrow: bool = True,
    ) -> np.ndarray:
        """Vẽ thanh đo rủi ro (Risk Gauge Bar) và vector dự báo quỹ đạo lên khung hình.

        Args:
            frame: Ảnh OpenCV BGR.
            assessments: Danh sách kết quả đánh giá rủi ro.
            draw_trajectory_arrow: Có vẽ mũi tên dự báo quỹ đạo không.

        Returns:
            np.ndarray: Khung hình với giao diện giám sát HUD.
        """
        if frame is None or frame.size == 0 or not assessments:
            return frame

        for res in assessments:
            x1, y1, x2, y2 = res.bbox

            # Lựa chọn màu theo Risk Level
            if res.risk_level == RiskLevel.DANGER:
                color = (0, 0, 255)  # Đỏ
            elif res.risk_level == RiskLevel.WARNING:
                color = (0, 165, 255)  # Vàng cam
            else:
                color = (0, 255, 0)  # Xanh lá

            # 1. Vẽ khung viền đối tượng theo màu rủi ro
            thickness = 3 if res.risk_level == RiskLevel.DANGER else 2
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

            # 2. Vẽ nhãn điểm rủi ro WRI và thanh tiến trình (Gauge Bar)
            hud_label = strip_accents(f"ID #{res.track_id} | WRI: {res.wri_score}% [{res.risk_level.value.upper()}]")
            (tw, th), _ = cv2.getTextSize(hud_label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)

            hud_y = max(20, y1 - 22)
            cv2.rectangle(frame, (x1, hud_y - th - 4), (x1 + max(tw + 8, 120), hud_y + 12), (20, 20, 20), -1)
            cv2.putText(frame, hud_label, (x1 + 3, hud_y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)

            # Thanh Mini Gauge Bar (rộng 100px)
            bar_w = 100
            fill_w = int((res.wri_score / 100.0) * bar_w)
            cv2.rectangle(frame, (x1 + 3, hud_y + 3), (x1 + 3 + bar_w, hud_y + 8), (70, 70, 70), -1)
            cv2.rectangle(frame, (x1 + 3, hud_y + 3), (x1 + 3 + fill_w, hud_y + 8), color, -1)

            # 3. Vẽ mũi tên dự báo quỹ đạo di chuyển
            if draw_trajectory_arrow and res.trajectory:
                traj = res.trajectory
                if traj.speed_px_s > 15.0:
                    cx, cy = traj.current_pos
                    px, py = traj.predicted_pos_2s
                    arrow_color = (0, 0, 255) if traj.imminent_zone_collision else (255, 200, 0)
                    cv2.arrowedLine(
                        frame,
                        (int(cx), int(cy)),
                        (int(px), int(py)),
                        arrow_color,
                        2,
                        tipLength=0.25,
                    )
                    if traj.imminent_zone_collision:
                        warn_txt = strip_accents(f"[CANH BAO] SAP VA CHAM ({traj.time_to_danger_seconds:.1f}s)!")
                        cv2.putText(
                            frame,
                            warn_txt,
                            (int(px) - 20, int(py) - 10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.45,
                            (0, 0, 255),
                            1,
                            cv2.LINE_AA,
                        )

        return frame
