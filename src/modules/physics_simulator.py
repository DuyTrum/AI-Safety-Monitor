"""Real-Time Accident Physics Simulation & Trajectory Hazard Engine Module.

Module mô phỏng vật lý tai nạn công trường thời gian thực:
1. Mô phỏng rơi tự do của dụng cụ/vật liệu từ trên cao (Free-Fall Kinematics).
2. Tính toán năng lượng va đập (Impact Energy Joule) và phân cấp thương tích.
3. Chiếu "Nón Nguy Hiểm Rơi" (Hazard Drop Cone) xuống mặt sàn và phát hiện công nhân trong vùng nguy hiểm.
4. Ngoại suy "Bóng ma trượt ngã" (Ghost Fall Phantom) theo quán tính và góc nghiêng cơ thể.
5. Vẽ lớp phủ mô phỏng trực quan thời gian thực (Visual Simulation HUD) lên khung hình OpenCV.
"""

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from src.utils.text_utils import strip_accents


class ImpactSeverity(str, Enum):
    """Phân cấp mức độ thương tích do va chạm động năng rơi tự do."""

    MINOR = "minor"  # < 20 Joules: Bầm tím nhẹ, xây xát
    MODERATE = "moderate"  # 20 - 50 Joules: Rách da, chấn thương mô mềm
    SEVERE = "severe"  # 50 - 100 Joules: Chấn động não, gãy xương
    FATAL = "fatal"  # > 100 Joules: Đe dọa tính mạng / Chấn thương sọ não nguy kịch


@dataclass
class DroppedObjectSimulation:
    """Kết quả mô phỏng động học rơi tự do của một vật dụng."""

    source_id: str
    source_label: str
    origin_point: Tuple[int, int]  # (x, y) trên cao
    estimated_height_m: float  # Độ cao ước lượng (mét)
    object_mass_kg: float  # Khối lượng vật thể (kg)
    impact_velocity_ms: float  # Vận tốc chạm đất (m/s)
    impact_velocity_kmh: float  # Vận tốc chạm đất (km/h)
    impact_energy_joules: float  # Động năng va đập (Joule)
    fall_time_seconds: float  # Thời gian rơi (giây)
    severity: ImpactSeverity  # Mức độ thương tích dự kiến
    drop_cone_ellipse: Tuple[Tuple[int, int], Tuple[int, int], float]  # Center, Axes, Angle
    workers_at_risk: List[int] = field(default_factory=list)  # Danh sách Track ID công nhân trong nón rơi


@dataclass
class GhostFallSimulation:
    """Mô phỏng bóng ma trượt ngã theo quán tính của công nhân."""

    track_id: int
    origin_bbox: Tuple[int, int, int, int]
    ghost_bbox_1s: Tuple[int, int, int, int]
    ghost_bbox_2s: Tuple[int, int, int, int]
    trajectory_points: List[Tuple[int, int]]
    fall_cause: str  # "UNHOOKED_SCAFFOLD", "EDGE_PROXIMITY", "POSTURE_LOSS"
    time_to_impact_s: float
    simulated_impact_joules: float


class PhysicsSimulator:
    """Bộ mô phỏng vật lý tai nạn công trường và chiếu kịch bản tương lai."""

    GRAVITY_ACCELERATION: float = 9.80665  # m/s^2

    # Bảng trọng lượng ước lượng theo loại dụng cụ phổ biến (kg)
    DEFAULT_TOOL_MASSES: Dict[str, float] = {
        "hammer": 1.2,
        "wrench": 0.8,
        "drill": 2.5,
        "brick": 2.0,
        "scaffold_clamp": 1.5,
        "metal_pipe": 4.0,
        "tool_generic": 1.5,
    }

    def __init__(
        self,
        pixel_to_meter_ratio: float = 0.015,  # 1 pixel ~ 0.015m (tùy camera góc rộng)
        worker_mass_kg: float = 70.0,
    ) -> None:
        """Khởi tạo bộ mô phỏng vật lý.

        Args:
            pixel_to_meter_ratio: Tỷ lệ quy đổi từ pixel sang mét thực tế.
            worker_mass_kg: Khối lượng trung bình của một công nhân (kg).
        """
        self.pixel_to_meter_ratio = pixel_to_meter_ratio
        self.worker_mass_kg = worker_mass_kg
        self.is_enabled = True

    def calculate_free_fall(
        self,
        height_meters: float,
        mass_kg: float,
    ) -> Tuple[float, float, float, ImpactSeverity]:
        """Tính toán các thông số động học rơi tự do theo định luật Newton.

        Công thức:
            v = sqrt(2 * g * h)
            t = sqrt(2 * h / g)
            E_k = m * g * h = 0.5 * m * v^2

        Args:
            height_meters: Độ cao rơi (m).
            mass_kg: Khối lượng vật thể rơi (kg).

        Returns:
            v_impact_ms: Vận tốc chạm đất (m/s).
            t_fall_s: Thời gian rơi (giây).
            energy_joules: Động năng va đập khi chạm đất (Joule).
            severity: Phân cấp mức độ nguy hiểm thương tật.
        """
        h = max(0.5, height_meters)
        m = max(0.1, mass_kg)
        g = self.GRAVITY_ACCELERATION

        v_impact_ms = math.sqrt(2 * g * h)
        t_fall_s = math.sqrt((2 * h) / g)
        energy_joules = m * g * h

        if energy_joules < 20.0:
            severity = ImpactSeverity.MINOR
        elif energy_joules < 50.0:
            severity = ImpactSeverity.MODERATE
        elif energy_joules < 100.0:
            severity = ImpactSeverity.SEVERE
        else:
            severity = ImpactSeverity.FATAL

        return v_impact_ms, t_fall_s, energy_joules, severity

    def simulate_dropped_tool(
        self,
        tool_bbox: Tuple[int, int, int, int],
        frame_height: int,
        tool_name: str = "tool_generic",
        ground_y: Optional[int] = None,
        custom_mass_kg: Optional[float] = None,
        worker_bboxes: Optional[List[Tuple[int, Tuple[int, int, int, int]]]] = None,
    ) -> DroppedObjectSimulation:
        """Mô phỏng sự cố rơi dụng cụ từ trên cao xuống sàn thi công.

        Args:
            tool_bbox: Tọa độ bounding box của dụng cụ (x1, y1, x2, y2).
            frame_height: Chiều cao khung hình (pixels).
            tool_name: Tên loại dụng cụ.
            ground_y: Tọa độ y của mặt đất/mặt sàn dưới chân (mặc định gần đáy khung hình).
            custom_mass_kg: Khối lượng tùy chỉnh (nếu có).
            worker_bboxes: Danh sách [(track_id, (x1, y1, x2, y2))] của công nhân để kiểm tra va chạm.

        Returns:
            DroppedObjectSimulation: Dữ liệu mô phỏng đầy đủ.
        """
        tx1, ty1, tx2, ty2 = tool_bbox
        origin_x = int((tx1 + tx2) / 2)
        origin_y = int(ty2)

        if ground_y is None:
            ground_y = int(frame_height * 0.90)

        # Tính độ cao rơi theo pixels và quy đổi ra mét thực tế
        pixel_height = max(50, ground_y - origin_y)
        height_meters = pixel_height * self.pixel_to_meter_ratio

        mass_kg = custom_mass_kg or self.DEFAULT_TOOL_MASSES.get(tool_name.lower(), 1.5)
        v_ms, t_s, joules, severity = self.calculate_free_fall(height_meters, mass_kg)

        # Mô phỏng "Nón Nguy Hiểm Rơi" (Hazard Drop Cone) chiếu xuống mặt sàn
        # Bán kính nón rơi mở rộng theo độ cao rơi: R = h * tan(15 độ) + biên an toàn
        dispersion_radius_px = int(pixel_height * 0.25) + 30
        cone_center = (origin_x, ground_y)
        cone_axes = (dispersion_radius_px, int(dispersion_radius_px * 0.45))
        drop_cone_ellipse = (cone_center, cone_axes, 0.0)

        # Kiểm tra xem có công nhân nào đang đứng trong nón rơi hay không
        workers_at_risk = []
        if worker_bboxes:
            for w_id, (wx1, wy1, wx2, wy2) in worker_bboxes:
                w_foot_x = int((wx1 + wx2) / 2)
                w_foot_y = int(wy2)
                dx = (w_foot_x - cone_center[0]) / max(1, cone_axes[0])
                dy = (w_foot_y - cone_center[1]) / max(1, cone_axes[1])
                if (dx * dx + dy * dy) <= 1.2:
                    workers_at_risk.append(w_id)

        return DroppedObjectSimulation(
            source_id=f"drop_{origin_x}_{origin_y}",
            source_label=tool_name,
            origin_point=(origin_x, origin_y),
            estimated_height_m=round(height_meters, 2),
            object_mass_kg=round(mass_kg, 2),
            impact_velocity_ms=round(v_ms, 2),
            impact_velocity_kmh=round(v_ms * 3.6, 1),
            impact_energy_joules=round(joules, 1),
            fall_time_seconds=round(t_s, 2),
            severity=severity,
            drop_cone_ellipse=drop_cone_ellipse,
            workers_at_risk=workers_at_risk,
        )

    def simulate_worker_ghost_fall(
        self,
        track_id: int,
        worker_bbox: Tuple[int, int, int, int],
        frame_height: int,
        fall_cause: str = "POSTURE_LOSS",
        horizontal_velocity_px_s: float = 25.0,
        height_offset_m: float = 1.5,
    ) -> GhostFallSimulation:
        """Mô phỏng cơ sinh học trượt ngã (Biomechanic Fall Kinematics) trong cửa sổ 0.35s - 0.70s.

        Theo các nghiên cứu cơ sinh học về ngã người (Biomechanics of Human Falls - Robinovitch et al.),
        một cú trượt ngã tự do của con người diễn ra rất nhanh trong khoảng 400ms - 800ms:
        - Pha 1 (0.0s - 0.35s): Mất thăng bằng, phản xạ giật mình (Reaction Latency ~250ms), trọng tâm lệch khỏi chân đỡ.
        - Pha 2 (0.35s - 0.70s): Rơi tự do không kiểm soát và va chạm tiếp đất (Impact Phase).
        (Lưu ý: Cửa sổ 2-3s chỉ áp dụng cho hướng đi bộ thông thường; đối với trượt ngã, mốc 0.7s là chuẩn xác vật lý).

        Args:
            track_id: ID công nhân.
            worker_bbox: Bbox hiện tại (x1, y1, x2, y2).
            frame_height: Chiều cao khung hình.
            fall_cause: Nguyên nhân nguy cơ.
            horizontal_velocity_px_s: Vận tốc dạt ngang (pixel/s) theo quán tính.
            height_offset_m: Chiều cao trọng tâm hoặc sàn làm việc (m).

        Returns:
            GhostFallSimulation: Quỹ đạo và các vị trí bóng ma tương lai.
        """
        x1, y1, x2, y2 = worker_bbox
        w = x2 - x1
        h = y2 - y1
        cx = int((x1 + x2) / 2)
        bottom_y = y2

        # Cửa sổ cơ sinh học: t1 = 0.35s (mất thăng bằng), t2 = 0.70s (tiếp đất)
        t1 = 0.35
        t2 = 0.70

        # y(t) = 0.5 * g * t^2 (pixels)
        fall_px_1 = int(0.5 * 980 * (t1 ** 2) * self.pixel_to_meter_ratio * 40)
        shift_x_1 = int(horizontal_velocity_px_s * t1)
        ghost_x1_1s = max(0, x1 + shift_x_1)
        ghost_y1_1s = min(frame_height - h, y1 + fall_px_1)
        ghost_bbox_1s = (ghost_x1_1s, ghost_y1_1s, ghost_x1_1s + w, ghost_y1_1s + h)

        fall_px_2 = int(0.5 * 980 * (t2 ** 2) * self.pixel_to_meter_ratio * 40)
        shift_x_2 = int(horizontal_velocity_px_s * t2)
        ghost_x1_2s = max(0, x1 + shift_x_2)
        ghost_y1_2s = min(frame_height - int(h * 0.4), y1 + fall_px_2)
        ghost_bbox_2s = (ghost_x1_2s, ghost_y1_2s, ghost_x1_2s + int(h * 1.1), ghost_y1_2s + int(w * 0.6))

        trajectory_points = [
            (cx, bottom_y),
            (cx + int(shift_x_1 * 0.5), bottom_y + int(fall_px_1 * 0.5)),
            (cx + shift_x_1, bottom_y + fall_px_1),
            (cx + shift_x_2, bottom_y + fall_px_2),
        ]

        _, _, impact_joules, _ = self.calculate_free_fall(height_offset_m, self.worker_mass_kg)

        return GhostFallSimulation(
            track_id=track_id,
            origin_bbox=worker_bbox,
            ghost_bbox_1s=ghost_bbox_1s,
            ghost_bbox_2s=ghost_bbox_2s,
            trajectory_points=trajectory_points,
            fall_cause=fall_cause,
            time_to_impact_s=t2,
            simulated_impact_joules=round(impact_joules, 1),
        )

    def draw_physics_hud(
        self,
        frame: np.ndarray,
        drop_simulations: List[DroppedObjectSimulation],
        ghost_simulations: List[GhostFallSimulation],
    ) -> np.ndarray:
        """Vẽ trực quan lớp phủ mô phỏng vật lý tai nạn lên khung hình camera.

        Args:
            frame: Khung hình BGR từ OpenCV.
            drop_simulations: Danh sách các mô phỏng rơi vật dụng.
            ghost_simulations: Danh sách các mô phỏng bóng ma trượt ngã.

        Returns:
            np.ndarray: Khung hình đã được vẽ HUD mô phỏng.
        """
        if not self.is_enabled or (not drop_simulations and not ghost_simulations):
            return frame

        overlay = frame.copy()
        h, w = frame.shape[:2]

        # 1. Vẽ Nón Rơi Vật Dụng (Hazard Drop Cone)
        for d in drop_simulations:
            center, axes, angle = d.drop_cone_ellipse
            has_worker = len(d.workers_at_risk) > 0

            color = (0, 0, 255) if has_worker else (0, 140, 255)

            # Tô mảng elip bán trong suốt
            cv2.ellipse(overlay, center, axes, angle, 0, 360, color, -1)
            # Viền elip
            cv2.ellipse(frame, center, axes, angle, 0, 360, color, 2)

            # Vẽ đường nét đứt rơi từ vật dụng xuống tâm nón
            ox, oy = d.origin_point
            cx, cy = center
            steps = 15
            for i in range(0, steps, 2):
                p1_x = int(ox + (cx - ox) * (i / steps))
                p1_y = int(oy + (cy - oy) * (i / steps))
                p2_x = int(ox + (cx - ox) * ((i + 1) / steps))
                p2_y = int(oy + (cy - oy) * ((i + 1) / steps))
                cv2.line(frame, (p1_x, p1_y), (p2_x, p2_y), color, 2)

            # Vẽ mũi tên hướng xuống
            cv2.arrowedLine(frame, (cx, cy - 40), (cx, cy - 5), color, 3, tipLength=0.3)

            # Bảng thông số động học Joule ngay tâm nón rơi
            info_text = strip_accents(
                f"[MO PHONG ROI] {d.source_label.upper()} ({d.object_mass_kg}kg | {d.estimated_height_m}m)"
            )
            stats_text = strip_accents(
                f"Dong nang: {d.impact_energy_joules:.0f}J | V: {d.impact_velocity_kmh:.0f}km/h | {d.severity.value.upper()}"
            )
            cv2.putText(frame, info_text, (max(10, cx - 130), cy + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 2)
            cv2.putText(frame, stats_text, (max(10, cx - 130), cy + 45), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 2)

            if has_worker:
                alert_text = strip_accents(f"!!! CO CONG NHAN TRONG VUNG ROI (ID: {d.workers_at_risk}) !!!")
                cv2.putText(frame, alert_text, (max(10, cx - 150), cy - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)

        # 2. Vẽ Bóng Ma Trượt Ngã (Ghost Fall Simulation)
        for g in ghost_simulations:
            pts = np.array(g.trajectory_points, np.int32).reshape((-1, 1, 2))
            cv2.polylines(frame, [pts], False, (0, 0, 255), 2, cv2.LINE_AA)

            gx1, gy1, gx2, gy2 = g.ghost_bbox_2s
            cv2.rectangle(overlay, (gx1, gy1), (gx2, gy2), (0, 0, 255), -1)
            cv2.rectangle(frame, (gx1, gy1), (gx2, gy2), (0, 69, 255), 2)

            ghost_label = strip_accents(
                f"[BONG MA NGA t+{g.time_to_impact_s:.1f}s] Dong nang: {g.simulated_impact_joules:.0f}J"
            )
            cv2.putText(frame, ghost_label, (gx1, max(15, gy1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 2)

        # Hòa trộn kênh alpha làm mờ trong suốt
        cv2.addWeighted(overlay, 0.35, frame, 0.65, 0, frame)

        # Banner góc trên
        banner_text = strip_accents("CHE DO MO PHONG VAT LY TAI NAN (PHYSICS ENGINE ONLINE)")
        cv2.rectangle(frame, (w - 420, 10), (w - 10, 38), (20, 20, 20), -1)
        cv2.rectangle(frame, (w - 420, 10), (w - 10, 38), (0, 215, 255), 1)
        cv2.putText(frame, banner_text, (w - 410, 29), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 215, 255), 1)

        return frame
