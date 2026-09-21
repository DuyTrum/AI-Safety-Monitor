"""Standalone Demo Script for Open-Vocabulary Safety Relation Reasoning.

Thử nghiệm và trực quan hóa mô hình suy luận quan hệ thị giác (RelateAnything)
kết hợp cùng YOLO11 trên Ảnh, Thư mục ảnh, Video tệp hoặc Webcam thời gian thực:
- Tự động phát hiện các thực thể công trường (Người, Xe cơ giới, Giàn giáo, Trang bị PPE).
- Trích xuất và suy luận các bộ ba quan hệ (Subject - Predicate - Object).
- Đánh dấu mức độ rủi ro an toàn lao động và xuất video/ảnh trực quan sang thư mục runs/relations/.
"""

import argparse
import logging
import os
import sys
import time
from typing import List, Optional, Tuple, Union

import cv2
import numpy as np
from ultralytics import YOLO

# Đảm bảo đường dẫn gốc của dự án có trong sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.modules.relation_engine import SafetyRelationEngine, SafetyRelationTriplet
from src.utils.text_utils import strip_accents

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("DemoRelations")


def process_single_frame(
    frame: np.ndarray,
    yolo_model: YOLO,
    relation_engine: SafetyRelationEngine,
    conf_threshold: float = 0.25,
) -> Tuple[np.ndarray, List[SafetyRelationTriplet]]:
    """Xử lý một khung hình: suy luận YOLO11, trích xuất quan hệ và vẽ trực quan hóa.

    Args:
        frame: Khung hình OpenCV BGR.
        yolo_model: Mô hình YOLO11.
        relation_engine: Bộ máy SafetyRelationEngine.
        conf_threshold: Ngưỡng tin cậy của YOLO.

    Returns:
        Tuple[np.ndarray, List[SafetyRelationTriplet]]: (Khung hình đã vẽ, Danh sách bộ ba quan hệ).
    """
    results = yolo_model(frame, conf=conf_threshold, verbose=False)
    detections: List[Tuple[int, Tuple[int, int, int, int], str, float]] = []

    if results and len(results) > 0:
        boxes = results[0].boxes
        for idx, box in enumerate(boxes):
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            conf = float(box.conf[0])
            cls_id = int(box.cls[0])
            cls_name = yolo_model.names[cls_id]
            detections.append((idx + 1, (x1, y1, x2, y2), cls_name, conf))

    # Suy luận quan hệ
    triplets = relation_engine.infer_safety_relations(frame, detections)

    out_frame = frame.copy()
    # Vẽ bounding box
    for det_id, (x1, y1, x2, y2), cname, cconf in detections:
        color = (0, 0, 255) if cname.startswith("no-") else (0, 255, 0)
        cv2.rectangle(out_frame, (x1, y1), (x2, y2), color, 2)
        label = strip_accents(f"#{det_id} {cname} {cconf:.2f}")
        cv2.putText(
            out_frame, label, (x1, max(15, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA
        )

    # Vẽ liên kết quan hệ (mũi tên + nhãn HUD)
    out_frame = relation_engine.draw_relations_on_frame(out_frame, triplets)

    return out_frame, triplets


def run_relation_inference_on_video(
    video_source: Union[int, str],
    yolo_model: YOLO,
    relation_engine: SafetyRelationEngine,
    output_dir: str,
    conf_threshold: float = 0.25,
    save: bool = True,
    show: bool = False,
    max_frames: Optional[int] = None,
) -> None:
    """Chạy suy luận quan hệ an toàn trên Video hoặc Webcam thời gian thực.

    Args:
        video_source: Đường dẫn video, RTSP URL hoặc index Webcam (0, 1).
        yolo_model: Mô hình YOLO11.
        relation_engine: Bộ máy SafetyRelationEngine.
        output_dir: Thư mục lưu video kết quả.
        conf_threshold: Ngưỡng tin cậy của YOLO.
        save: Cờ lưu video mp4 ra đĩa.
        show: Cờ hiển thị cửa sổ xem trực tiếp qua OpenCV GUI.
        max_frames: Số lượng frame tối đa cần xử lý (None: toàn bộ).
    """
    cap = cv2.VideoCapture(video_source)
    if not cap.isOpened():
        logger.error(f"Không thể mở luồng video hoặc webcam từ: {video_source}")
        return

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) if isinstance(video_source, str) and os.path.isfile(video_source) else -1

    logger.info(
        f"Bắt đầu xử lý Video: Độ phân giải {width}x{height}, FPS: {fps:.1f}, "
        f"Tổng frames: {total_frames if total_frames > 0 else 'Live Stream'}"
    )

    writer = None
    if save:
        os.makedirs(output_dir, exist_ok=True)
        out_name = "webcam_relation_out.mp4" if isinstance(video_source, int) else f"rel_{os.path.basename(str(video_source))}"
        out_path = os.path.join(output_dir, out_name)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(out_path, fourcc, fps, (width, height))
        logger.info(f"Video kết quả sẽ được ghi vào: {out_path}")

    frame_idx = 0
    total_triplets = 0
    total_hazards = 0
    t_start = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_idx += 1
            if max_frames and frame_idx > max_frames:
                break

            t0 = time.time()
            out_frame, triplets = process_single_frame(
                frame=frame,
                yolo_model=yolo_model,
                relation_engine=relation_engine,
                conf_threshold=conf_threshold,
            )
            t_infer = time.time() - t0
            cur_fps = 1.0 / max(0.001, t_infer)

            # Vẽ HUD thông số hiệu năng góc trên
            hud_text = strip_accents(
                f"FPS: {cur_fps:.1f} | Frame #{frame_idx} | Relations: {len(triplets)} | Hazards: {sum(1 for t in triplets if t.is_hazard)}"
            )
            cv2.rectangle(out_frame, (10, 10), (450, 40), (20, 20, 20), -1)
            cv2.rectangle(out_frame, (10, 10), (450, 40), (0, 255, 255), 1)
            cv2.putText(out_frame, hud_text, (18, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)

            total_triplets += len(triplets)
            total_hazards += sum(1 for t in triplets if t.is_hazard)

            if writer is not None:
                writer.write(out_frame)

            if show:
                cv2.imshow("Safety Relation Reasoning - Live Stream", out_frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    logger.info("Người dùng bấm 'q' để dừng luồng.")
                    break

            if frame_idx % 30 == 0:
                logger.info(
                    f"Đã xử lý {frame_idx} frames | Tốc độ: {cur_fps:.1f} FPS | "
                    f"Quan hệ nguy hiểm tích lũy: {total_hazards}"
                )

    finally:
        cap.release()
        if writer is not None:
            writer.release()
        if show:
            cv2.destroyAllWindows()

    total_time = time.time() - t_start
    avg_fps = frame_idx / max(0.001, total_time)
    logger.info("=" * 60)
    logger.info(f"HOÀN TẤT XỬ LÝ VIDEO TRONG {total_time:.2f} GIÂY ({frame_idx} FRAMES, AVG {avg_fps:.1f} FPS).")
    logger.info(f"Tổng số quan hệ đã phân tích: {total_triplets}")
    logger.info(f"Tổng số cảnh báo nguy hiểm: {total_hazards}")
    logger.info("=" * 60)


def run_relation_inference_on_image(
    image_path: str,
    yolo_model: YOLO,
    relation_engine: SafetyRelationEngine,
    output_dir: str,
    conf_threshold: float = 0.25,
    save: bool = True,
) -> List[SafetyRelationTriplet]:
    """Chạy phát hiện đối tượng và suy luận quan hệ thị giác trên một ảnh."""
    frame = cv2.imread(image_path)
    if frame is None:
        logger.error(f"Không thể đọc ảnh từ: {image_path}")
        return []

    out_frame, triplets = process_single_frame(
        frame=frame,
        yolo_model=yolo_model,
        relation_engine=relation_engine,
        conf_threshold=conf_threshold,
    )

    logger.info(f"[{os.path.basename(image_path)}] Trích xuất được {len(triplets)} bộ ba quan hệ.")
    for t in triplets:
        haz_flag = "🚨 [NGUY HIỂM]" if t.is_hazard else "🟢 [AN TOÀN]"
        logger.info(
            f"   {haz_flag} #{t.subject_id} ({t.subject_label}) --[{t.predicate.upper()}]--> "
            f"#{t.object_id} ({t.object_label}) [Độ tin cậy: {t.confidence:.2f}]"
        )
        if t.hazard_description:
            logger.info(f"      -> {t.hazard_description}")

    if save:
        os.makedirs(output_dir, exist_ok=True)
        out_filename = f"rel_{os.path.basename(image_path)}"
        out_path = os.path.join(output_dir, out_filename)
        cv2.imwrite(out_path, out_frame)
        logger.info(f"Đã lưu ảnh trực quan quan hệ tại: {out_path}")

    return triplets


def parse_args() -> argparse.Namespace:
    """Xử lý đối số dòng lệnh CLI."""
    parser = argparse.ArgumentParser(
        description="Demo suy luận quan hệ thị giác an toàn lao động với RelateAnything & YOLO11."
    )
    parser.add_argument(
        "--source",
        type=str,
        default="data/sample_images",
        help="Nguồn dữ liệu: Tệp ảnh, thư mục ảnh, tệp video (.mp4/.avi) hoặc '0' cho Webcam máy tính.",
    )
    parser.add_argument(
        "--yolo-weights",
        type=str,
        default="weights/best.pt",
        help="Đường dẫn tới trọng số YOLO11 (mặc định: weights/best.pt hoặc yolo11s.pt).",
    )
    parser.add_argument(
        "--rel-model",
        type=str,
        default="maelic/relsgg-vits16",
        help="Tên mô hình RelateAnything trên Hugging Face (mặc định: maelic/relsgg-vits16).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="runs/relations",
        help="Thư mục xuất ảnh/video kết quả (mặc định: runs/relations).",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.25,
        help="Ngưỡng tin cậy phát hiện YOLO.",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Thiết bị suy luận ('cuda' hoặc 'cpu'). Tự động phát hiện nếu bỏ trống.",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        default=True,
        help="Ghi kết quả ra tệp ảnh hoặc video.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        default=False,
        help="Hiển thị cửa sổ GUI xem trực tiếp video/webcam bằng OpenCV.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Giới hạn số frame cần xử lý khi chạy video hoặc webcam.",
    )
    return parser.parse_args()


def main() -> None:
    """Hàm chạy chính của chương trình CLI demo."""
    args = parse_args()

    # Nạp mô hình YOLO
    yolo_path = args.yolo_weights
    if not os.path.exists(yolo_path):
        if os.path.exists("yolo11s.pt"):
            yolo_path = "yolo11s.pt"
        else:
            logger.warning(f"Không tìm thấy {yolo_path}. Ultralytics sẽ tải yolo11s.pt.")
            yolo_path = "yolo11s.pt"

    logger.info(f"Đang tải mô hình YOLO từ: {yolo_path}...")
    yolo_model = YOLO(yolo_path)

    # Nạp SafetyRelationEngine
    logger.info("Đang khởi tạo SafetyRelationEngine (RelateAnything)...")
    relation_engine = SafetyRelationEngine(
        model_name=args.rel_model,
        device=args.device,
    )
    logger.info(
        f"Chế độ hoạt động của RelationEngine: "
        f"{'Deep Learning (RelateAnything)' if relation_engine.is_deep_learning_active else 'Spatial-Semantic Fallback'}"
    )

    source = args.source

    # Trường hợp 1: Webcam (ví dụ: --source 0)
    if source.isdigit():
        webcam_idx = int(source)
        logger.info(f"Khởi chạy trên Webcam ID #{webcam_idx}...")
        run_relation_inference_on_video(
            video_source=webcam_idx,
            yolo_model=yolo_model,
            relation_engine=relation_engine,
            output_dir=args.output_dir,
            conf_threshold=args.conf,
            save=args.save,
            show=args.show,
            max_frames=args.max_frames,
        )
        return

    # Trường hợp 2: Tệp Video hoặc luồng RTSP
    video_extensions = (".mp4", ".avi", ".mov", ".mkv", ".flv", ".webm")
    if source.startswith("rtsp://") or source.lower().endswith(video_extensions):
        logger.info(f"Khởi chạy trên tệp Video / Luồng RTSP: {source}...")
        run_relation_inference_on_video(
            video_source=source,
            yolo_model=yolo_model,
            relation_engine=relation_engine,
            output_dir=args.output_dir,
            conf_threshold=args.conf,
            save=args.save,
            show=args.show,
            max_frames=args.max_frames,
        )
        return

    # Trường hợp 3: Ảnh đơn hoặc thư mục ảnh
    image_paths: List[str] = []
    if os.path.isfile(source):
        image_paths.append(source)
    elif os.path.isdir(source):
        for fname in os.listdir(source):
            if fname.lower().endswith((".jpg", ".jpeg", ".png", ".bmp")):
                image_paths.append(os.path.join(source, fname))
    else:
        logger.error(f"Nguồn dữ liệu không hợp lệ: {source}")
        return

    if not image_paths:
        logger.warning(f"Không tìm thấy ảnh nào trong: {source}")
        return

    logger.info(f"Tìm thấy {len(image_paths)} ảnh cần xử lý.")
    total_triplets = 0
    total_hazards = 0

    start_time = time.time()
    for img_path in image_paths:
        triplets = run_relation_inference_on_image(
            image_path=img_path,
            yolo_model=yolo_model,
            relation_engine=relation_engine,
            output_dir=args.output_dir,
            conf_threshold=args.conf,
            save=args.save,
        )
        total_triplets += len(triplets)
        total_hazards += sum(1 for t in triplets if t.is_hazard)

    elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info(f"HOÀN THÀNH XỬ LÝ {len(image_paths)} ẢNH TRONG {elapsed:.2f} GIÂY.")
    logger.info(f"Tổng số quan hệ phát hiện: {total_triplets}")
    logger.info(f"Tổng số quan hệ nguy hiểm cảnh báo: {total_hazards}")
    logger.info(f"Kết quả ảnh trực quan được lưu tại: {os.path.abspath(args.output_dir)}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
