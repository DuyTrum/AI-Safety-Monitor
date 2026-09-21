"""Safety Relation Engine & Scene Graph Generator Module.

Mô-đun phân tích quan hệ ngữ nghĩa thị giác (Open-Vocabulary Visual Relationship Reasoning)
dựa trên kiến trúc RelateAnything (arXiv:2609.12552) phục vụ an toàn lao động:
1. Dự đoán mối quan hệ động giữa các thực thể phát hiện từ YOLO11 (Người - Trang bị - Máy móc - Giàn giáo).
2. Xây dựng đồ thị ngữ cảnh an toàn (Safety Scene Graph) thời gian thực.
3. Nhận diện các tương tác rủi ro nghiêm trọng theo chuẩn OSHA Focus Four (Ngã cao, Va quẹt xe cơ giới, Vật rơi).
4. Hỗ trợ cơ chế Graceful Fallback (tự động chuyển sang mô hình suy luận hình học ngữ nghĩa khi chạy CPU/thiếu thư viện).
"""

import logging
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from src.utils.text_utils import strip_accents

logger = logging.getLogger("SafetyRelationEngine")


class RelationHazardSeverity(str, Enum):
    """Mức độ nghiêm trọng của quan hệ nguy hiểm."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class SafetyRelationTriplet:
    """Bộ ba quan hệ an toàn (Subject - Predicate - Object)."""

    subject_id: int
    subject_label: str
    subject_bbox: Tuple[int, int, int, int]
    predicate: str
    object_id: int
    object_label: str
    object_bbox: Tuple[int, int, int, int]
    confidence: float
    is_hazard: bool = False
    hazard_severity: RelationHazardSeverity = RelationHazardSeverity.LOW
    hazard_description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Chuyển đổi bộ ba quan hệ sang dạng Dictionary."""
        data = asdict(self)
        data["hazard_severity"] = self.hazard_severity.value
        return data


# Danh mục từ vựng quan hệ an toàn chuẩn hóa cho công trường & nhà máy
DEFAULT_SAFETY_VOCABULARY: List[str] = [
    # Làm việc trên cao & Giàn giáo (Fall Hazards - OSHA 1926 Subpart M & L)
    "hooked to",
    "unhooked from",
    "climbing on",
    "standing on",
    "leaning dangerously over",
    # Va chạm xe cơ giới & Máy móc nguy hiểm (Struck-By & Caught-In - OSHA 1926 Subpart O)
    "standing in blind spot of",
    "walking in path of",
    "operating",
    "riding on",
    "approaching danger zone of",
    # Vật rơi từ trên cao & Dụng cụ lao động (Struck-By Falling Objects)
    "working underneath",
    "carrying",
    "holding",
    # Trang bị bảo hộ cá nhân (PPE Association)
    "wearing",
    "attached to",
]


class SafetyRelationEngine:
    """Bộ máy suy luận quan hệ thị giác an toàn mở (Open-Vocabulary Safety Relation Engine)."""

    def __init__(
        self,
        model_name: str = "maelic/relsgg-vits16",
        device: Optional[str] = None,
        confidence_threshold: float = 0.35,
        vocabulary: Optional[List[str]] = None,
    ) -> None:
        """Khởi tạo SafetyRelationEngine.

        Args:
            model_name: Tên hoặc đường dẫn trọng số RelateAnything trên Hugging Face.
            device: Thiết bị tính toán ('cuda', 'cpu', hoặc None để tự phát hiện).
            confidence_threshold: Ngưỡng tin cậy tối thiểu để giữ lại quan hệ.
            vocabulary: Danh sách từ vựng vị ngữ quan hệ an toàn tùy biến.
        """
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self.vocabulary = vocabulary or list(DEFAULT_SAFETY_VOCABULARY)
        self.model = None
        self.is_deep_learning_active = False

        if device is None:
            try:
                import torch
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                self.device = "cpu"
        else:
            self.device = device

        self._load_model()

    def _load_model(self) -> None:
        """Nạp mô hình RelateAnything từ thư viện relsgg (nếu có sẵn)."""
        try:
            from relsgg import RelateAnything  # type: ignore

            logger.info(f"Đang nạp mô hình RelateAnything '{self.model_name}' trên {self.device}...")
            self.model = RelateAnything.from_pretrained(self.model_name, device=self.device)
            if hasattr(self.model, "set_vocabulary"):
                self.model.set_vocabulary(self.vocabulary)
            self.is_deep_learning_active = True
            logger.info("Nạp thành công mô hình RelateAnything Deep Learning.")
        except ImportError:
            logger.info(
                "Chưa cài đặt thư viện 'relsgg' (Maelic/RelateAnything). "
                "Hệ thống sẽ kích hoạt bộ suy luận quan hệ ngữ cảnh hình học (Spatial-Semantic Fallback Engine)."
            )
            self.is_deep_learning_active = False
            self.model = None
        except Exception as err:
            logger.warning(
                f"Không thể khởi tạo mô hình RelateAnything ({err}). "
                "Chuyển sang chế độ dự phòng Spatial-Semantic Fallback Engine."
            )
            self.is_deep_learning_active = False
            self.model = None

    def set_vocabulary(self, vocabulary: List[str]) -> None:
        """Cập nhật danh mục từ vựng quan hệ an toàn.

        Args:
            vocabulary: Danh sách các vị ngữ quan hệ mới.
        """
        self.vocabulary = [v.strip().lower() for v in vocabulary if v.strip()]
        if self.is_deep_learning_active and self.model is not None:
            try:
                if hasattr(self.model, "set_vocabulary"):
                    self.model.set_vocabulary(self.vocabulary)
            except Exception as err:
                logger.error(f"Lỗi khi cập nhật vocabulary cho RelateAnything: {err}")

    def classify_relation_hazard(
        self,
        subject_label: str,
        predicate: str,
        object_label: str,
    ) -> Tuple[bool, RelationHazardSeverity, str]:
        """Phân loại mức độ nguy hiểm của một bộ ba quan hệ theo tiêu chuẩn an toàn lao động.

        Args:
            subject_label: Nhãn của chủ thể (ví dụ: 'person', 'worker', 'hook').
            predicate: Vị ngữ quan hệ (ví dụ: 'standing in blind spot of', 'hooked to').
            object_label: Nhãn đối tượng tương tác (ví dụ: 'forklift', 'scaffold').

        Returns:
            Tuple[bool, RelationHazardSeverity, str]: (Có rủi ro hay không, Mức độ, Mô tả cảnh báo).
        """
        s = subject_label.lower()
        p = predicate.lower()
        o = object_label.lower()

        # 1. Nhóm va quẹt phương tiện cơ giới & thiết bị nặng (Struck-By Hazards)
        vehicle_keywords = {"forklift", "truck", "excavator", "crane", "car", "vehicle", "machinery"}
        is_vehicle = any(v in o for v in vehicle_keywords) or any(v in s for v in vehicle_keywords)

        if is_vehicle:
            if "blind spot" in p:
                return (
                    True,
                    RelationHazardSeverity.CRITICAL,
                    f"CẢNH BÁO NGUY CẤP: Công nhân #{s} đang ở đúng ĐIỂM MÙ của {o}!",
                )
            if "path of" in p or "collide" in p:
                return (
                    True,
                    RelationHazardSeverity.HIGH,
                    f"NGUY HIỂM VA CHẠM: Công nhân #{s} cắt ngang đường di chuyển của {o}.",
                )
            if "riding on" in p and "person" in s and not ("seat" in o or "cabin" in o):
                return (
                    True,
                    RelationHazardSeverity.HIGH,
                    f"VI PHẠM AN TOÀN: Đu bám bất hợp pháp trên phương tiện {o}.",
                )

        # 2. Nhóm làm việc trên cao & Giàn giáo (Fall Hazards)
        scaffold_keywords = {"scaffold", "ladder", "edge", "height", "platform", "roof"}
        is_height = any(h in o for h in scaffold_keywords) or any(h in s for h in scaffold_keywords)

        if is_height:
            if "unhooked" in p:
                return (
                    True,
                    RelationHazardSeverity.CRITICAL,
                    f"CẢNH BÁO TỬ VONG: Công nhân trên {o} nhưng CHƯA CHỐT DÂY AN TOÀN!",
                )
            if "leaning" in p or "dangerously" in p:
                return (
                    True,
                    RelationHazardSeverity.HIGH,
                    f"NGUY CƠ NGÃ CAO: Nghiêng người nguy hiểm ngoài tầm lan can {o}.",
                )
            if "standing on" in p or "climbing on" in p:
                return (
                    False,
                    RelationHazardSeverity.LOW,
                    f"Đang thao tác làm việc trên {o}.",
                )

        # 3. Nhóm vật thể rơi & Treo lơ lửng (Dropped Objects / Suspended Load)
        load_keywords = {"load", "crane", "suspended", "hoist", "hook"}
        is_suspended = any(k in o for k in load_keywords) or any(k in s for k in load_keywords)

        if is_suspended and "underneath" in p:
            return (
                True,
                RelationHazardSeverity.CRITICAL,
                f"CẢNH BÁO VẬT RƠI: Công nhân đứng ngay DƯỚI TẢI TREO NGUY HIỂM của {o}!",
            )

        # 4. Trạng thái móc an toàn (Safe Positive States)
        if "hooked to" in p or "attached to" in p:
            return (
                False,
                RelationHazardSeverity.LOW,
                f"An toàn: Đã chốt móc an toàn vào {o}.",
            )

        return False, RelationHazardSeverity.LOW, f"Tương tác {p} với {o}."

    def _fallback_infer_relations(
        self,
        frame: np.ndarray,
        detections: List[Tuple[int, Tuple[int, int, int, int], str, float]],
    ) -> List[SafetyRelationTriplet]:
        """Suy luận quan hệ dựa trên hình học không gian (Spatial-Semantic Heuristics).

        Kích hoạt khi chưa nạp mô hình deep learning hoặc chạy môi trường máy chủ nhẹ.

        Args:
            frame: Ảnh frame gốc.
            detections: Danh sách (track_id, (x1, y1, x2, y2), class_name, confidence).

        Returns:
            List[SafetyRelationTriplet]: Danh sách các bộ ba quan hệ.
        """
        triplets: List[SafetyRelationTriplet] = []
        n = len(detections)
        if n < 2:
            return triplets

        for i in range(n):
            id_a, box_a, cls_a, conf_a = detections[i]
            ax1, ay1, ax2, ay2 = box_a
            acenter = ((ax1 + ax2) / 2.0, (ay1 + ay2) / 2.0)
            awidth = max(1, ax2 - ax1)
            aheight = max(1, ay2 - ay1)

            for j in range(n):
                if i == j:
                    continue

                id_b, box_b, cls_b, conf_b = detections[j]
                bx1, by1, bx2, by2 = box_b
                bcenter = ((bx1 + bx2) / 2.0, (by1 + by2) / 2.0)

                # Tính khoảng cách tâm chuẩn hóa theo kích thước vật thể
                dx = acenter[0] - bcenter[0]
                dy = acenter[1] - bcenter[1]
                dist_px = np.sqrt(dx**2 + dy**2)

                # Tính phần diện tích giao thoa (IoU / Overlap)
                ix1, iy1 = max(ax1, bx1), max(ay1, by1)
                ix2, iy2 = min(ax2, bx2), min(ay2, by2)
                inter_area = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                area_a = awidth * aheight
                overlap_ratio = inter_area / float(area_a)

                pred = None
                conf_rel = round(float(min(conf_a, conf_b) * 0.9), 2)

                # Trường hợp 1: Người (Person) tương tác với Giàn giáo (Scaffold)
                is_a_person = "person" in cls_a.lower() or "worker" in cls_a.lower() or cls_a.startswith("no-") or cls_a in {"helmet", "vest"}
                is_b_scaffold = "scaffold" in cls_b.lower() or "ladder" in cls_b.lower()

                if is_a_person and is_b_scaffold:
                    if ay2 <= by2 and ay2 >= by1 and (bx1 <= acenter[0] <= bx2):
                        pred = "standing on"
                    elif overlap_ratio > 0.3:
                        pred = "climbing on"

                # Trường hợp 2: Móc khóa / Dây an toàn (Hook / Harness) và Giàn giáo / Điểm neo
                is_a_hook = "hook" in cls_a.lower() or "harness" in cls_a.lower() or "belt" in cls_a.lower()
                if is_a_hook and is_b_scaffold:
                    if overlap_ratio > 0.15 or dist_px < 60:
                        pred = "hooked to"
                    else:
                        pred = "unhooked from"

                # Trường hợp 3: Người và Xe nâng / Phương tiện cơ giới (Vehicle / Forklift)
                is_b_vehicle = any(v in cls_b.lower() for v in ["forklift", "truck", "crane", "car", "vehicle"])
                if is_a_person and is_b_vehicle:
                    # Nếu ở phía sau hoặc bên hông trong khoảng cách gần
                    if dist_px < max(awidth, aheight) * 2.5:
                        if ax2 < bx1 or ax1 > bx2:
                            pred = "standing in blind spot of"
                        elif ay2 > by2 - 50:
                            pred = "walking in path of"
                        else:
                            pred = "approaching danger zone of"

                # Trường hợp 4: Người ở dưới Cẩu / Tải treo
                is_b_crane = "crane" in cls_b.lower() or "load" in cls_b.lower()
                if is_a_person and is_b_crane:
                    if ay1 > by2 and (bx1 - 50 <= acenter[0] <= bx2 + 50):
                        pred = "working underneath"

                # Trường hợp 5: Người và Trang bị bảo hộ cá nhân (PPE Wearing)
                ppe_items = {"helmet", "vest", "boots", "gloves", "goggles", "safety-harness", "harness"}
                if is_a_person and cls_b.lower() in ppe_items:
                    # Bounding box của PPE nằm trong hoặc giao cắt lớn với cơ thể người
                    if (ax1 - 10 <= bcenter[0] <= ax2 + 10) and (ay1 - 10 <= bcenter[1] <= ay2 + 10):
                        pred = "wearing"

                if pred:
                    is_haz, sev, desc = self.classify_relation_hazard(cls_a, pred, cls_b)
                    triplets.append(
                        SafetyRelationTriplet(
                            subject_id=id_a,
                            subject_label=cls_a,
                            subject_bbox=box_a,
                            predicate=pred,
                            object_id=id_b,
                            object_label=cls_b,
                            object_bbox=box_b,
                            confidence=conf_rel,
                            is_hazard=is_haz,
                            hazard_severity=sev,
                            hazard_description=desc,
                        )
                    )

        return triplets

    def infer_safety_relations(
        self,
        frame: np.ndarray,
        detections: List[Tuple[int, Tuple[int, int, int, int], str, float]],
        topk: int = 15,
    ) -> List[SafetyRelationTriplet]:
        """Dự đoán các bộ ba quan hệ an toàn giữa các thực thể trong khung hình.

        Args:
            frame: Ảnh frame gốc (BGR NumPy array).
            detections: Danh sách thực thể [(track_id, (x1, y1, x2, y2), class_name, confidence)].
            topk: Số lượng quan hệ tối đa cần trích xuất.

        Returns:
            List[SafetyRelationTriplet]: Danh sách các quan hệ phát hiện được.
        """
        if frame is None or len(detections) < 2:
            return []

        # Nếu có mô hình RelateAnything Deep Learning hoạt động
        if self.is_deep_learning_active and self.model is not None:
            try:
                boxes_xyxy = np.array([det[1] for det in detections], dtype=np.float32)
                raw_results = self.model.predict(frame, boxes_xyxy, topk=topk)
                triplets: List[SafetyRelationTriplet] = []

                for item in raw_results:
                    # Giả định item có cấu trúc (subj_idx, predicate, obj_idx, score)
                    if hasattr(item, "subj_idx") and hasattr(item, "obj_idx"):
                        s_idx = int(item.subj_idx)
                        o_idx = int(item.obj_idx)
                        pred = str(item.predicate)
                        score = float(getattr(item, "score", 0.5))
                    elif isinstance(item, (list, tuple)) and len(item) >= 4:
                        s_idx, pred, o_idx, score = item[0], item[1], item[2], item[3]
                    else:
                        continue

                    if score < self.confidence_threshold:
                        continue

                    if 0 <= s_idx < len(detections) and 0 <= o_idx < len(detections):
                        s_id, s_box, s_cls, _ = detections[s_idx]
                        o_id, o_box, o_cls, _ = detections[o_idx]

                        is_haz, sev, desc = self.classify_relation_hazard(s_cls, pred, o_cls)
                        triplets.append(
                            SafetyRelationTriplet(
                                subject_id=s_id,
                                subject_label=s_cls,
                                subject_bbox=s_box,
                                predicate=pred,
                                object_id=o_id,
                                object_label=o_cls,
                                object_bbox=o_box,
                                confidence=round(score, 2),
                                is_hazard=is_haz,
                                hazard_severity=sev,
                                hazard_description=desc,
                            )
                        )

                if triplets:
                    return triplets
            except Exception as err:
                logger.warning(f"Lỗi khi chạy model.predict của RelateAnything ({err}). Sử dụng fallback.")

        # Fallback về bộ suy luận hình học ngữ nghĩa
        return self._fallback_infer_relations(frame, detections)

    def draw_relations_on_frame(
        self,
        frame: np.ndarray,
        triplets: List[SafetyRelationTriplet],
        draw_arrows: bool = True,
    ) -> np.ndarray:
        """Vẽ trực quan hóa các mối quan hệ an toàn lên khung hình video.

        Args:
            frame: Ảnh frame OpenCV BGR.
            triplets: Danh sách bộ ba quan hệ an toàn.
            draw_arrows: Cờ bật vẽ mũi tên vector liên kết giữa 2 đối tượng.

        Returns:
            np.ndarray: Khung hình đã được vẽ các liên kết quan hệ.
        """
        if frame is None or not triplets:
            return frame

        out_frame = frame.copy()

        # Bảng màu đại diện cho các mức độ nguy hiểm
        color_map = {
            RelationHazardSeverity.LOW: (0, 220, 0),       # Xanh lá (Bình thường / An toàn)
            RelationHazardSeverity.MEDIUM: (0, 215, 255), # Vàng cam (Cảnh giác)
            RelationHazardSeverity.HIGH: (0, 100, 255),   # Cam đậm (Nguy hiểm)
            RelationHazardSeverity.CRITICAL: (0, 0, 255), # Đỏ tươi (Nguy cấp)
        }

        for trip in triplets:
            sx1, sy1, sx2, sy2 = trip.subject_bbox
            ox1, oy1, ox2, oy2 = trip.object_bbox

            # Tâm của Subject và Object
            sc = (int((sx1 + sx2) / 2), int((sy1 + sy2) / 2))
            oc = (int((ox1 + ox2) / 2), int((oy1 + oy2) / 2))

            color = color_map.get(trip.hazard_severity, (0, 255, 0))
            thickness = 2 if trip.is_hazard else 1

            if draw_arrows:
                # Vẽ mũi tên định hướng tương tác: Subject -> Object
                cv2.arrowedLine(
                    out_frame,
                    sc,
                    oc,
                    color,
                    thickness,
                    tipLength=0.08,
                    line_type=cv2.LINE_AA,
                )

            # Điểm đặt nhãn quan hệ (nằm giữa đoạn thẳng)
            mid_pt = (int((sc[0] + oc[0]) / 2), int((sc[1] + oc[1]) / 2))

            # Nội dung nhãn: [PREDICATE] (conf)
            prefix = "(!)" if trip.is_hazard else ""
            label_txt = f"{prefix} {trip.predicate.upper()} ({trip.confidence:.2f})"
            label_txt = strip_accents(label_txt)

            # Tính kích thước nền text
            (txt_w, txt_h), baseline = cv2.getTextSize(
                label_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1
            )
            rx1 = mid_pt[0] - txt_w // 2 - 4
            ry1 = mid_pt[1] - txt_h - 4
            rx2 = rx1 + txt_w + 8
            ry2 = ry1 + txt_h + baseline + 6

            # Vẽ nền hộp và viền
            cv2.rectangle(out_frame, (rx1, ry1), (rx2, ry2), (30, 30, 30), -1)
            cv2.rectangle(out_frame, (rx1, ry1), (rx2, ry2), color, 1)
            cv2.putText(
                out_frame,
                label_txt,
                (rx1 + 4, ry1 + txt_h + 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        return out_frame
