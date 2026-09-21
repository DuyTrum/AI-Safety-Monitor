"""Worker Pose Estimation & Fall Detection Engine Module.

Sử dụng YOLO11-Pose để trích xuất 17 điểm khớp xương cơ thể người (COCO Keypoints),
phân tích góc nghiêng thân mình, phát hiện sự cố té ngã, công nhân nằm bất động,
và các tư thế mang vác sai chuẩn công thái học (Ergonomic Risk).
"""

import logging
import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

import cv2
import numpy as np
import torch
from ultralytics import YOLO

from src.utils.text_utils import strip_accents

logger = logging.getLogger("PoseEngine")


# Định nghĩa các cặp nối xương khớp cơ thể (COCO 17 Keypoints Skeleton)
SKELETON_CONNECTIONS = [
    (0, 1), (0, 2), (1, 3), (2, 4),  # Đầu & mặt
    (5, 6),  # Hai vai
    (5, 7), (7, 9),  # Tay trái
    (6, 8), (8, 10),  # Tay phải
    (5, 11), (6, 12),  # Thân mình (Vai -> Hông)
    (11, 12),  # Hai hông
    (11, 13), (13, 15),  # Chân trái
    (12, 14), (14, 16),  # Chân phải
]


@dataclass
class PoseAnalysisResult:
    """Kết quả phân tích tư thế cho một đối tượng người."""

    track_id: Optional[int]
    bbox: Tuple[int, int, int, int]
    keypoints: np.ndarray  # Shape: (17, 3) [x, y, conf]
    torso_angle: float  # Góc nghiêng thân so với phương thẳng đứng (độ)
    aspect_ratio: float  # Tỷ lệ width / height của bbox
    posture_state: str  # "STANDING", "BENDING", "SITTING", "FALLEN"
    is_fallen: bool
    is_bending_risk: bool
    confidence: float
    risk_penalty: float = 0.0


class PoseEngine:
    """Bộ xử lý ước lượng tư thế người và phân loại hành vi nguy hiểm."""

    def __init__(
        self,
        model_path: str = "yolo11n-pose.pt",
        device: Optional[str] = None,
        conf_threshold: float = 0.35,
    ) -> None:
        """Khởi tạo mô hình ước lượng tư thế YOLO11-Pose.

        Args:
            model_path: Đường dẫn tới trọng số pose model (mặc định yolo11n-pose.pt).
            device: Thiết bị chạy (cuda / cpu / 0). Mặc định tự động chọn CUDA nếu khả dụng.
            conf_threshold: Ngưỡng độ tin cậy tối thiểu cho khớp xương.
        """
        self.conf_threshold: float = conf_threshold
        if device is None:
            self.device: str = "0" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        self.model_path = model_path
        self.model: Optional[YOLO] = None
        self._load_model()

    def _load_model(self) -> None:
        """Tải mô hình YOLO Pose."""
        try:
            logger.info(f"Đang tải mô hình YOLO11-Pose từ '{self.model_path}' trên thiết bị {self.device}...")
            self.model = YOLO(self.model_path)
            logger.info("Đã khởi tạo thành công YOLO11-Pose Engine.")
        except Exception as e:
            logger.error(f"Không thể tải mô hình Pose từ {self.model_path}: {e}")
            self.model = None

    def analyze_frame(
        self, frame: np.ndarray, tracked_person_bboxes: Optional[List[Tuple[int, Tuple[int, int, int, int]]]] = None
    ) -> List[PoseAnalysisResult]:
        """Chạy suy luận pose trên toàn bộ khung hình và phân tích tư thế người.

        Args:
            frame: Khung hình BGR từ camera.
            tracked_person_bboxes: Danh sách tùy chọn [(track_id, bbox)] để gán ID người.

        Returns:
            List[PoseAnalysisResult]: Danh sách kết quả phân tích tư thế cho từng người.
        """
        if self.model is None or frame is None or frame.size == 0:
            return []

        try:
            results = self.model(frame, conf=self.conf_threshold, device=self.device, verbose=False)
        except Exception as e:
            logger.error(f"Lỗi suy luận Pose Model: {e}")
            return []

        if not results or len(results) == 0:
            return []

        pose_results: List[PoseAnalysisResult] = []
        result = results[0]

        if result.keypoints is None or result.boxes is None:
            return []

        boxes_data = result.boxes.xyxy.cpu().numpy()
        conf_data = result.boxes.conf.cpu().numpy()
        kpts_data = result.keypoints.data.cpu().numpy()  # (N, 17, 3)

        for i in range(len(boxes_data)):
            bbox = tuple(map(int, boxes_data[i]))
            conf = float(conf_data[i])
            kpts = kpts_data[i]  # (17, 3)

            # Khớp track_id nếu có danh sách theo dõi truyền vào
            matched_tid = None
            if tracked_person_bboxes:
                matched_tid = self._match_track_id(bbox, tracked_person_bboxes)

            analysis = self._classify_pose(bbox, kpts, conf, matched_tid)
            pose_results.append(analysis)

        return pose_results

    def _match_track_id(
        self, bbox: Tuple[int, int, int, int], tracked_boxes: List[Tuple[int, Tuple[int, int, int, int]]]
    ) -> Optional[int]:
        """Khớp bounding box của pose với danh sách track_id dựa trên IoU lớn nhất."""
        best_tid = None
        best_iou = 0.35  # Ngưỡng IoU tối thiểu
        x1, y1, x2, y2 = bbox

        for tid, tbox in tracked_boxes:
            tx1, ty1, tx2, ty2 = tbox
            ix1 = max(x1, tx1)
            iy1 = max(y1, ty1)
            ix2 = min(x2, tx2)
            iy2 = min(y2, ty2)
            iw = max(0, ix2 - ix1)
            ih = max(0, iy2 - iy1)
            inter = iw * ih
            union = (x2 - x1) * (y2 - y1) + (tx2 - tx1) * (ty2 - ty1) - inter
            if union > 0:
                iou = inter / union
                if iou > best_iou:
                    best_iou = iou
                    best_tid = tid

        return best_tid

    def _classify_pose(
        self,
        bbox: Tuple[int, int, int, int],
        kpts: np.ndarray,
        confidence: float,
        track_id: Optional[int],
    ) -> PoseAnalysisResult:
        """Phân tích góc thân, tỷ lệ khung bao và phát hiện té ngã / cúi gập nguy hiểm."""
        x1, y1, x2, y2 = bbox
        width = max(1, x2 - x1)
        height = max(1, y2 - y1)
        aspect_ratio = width / float(height)

        # Trích xuất các khớp quan trọng: Vai (5, 6), Hông (11, 12), Mũi (0)
        l_shoulder, r_shoulder = kpts[5], kpts[6]
        l_hip, r_hip = kpts[11], kpts[12]
        nose = kpts[0]

        # Tính trung điểm hai vai và hai hông
        has_shoulders = l_shoulder[2] > 0.2 and r_shoulder[2] > 0.2
        has_hips = l_hip[2] > 0.2 and r_hip[2] > 0.2

        torso_angle = 0.0
        if has_shoulders and has_hips:
            mid_shoulder_x = (l_shoulder[0] + r_shoulder[0]) / 2.0
            mid_shoulder_y = (l_shoulder[1] + r_shoulder[1]) / 2.0
            mid_hip_x = (l_hip[0] + r_hip[0]) / 2.0
            mid_hip_y = (l_hip[1] + r_hip[1]) / 2.0

            dx = mid_shoulder_x - mid_hip_x
            dy = mid_shoulder_y - mid_hip_y

            # Góc so với phương thẳng đứng dy (0 độ là đứng thẳng)
            angle_rad = math.atan2(abs(dx), abs(dy) + 1e-6)
            torso_angle = math.degrees(angle_rad)
        else:
            # Ước lượng thô theo tỷ lệ bbox nếu khớp bị che khuất
            torso_angle = 80.0 if aspect_ratio > 1.2 else 15.0

        # Tiêu chí nhận diện TÉ NGÃ (FALLEN):
        # 1. Thân người nằm ngang (torso_angle > 58 độ)
        # 2. Hoặc khung hình chiều rộng lớn hơn chiều cao rõ rệt (aspect_ratio > 1.1)
        # 3. Và độ cao của đầu (nose) nằm ngang với tầm hông
        is_fallen = False
        if torso_angle > 58.0 and aspect_ratio > 1.05:
            is_fallen = True
        elif aspect_ratio > 1.35:
            is_fallen = True
        elif nose[2] > 0.25 and has_hips:
            mid_hip_y = (l_hip[1] + r_hip[1]) / 2.0
            if abs(nose[1] - mid_hip_y) < (height * 0.25) and aspect_ratio > 0.95:
                is_fallen = True

        # Tiêu chí nhận diện CÚI GẬP LƯNG NGUY HIỂM (BENDING / ERGONOMIC STRAIN):
        is_bending_risk = False
        if not is_fallen and (35.0 <= torso_angle <= 65.0):
            is_bending_risk = True

        # Phân loại trạng thái tư thế
        if is_fallen:
            posture_state = "FALLEN"
            risk_penalty = 95.0
        elif is_bending_risk:
            posture_state = "BENDING"
            risk_penalty = 35.0
        elif aspect_ratio > 0.8 and height < 120:
            posture_state = "SITTING"
            risk_penalty = 15.0
        else:
            posture_state = "STANDING"
            risk_penalty = 0.0

        return PoseAnalysisResult(
            track_id=track_id,
            bbox=bbox,
            keypoints=kpts,
            torso_angle=torso_angle,
            aspect_ratio=aspect_ratio,
            posture_state=posture_state,
            is_fallen=is_fallen,
            is_bending_risk=is_bending_risk,
            confidence=confidence,
            risk_penalty=risk_penalty,
        )

    def draw_pose_on_frame(
        self, frame: np.ndarray, pose_results: List[PoseAnalysisResult], draw_skeleton: bool = True
    ) -> np.ndarray:
        """Vẽ khung xương và trạng thái tư thế lên khung hình.

        Args:
            frame: Ảnh OpenCV BGR.
            pose_results: Danh sách kết quả phân tích tư thế.
            draw_skeleton: Có vẽ các đường nối xương hay không.

        Returns:
            np.ndarray: Khung hình sau khi vẽ.
        """
        if frame is None or frame.size == 0 or not pose_results:
            return frame

        for pose in pose_results:
            kpts = pose.keypoints
            bbox = pose.bbox

            # Lựa chọn màu sắc theo mức độ rủi ro
            if pose.is_fallen:
                color = (0, 0, 255)  # Đỏ khẩn cấp
                state_text = "TE NGA (FALLEN)"
            elif pose.is_bending_risk:
                color = (0, 165, 255)  # Cam
                state_text = f"CUI LUNG ({int(pose.torso_angle)} deg)"
            else:
                color = (0, 255, 0)  # Xanh an toàn
                state_text = "BINH THUONG"

            # Vẽ các khớp xương và đường nối nếu cần
            if draw_skeleton:
                # Vẽ đường nối xương
                for pt1_idx, pt2_idx in SKELETON_CONNECTIONS:
                    x1, y1, c1 = kpts[pt1_idx]
                    x2, y2, c2 = kpts[pt2_idx]
                    if c1 > 0.3 and c2 > 0.3:
                        cv2.line(
                            frame,
                            (int(x1), int(y1)),
                            (int(x2), int(y2)),
                            color,
                            2,
                            cv2.LINE_AA,
                        )

                # Vẽ điểm tròn tại các khớp
                for x, y, c in kpts:
                    if c > 0.3:
                        cv2.circle(frame, (int(x), int(y)), 3, (255, 255, 255), -1, cv2.LINE_AA)
                        cv2.circle(frame, (int(x), int(y)), 2, color, -1, cv2.LINE_AA)

            # Vẽ nhãn trạng thái tư thế phía trên bbox
            bx1, by1, bx2, by2 = bbox
            label_str = strip_accents(f"[{pose.posture_state}] {state_text}")
            (tw, th), _ = cv2.getTextSize(label_str, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            ly = max(15, by1 - 6)
            cv2.rectangle(frame, (bx1, ly - th - 3), (bx1 + tw + 6, ly + 3), (0, 0, 0), -1)
            cv2.putText(
                frame,
                label_str,
                (bx1 + 3, ly),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                color,
                1,
                cv2.LINE_AA,
            )

        return frame
