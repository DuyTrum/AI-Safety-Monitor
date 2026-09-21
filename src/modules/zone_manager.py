"""Virtual Danger Geofencing & Polygonal Zone Manager Module.

Quản lý các vùng nguy hiểm ảo trên khung hình camera công trường:
- Hố móng sâu (Excavation Pit)
- Vùng mép sàn thi công trên cao (Edge Fall Hazard)
- Vùng chân giàn giáo / nguy cơ vật rơi (Scaffold Drop Zone)
- Vùng quay của máy móc xe cơ giới (Machinery Proximity Zone)
- Khu vực hạn chế tiếp cận (Restricted Access Zone)
"""

import json
import logging
import os
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any

import cv2
import numpy as np

logger = logging.getLogger("ZoneManager")


class ZoneType(str, Enum):
    """Phân loại các khu vực nguy hiểm trên công trường."""

    EXCAVATION_PIT = "excavation_pit"  # Hố móng sâu, nguy cơ sụt lún
    EDGE_FALL_HAZARD = "edge_fall_hazard"  # Mép sàn không lan can bảo vệ
    SCAFFOLD_DROP_ZONE = "scaffold_drop_zone"  # Khu vực chân giàn giáo có nguy cơ vật thể rơi
    MACHINERY_PROXIMITY = "machinery_proximity"  # Bán kính nguy hiểm quanh máy móc
    RESTRICTED_ACCESS = "restricted_access"  # Khu vực cấm công nhân không phận sự


class ZoneSeverity(str, Enum):
    """Mức độ nghiêm trọng của khu vực nguy hiểm."""

    WARNING = "warning"  # Mức cảnh báo (vàng)
    DANGER = "danger"  # Mức nguy hiểm cao (cam/đỏ)
    CRITICAL = "critical"  # Mức khẩn cấp đe dọa tính mạng (đỏ đậm)


class SafetyZone:
    """Biểu diễn một vùng nguy hiểm hình đa giác (Polygon RoI)."""

    def __init__(
        self,
        zone_id: str,
        name: str,
        zone_type: ZoneType,
        points: List[Tuple[int, int]],
        severity: ZoneSeverity = ZoneSeverity.DANGER,
        is_active: bool = True,
        penalty_score: float = 75.0,
    ) -> None:
        """Khởi tạo một vùng an toàn/nguy hiểm ảo.

        Args:
            zone_id: Mã định danh duy nhất của vùng.
            name: Tên hiển thị của khu vực (vd: "Khu vực Hố móng A1").
            zone_type: Loại nguy cơ của vùng.
            points: Danh sách các điểm tọa độ đa giác [(x1, y1), (x2, y2), ...].
            severity: Mức độ nghiêm trọng (WARNING / DANGER / CRITICAL).
            is_active: Trạng thái kích hoạt giám sát của vùng.
            penalty_score: Điểm phạt rủi ro khi công nhân xâm nhập (0 - 100).
        """
        self.zone_id: str = zone_id
        self.name: str = name
        self.zone_type: ZoneType = zone_type
        self.points: List[Tuple[int, int]] = points
        self.severity: ZoneSeverity = severity
        self.is_active: bool = is_active
        self.penalty_score: float = penalty_score
        self._np_points = np.array(points, dtype=np.int32).reshape((-1, 1, 2))

    def update_points(self, points: List[Tuple[int, int]]) -> None:
        """Cập nhật tọa độ các đỉnh của đa giác."""
        self.points = points
        self._np_points = np.array(points, dtype=np.int32).reshape((-1, 1, 2))

    def contains_point(self, point: Tuple[float, float]) -> bool:
        """Kiểm tra một điểm (x, y) có nằm bên trong vùng đa giác hay không.

        Args:
            point: Tọa độ (x, y) cần kiểm tra.

        Returns:
            bool: True nếu điểm nằm trong hoặc trên viền đa giác.
        """
        if not self.is_active or len(self.points) < 3:
            return False
        # measureDist=False: >0 inside, ==0 on edge, <0 outside
        dist = cv2.pointPolygonTest(self._np_points, (float(point[0]), float(point[1])), False)
        return dist >= 0

    def distance_to_point(self, point: Tuple[float, float]) -> float:
        """Tính khoảng cách có dấu từ điểm đến đường viền đa giác.

        Args:
            point: Tọa độ (x, y).

        Returns:
            float: Khoảng cách pixel. Dương nếu ở trong, âm nếu ở ngoài.
        """
        if len(self.points) < 3:
            return -9999.0
        return float(cv2.pointPolygonTest(self._np_points, (float(point[0]), float(point[1])), True))

    def to_dict(self) -> Dict[str, Any]:
        """Xuất thông tin vùng ra định dạng từ điển JSON."""
        return {
            "zone_id": self.zone_id,
            "name": self.name,
            "zone_type": self.zone_type.value,
            "points": self.points,
            "severity": self.severity.value,
            "is_active": self.is_active,
            "penalty_score": self.penalty_score,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SafetyZone":
        """Khởi tạo thực thể vùng từ định dạng từ điển JSON."""
        return cls(
            zone_id=data["zone_id"],
            name=data["name"],
            zone_type=ZoneType(data.get("zone_type", ZoneType.RESTRICTED_ACCESS.value)),
            points=[tuple(p) for p in data["points"]],
            severity=ZoneSeverity(data.get("severity", ZoneSeverity.DANGER.value)),
            is_active=data.get("is_active", True),
            penalty_score=float(data.get("penalty_score", 75.0)),
        )


from src.utils.text_utils import strip_accents


class ZoneManager:
    """Bộ quản trị các vùng nguy hiểm ảo và thuật toán kiểm tra xâm nhập."""

    # Màu hiển thị BGR cho từng cấp độ nguy hiểm
    SEVERITY_COLORS = {
        ZoneSeverity.WARNING: (0, 215, 255),  # Vàng cam
        ZoneSeverity.DANGER: (0, 69, 255),  # Đỏ cam
        ZoneSeverity.CRITICAL: (0, 0, 220),  # Đỏ đậm
    }

    def __init__(self, config_path: Optional[str] = None) -> None:
        """Khởi tạo quản lý vùng nguy hiểm.

        Args:
            config_path: Đường dẫn tới tệp cấu hình JSON lưu danh sách vùng.
        """
        self.zones: Dict[str, SafetyZone] = {}
        self.config_path: Optional[str] = config_path

        if config_path and os.path.exists(config_path):
            self.load_from_file(config_path)

    def add_zone(self, zone: SafetyZone) -> None:
        """Thêm hoặc cập nhật một vùng nguy hiểm vào danh sách quản lý."""
        self.zones[zone.zone_id] = zone
        logger.info(f"Đã thêm/cập nhật vùng an toàn ID: {zone.zone_id} ({zone.name})")

    def remove_zone(self, zone_id: str) -> bool:
        """Xóa một vùng nguy hiểm theo ID."""
        if zone_id in self.zones:
            del self.zones[zone_id]
            logger.info(f"Đã xóa vùng an toàn ID: {zone_id}")
            return True
        return False

    def get_zone(self, zone_id: str) -> Optional[SafetyZone]:
        """Lấy thông tin vùng nguy hiểm theo ID."""
        return self.zones.get(zone_id)

    def list_zones(self) -> List[SafetyZone]:
        """Trả về danh sách tất cả các vùng đang quản lý."""
        return list(self.zones.values())

    def check_bbox_intrusion(
        self, bbox: Tuple[int, int, int, int]
    ) -> List[Tuple[SafetyZone, float]]:
        """Kiểm tra xem vị trí chân công nhân có xâm nhập vùng cấm hay không.

        Sử dụng vị trí tiếp đất (chân) của công nhân: (tâm X, đáy Y) = ((x1 + x2) / 2, y2).

        Args:
            bbox: Tọa độ bounding box (x1, y1, x2, y2) của người.

        Returns:
            List[Tuple[SafetyZone, float]]: Danh sách các vùng bị xâm nhập kèm khoảng cách.
        """
        foot_point = ((bbox[0] + bbox[2]) / 2.0, float(bbox[3]))
        intrusions = []

        for zone in self.zones.values():
            if not zone.is_active:
                continue
            dist = zone.distance_to_point(foot_point)
            if dist >= 0:
                # Chân công nhân nằm bên trong vùng
                intrusions.append((zone, dist))

        return intrusions

    def check_proximity_warning(
        self, bbox: Tuple[int, int, int, int], buffer_distance_px: float = 40.0
    ) -> List[Tuple[SafetyZone, float]]:
        """Kiểm tra công nhân có đang tiến sát mép vùng nguy hiểm hay không (Buffer Zone).

        Args:
            bbox: Tọa độ bounding box (x1, y1, x2, y2) của người.
            buffer_distance_px: Khoảng cách an toàn tối thiểu tính bằng pixel.

        Returns:
            List[Tuple[SafetyZone, float]]: Các vùng mà công nhân đang ở cự ly nguy hiểm.
        """
        foot_point = ((bbox[0] + bbox[2]) / 2.0, float(bbox[3]))
        warnings = []

        for zone in self.zones.values():
            if not zone.is_active:
                continue
            dist = zone.distance_to_point(foot_point)
            # dist < 0 nghĩa là ở ngoài, nếu abs(dist) <= buffer_distance_px thì là sát mép
            if 0 > dist >= -buffer_distance_px:
                warnings.append((zone, abs(dist)))

        return warnings

    def draw_zones_on_frame(self, frame: np.ndarray, alpha: float = 0.28) -> np.ndarray:
        """Vẽ các vùng nguy hiểm bán trong suốt và nhãn lên khung hình OpenCV.

        Args:
            frame: Ảnh gốc OpenCV BGR.
            alpha: Độ trong suốt của lớp phủ màu (0.0 đến 1.0).

        Returns:
            np.ndarray: Ảnh đã được vẽ các vùng nguy hiểm.
        """
        if not self.zones or frame is None or frame.size == 0:
            return frame

        overlay = frame.copy()
        h, w = frame.shape[:2]

        for zone in self.zones.values():
            if not zone.is_active or len(zone.points) < 3:
                continue

            color = self.SEVERITY_COLORS.get(zone.severity, (0, 0, 255))
            pts = zone._np_points

            # 1. Vẽ đa giác đặc lên lớp overlay
            cv2.fillPoly(overlay, [pts], color)

            # 2. Vẽ viền nét đứt hoặc nét liền đậm lên frame chính
            cv2.polylines(frame, [pts], isClosed=True, color=color, thickness=2, lineType=cv2.LINE_AA)

            # 3. Vẽ nhãn tên khu vực tại trọng tâm đa giác
            m = cv2.moments(pts)
            if m["m00"] != 0:
                cx = int(m["m10"] / m["m00"])
                cy = int(m["m01"] / m["m00"])
            else:
                cx, cy = zone.points[0]

            label = f"[ZONE] {strip_accents(zone.name).upper()}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            tx = max(5, min(w - tw - 5, cx - tw // 2))
            ty = max(20, min(h - 10, cy + th // 2))

            cv2.rectangle(frame, (tx - 3, ty - th - 3), (tx + tw + 3, ty + 3), (0, 0, 0), -1)
            cv2.putText(
                frame,
                label,
                (tx, ty),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
                cv2.LINE_AA,
            )

        # Trộn lớp phủ bán trong suốt
        cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, frame)
        return frame

    def load_from_file(self, file_path: str) -> bool:
        """Nạp danh sách vùng an toàn từ tệp JSON."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                zones_list = data.get("zones", [])
                self.zones.clear()
                for item in zones_list:
                    zone = SafetyZone.from_dict(item)
                    self.zones[zone.zone_id] = zone
            logger.info(f"Đã nạp thành công {len(self.zones)} vùng an toàn từ {file_path}")
            return True
        except Exception as e:
            logger.error(f"Lỗi khi đọc file cấu hình vùng an toàn {file_path}: {e}")
            return False

    def save_to_file(self, file_path: Optional[str] = None) -> bool:
        """Lưu danh sách vùng an toàn hiện tại ra tệp JSON."""
        target_path = file_path or self.config_path
        if not target_path:
            logger.error("Không có đường dẫn tệp để lưu danh sách vùng.")
            return False

        try:
            os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
            data = {"zones": [zone.to_dict() for zone in self.zones.values()]}
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Đã lưu thành công {len(self.zones)} vùng an toàn vào {target_path}")
            return True
        except Exception as e:
            logger.error(f"Lỗi khi lưu file cấu hình vùng an toàn {target_path}: {e}")
            return False
