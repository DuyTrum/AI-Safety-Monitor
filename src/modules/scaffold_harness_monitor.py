"""Scaffolding, Safety Harness & Dropped Tool Hazard Monitor Module.

Giám sát an toàn làm việc trên cao và giàn giáo:
1. Xác định công nhân đang thao tác trên giàn giáo (Scaffolding / Ladder).
2. Kiểm tra dây đai an toàn toàn thân (Safety Harness) và trạng thái móc khóa (Hooked vs Unhooked).
3. Cảnh báo nguy cơ rơi dụng cụ lao động từ trên cao (Dropped Tool Hazard) và vùng nguy hiểm dưới chân giàn giáo.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any

import cv2
import numpy as np

from src.utils.text_utils import strip_accents

logger = logging.getLogger("ScaffoldHarnessMonitor")


class HeightViolationType(str, Enum):
    """Phân loại vi phạm an toàn làm việc trên cao."""

    ON_SCAFFOLD_NO_HARNESS = "on_scaffold_no_harness"  # Trên giàn giáo nhưng không mặc dây an toàn
    ON_SCAFFOLD_UNHOOKED = "on_scaffold_unhooked"  # Có mặc dây an toàn nhưng chưa móc chốt neo
    TOOL_ON_SCAFFOLD_EDGE = "tool_on_scaffold_edge"  # Dụng cụ để sát mép giàn giáo có nguy cơ rơi
    WORKER_IN_DROP_ZONE = "worker_in_drop_zone"  # Công nhân đứng dưới vùng nguy hiểm vật thể rơi


@dataclass
class HeightSafetyStatus:
    """Trạng thái an toàn trên cao của một công nhân."""

    track_id: int
    worker_bbox: Tuple[int, int, int, int]
    is_on_scaffold: bool
    has_harness: bool
    is_hooked: bool
    scaffold_id: Optional[int] = None
    violation_type: Optional[HeightViolationType] = None
    penalty_score: float = 0.0
    description: str = "Bình thường"


@dataclass
class ToolHazardEvent:
    """Sự kiện nguy cơ liên quan đến dụng cụ lao động."""

    tool_name: str
    tool_bbox: Tuple[int, int, int, int]
    hazard_type: str
    penalty_score: float
    description: str


class ScaffoldHarnessMonitor:
    """Bộ giám sát giàn giáo, dây đai an toàn và chốt neo."""

    def __init__(
        self,
        min_overlap_ratio: float = 0.25,
        tool_edge_margin_px: int = 35,
    ) -> None:
        """Khởi tạo bộ giám sát làm việc trên cao.

        Args:
            min_overlap_ratio: Tỷ lệ diện tích giao cắt tối thiểu giữa người và giàn giáo.
            tool_edge_margin_px: Khoảng cách pixel tối đa coi là dụng cụ sát mép sàn giàn giáo.
        """
        self.min_overlap_ratio = min_overlap_ratio
        self.tool_edge_margin_px = tool_edge_margin_px

    def check_scaffold_occupancy(
        self,
        worker_bbox: Tuple[int, int, int, int],
        scaffold_bboxes: List[Tuple[int, Tuple[int, int, int, int]]],
    ) -> Tuple[bool, Optional[int]]:
        """Kiểm tra xem công nhân có đang đứng hoặc thao tác trên giàn giáo hay không.

        Args:
            worker_bbox: (wx1, wy1, wx2, wy2) của công nhân.
            scaffold_bboxes: Danh sách [(scaffold_id, (sx1, sy1, sx2, sy2))].

        Returns:
            Tuple[bool, Optional[int]]: (True nếu trên giàn giáo, ID của giàn giáo).
        """
        wx1, wy1, wx2, wy2 = worker_bbox
        w_area = max(1, (wx2 - wx1) * (wy2 - wy1))
        # Tâm chân của công nhân
        foot_x = (wx1 + wx2) / 2.0
        foot_y = float(wy2)

        for s_id, s_box in scaffold_bboxes:
            sx1, sy1, sx2, sy2 = s_box
            # Kiểm tra chân công nhân có nằm trong phạm vi ngang của giàn giáo và ở độ cao trên đáy giàn giáo
            if (sx1 <= foot_x <= sx2) and (sy1 <= foot_y <= sy2):
                # Tính diện tích giao cắt
                ix1 = max(wx1, sx1)
                iy1 = max(wy1, sy1)
                ix2 = min(wx2, sx2)
                iy2 = min(wy2, sy2)
                iw = max(0, ix2 - ix1)
                ih = max(0, iy2 - iy1)
                inter_area = iw * ih

                if (inter_area / w_area) >= self.min_overlap_ratio or (foot_y < sy2 - 20):
                    return True, s_id

        return False, None

    def evaluate_worker_height_safety(
        self,
        track_id: int,
        worker_bbox: Tuple[int, int, int, int],
        associated_labels: List[str],
        scaffold_bboxes: List[Tuple[int, Tuple[int, int, int, int]]],
        is_elevated_ground: bool = False,
        relation_triplets: Optional[List[Any]] = None,
    ) -> HeightSafetyStatus:
        """Đánh giá toàn diện an toàn làm việc trên cao cho từng công nhân.

        Args:
            track_id: Mã định danh công nhân.
            worker_bbox: Tọa độ bounding box của công nhân.
            associated_labels: Danh sách các nhãn trang bị gắn liền với công nhân (vd: helmet, harness, hook).
            scaffold_bboxes: Danh sách giàn giáo trong khung hình.
            is_elevated_ground: Cờ báo công nhân đang ở vị trí sàn cao nguy hiểm.
            relation_triplets: Danh sách bộ ba quan hệ thị giác từ SafetyRelationEngine.

        Returns:
            HeightSafetyStatus: Đối tượng lưu kết quả đánh giá an toàn.
        """
        is_on_scaffold, scaffold_id = self.check_scaffold_occupancy(worker_bbox, scaffold_bboxes)
        is_at_height = is_on_scaffold or is_elevated_ground

        # Kiểm tra dây đai toàn thân (harness)
        has_harness = any(label in ["harness", "safety-harness", "belt"] for label in associated_labels)
        # Kiểm tra trạng thái chốt móc neo (hooked)
        is_hooked = any(label in ["hooked", "hook", "anchor", "lifeline"] for label in associated_labels)

        # Tích hợp ngữ cảnh suy luận quan hệ từ RelateAnything (nếu có)
        if relation_triplets:
            for trip in relation_triplets:
                t_sid = getattr(trip, "subject_id", None)
                t_oid = getattr(trip, "object_id", None)
                if t_sid == track_id or t_oid == track_id:
                    pred = getattr(trip, "predicate", "").lower()
                    obj_label = getattr(trip, "object_label", "").lower()

                    if "standing on" in pred or "climbing on" in pred:
                        is_on_scaffold = True
                        is_at_height = True
                    if "unhooked" in pred:
                        is_hooked = False
                    elif "hooked to" in pred or "attached to" in pred:
                        is_hooked = True
                        has_harness = True
                    if "wearing" in pred and any(h in obj_label for h in ["harness", "belt"]):
                        has_harness = True

        if not is_at_height:
            return HeightSafetyStatus(
                track_id=track_id,
                worker_bbox=worker_bbox,
                is_on_scaffold=False,
                has_harness=has_harness,
                is_hooked=is_hooked,
                scaffold_id=None,
                violation_type=None,
                penalty_score=0.0,
                description="Làm việc tại mặt đất an toàn",
            )

        # Công nhân đang ở trên cao hoặc giàn giáo:
        if not has_harness:
            # Nguy cơ tính mạng cao nhất: Trên giàn giáo KHÔNG CÓ dây đai
            return HeightSafetyStatus(
                track_id=track_id,
                worker_bbox=worker_bbox,
                is_on_scaffold=is_on_scaffold,
                has_harness=False,
                is_hooked=False,
                scaffold_id=scaffold_id,
                violation_type=HeightViolationType.ON_SCAFFOLD_NO_HARNESS,
                penalty_score=95.0,
                description="🚨 KHẨN CẤP: Trên giàn giáo KHÔNG mặc dây đai an toàn!",
            )

        if has_harness and not is_hooked:
            # Nguy cơ cao: Có dây nhưng chưa móc chốt
            return HeightSafetyStatus(
                track_id=track_id,
                worker_bbox=worker_bbox,
                is_on_scaffold=is_on_scaffold,
                has_harness=True,
                is_hooked=False,
                scaffold_id=scaffold_id,
                violation_type=HeightViolationType.ON_SCAFFOLD_UNHOOKED,
                penalty_score=75.0,
                description="⚠️ NGUY HIỂM: Có dây an toàn nhưng CHƯA MÓC CHỐT NEO!",
            )

        # Đã mặc dây đai và đã móc chốt an toàn
        return HeightSafetyStatus(
            track_id=track_id,
            worker_bbox=worker_bbox,
            is_on_scaffold=is_on_scaffold,
            has_harness=True,
            is_hooked=True,
            scaffold_id=scaffold_id,
            violation_type=None,
            penalty_score=0.0,
            description="Đạt chuẩn an toàn làm việc trên cao",
        )

    def detect_tool_drop_hazards(
        self,
        tool_detections: List[Tuple[str, Tuple[int, int, int, int]]],
        scaffold_bboxes: List[Tuple[int, Tuple[int, int, int, int]]],
    ) -> List[ToolHazardEvent]:
        """Phát hiện các dụng cụ thi công bị để bừa bãi sát mép sàn giàn giáo.

        Args:
            tool_detections: Danh sách [(tool_name, bbox)] (búa, máy cắt, thùng...).
            scaffold_bboxes: Danh sách giàn giáo.

        Returns:
            List[ToolHazardEvent]: Danh sách các sự cố dụng cụ nguy hiểm.
        """
        hazards: List[ToolHazardEvent] = []

        for tool_name, (tx1, ty1, tx2, ty2) in tool_detections:
            tool_center_x = (tx1 + tx2) / 2.0
            tool_bottom_y = ty2

            for s_id, (sx1, sy1, sx2, sy2) in scaffold_bboxes:
                # Kiểm tra dụng cụ có nằm trên giàn giáo không
                if (sx1 <= tool_center_x <= sx2) and (sy1 <= tool_bottom_y <= sy2):
                    # Khoảng cách đến 2 mép trái/phải của giàn giáo
                    dist_to_left = abs(tool_center_x - sx1)
                    dist_to_right = abs(tool_center_x - sx2)
                    min_edge_dist = min(dist_to_left, dist_to_right)

                    if min_edge_dist <= self.tool_edge_margin_px:
                        hazards.append(
                            ToolHazardEvent(
                                tool_name=tool_name,
                                tool_bbox=(tx1, ty1, tx2, ty2),
                                hazard_type=HeightViolationType.TOOL_ON_SCAFFOLD_EDGE.value,
                                penalty_score=65.0,
                                description=f"Dụng cụ '{tool_name}' để sát mép giàn giáo ({int(min_edge_dist)}px) - Nguy cơ rơi tự do!",
                            )
                        )

        return hazards

    def compute_scaffold_drop_zone(
        self, scaffold_bbox: Tuple[int, int, int, int], ground_y: int
    ) -> List[Tuple[int, int]]:
        """Tính toán đa giác vùng nguy hiểm rơi tự do (Drop Zone) hình nón/hình thang dưới chân giàn giáo.

        Args:
            scaffold_bbox: (sx1, sy1, sx2, sy2) của giàn giáo.
            ground_y: Tọa độ Y của mặt đất.

        Returns:
            List[Tuple[int, int]]: 4 đỉnh đa giác vùng rơi tự do dưới chân giàn giáo.
        """
        sx1, sy1, sx2, sy2 = scaffold_bbox
        # Vùng rơi xòe rộng ra mỗi bên 40px khi xuống tới mặt đất
        cone_expansion = 45
        dx1 = max(0, sx1 - cone_expansion)
        dx2 = sx2 + cone_expansion
        dy2 = max(sy2, ground_y)

        return [(sx1, sy2), (sx2, sy2), (dx2, dy2), (dx1, dy2)]

    def draw_height_safety_overlay(
        self,
        frame: np.ndarray,
        worker_statuses: List[HeightSafetyStatus],
        tool_hazards: List[ToolHazardEvent],
    ) -> np.ndarray:
        """Vẽ cảnh báo an toàn trên cao và dụng cụ lên khung hình.

        Args:
            frame: Ảnh OpenCV BGR.
            worker_statuses: Danh sách trạng thái an toàn của công nhân.
            tool_hazards: Danh sách sự cố dụng cụ.

        Returns:
            np.ndarray: Ảnh đã được vẽ thông tin cảnh báo.
        """
        if frame is None or frame.size == 0:
            return frame

        # Vẽ cảnh báo công nhân
        for st in worker_statuses:
            if st.violation_type is not None:
                x1, y1, x2, y2 = st.worker_bbox
                # Màu đỏ cho vi phạm an toàn trên cao
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)

                label = strip_accents(f"[CANH BAO] {st.description}")
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                ly = max(20, y1 - 10)
                cv2.rectangle(frame, (x1, ly - th - 4), (x1 + tw + 6, ly + 2), (0, 0, 0), -1)
                cv2.putText(frame, label, (x1 + 3, ly - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1, cv2.LINE_AA)

        # Vẽ cảnh báo dụng cụ
        for th in tool_hazards:
            tx1, ty1, tx2, ty2 = th.tool_bbox
            cv2.rectangle(frame, (tx1, ty1), (tx2, ty2), (0, 140, 255), 2)
            cv2.putText(
                frame,
                "VAT ROI!",
                (tx1, max(15, ty1 - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (0, 140, 255),
                1,
                cv2.LINE_AA,
            )

        return frame
