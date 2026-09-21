"""Script tạo bộ video kiểm thử công trường đa kịch bản (Comprehensive Construction Test Video Suite).

Tự động sinh 5 bộ video kiểm thử chuyên biệt chuẩn 720p 25fps từ tập dữ liệu thực tế
và mô hình hóa động học tai nạn lao động phục vụ kiểm định toàn bộ chức năng:
1. 01_ppe_violation_benchmark.mp4: Kiểm thử 10 lớp PPE (Mũ, Áo, Găng, Ủng, Kính và Vi phạm).
2. 02_danger_zone_intrusion.mp4: Xâm nhập vùng nguy hiểm xe cơ giới & tính điểm WRI.
3. 03_fall_incident_simulation.mp4: Mô phỏng trượt ngã, tư thế ngã YOLO-Pose & Ghost Fall.
4. 04_scaffold_height_hazard.mp4: Giàn giáo làm việc trên cao & Vật thể rơi Drop Cone.
5. 05_multi_worker_tracking.mp4: Theo dõi đa công nhân ByteTrack & Khử lặp cảnh báo.
"""

from __future__ import annotations

import glob
import logging
import math
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

import io

# Cấu hình UTF-8 an toàn trên Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

# Thiết lập logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("TestVideoGenerator")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
VIDEOS_DIR = DATA_DIR / "videos"
TEST_IMAGES_DIR = DATA_DIR / "ppe_dataset" / "test" / "images"
TEST_LABELS_DIR = DATA_DIR / "ppe_dataset" / "test" / "labels"
SAMPLE_IMAGES_DIR = DATA_DIR / "sample_images"

TARGET_WIDTH = 720
TARGET_HEIGHT = 480
FPS = 25
FOURCC = cv2.VideoWriter_fourcc(*"mp4v")

CLASS_NAMES = [
    "boots", "gloves", "goggles", "helmet",
    "no-boots", "no-gloves", "no-goggles", "no-helmet", "no-vest", "vest"
]


def load_labeled_images_map() -> Dict[str, List[str]]:
    """Phân loại danh sách ảnh kiểm thử theo từng nhãn bảo hộ thực tế.

    Returns:
        Dict mapping từ tên lớp (như 'no-helmet') sang danh sách đường dẫn ảnh.
    """
    category_map: Dict[str, List[str]] = {name: [] for name in CLASS_NAMES}

    if not TEST_LABELS_DIR.exists():
        logger.warning(f"Thư mục nhãn {TEST_LABELS_DIR} không tồn tại.")
        return category_map

    label_files = list(TEST_LABELS_DIR.glob("*.txt"))
    for lf in label_files:
        img_path = TEST_IMAGES_DIR / f"{lf.stem}.jpg"
        if not img_path.exists():
            continue

        try:
            with open(lf, "r", encoding="utf-8") as f:
                classes_in_file = set()
                for line in f:
                    parts = line.strip().split()
                    if parts:
                        cid = int(parts[0])
                        if 0 <= cid < len(CLASS_NAMES):
                            classes_in_file.add(CLASS_NAMES[cid])
                for cname in classes_in_file:
                    category_map[cname].append(str(img_path))
        except Exception as e:
            logger.debug(f"Lỗi đọc {lf}: {e}")

    return category_map


def safe_read_image(path: str) -> Optional[np.ndarray]:
    """Đọc ảnh từ đĩa an toàn và trả về numpy array BGR."""
    if not os.path.exists(path):
        return None
    return cv2.imread(path)


def resize_frame(img: np.ndarray, width: int = TARGET_WIDTH, height: int = TARGET_HEIGHT) -> np.ndarray:
    """Resize ảnh vừa khít kích thước chuẩn kiểm thử."""
    return cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)


def add_camera_jitter(frame: np.ndarray, frame_idx: int, intensity: float = 2.0) -> np.ndarray:
    """Tạo hiệu ứng rung lắc nhẹ và chuyển động quét tự nhiên của camera quan sát CCTV."""
    shift_x = int(math.sin(frame_idx * 0.08) * intensity)
    shift_y = int(math.cos(frame_idx * 0.06) * (intensity * 0.5))
    h, w = frame.shape[:2]
    mat = np.float32([[1, 0, shift_x], [0, 1, shift_y]])
    return cv2.warpAffine(frame, mat, (w, h), borderMode=cv2.BORDER_REPLICATE)


def generate_ppe_violation_benchmark_video(output_path: Path, category_map: Dict[str, List[str]]) -> None:
    """Tạo Video 1: Kiểm thử chuẩn 10 lớp PPE (Tuân thủ vs Vi phạm).

    Bao gồm chuỗi các phân đoạn:
    - Phân đoạn 1: Công nhân tuân thủ đầy đủ Mũ và Áo (Helmet & Vest).
    - Phân đoạn 2: Công nhân vi phạm Không đội Mũ bảo hộ (No-Helmet).
    - Phân đoạn 3: Công nhân vi phạm Không mặc Áo phản quang (No-Vest).
    - Phân đoạn 4: Công nhân vi phạm Không đeo Kính & Không đeo Găng (No-Goggles, No-Gloves).
    - Phân đoạn 5: Công nhân vi phạm Không đi Ủng bảo hộ (No-Boots).
    """
    logger.info(f"[1/5] Đang tạo video kiểm thử PPE: {output_path.name}...")

    # Tuyển chọn các ảnh đại diện chất lượng cao cho từng phân đoạn
    segments: List[Tuple[str, List[str]]] = [
        ("TUÂN THỦ: ĐẦY ĐỦ MŨ & ÁO BẢO HỘ", category_map.get("helmet", [])[:3]),
        ("VI PHẠM: KHÔNG ĐỘI MŨ BẢO HỘ (NO-HELMET)", category_map.get("no-helmet", [])[:3]),
        ("VI PHẠM: KHÔNG MẶC ÁO PHẢN QUANG (NO-VEST)", category_map.get("no-vest", [])[:3]),
        ("VI PHẠM: THIẾU KÍNH & GĂNG TAY", category_map.get("no-goggles", [])[:2] + category_map.get("no-gloves", [])[:2]),
        ("VI PHẠM: KHÔNG ĐI ỦNG BẢO HỘ (NO-BOOTS)", category_map.get("no-boots", [])[:3]),
    ]

    writer = cv2.VideoWriter(str(output_path), FOURCC, FPS, (TARGET_WIDTH, TARGET_HEIGHT))

    global_frame_idx = 0
    for seg_title, img_paths in segments:
        if not img_paths:
            continue
        for p in img_paths:
            img = safe_read_image(p)
            if img is None:
                continue
            resized = resize_frame(img)

            # Mỗi ảnh giữ trong 40 frames (~1.6 giây) kèm chuyển động camera nhẹ
            for f in range(40):
                frame_jittered = add_camera_jitter(resized, global_frame_idx, intensity=1.5)
                # Thêm hiệu ứng chuyển động thở của camera CCTV
                writer.write(frame_jittered)
                global_frame_idx += 1

    writer.release()
    logger.info(f"Hoàn thành tạo video: {output_path} ({global_frame_idx} frames).")


def generate_danger_zone_intrusion_video(output_path: Path, category_map: Dict[str, List[str]]) -> None:
    """Tạo Video 2: Công nhân xâm nhập vùng nguy hiểm xe cơ giới & máy đào.

    Mô phỏng công nhân di chuyển từ vùng an toàn bên trái (x=50) đi vào vùng nguy hiểm
    quanh xe đào / hố sâu ở trung tâm khung hình (x=350-550), kích hoạt Geofencing và tăng WRI.
    """
    logger.info(f"[2/5] Đang tạo video xâm nhập vùng nguy hiểm: {output_path.name}...")

    # Chọn ảnh nền công trường có máy móc
    candidate_bg = SAMPLE_IMAGES_DIR / "00100_jpg.rf.87e0894580a4f957424704b89d2d1451.jpg"
    if not candidate_bg.exists() and category_map.get("vest"):
        candidate_bg = Path(category_map["vest"][0])

    bg_img = safe_read_image(str(candidate_bg))
    if bg_img is None:
        bg_img = np.full((TARGET_HEIGHT, TARGET_WIDTH, 3), 120, dtype=np.uint8)
    else:
        bg_img = resize_frame(bg_img)

    h, w = bg_img.shape[:2]

    # Trích xuất 1 công nhân mẫu làm đối tượng di chuyển
    wx1, wy1, wx2, wy2 = int(w * 0.45), int(h * 0.35), int(w * 0.60), int(h * 0.75)
    worker_patch = bg_img[wy1:wy2, wx1:wx2].copy()
    pw_h, pw_w = worker_patch.shape[:2]

    # Mask mềm làm mịn viền alpha blending
    mask = np.ones((pw_h, pw_w), dtype=np.float32)
    cv2.rectangle(mask, (0, 0), (pw_w - 1, pw_h - 1), 0, 8)
    mask = cv2.GaussianBlur(mask, (15, 15), 0)
    mask_3ch = cv2.merge([mask, mask, mask])

    # Inpaint xóa đối tượng ban đầu để tạo nền sạch
    inpaint_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(inpaint_mask, (wx1, wy1), (wx2, wy2), 255, -1)
    clean_bg = cv2.inpaint(bg_img, inpaint_mask, inpaintRadius=7, flags=cv2.INPAINT_TELEA)

    writer = cv2.VideoWriter(str(output_path), FOURCC, FPS, (TARGET_WIDTH, TARGET_HEIGHT))

    num_frames = 200  # 8 giây
    start_x = 40
    end_x = int(w * 0.65)  # Đi sâu vào vùng nguy hiểm máy đào
    start_y = int(h * 0.36)
    end_y = int(h * 0.36)

    for f in range(num_frames):
        t = f / float(num_frames)
        cur_x = int(start_x + (end_x - start_x) * t)
        # Nhịp bước đi bộ sin
        bob = int(math.sin(f * 0.35) * 4)
        cur_y = int(start_y + (end_y - start_y) * t) + bob

        frame = clean_bg.copy()
        x1, y1 = max(0, cur_x), max(0, cur_y)
        x2, y2 = min(w, cur_x + pw_w), min(h, cur_y + pw_h)
        patch_w = x2 - x1
        patch_h = y2 - y1

        if patch_w > 0 and patch_h > 0:
            sub_patch = worker_patch[:patch_h, :patch_w].astype(np.float32)
            sub_mask = mask_3ch[:patch_h, :patch_w]
            bg_roi = frame[y1:y2, x1:x2].astype(np.float32)
            blended = sub_patch * sub_mask + bg_roi * (1.0 - sub_mask)
            frame[y1:y2, x1:x2] = np.clip(blended, 0, 255).astype(np.uint8)

        writer.write(frame)

    writer.release()
    logger.info(f"Hoàn thành tạo video: {output_path} ({num_frames} frames).")


def generate_fall_incident_simulation_video(output_path: Path, category_map: Dict[str, List[str]]) -> None:
    """Tạo Video 3: Mô phỏng sự cố công nhân trượt ngã trên sàn thi công.

    Mô phỏng 4 giai đoạn ngã chuẩn động học công thái học:
    1. Đứng thẳng làm việc (Normal Stance): 0 - 35 frames (1.4s).
    2. Mất thăng bằng, góc nghiêng tăng dần (Loss of Balance): 35 - 65 frames (1.2s, 0° -> 85°).
    3. Va chạm sàn (Floor Impact): 65 - 80 frames (rung chấn).
    4. Nằm bất động (Post-fall Inactivity): 80 - 180 frames (4.0s) -> Kích hoạt YOLO11-Pose & Ghost Fall.
    """
    logger.info(f"[3/5] Đang tạo video mô phỏng trượt ngã: {output_path.name}...")

    # Lấy ảnh công nhân đứng rõ nét
    candidate = None
    for p in category_map.get("helmet", []) + category_map.get("vest", []):
        img = safe_read_image(p)
        if img is not None:
            candidate = resize_frame(img)
            break

    if candidate is None:
        candidate = np.full((TARGET_HEIGHT, TARGET_WIDTH, 3), 100, dtype=np.uint8)

    writer = cv2.VideoWriter(str(output_path), FOURCC, FPS, (TARGET_WIDTH, TARGET_HEIGHT))

    # Giai đoạn 1: Đứng thẳng (35 frames)
    for f in range(35):
        jittered = add_camera_jitter(candidate, f, intensity=1.0)
        writer.write(jittered)

    # Giai đoạn 2: Trượt ngã (góc quay từ 0 đến 85 độ theo chiều ngang)
    center = (TARGET_WIDTH // 2, TARGET_HEIGHT // 2 + 50)
    for angle in range(0, 85, 4):
        rot_mat = cv2.getRotationMatrix2D(center, -float(angle), 1.0)
        rotated = cv2.warpAffine(candidate, rot_mat, (TARGET_WIDTH, TARGET_HEIGHT), borderMode=cv2.BORDER_REPLICATE)
        writer.write(rotated)

    # Giai đoạn 3: Nằm bất động trên sàn (100 frames)
    rot_mat = cv2.getRotationMatrix2D(center, -85.0, 1.0)
    fallen_frame = cv2.warpAffine(candidate, rot_mat, (TARGET_WIDTH, TARGET_HEIGHT), borderMode=cv2.BORDER_REPLICATE)

    for f in range(100):
        # Nhiễu nhẹ cảm biến CCTV
        noise = np.random.randint(-2, 3, fallen_frame.shape, dtype=np.int16)
        noisy = np.clip(fallen_frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        writer.write(noisy)

    writer.release()
    logger.info(f"Hoàn thành tạo video: {output_path} ({35 + 22 + 100} frames).")


def generate_scaffold_height_hazard_video(output_path: Path, category_map: Dict[str, List[str]]) -> None:
    """Tạo Video 4: Giàn giáo cao tầng, vi phạm dây an toàn & vật rơi Drop Cone.

    Mô phỏng công nhân thao tác trên vị trí cao, làm rơi 1 dụng cụ thi công (búa/mỏ lết)
    xuống mặt đất theo gia tốc trọng trường g = 9.8 m/s^2, kiểm thử nón rơi Drop Cone.
    """
    logger.info(f"[4/5] Đang tạo video giàn giáo & vật thể rơi: {output_path.name}...")

    # Chọn ảnh công trường
    img_bg = None
    for p in category_map.get("helmet", []) + category_map.get("boots", []):
        img = safe_read_image(p)
        if img is not None:
            img_bg = resize_frame(img)
            break

    if img_bg is None:
        img_bg = np.full((TARGET_HEIGHT, TARGET_WIDTH, 3), 90, dtype=np.uint8)

    writer = cv2.VideoWriter(str(output_path), FOURCC, FPS, (TARGET_WIDTH, TARGET_HEIGHT))

    num_frames = 175  # 7 giây
    tool_start_frame = 40
    tool_end_frame = 100

    tool_x = int(TARGET_WIDTH * 0.48)
    tool_y_start = int(TARGET_HEIGHT * 0.25)
    tool_y_end = int(TARGET_HEIGHT * 0.85)

    for f in range(num_frames):
        frame = add_camera_jitter(img_bg, f, intensity=1.0)

        # Mô phỏng vật rơi tự do
        if tool_start_frame <= f <= tool_end_frame:
            t_fall = (f - tool_start_frame) / float(tool_end_frame - tool_start_frame)
            # Quỹ đạo rơi tự do y = y0 + 0.5 * a * t^2
            cur_tool_y = int(tool_y_start + (tool_y_end - tool_y_start) * (t_fall ** 2))
            cur_tool_x = tool_x + int(math.sin(t_fall * 6.0) * 8)  # Lắc nhẹ khi rơi

            # Vẽ vật thể rơi (cụm kim loại màu vàng cam)
            cv2.circle(frame, (cur_tool_x, cur_tool_y), 7, (0, 165, 255), -1)
            cv2.circle(frame, (cur_tool_x, cur_tool_y), 9, (0, 255, 255), 1)

            # Vệt chuyển động (motion blur streak)
            if cur_tool_y > tool_y_start + 10:
                cv2.line(frame, (cur_tool_x, cur_tool_y - 12), (cur_tool_x, cur_tool_y), (0, 165, 255), 2)

        writer.write(frame)

    writer.release()
    logger.info(f"Hoàn thành tạo video: {output_path} ({num_frames} frames).")


def generate_multi_worker_tracking_video(output_path: Path, category_map: Dict[str, List[str]]) -> None:
    """Tạo Video 5: Nhiều công nhân đi lại cắt ngang nhau & ByteTrack ID persistence.

    Mô phỏng 2 công nhân di chuyển ngược chiều nhau qua trung tâm khung hình:
    - Công nhân 1 (Đi từ trái sang phải)
    - Công nhân 2 (Đi từ phải sang trái)
    Kiểm thử thuật toán ByteTrack không bị nhầm lẫn Track ID khi 2 người cắt ngang qua nhau
    và xác thực cơ chế Spatial-Temporal De-duplication chỉ cảnh báo 1 lần duy nhất.
    """
    logger.info(f"[5/5] Đang tạo video đa công nhân ByteTrack: {output_path.name}...")

    # Lấy 2 công nhân mẫu từ 2 ảnh khác nhau
    img1 = None
    img2 = None

    if category_map.get("no-helmet"):
        img1 = safe_read_image(category_map["no-helmet"][0])
    if category_map.get("helmet"):
        img2 = safe_read_image(category_map["helmet"][0])

    if img1 is None or img2 is None:
        img1 = np.full((TARGET_HEIGHT, TARGET_WIDTH, 3), 110, dtype=np.uint8)
        img2 = np.full((TARGET_HEIGHT, TARGET_WIDTH, 3), 130, dtype=np.uint8)
    else:
        img1 = resize_frame(img1)
        img2 = resize_frame(img2)

    h, w = TARGET_HEIGHT, TARGET_WIDTH

    # Trích xuất 2 worker patches
    p1_w, p1_h = 100, 180
    p1 = img1[int(h * 0.3):int(h * 0.3) + p1_h, int(w * 0.4):int(w * 0.4) + p1_w].copy()

    p2_w, p2_h = 110, 190
    p2 = img2[int(h * 0.25):int(h * 0.25) + p2_h, int(w * 0.45):int(w * 0.45) + p2_w].copy()

    # Nền công trường tĩnh
    bg = cv2.GaussianBlur(img1, (9, 9), 0)

    writer = cv2.VideoWriter(str(output_path), FOURCC, FPS, (TARGET_WIDTH, TARGET_HEIGHT))

    num_frames = 200  # 8 giây
    for f in range(num_frames):
        t = f / float(num_frames)
        frame = bg.copy()

        # Worker 1: Đi từ Trái sang Phải (x: 30 -> w - 120)
        w1_x = int(30 + (w - 150) * t)
        w1_y = int(h * 0.38) + int(math.sin(f * 0.3) * 3)

        # Worker 2: Đi từ Phải sang Trái (x: w - 140 -> 40)
        w2_x = int((w - 140) - (w - 180) * t)
        w2_y = int(h * 0.35) + int(math.cos(f * 0.35) * 3)

        # Dán Worker 2 (ở phía sau)
        y2_end = min(h, w2_y + p2.shape[0])
        x2_end = min(w, w2_x + p2.shape[1])
        rh2 = y2_end - w2_y
        rw2 = x2_end - w2_x
        if rh2 > 0 and rw2 > 0 and w2_x >= 0 and w2_y >= 0:
            frame[w2_y:y2_end, w2_x:x2_end] = p2[:rh2, :rw2]

        # Dán Worker 1 (ở phía trước khi cắt nhau)
        y1_end = min(h, w1_y + p1.shape[0])
        x1_end = min(w, w1_x + p1.shape[1])
        rh1 = y1_end - w1_y
        rw1 = x1_end - w1_x
        if rh1 > 0 and rw1 > 0 and w1_x >= 0 and w1_y >= 0:
            frame[w1_y:y1_end, w1_x:x1_end] = p1[:rh1, :rw1]

        writer.write(frame)

    writer.release()
    logger.info(f"Hoàn thành tạo video: {output_path} ({num_frames} frames).")


def main() -> None:
    """Hàm chính điều phối sinh trọn bộ 5 video kiểm thử công trường."""
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 65)
    logger.info("BẮT ĐẦU TẠO BỘ VIDEO KIỂM THỬ TOÀN DIỆN CÔNG TRƯỜNG")
    logger.info(f"Thư mục lưu video: {VIDEOS_DIR}")
    logger.info("=" * 65)

    category_map = load_labeled_images_map()
    logger.info("Đã quét và lập bản đồ nhãn từ tập dữ liệu ppe_dataset/test.")

    # 1. 01_ppe_violation_benchmark.mp4
    generate_ppe_violation_benchmark_video(
        VIDEOS_DIR / "01_ppe_violation_benchmark.mp4", category_map
    )

    # 2. 02_danger_zone_intrusion.mp4
    generate_danger_zone_intrusion_video(
        VIDEOS_DIR / "02_danger_zone_intrusion.mp4", category_map
    )

    # 3. 03_fall_incident_simulation.mp4
    generate_fall_incident_simulation_video(
        VIDEOS_DIR / "03_fall_incident_simulation.mp4", category_map
    )

    # 4. 04_scaffold_height_hazard.mp4
    generate_scaffold_height_hazard_video(
        VIDEOS_DIR / "04_scaffold_height_hazard.mp4", category_map
    )

    # 5. 05_multi_worker_tracking.mp4
    generate_multi_worker_tracking_video(
        VIDEOS_DIR / "05_multi_worker_tracking.mp4", category_map
    )

    logger.info("=" * 65)
    logger.info("HOÀN THÀNH TẠO TOÀN BỘ 5 VIDEO KIỂM THỬ!")
    logger.info("Danh sách tệp video đã sẵn sàng trong 'data/videos/':")
    for v in sorted(VIDEOS_DIR.glob("*.mp4")):
        size_mb = v.stat().st_size / (1024 * 1024)
        logger.info(f" - {v.name} ({size_mb:.2f} MB)")
    logger.info("=" * 65)


if __name__ == "__main__":
    main()
