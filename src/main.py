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
    send_test_telegram,
    load_notification_config,
    save_notification_config,
)
from src.utils.reporter import generate_violation_report
from src.utils.tracker import RobustViolationTracker

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
    snapshot_cooldown: int = 15
    notify_violations: List[str] = ["no-helmet", "no-vest", "no-gloves", "no-boots", "no-goggles"]
    active_rules: Dict[str, bool] = {
        "helmet": True,
        "vest": True,
        "boots": False,
        "gloves": False,
        "goggles": False
    }

class TelegramTestRequest(BaseModel):
    token: Optional[str] = None
    chat_id: Optional[str] = None

# Quản lý dữ liệu Vi phạm (Violations Database sử dụng PostgreSQL)
class ViolationDB:
    """Quản lý việc lưu trữ và thống kê lịch sử vi phạm (PostgreSQL + In-memory fallback)."""
    
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")
        self.candidate_urls = [
            self.db_url,
            "postgresql://postgres:postgres@127.0.0.1:5432/safety_monitor",
            "postgresql://postgres:postgres@127.0.0.1:5433/safety_monitor",
        ]
        self.candidate_urls = [u for u in self.candidate_urls if u]
        self.use_db = False
        self.memory_violations: List[Dict[str, Any]] = []
        self._init_db()

    def _get_connection(self):
        """Tạo kết nối mới đến PostgreSQL."""
        return psycopg2.connect(self.db_url, connect_timeout=3)

    def _init_db(self) -> None:
        """Khởi tạo cơ sở dữ liệu và tạo bảng nếu chưa tồn tại."""
        for target_url in self.candidate_urls:
            conn = None
            try:
                self.db_url = target_url
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
                logger.info(f"Đã kết nối và khởi tạo thành công CSDL PostgreSQL tại: {self.db_url}")
                break
            except Exception as e:
                logger.debug(f"Không thể kết nối đến {target_url}: {e}")
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

@app.post("/api/settings/notifications/test-telegram")
def test_telegram_notification(req: Optional[TelegramTestRequest] = None):
    """Kiểm tra kết nối và gửi tin nhắn thử nghiệm tới Telegram Bot."""
    token = req.token if req else None
    chat_id = req.chat_id if req else None
    success, message = send_test_telegram(token=token, chat_id=chat_id)
    if success:
        return {"status": "success", "message": message}
    return {"status": "error", "message": message}


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
    frame: cv2.Mat,
    tracker: Optional[RobustViolationTracker] = None,
    active_rules: Optional[Dict[str, bool]] = None,
) -> tuple[cv2.Mat, List[str], Dict[str, bool], List[tuple[str, float, int, bool]]]:
    """Chạy suy luận YOLO11 và theo dõi ID đối tượng bằng RobustViolationTracker.
    
    Args:
        frame: Ảnh gốc từ camera (OpenCV Mat).
        tracker: Bộ theo dõi đối tượng Spatial-Temporal RobustViolationTracker.
        active_rules: Dictionary cấu hình bật/tắt các quy định bảo hộ.
        
    Returns:
        frame_out: Ảnh đã được vẽ bounding box và cảnh báo.
        violations: Danh sách các lớp vi phạm phát hiện trong frame.
        current_detections: Trạng thái an toàn của từng loại trang bị.
        raw_violations: Danh sách tuple chứa (class_name, confidence, track_id, is_already_alerted).
    """
    if active_rules is None:
        config = load_notification_config()
        active_rules = config.get("active_rules", {
            "helmet": True, "vest": True, "boots": False, "gloves": False, "goggles": False
        })

    current_detections = {
        "helmet": False,
        "vest": False,
        "gloves": False,
        "boots": False,
        "goggles": False
    }

    if model is None or frame is None or frame.size == 0:
        return frame, [], current_detections, []

    # 1. Chạy YOLO11 phát hiện đối tượng
    try:
        results = model(frame, conf=0.25, verbose=False)
    except Exception as e:
        logger.error(f"Lỗi suy luận YOLO: {e}")
        return frame, [], current_detections, []

    raw_detections = []
    if results and len(results) > 0:
        boxes = results[0].boxes
        for box in boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            conf = float(box.conf[0])
            class_id = int(box.cls[0])
            class_name = model.names[class_id]

            # Kiểm tra quy định bảo hộ tương ứng có đang BẬT không
            base_rule = class_name.replace("no-", "")
            if not active_rules.get(base_rule, True):
                continue

            raw_detections.append(((x1, y1, x2, y2), class_name, conf))

    # 2. Cập nhật qua Spatial-Temporal Tracker để gán ID bền vững
    tracked_items = []
    if tracker is not None:
        tracked_items = tracker.update(raw_detections, timestamp=time.time())
    else:
        for idx, (bbox, cname, cconf) in enumerate(raw_detections):
            tracked_items.append((idx + 1, bbox, cname, cconf, False))

    violations = []
    raw_violations = []

    # 3. Vẽ Bounding Box trực quan
    for track_id, (x1, y1, x2, y2), class_name, conf, is_alerted in tracked_items:
        base_rule = class_name.replace("no-", "")

        if class_name in UNSAFE_CLASSES:
            violations.append(class_name)
            raw_violations.append((class_name, conf, track_id, is_alerted))

            if is_alerted:
                # Đã cảnh báo rồi: Viền cam đậm, ghi rõ [ID #X] VI PHAM (DA BAO)
                color = (0, 140, 255)  # BGR Orange
                status_text = "DA BAO"
            else:
                # Chưa cảnh báo: Viền đỏ rực, ghi rõ [ID #X] VI PHAM (MOI)
                color = COLORS["unsafe"]  # BGR Red
                status_text = "MOI"

            label = f"[ID #{track_id}] {class_name.upper()} ({status_text}) {conf:.2f}"
        else:
            # Trang bị an toàn
            color = COLORS["safe"]  # BGR Green
            label = f"[ID #{track_id}] {class_name} ({conf:.2f})"
            if base_rule in current_detections:
                current_detections[base_rule] = True

        # Vẽ hình chữ nhật bounding box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # Vẽ nền label
        text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0]
        cv2.rectangle(frame, (x1, y1 - 22), (x1 + text_size[0] + 6, y1), color, -1)

        # Viết text label
        cv2.putText(frame, label, (x1 + 3, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

    # Hiển thị thông tin cảnh báo tổng quan góc trên bên trái
    if violations:
        violation_text = f"CANH BAO: {len(violations)} vi pham!"
        cv2.putText(frame, violation_text, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.75, COLORS["unsafe"], 2)
    else:
        cv2.putText(frame, "AN TOAN LAO DONG", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.75, COLORS["safe"], 2)

    return frame, violations, current_detections, raw_violations


@app.websocket("/api/ws/stream")
async def websocket_stream(websocket: WebSocket, source: str = "0"):
    """WebSocket endpoint truyền trực tiếp video/webcam đã qua xử lý YOLO & RobustTracker.
    
    Args:
        websocket: Đối tượng kết nối WebSocket.
        source: Nguồn luồng. Mặc định "0" là camera laptop, có thể là đường dẫn video .mp4.
    """
    await manager.connect(websocket)
    
    # Tạo một instance RobustViolationTracker riêng biệt cho phiên stream này
    tracker = RobustViolationTracker(max_disappear_seconds=30.0)

    # Xác định nguồn video đầu vào
    if source.isdigit():
        video_source = int(source)
        logger.info(f"Khởi chạy luồng từ Webcam ID: {video_source}")
    else:
        video_source = os.path.abspath(source)
        if not os.path.exists(video_source):
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

    try:
        while True:
            frame = None
            
            if cap is not None and cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    if isinstance(video_source, str):
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    else:
                        break
            elif mock_images:
                # Đọc ảnh giả lập tuần hoàn với nhịp 1.5s mỗi ảnh để quan sát rõ ràng
                img_path = mock_images[mock_idx % len(mock_images)]
                frame = cv2.imread(img_path)
                mock_idx += 1
                await asyncio.sleep(1.5)
            else:
                logger.error("Không tìm thấy nguồn video hay ảnh giả lập khả dụng.")
                await websocket.send_json({
                    "error": "Không thể kết nối tới Camera này. Vui lòng kiểm tra cổng cắm hoặc đổi Webcam ID khác."
                })
                break

            if frame is None:
                await asyncio.sleep(0.01)
                continue

            current_config = load_notification_config()
            active_rules = current_config.get("active_rules", {
                "helmet": True, "vest": True, "boots": False, "gloves": False, "goggles": False
            })

            # Xử lý khung hình với RobustViolationTracker
            frame_processed, violations, current_detections, raw_violations = process_frame(
                frame, tracker=tracker, active_rules=active_rules
            )

            # 🔥 CHỈ CẢNH BÁO 1 LẦN DUY NHẤT CHO MỖI ID ĐỐI TƯỢNG
            unalerted_violations = [
                (v_type, conf, tid)
                for (v_type, conf, tid, is_alerted) in raw_violations
                if not is_alerted and not tracker.is_alerted(tid, v_type)
            ]

            if unalerted_violations:
                # 1. Lưu 1 snapshot duy nhất cho khung hình chứa các vi phạm mới
                first_v_type, first_conf, first_tid = unalerted_violations[0]
                snap_info = save_violation_snapshot(frame_processed, first_v_type, first_conf, first_tid)
                snap_url = snap_info.get("relative_url", "")
                snap_file = snap_info.get("file_path", "")

                for v_type, v_conf, tid in unalerted_violations:
                    # 2. Đánh dấu ngay lập tức rằng đối tượng ID này ĐÃ ĐƯỢC CẢNH BÁO
                    tracker.mark_alerted(tid, v_type)

                    # 3. Ghi vào CSDL vi phạm
                    db.add_violation(v_type, v_conf, snap_url)
                    logger.info(f"🚨 [CẢNH BÁO LẦN ĐẦU] Đối tượng ID #{tid} vi phạm {v_type} ({v_conf:.2f}). Đã chụp snapshot và gửi cảnh báo!")

                    # 4. Gửi thông báo Telegram (chỉ 1 lần duy nhất cho ID này)
                    asyncio.create_task(send_violation_alert(v_type, v_conf, snap_file, tid))

            # Nén ảnh thành định dạng JPG
            _, buffer = cv2.imencode(".jpg", frame_processed, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
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
