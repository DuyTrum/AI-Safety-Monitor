"""Violation snapshot storage module.

Chức năng tự động chụp, lưu trữ khung hình vi phạm an toàn lao động
kèm nhãn, timestamp và thông tin độ tin cậy.
"""

import os
import cv2
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger("SnapshotManager")

# Thư mục gốc lưu trữ ảnh snapshot vi phạm
SNAPSHOT_BASE_DIR = os.path.abspath("data/violations")


def ensure_snapshot_dir(date_str: Optional[str] = None) -> str:
    """Tạo và đảm bảo thư mục snapshot theo ngày tồn tại.

    Args:
        date_str: Chuỗi ngày theo định dạng YYYY-MM-DD. Nếu None, dùng ngày hiện tại.

    Returns:
        Đường dẫn tuyệt đối đến thư mục snapshot của ngày.
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    target_dir = os.path.join(SNAPSHOT_BASE_DIR, date_str)
    os.makedirs(target_dir, exist_ok=True)
    return target_dir


def save_violation_snapshot(
    frame: cv2.Mat,
    violation_type: str,
    confidence: float,
    track_id: Optional[int] = None
) -> Dict[str, str]:
    """Lưu khung hình vi phạm thành file ảnh JPEG.

    Args:
        frame: Khung hình OpenCV BGR (đã vẽ hoặc chưa vẽ bounding box).
        violation_type: Tên loại vi phạm (vd: no-helmet, no-vest).
        confidence: Độ tin cậy của phát hiện (0.0 - 1.0).
        track_id: ID theo dõi đối tượng (nếu có).

    Returns:
        Dict chứa 'file_path' (tuyệt đối) và 'relative_url' (để gọi từ API).
    """
    if frame is None or frame.size == 0:
        logger.error("Khung hình rỗng, không thể lưu snapshot.")
        return {"file_path": "", "relative_url": ""}

    try:
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H%M%S_%f")[:10]
        dir_path = ensure_snapshot_dir(date_str)

        track_str = f"_track{track_id}" if track_id is not None else ""
        filename = f"violation_{time_str}_{violation_type}{track_str}.jpg"
        file_path = os.path.join(dir_path, filename)

        # Lưu ảnh JPEG với chất lượng 85%
        cv2.imwrite(file_path, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])

        relative_url = f"/static/snapshots/{date_str}/{filename}"
        logger.info(f"Đã lưu ảnh snapshot vi phạm: {file_path}")

        return {
            "file_path": file_path,
            "relative_url": relative_url,
            "filename": filename,
            "date": date_str
        }
    except Exception as e:
        logger.error(f"Lỗi khi lưu snapshot vi phạm: {e}")
        return {"file_path": "", "relative_url": ""}
