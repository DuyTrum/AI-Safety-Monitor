import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
import json
import time
import base64
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

import torch
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from ultralytics import YOLO

from src.utils.snapshot import save_violation_snapshot, SNAPSHOT_BASE_DIR
from src.utils.notifier import (
    send_violation_alert,
    load_notification_config,
    save_notification_config
)
from src.utils.reporter import generate_violation_report

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("SafetyMonitorBackend")

app = FastAPI(
    title="AI Safety Monitoring API",
    description="Backend API cho hệ thống giám sát an toàn lao động thời gian thực sử dụng YOLO11.",
    version="1.0.0"
)

# Cấu hình CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount thư mục phục vụ tải và hiển thị ảnh snapshot vi phạm
os.makedirs(SNAPSHOT_BASE_DIR, exist_ok=True)
app.mount("/static/snapshots", StaticFiles(directory=SNAPSHOT_BASE_DIR), name="snapshots")

# Định nghĩa các hằng số
MODEL_PATH = os.getenv("MODEL_PATH", "weights/best.pt")
VIOLATIONS_FILE = "runs/violations.json"

UNSAFE_CLASSES = {"no-boots", "no-gloves", "no-goggles", "no-helmet", "no-vest"}
SAFE_CLASSES = {"boots", "gloves", "goggles", "helmet", "vest"}

# Phân loại màu sắc (BGR)
COLORS = {
    "safe": (0, 255, 0),    # Xanh lá
    "unsafe": (0, 0, 255)   # Đỏ
}

# Tải mô hình YOLO
if not os.path.exists(MODEL_PATH):
    fallback_paths = [
        "weights/best.pt",
        "runs/detect/runs/detect/train_safety_150/weights/best.pt",
        "runs/detect/train_safety/weights/best.pt",
        "yolo11s.pt"
    ]
    for p in fallback_paths:
        if os.path.exists(p):
            MODEL_PATH = p
            break
    else:
        logger.warning(f"Không tìm thấy mô hình tại {MODEL_PATH}. Ultralytics sẽ tự động tải yolo11s.pt.")
        MODEL_PATH = "yolo11s.pt"

try:
    device = "0" if torch.cuda.is_available() else "cpu"
    model = YOLO(MODEL_PATH)
    logger.info(f"Đã tải thành công mô hình YOLO từ {MODEL_PATH} trên thiết bị {device}")
except Exception as e:
    logger.error(f"Lỗi tải mô hình YOLO: {e}")
    model = None

# Mô hình dữ liệu Pydantic
class ViolationEvent(BaseModel):
    id: str
    timestamp: str
    type: str
    confidence: float
    snapshot_url: Optional[str] = None

class SystemStats(BaseModel):
    total_violations: int
    compliance_rate: float
    alert_count: int
    violations_today: int
    class_stats: Dict[str, int]

class NotificationSettingsModel(BaseModel):
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    webhook_enabled: bool = False
    webhook_url: str = ""
    notify_violations: List[str] = ["no-helmet", "no-vest", "no-gloves", "no-boots", "no-goggles"]
    active_rules: Dict[str, bool] = {
        "helmet": True,
        "vest": True,
        "boots": False,
        "gloves": False,
        "goggles": False
    }

# Quản lý dữ liệu Vi phạm (Violations Database sử dụng PostgreSQL)
class ViolationDB:
    """Quản lý việc lưu trữ và thống kê lịch sử vi phạm (PostgreSQL + In-memory fallback)."""
    
    def __init__(self):
        self.db_url = os.getenv(
            "DATABASE_URL", 
            "postgresql://postgres:postgres@127.0.0.1:5433/safety_monitor"
        )
        self.use_db = False
        self.memory_violations: List[Dict[str, Any]] = []
        self._init_db()

    def _get_connection(self):
        """Tạo kết nối mới đến PostgreSQL."""
        return psycopg2.connect(self.db_url)

    def _init_db(self) -> None:
        """Khởi tạo cơ sở dữ liệu và tạo bảng nếu chưa tồn tại."""
        retries = 2
        conn = None
        while retries > 0:
            try:
                conn = self._get_connection()
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS violations (
                            id VARCHAR(50) PRIMARY KEY,
                            timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                            type VARCHAR(50) NOT NULL,
                            confidence REAL NOT NULL,
                            snapshot_url VARCHAR(255) DEFAULT ''
                        );
                    """)
                    cur.execute("""
                        ALTER TABLE violations ADD COLUMN IF NOT EXISTS snapshot_url VARCHAR(255) DEFAULT '';
                    """)
                    conn.commit()
                self.use_db = True
                logger.info("Đã kết nối và khởi tạo thành công CSDL PostgreSQL.")
                break
            except Exception:
                retries -= 1
                if retries > 0:
                    time.sleep(0.5)
            finally:
                if conn:
                    conn.close()
        
        if not self.use_db:
            logger.info("Chạy ở chế độ Standalone Dev: Tự động sử dụng bộ nhớ tạm (In-memory Storage Fallback).")

    def add_violation(self, violation_type: str, confidence: float, snapshot_url: str = "") -> Dict[str, Any]:
        """Thêm sự kiện vi phạm mới."""
        now = datetime.now()
        event_id = f"evt_{int(time.time() * 1000)}"
        event = {
            "id": event_id,
            "timestamp": now.isoformat(),
            "type": violation_type,
            "confidence": round(confidence, 2),
            "snapshot_url": snapshot_url
        }
        
        self.memory_violations.insert(0, event)
        if len(self.memory_violations) > 500:
            self.memory_violations.pop()

        if self.use_db:
            try:
                with self._get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO violations (id, timestamp, type, confidence, snapshot_url) VALUES (%s, %s, %s, %s, %s)",
                            (event_id, now, violation_type, confidence, snapshot_url)
                        )
                        conn.commit()
            except Exception as e:
                logger.error(f"Lỗi khi thêm vi phạm vào Postgres: {e}")
        return event

    def get_violations(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Lấy danh sách các sự kiện vi phạm gần nhất."""
        if self.use_db:
            try:
                with self._get_connection() as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute(
                            "SELECT id, timestamp, type, confidence, snapshot_url FROM violations ORDER BY timestamp DESC LIMIT %s",
                            (limit,)
                        )
                        rows = cur.fetchall()
                        results = []
                        for row in rows:
                            results.append({
                                "id": row["id"],
                                "timestamp": row["timestamp"].isoformat(),
                                "type": row["type"],
                                "confidence": round(float(row["confidence"]), 2),
                                "snapshot_url": row.get("snapshot_url", "") or ""
                            })
                        return results
            except Exception as e:
                logger.error(f"Lỗi khi đọc danh sách vi phạm từ Postgres: {e}")
        
        return self.memory_violations[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Tính toán thống kê hoạt động giám sát."""
        if self.use_db:
            try:
                with self._get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT COUNT(*) FROM violations")
                        total = cur.fetchone()[0]

                        cur.execute("SELECT type, COUNT(*) FROM violations GROUP BY type")
                        rows = cur.fetchall()
                        class_stats = {cls: 0 for cls in UNSAFE_CLASSES}
                        for v_type, count in rows:
                            if v_type in class_stats:
                                class_stats[v_type] = count

                        cur.execute("SELECT COUNT(*) FROM violations WHERE timestamp >= CURRENT_DATE")
                        violations_today = cur.fetchone()[0]

                compliance_rate = 100.0 if total == 0 else max(50.0, 100.0 - (total * 0.5))
                return {
                    "total_violations": total,
                    "compliance_rate": round(compliance_rate, 1),
                    "alert_count": violations_today,
                    "violations_today": violations_today,
                    "class_stats": class_stats
                }
            except Exception as e:
                logger.error(f"Lỗi khi lấy thống kê từ Postgres: {e}")

        total = len(self.memory_violations)
        class_stats = {cls: 0 for cls in UNSAFE_CLASSES}
        for item in self.memory_violations:
            if item["type"] in class_stats:
                class_stats[item["type"]] += 1
        
        compliance_rate = 100.0 if total == 0 else max(50.0, 100.0 - (total * 0.5))
        return {
            "total_violations": total,
            "compliance_rate": round(compliance_rate, 1),
            "alert_count": total,
            "violations_today": total,
            "class_stats": class_stats
        }

    def clear(self) -> None:
        """Xóa sạch lịch sử vi phạm."""
        self.memory_violations = []
        if self.use_db:
            try:
                with self._get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("TRUNCATE TABLE violations")
                        conn.commit()
            except Exception as e:
                logger.error(f"Lỗi khi xóa bảng violations: {e}")

db = ViolationDB()


# REST Endpoints
@app.get("/api/stats", response_model=SystemStats)
def get_stats():
    """Lấy dữ liệu thống kê giám sát an toàn lao động."""
    return db.get_stats()

@app.get("/api/violations", response_model=List[ViolationEvent])
def get_violations(limit: int = 50):
    """Lấy danh sách các sự kiện vi phạm gần nhất."""
    return db.get_violations(limit)

@app.delete("/api/violations")
def clear_violations():
    """Xóa toàn bộ lịch sử cảnh báo vi phạm."""
    db.clear()
    return {"status": "success", "message": "Đã xóa sạch lịch sử vi phạm."}

@app.get("/api/reports/export")
def export_report(period: str = "today", format: str = "excel"):
    """Xuất báo cáo vi phạm an toàn lao động ra tệp Excel (.xlsx) hoặc CSV."""
    violations = db.get_violations(limit=1000)
    stats = db.get_stats()
    result = generate_violation_report(violations, stats, period=period, file_format=format)
    file_path = result["file_path"]
    filename = result["filename"]

    if not os.path.exists(file_path):
        return {"error": "Không thể tạo tệp báo cáo"}

    media_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if format == "excel"
        else "text/csv"
    )
    return FileResponse(file_path, filename=filename, media_type=media_type)

@app.get("/api/settings/notifications", response_model=NotificationSettingsModel)
def get_notification_settings():
    """Lấy cấu hình thông báo hiện tại."""
    return load_notification_config()

@app.post("/api/settings/notifications")
def update_notification_settings(settings: NotificationSettingsModel):
    """Cập nhật cấu hình thông báo Telegram / Webhook."""
    success = save_notification_config(settings.dict())
    if success:
        return {"status": "success", "message": "Đã lưu cấu hình thông báo mới."}
    return {"status": "error", "message": "Lỗi khi lưu cấu hình."}


# Quản lý WebSocket Streams
class ConnectionManager:
    """Quản lý các kết nối WebSocket của máy khách."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("Máy khách đã kết nối WebSocket.")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info("Máy khách đã ngắt kết nối WebSocket.")

    async def send_json(self, message: Dict[str, Any], websocket: WebSocket):
        await websocket.send_json(message)

manager = ConnectionManager()


def process_frame(
    frame: cv2.Mat, use_tracking: bool = True, active_rules: Optional[Dict[str, bool]] = None
) -> tuple[cv2.Mat, List[str], Dict[str, bool], List[tuple[str, float, Optional[int]]]]:
    """Chạy suy luận YOLO11 (kèm ByteTrack tracking) trên khung hình và vẽ bounding box.
    
    Args:
        frame: Ảnh gốc từ camera (OpenCV Mat).
        use_tracking: Có sử dụng ByteTrack tracking hay không.
        active_rules: Dictionary cấu hình bật/tắt các quy định bảo hộ.
        
    Returns:
        frame_out: Ảnh đã được vẽ bounding box và cảnh báo.
        violations: Danh sách các lớp vi phạm phát hiện trong frame.
        current_detections: Trạng thái an toàn của từng loại trang bị.
        raw_violations: Danh sách tuple chứa (tên_lớp, độ_tin_cậy, track_id) của vi phạm.
    """
    if active_rules is None:
        config = load_notification_config()
        active_rules = config.get("active_rules", {
            "helmet": True, "vest": True, "boots": False, "gloves": False, "goggles": False
        })

    if model is None:
        return frame, [], {cls: False for cls in SAFE_CLASSES}, []

    # Chạy YOLO11 với Object Tracking (ByteTrack) nếu enabled
    try:
        if use_tracking:
            results = model.track(frame, conf=0.25, persist=True, verbose=False)
        else:
            results = model(frame, conf=0.25, verbose=False)
    except Exception as e:
        logger.warning(f"Không thể khởi chạy Object Tracking, dùng suy luận mặc định: {e}")
        results = model(frame, conf=0.25, verbose=False)

    violations = []
    raw_violations = []

    # Khởi tạo trạng thái phát hiện hiện tại
    current_detections = {
        "helmet": False,
        "vest": False,
        "gloves": False,
        "boots": False,
        "goggles": False
    }

    if not results:
        return frame, violations, current_detections, raw_violations

    result = results[0]
    boxes = result.boxes

    for box in boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        conf = float(box.conf[0])
        class_id = int(box.cls[0])
        class_name = model.names[class_id]

        track_id = None
        if hasattr(box, "id") and box.id is not None:
            try:
                track_id = int(box.id[0])
            except Exception:
                track_id = None

        # Phân loại an toàn vs vi phạm
        if class_name in UNSAFE_CLASSES:
            base_rule = class_name.replace("no-", "")
            # Lọc bỏ nếu quy định bảo hộ tương ứng đang TẮT
            if not active_rules.get(base_rule, True):
                continue

            color = COLORS["unsafe"]
            track_str = f" #{track_id}" if track_id is not None else ""
            label = f"VI PHAM: {class_name}{track_str} ({conf:.2f})"
            violations.append(class_name)
            raw_violations.append((class_name, conf, track_id))
        else:
            base_rule = class_name
            # Lọc bỏ nếu quy định bảo hộ tương ứng đang TẮT
            if not active_rules.get(base_rule, True):
                continue

            color = COLORS["safe"]
            track_str = f" #{track_id}" if track_id is not None else ""
            label = f"{class_name}{track_str} ({conf:.2f})"
            # Ghi nhận trạng thái an toàn
            if base_rule in current_detections:
                current_detections[base_rule] = True

        # Vẽ bounding box lên ảnh
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # Vẽ label background
        text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
        cv2.rectangle(frame, (x1, y1 - 20), (x1 + text_size[0], y1), color, -1)

        # Viết text label
        cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    # Hiển thị thông tin cảnh báo trực tiếp trên ảnh
    if violations:
        violation_text = f"CANH BAO: Phat hien {len(violations)} vi pham!"
        cv2.putText(frame, violation_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, COLORS["unsafe"], 2)
    else:
        cv2.putText(frame, "AN TOAN LAO DONG", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, COLORS["safe"], 2)

    return frame, violations, current_detections, raw_violations


@app.websocket("/api/ws/stream")
async def websocket_stream(websocket: WebSocket, source: str = "0"):
    """WebSocket endpoint truyền trực tiếp video/webcam đã qua xử lý YOLO.
    
    Args:
        websocket: Đối tượng kết nối WebSocket.
        source: Nguồn luồng. Mặc định "0" là camera laptop, có thể là đường dẫn video .mp4.
    """
    await manager.connect(websocket)
    
    # Xác định nguồn video đầu vào
    if source.isdigit():
        video_source = int(source)
        logger.info(f"Khởi chạy luồng từ Webcam ID: {video_source}")
    else:
        video_source = os.path.abspath(source)
        if not os.path.exists(video_source):
            # Nếu không tìm thấy tệp video cụ thể, thử tìm trong thư mục test images
            logger.warning(f"Không tìm thấy video: {video_source}. Sử dụng giả lập chuỗi ảnh test.")
            video_source = "mock"
        else:
            logger.info(f"Khởi chạy luồng từ video tệp: {video_source}")

    cap = None
    mock_images = []
    mock_idx = 0

    if video_source != "mock":
        if isinstance(video_source, int):
            # Trên Windows, sử dụng cv2.CAP_DSHOW giúp nhận diện camera USB/Laptop nhanh và ổn định hơn rất nhiều
            cap = cv2.VideoCapture(video_source, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap = cv2.VideoCapture(video_source)
        else:
            cap = cv2.VideoCapture(video_source)
            
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        else:
            logger.error(f"Không thể mở nguồn video/webcam: {video_source}")
    else:
        # Chuẩn bị dữ liệu mock bằng cách duyệt qua ảnh trong thư mục sample hoặc test
        candidate_dirs = [
            "data/sample_images",
            "data/ppe_dataset/test/images",
            "data/test/images"
        ]
        for cdir in candidate_dirs:
            if os.path.exists(cdir):
                found = [os.path.join(cdir, f) for f in os.listdir(cdir) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
                if found:
                    mock_images = found
                    logger.info(f"Đã nạp {len(mock_images)} ảnh giả lập từ '{cdir}' cho luồng WebSocket.")
                    break

    # Quản lý trạng thái vi phạm liên tục & ByteTrack để tránh lặp vi phạm khi 1 người đứng trong khung hình
    logged_track_violations: set = set()      # Set chứa các tuple (track_id, v_type) đã được ghi DB
    track_last_seen: Dict[int, float] = {}     # Thời điểm thấy track_id gần nhất

    active_type_counts: Dict[str, int] = {}    # Fallback: đếm số lượng vi phạm hiện tại từng loại
    last_type_seen: Dict[str, float] = {}

    TRACK_EXPIRATION_SECONDS = 5.0  # Hết hạn theo dõi nếu đối tượng rời khỏi khung hình > 5s
    TYPE_PERSISTENCE_SECONDS = 3.0  # Hết hạn vi phạm fallback nếu không thấy > 3s

    try:
        while True:
            frame = None
            
            if cap is not None and cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    # Nếu hết video, cuộn lại từ đầu (loop video)
                    if isinstance(video_source, str):
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    else:
                        break
            elif mock_images:
                # Đọc ảnh giả lập tuần hoàn
                img_path = mock_images[mock_idx % len(mock_images)]
                frame = cv2.imread(img_path)
                mock_idx += 1
                # Giả lập FPS cho luồng ảnh mock (~10 FPS để người dùng dễ xem)
                await asyncio.sleep(0.1)
            else:
                # Không có camera lẫn dữ liệu mock hoặc camera mở lỗi
                logger.error("Không tìm thấy nguồn video hay ảnh giả lập khả dụng.")
                await websocket.send_json({
                    "error": "Không thể kết nối tới Camera này. Vui lòng kiểm tra cổng cắm, đảm bảo camera không bị ứng dụng khác chiếm dụng, hoặc thử đổi Webcam ID khác (ID 1, ID 2)."
                })
                break

            if frame is None:
                await asyncio.sleep(0.01)
                continue

            # Read config dynamically per frame (or use loaded config)
            current_config = load_notification_config()
            active_rules = current_config.get("active_rules", {
                "helmet": True, "vest": True, "boots": False, "gloves": False, "goggles": False
            })

            # Xử lý khung hình với ByteTrack Tracking & Dynamic Active Rules
            frame_processed, violations, current_detections, raw_violations = process_frame(
                frame, use_tracking=True, active_rules=active_rules
            )

            current_time = time.time()

            # 1. Dọn dẹp các track_id cũ đã rời khỏi camera > 5s
            expired_tracks = [tid for tid, last_seen in track_last_seen.items() if (current_time - last_seen) > TRACK_EXPIRATION_SECONDS]
            for tid in expired_tracks:
                del track_last_seen[tid]
                logged_track_violations = {item for item in logged_track_violations if item[0] != tid}

            # 2. Xử lý ghi nhận vi phạm không bị lặp lại khi người vi phạm vẫn đứng ở khung hình
            current_frame_counts: Dict[str, int] = {}

            for v_type, v_conf, track_id in raw_violations:
                current_frame_counts[v_type] = current_frame_counts.get(v_type, 0) + 1

                if track_id is not None:
                    track_last_seen[track_id] = current_time
                    track_key = (track_id, v_type)
                    # Nếu đối tượng cụ thể (track_id) này CHƯA từng bị ghi nhận lỗi v_type
                    if track_key not in logged_track_violations:
                        # 1. Tự động lưu ảnh Snapshot vi phạm
                        snap_info = save_violation_snapshot(frame_processed, v_type, v_conf, track_id)
                        snap_url = snap_info.get("relative_url", "")
                        snap_file = snap_info.get("file_path", "")

                        # 2. Lưu thông tin vào CSDL
                        db.add_violation(v_type, v_conf, snap_url)
                        logged_track_violations.add(track_key)
                        logger.info(f"Đã ghi nhận sự kiện vi phạm mới (Đối tượng #{track_id}): {v_type} ({v_conf:.2f})")

                        # 3. Gửi thông báo tự động (Telegram / Webhook)
                        asyncio.create_task(send_violation_alert(v_type, v_conf, snap_file, track_id))
                else:
                    last_type_seen[v_type] = current_time

            # 3. Fallback xử lý khi không lấy được track_id (chỉ ghi nhận khi số lượng lỗi loại này tăng thêm)
            for v_type, count in current_frame_counts.items():
                if any(t_id is None for t, _, t_id in raw_violations if t == v_type):
                    prev_count = active_type_counts.get(v_type, 0)
                    if count > prev_count:
                        new_count = count - prev_count
                        for _ in range(new_count):
                            conf = next((c for t, c, tid in raw_violations if t == v_type and tid is None), 0.8)
                            snap_info = save_violation_snapshot(frame_processed, v_type, conf, None)
                            snap_url = snap_info.get("relative_url", "")
                            snap_file = snap_info.get("file_path", "")

                            db.add_violation(v_type, conf, snap_url)
                            logger.info(f"Đã ghi nhận sự kiện vi phạm mới (Fallback): {v_type} ({conf:.2f})")
                            asyncio.create_task(send_violation_alert(v_type, conf, snap_file, None))
                        active_type_counts[v_type] = count
                    else:
                        last_type_seen[v_type] = current_time

            # Dọn dẹp trạng thái fallback nếu vi phạm loại này biến mất quá 3s
            for v_type in list(active_type_counts.keys()):
                if v_type not in current_frame_counts:
                    if (current_time - last_type_seen.get(v_type, 0)) > TYPE_PERSISTENCE_SECONDS:
                        active_type_counts[v_type] = 0

            # Nén ảnh thành định dạng JPG
            _, buffer = cv2.imencode(".jpg", frame_processed, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            # Mã hóa Base64 để gửi qua JSON
            jpg_as_text = base64.b64encode(buffer).decode("utf-8")

            # Gửi gói tin trạng thái cập nhật thời gian thực
            message = {
                "frame": f"data:image/jpeg;base64,{jpg_as_text}",
                "violations": violations,
                "current_detections": current_detections,
                "active_rules": active_rules,
                "stats": db.get_stats()
            }
            await manager.send_json(message, websocket)
            
            # Khống chế FPS luồng truyền ở mức ~25-30 FPS để tránh ngập mạng (sleep ~33ms)
            if cap is not None:
                await asyncio.sleep(0.03)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Lỗi xảy ra trong luồng truyền WebSocket: {e}")
        manager.disconnect(websocket)
    finally:
        if cap is not None:
            cap.release()
            logger.info("Đã giải phóng OpenCV VideoCapture.")

# Import asyncio cho mock sleep ở luồng WebSocket
import asyncio

if __name__ == "__main__":
    import uvicorn
    # Mặc định chạy ở cổng 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
