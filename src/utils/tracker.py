"""Spatial-Temporal Object & Violation Tracker Module.

Cung cấp bộ theo dõi đối tượng thông minh (Spatial Centroid & IoU Multi-Object Tracker)
giúp gán định danh (ID) bền vững, chống nhảy ID và đảm bảo CHỈ CẢNH BÁO 1 LẦN DUY NHẤT
cho mỗi đối tượng vi phạm khi họ còn ở trong khung hình camera.
"""

import math
import time
import logging
from typing import Dict, List, Tuple, Optional, Set

logger = logging.getLogger("ViolationTracker")


def calculate_iou(box1: Tuple[int, int, int, int], box2: Tuple[int, int, int, int]) -> float:
    """Tính toán chỉ số Intersection over Union (IoU) giữa 2 Bounding Box.

    Args:
        box1: (x1, y1, x2, y2)
        box2: (x1, y1, x2, y2)

    Returns:
        float: Giá trị IoU (0.0 đến 1.0).
    """
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    inter_width = max(0, x2 - x1)
    inter_height = max(0, y2 - y1)
    inter_area = inter_width * inter_height

    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])

    union_area = area1 + area2 - inter_area
    if union_area <= 0:
        return 0.0
    return inter_area / union_area


def calculate_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Tính khoảng cách Euclid giữa 2 tâm đối tượng.

    Args:
        p1: (cx1, cy1)
        p2: (cx2, cy2)

    Returns:
        float: Khoảng cách pixel.
    """
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


class TrackedEntity:
    """Đại diện cho một thực thể hoặc trang bị đang được hệ thống theo dõi."""

    def __init__(
        self,
        track_id: int,
        bbox: Tuple[int, int, int, int],
        class_name: str,
        confidence: float,
        timestamp: float,
    ) -> None:
        """Khởi tạo một thực thể theo dõi mới.

        Args:
            track_id: Mã định danh duy nhất của đối tượng.
            bbox: Tọa độ bounding box (x1, y1, x2, y2).
            class_name: Tên nhãn nhận diện (vd: helmet, no-helmet, vest, no-vest).
            confidence: Độ tin cậy (0.0 - 1.0).
            timestamp: Thời điểm phát hiện lần đầu (epoch seconds).
        """
        self.track_id: int = track_id
        self.bbox: Tuple[int, int, int, int] = bbox
        self.class_name: str = class_name
        self.confidence: float = confidence
        self.cx: float = (bbox[0] + bbox[2]) / 2.0
        self.cy: float = (bbox[1] + bbox[3]) / 2.0
        self.first_seen: float = timestamp
        self.last_seen: float = timestamp
        self.missed_frames: int = 0
        # Tập các loại vi phạm đã được cảnh báo (Telegram + Snapshot + DB)
        self.alerted_violations: Set[str] = set()

    def update(
        self,
        bbox: Tuple[int, int, int, int],
        class_name: str,
        confidence: float,
        timestamp: float,
    ) -> None:
        """Cập nhật tọa độ và thông số mới nhất của thực thể.

        Args:
            bbox: Tọa độ bounding box mới.
            class_name: Tên nhãn nhận diện mới.
            confidence: Độ tin cậy mới.
            timestamp: Thời điểm cập nhật.
        """
        self.bbox = bbox
        self.class_name = class_name
        self.confidence = confidence
        self.cx = (bbox[0] + bbox[2]) / 2.0
        self.cy = (bbox[1] + bbox[3]) / 2.0
        self.last_seen = timestamp
        self.missed_frames = 0


class RobustViolationTracker:
    """Bộ theo dõi không gian - thời gian (Spatial-Temporal MOT Tracker).

    Duy trì ID ổn định dựa trên IoU và khoảng cách tâm, đảm bảo:
    1. Gán ID nhất quán cho từng người/trang bị.
    2. Chỉ bắn cảnh báo 1 lần duy nhất cho mỗi ID khi vẫn còn trong khung hình.
    3. Giữ bộ nhớ track trong thời gian timeout (mặc định 30s) trước khi giải phóng.
    """

    def __init__(
        self,
        max_disappear_seconds: float = 30.0,
        max_distance_threshold: float = 120.0,
        min_iou_threshold: float = 0.2,
    ) -> None:
        """Khởi tạo bộ theo dõi.

        Args:
            max_disappear_seconds: Thời gian tối đa lưu vết đối tượng khi tạm thời mất dấu (giây).
            max_distance_threshold: Khoảng cách tâm tối đa để gán cùng một đối tượng (pixel).
            min_iou_threshold: Ngưỡng IoU tối thiểu để nhận diện là cùng một đối tượng.
        """
        self.next_id: int = 1
        self.tracks: Dict[int, TrackedEntity] = {}
        self.max_disappear_seconds: float = max_disappear_seconds
        self.max_distance_threshold: float = max_distance_threshold
        self.min_iou_threshold: float = min_iou_threshold

    def update(
        self,
        detections: List[Tuple[Tuple[int, int, int, int], str, float]],
        timestamp: Optional[float] = None,
    ) -> List[Tuple[int, Tuple[int, int, int, int], str, float, bool]]:
        """Cập nhật các bounding box phát hiện trong frame hiện tại với các track đã lưu.

        Args:
            detections: Danh sách [(bbox, class_name, confidence)].
            timestamp: Thời điểm hiện tại (mặc định time.time()).

        Returns:
            List[Tuple[track_id, bbox, class_name, confidence, is_already_alerted]]
        """
        if timestamp is None:
            timestamp = time.time()

        # Dọn dẹp các track đã biến mất quá lâu (> max_disappear_seconds)
        expired_ids = [
            tid
            for tid, entity in self.tracks.items()
            if (timestamp - entity.last_seen) > self.max_disappear_seconds
        ]
        for tid in expired_ids:
            logger.info(f"Đối tượng ID #{tid} đã rời khỏi khung hình hoàn toàn (> {self.max_disappear_seconds}s). Giải phóng bộ nhớ track.")
            del self.tracks[tid]

        matched_detection_indices = set()
        matched_track_ids = set()
        results = []

        # 1. Khớp theo IoU và khoảng cách tâm với các track hiện có
        for det_idx, (bbox, class_name, conf) in enumerate(detections):
            det_center = ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)
            best_match_id: Optional[int] = None
            best_score: float = -1.0

            for tid, track in self.tracks.items():
                if tid in matched_track_ids:
                    continue

                iou = calculate_iou(bbox, track.bbox)
                dist = calculate_distance(det_center, (track.cx, track.cy))

                # Điều kiện khớp: IoU >= min_iou HOẶC tâm gần nhau < max_distance
                is_match = (iou >= self.min_iou_threshold) or (dist <= self.max_distance_threshold)
                if is_match:
                    # Điểm số kết hợp (ưu tiên IoU cao và khoảng cách gần)
                    score = iou * 100.0 - dist * 0.1
                    if score > best_score:
                        best_score = score
                        best_match_id = tid

            if best_match_id is not None:
                # Đã khớp với track cũ
                track = self.tracks[best_match_id]
                track.update(bbox, class_name, conf, timestamp)
                matched_track_ids.add(best_match_id)
                matched_detection_indices.add(det_idx)
                
                is_alerted = class_name in track.alerted_violations
                results.append((best_match_id, bbox, class_name, conf, is_alerted))

        # 2. Tạo track mới cho các phát hiện chưa khớp
        for det_idx, (bbox, class_name, conf) in enumerate(detections):
            if det_idx not in matched_detection_indices:
                new_id = self.next_id
                self.next_id += 1

                new_track = TrackedEntity(new_id, bbox, class_name, conf, timestamp)
                self.tracks[new_id] = new_track
                matched_track_ids.add(new_id)

                results.append((new_id, bbox, class_name, conf, False))

        # 3. Tăng missed_frames cho các track không xuất hiện trong frame này
        for tid, track in self.tracks.items():
            if tid not in matched_track_ids:
                track.missed_frames += 1

        return results

    def mark_alerted(self, track_id: int, violation_type: str) -> None:
        """Đánh dấu rằng đối tượng track_id này ĐÃ ĐƯỢC CẢNH BÁO lỗi vi phạm này.

        Args:
            track_id: Mã ID đối tượng.
            violation_type: Tên lỗi vi phạm (vd: no-helmet).
        """
        if track_id in self.tracks:
            self.tracks[track_id].alerted_violations.add(violation_type)
            logger.info(f"Đã gán cờ ĐÃ CẢNH BÁO cho Đối tượng ID #{track_id} (Lỗi: {violation_type}). Sẽ KHÔNG cảnh báo lại!")

    def is_alerted(self, track_id: int, violation_type: str) -> bool:
        """Kiểm tra đối tượng track_id đã từng được cảnh báo lỗi này chưa.

        Args:
            track_id: Mã ID đối tượng.
            violation_type: Tên lỗi vi phạm.

        Returns:
            bool: True nếu đã cảnh báo rồi, ngược lại False.
        """
        if track_id in self.tracks:
            return violation_type in self.tracks[track_id].alerted_violations
        return False

    def reset(self) -> None:
        """Xóa toàn bộ các track đang theo dõi."""
        self.tracks.clear()
        self.next_id = 1
        logger.info("Đã đặt lại toàn bộ bộ theo dõi đối tượng.")
