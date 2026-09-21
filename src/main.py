import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
import numpy as np
import json
import time
import uuid
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
from src.modules.zone_manager import ZoneManager, SafetyZone, ZoneType, ZoneSeverity
from src.modules.pose_engine import PoseEngine, PoseAnalysisResult
from src.modules.scaffold_harness_monitor import ScaffoldHarnessMonitor, HeightViolationType
from src.modules.risk_predictor import RiskPredictor, RiskLevel
from src.modules.physics_simulator import PhysicsSimulator, DroppedObjectSimulation, GhostFallSimulation
from src.modules.whatif_auditor import WhatIfAuditor, WhatIfScenario
from src.modules.relation_engine import SafetyRelationEngine, SafetyRelationTriplet, RelationHazardSeverity
from src.utils.text_utils import strip_accents

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

UNSAFE_CLASSES = {
    "no-boots", "no-gloves", "no-goggles", "no-helmet", "no-vest",
    "fall_detected", "zone_intrusion", "on_scaffold_no_harness", "on_scaffold_unhooked", "tool_drop_hazard"
}
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

# Khởi tạo các module an toàn mở rộng (Geofencing, Pose, Scaffold, Risk Engine, Physics Simulation, What-If Auditor, Relation Reasoning)
zone_manager = ZoneManager("configs/zones.json")
pose_engine = PoseEngine(model_path="yolo11n-pose.pt")
scaffold_monitor = ScaffoldHarnessMonitor()
risk_predictor = RiskPredictor()
physics_simulator = PhysicsSimulator()
relation_engine = SafetyRelationEngine()

initial_cfg = load_notification_config()
whatif_auditor = WhatIfAuditor(
    gemini_api_key=initial_cfg.get("gemini_api_key", os.getenv("GEMINI_API_KEY", ""))
)

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
    gemini_api_key: str = ""
    vlm_provider: str = "offline_expert"
    snapshot_cooldown: int = 15
    notify_violations: List[str] = [
        "no-helmet", "no-vest", "no-gloves", "no-boots", "no-goggles",
        "fall_detected", "zone_intrusion", "on_scaffold_no_harness", "on_scaffold_unhooked", "tool_drop_hazard"
    ]
    active_rules: Dict[str, bool] = {
        "helmet": True,
        "vest": True,
        "boots": False,
        "gloves": False,
        "goggles": False
    }
    advanced_features: Dict[str, bool] = {
        "danger_zones_enabled": True,
        "fall_detection_enabled": True,
        "scaffold_harness_enabled": True,
        "risk_prediction_enabled": True,
        "physics_simulation_enabled": True,
        "drop_cone_enabled": True,
        "ghost_fall_enabled": True,
        "relation_reasoning_enabled": True,
    }

class ZoneModel(BaseModel):
    zone_id: str
    name: str
    zone_type: str = "restricted_access"
    points: List[List[int]]
    severity: str = "danger"
    is_active: bool = True
    penalty_score: float = 75.0

class WhatIfRequest(BaseModel):
    violation_type: str
    context_data: Optional[Dict[str, Any]] = None
    image_base64: Optional[str] = None

class SimulationConfigModel(BaseModel):
    physics_simulation_enabled: Optional[bool] = None
    drop_cone_enabled: Optional[bool] = None
    ghost_fall_enabled: Optional[bool] = None
    gemini_api_key: Optional[str] = None
    vlm_provider: Optional[str] = None

class RelationVocabularyModel(BaseModel):
    vocabulary: List[str]

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
        event_id = f"evt_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
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


# API Quản lý Video Kiểm Thử (Test Video Management)
@app.get("/api/videos")
def list_available_videos():
    """Liệt kê toàn bộ các video kiểm thử có sẵn trong thư mục data/videos/."""
    videos_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "videos"))
    if not os.path.exists(videos_dir):
        return {"status": "success", "videos": []}

    video_files = sorted(
        [os.path.join(videos_dir, f) for f in os.listdir(videos_dir) if f.lower().endswith((".mp4", ".avi", ".mov"))]
    )
    result = []
    for vf in video_files:
        fname = os.path.basename(vf)
        size_mb = round(os.path.getsize(vf) / (1024 * 1024), 2)
        rel_path = f"data/videos/{fname}"

        # Đặt tên nhãn mô tả thân thiện hiển thị trên giao diện người dùng
        if fname == "real_ppe_site_01.mp4":
            label = "🎥 Thực tế: Công Nhân Công Trường Đầy Đủ PPE (11s)"
        elif fname == "real_ppe_site_02.mp4":
            label = "🎥 Thực tế: Công Nhân Vi Phạm Không Áo / Kính (8s)"
        elif fname == "real_ppe_site_03.mp4":
            label = "🎥 Thực tế: Nhóm Công Nhân Di Chuyển Trên Sàn (12s)"
        elif fname == "real_construction_site_raw_01.mp4":
            label = "🎥 Thực tế: Thi Công Cắt Thép & Máy Móc Công Trường (65s)"
        elif fname == "real_construction_scaffold_raw.mp4":
            label = "🎥 Thực tế: Công Nhân Làm Việc Trên Giàn Giáo (12s)"
        elif fname == "real_fall_incident.mp4":
            label = "⚠️ Thực tế: Sự Cố Trượt Ngã Trên Công Trường (5s)"
        elif fname == "worker_zone_detection.mp4":
            label = "🎥 Thực tế: Giám Sát Vùng Thi Công HD (76s)"
        else:
            label = fname

        result.append({
            "filename": fname,
            "label": label,
            "path": rel_path,
            "size_mb": size_mb,
        })

    return {"status": "success", "videos": result}


# API Quản lý Vùng Nguy hiểm Ảo (Geofencing Zones) & Đánh giá Rủi ro
@app.get("/api/zones")
def get_zones():
    """Lấy danh sách các vùng nguy hiểm đang được cấu hình."""
    return {"status": "success", "zones": [z.to_dict() for z in zone_manager.list_zones()]}


@app.post("/api/zones")
def add_or_update_zone(zone_req: ZoneModel):
    """Thêm hoặc cập nhật một vùng nguy hiểm ảo."""
    data = zone_req.dict()
    new_zone = SafetyZone.from_dict(data)
    zone_manager.add_zone(new_zone)
    zone_manager.save_to_file("configs/zones.json")
    return {"status": "success", "zone": new_zone.to_dict()}


@app.delete("/api/zones/{zone_id}")
def delete_zone(zone_id: str):
    """Xóa một vùng nguy hiểm ảo."""
    removed = zone_manager.remove_zone(zone_id)
    if removed:
        zone_manager.save_to_file("configs/zones.json")
        return {"status": "success", "message": f"Đã xóa vùng {zone_id}"}
    return {"status": "error", "message": "Không tìm thấy vùng cần xóa"}


@app.get("/api/risk/summary")
def get_risk_summary():
    """Lấy báo cáo tổng hợp các tính năng an toàn dự đoán."""
    return {
        "status": "success",
        "active_zones_count": len([z for z in zone_manager.list_zones() if z.is_active]),
        "features": {
            "pose_estimation": pose_engine.model is not None,
            "danger_geofencing": True,
            "scaffold_monitoring": True,
            "predictive_wri": True,
            "physics_simulation": True,
            "what_if_auditor": True,
        },
    }


# API Mô phỏng Tai nạn & Trợ lý What-If Safety Auditor
@app.post("/api/simulation/what-if")
def generate_what_if_scenario(req: WhatIfRequest):
    """Phân tích kịch bản tai nạn What-If (Offline Expert System hoặc Gemini VLM)."""
    try:
        scenario = whatif_auditor.generate_scenario(
            violation_type=req.violation_type,
            context_data=req.context_data,
            image_base64=req.image_base64,
        )
        return {"status": "success", "scenario": scenario.to_dict()}
    except Exception as e:
        logger.error(f"Lỗi phân tích kịch bản What-If: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/api/simulation/config")
def get_simulation_config():
    """Lấy thông tin cấu hình mô phỏng vật lý và VLM."""
    cfg = load_notification_config()
    adv = cfg.get("advanced_features", {})
    return {
        "physics_simulation_enabled": adv.get("physics_simulation_enabled", True),
        "drop_cone_enabled": adv.get("drop_cone_enabled", True),
        "ghost_fall_enabled": adv.get("ghost_fall_enabled", True),
        "vlm_provider": cfg.get("vlm_provider", "offline_expert"),
        "has_gemini_key": bool(whatif_auditor.gemini_api_key),
    }


@app.post("/api/simulation/config")
def update_simulation_config(sim_cfg: SimulationConfigModel):
    """Cập nhật tham số mô phỏng và khóa API Gemini."""
    cfg = load_notification_config()
    if "advanced_features" not in cfg:
        cfg["advanced_features"] = {}

    if sim_cfg.physics_simulation_enabled is not None:
        cfg["advanced_features"]["physics_simulation_enabled"] = sim_cfg.physics_simulation_enabled
        physics_simulator.is_enabled = sim_cfg.physics_simulation_enabled

    if sim_cfg.drop_cone_enabled is not None:
        cfg["advanced_features"]["drop_cone_enabled"] = sim_cfg.drop_cone_enabled

    if sim_cfg.ghost_fall_enabled is not None:
        cfg["advanced_features"]["ghost_fall_enabled"] = sim_cfg.ghost_fall_enabled

    if sim_cfg.gemini_api_key is not None:
        cfg["gemini_api_key"] = sim_cfg.gemini_api_key
        whatif_auditor.set_api_key(sim_cfg.gemini_api_key)

    if sim_cfg.vlm_provider is not None:
        cfg["vlm_provider"] = sim_cfg.vlm_provider

    success = save_notification_config(cfg)
    if success:
        return {"status": "success", "message": "Đã lưu cấu hình mô phỏng mới."}
    return {"status": "error", "message": "Lỗi lưu cấu hình mô phỏng."}


# API Quản lý Từ vựng Quan hệ Thị giác (Scene Graph Vocabulary)
@app.get("/api/relations/vocabulary")
def get_relation_vocabulary():
    """Lấy danh mục từ vựng quan hệ an toàn hiện tại."""
    return {
        "status": "success",
        "vocabulary": relation_engine.vocabulary,
        "is_deep_learning_active": relation_engine.is_deep_learning_active,
        "model_name": relation_engine.model_name,
        "device": relation_engine.device,
    }


@app.post("/api/relations/vocabulary")
def update_relation_vocabulary(data: RelationVocabularyModel):
    """Cập nhật từ vựng quan hệ an toàn tùy biến cho RelateAnything."""
    relation_engine.set_vocabulary(data.vocabulary)
    return {
        "status": "success",
        "message": "Đã cập nhật danh mục từ vựng quan hệ an toàn.",
        "vocabulary": relation_engine.vocabulary,
    }


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
    advanced_features: Optional[Dict[str, bool]] = None,
) -> tuple[cv2.Mat, List[str], Dict[str, bool], List[tuple[str, float, int, bool]], Dict[str, Any], Dict[str, Any]]:
    """Chạy suy luận YOLO11, ước lượng tư thế YOLO-Pose, kiểm soát vùng nguy hiểm và mô phỏng vật lý tai nạn.

    Args:
        frame: Ảnh gốc từ camera (OpenCV Mat).
        tracker: Bộ theo dõi đối tượng Spatial-Temporal RobustViolationTracker.
        active_rules: Dictionary cấu hình bật/tắt các quy định bảo hộ.
        advanced_features: Dictionary cấu hình bật/tắt các tính năng nâng cao.

    Returns:
        frame_out: Ảnh đã được vẽ bounding box, skeleton, zones, risk HUD và physics simulation.
        violations: Danh sách các lớp vi phạm phát hiện trong frame.
        current_detections: Trạng thái an toàn của từng loại trang bị.
        raw_violations: Danh sách tuple chứa (class_name, confidence, track_id, is_already_alerted).
        risk_summary: Báo cáo phân bố rủi ro an toàn lao động thời gian thực.
        simulation_summary: Dữ liệu mô phỏng vật lý nón rơi và bóng ma trượt ngã.
    """
    if active_rules is None:
        config = load_notification_config()
        active_rules = config.get("active_rules", {
            "helmet": True, "vest": True, "boots": False, "gloves": False, "goggles": False
        })

    if advanced_features is None:
        config = load_notification_config()
        advanced_features = config.get("advanced_features", {
            "danger_zones_enabled": True,
            "fall_detection_enabled": True,
            "scaffold_harness_enabled": True,
            "risk_prediction_enabled": True,
            "physics_simulation_enabled": True,
            "drop_cone_enabled": True,
            "ghost_fall_enabled": True,
            "relation_reasoning_enabled": True,
        })

    current_detections = {
        "helmet": False,
        "vest": False,
        "gloves": False,
        "boots": False,
        "goggles": False
    }

    default_risk_summary = {
        "total_tracked": 0,
        "safe_count": 0,
        "warning_count": 0,
        "danger_count": 0,
        "average_wri": 0.0,
        "assessments": [],
    }

    default_simulation_summary = {
        "physics_enabled": False,
        "drop_cones_count": 0,
        "ghost_falls_count": 0,
        "active_simulations": [],
    }

    if frame is None or frame.size == 0:
        return frame, [], current_detections, [], default_risk_summary, default_simulation_summary

    # 1. Vẽ các vùng nguy hiểm ảo (Geofencing Zones)
    if advanced_features.get("danger_zones_enabled", True):
        frame = zone_manager.draw_zones_on_frame(frame)

    # 2. Chạy YOLO11 phát hiện đối tượng trang bị bảo hộ (PPE)
    raw_detections = []
    if model is not None:
        try:
            results = model(frame, conf=0.25, verbose=False)
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
        except Exception as e:
            logger.error(f"Lỗi suy luận YOLO PPE: {e}")

    # 3. Cập nhật qua Spatial-Temporal Tracker để gán ID bền vững
    tracked_items = []
    if tracker is not None:
        tracked_items = tracker.update(raw_detections, timestamp=time.time())
    else:
        for idx, (bbox, cname, cconf) in enumerate(raw_detections):
            tracked_items.append((idx + 1, bbox, cname, cconf, False))

    violations = []
    raw_violations = []

    # 4. Phân tích tư thế và phát hiện Té ngã (YOLO11-Pose)
    pose_results = []
    if advanced_features.get("fall_detection_enabled", True) and pose_engine.model is not None:
        tracked_boxes = [(t[0], t[1]) for t in tracked_items]
        pose_results = pose_engine.analyze_frame(frame, tracked_person_bboxes=tracked_boxes)
        frame = pose_engine.draw_pose_on_frame(frame, pose_results)
        for pr in pose_results:
            if pr.is_fallen:
                tid = pr.track_id or 1
                violations.append("fall_detected")
                raw_violations.append(("fall_detected", pr.confidence, tid, False))

    # 5. Kiểm tra Xâm nhập Vùng nguy hiểm ảo
    if advanced_features.get("danger_zones_enabled", True):
        for track_id, (x1, y1, x2, y2), class_name, conf, is_alerted in tracked_items:
            intrusions = zone_manager.check_bbox_intrusion((x1, y1, x2, y2))
            if intrusions:
                violations.append("zone_intrusion")
                raw_violations.append(("zone_intrusion", 0.95, track_id, is_alerted))

    # 5.5. Phân tích Quan hệ Ngữ cảnh Thị giác (Scene Graph / RelateAnything)
    relation_triplets = []
    if advanced_features.get("relation_reasoning_enabled", True) and len(tracked_items) >= 2:
        detections_for_rel = [(t[0], t[1], t[2], t[3]) for t in tracked_items]
        relation_triplets = relation_engine.infer_safety_relations(frame, detections_for_rel)
        if relation_triplets:
            frame = relation_engine.draw_relations_on_frame(frame, relation_triplets)
            for trip in relation_triplets:
                if trip.is_hazard:
                    haz_type = f"relation_{trip.predicate.lower().replace(' ', '_')}"
                    violations.append(haz_type)
                    raw_violations.append((haz_type, trip.confidence, trip.subject_id, False))

    # 6. Giám sát An toàn Giàn giáo, Thang và Dây đai an toàn
    scaffold_statuses = []
    if advanced_features.get("scaffold_harness_enabled", True):
        scaffold_boxes = []
        for z in zone_manager.list_zones():
            if z.is_active and z.zone_type == ZoneType.SCAFFOLD_DROP_ZONE:
                pts = np.array(z.points)
                sx1, sy1 = int(pts[:, 0].min()), int(pts[:, 1].min())
                sx2, sy2 = int(pts[:, 0].max()), int(pts[:, 1].max())
                scaffold_boxes.append((1, (sx1, sy1, sx2, sy2)))

        for track_id, (x1, y1, x2, y2), class_name, conf, is_alerted in tracked_items:
            st = scaffold_monitor.evaluate_worker_height_safety(
                track_id, (x1, y1, x2, y2), [class_name], scaffold_boxes, relation_triplets=relation_triplets
            )
            scaffold_statuses.append(st)
            if st.violation_type:
                vtype = st.violation_type.value
                violations.append(vtype)
                raw_violations.append((vtype, 0.90, track_id, is_alerted))

    # 7. Vẽ Bounding Box cơ bản cho các trang bị PPE
    for track_id, (x1, y1, x2, y2), class_name, conf, is_alerted in tracked_items:
        base_rule = class_name.replace("no-", "")

        if class_name in UNSAFE_CLASSES:
            violations.append(class_name)
            raw_violations.append((class_name, conf, track_id, is_alerted))

            if is_alerted:
                color = (0, 140, 255)  # BGR Orange
                status_text = "DA BAO"
            else:
                color = COLORS["unsafe"]  # BGR Red
                status_text = "MOI"

            label = f"[ID #{track_id}] {class_name.upper()} ({status_text}) {conf:.2f}"
        else:
            color = COLORS["safe"]  # BGR Green
            label = f"[ID #{track_id}] {class_name} ({conf:.2f})"
            if base_rule in current_detections:
                current_detections[base_rule] = True

        label = strip_accents(label)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0]
        cv2.rectangle(frame, (x1, y1 - 22), (x1 + text_size[0] + 6, y1), color, -1)
        cv2.putText(frame, label, (x1 + 3, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

    # 8. Tính toán Chỉ số Rủi ro Công nhân Động (WRI) & Vẽ Risk HUD
    risk_assessments = []
    if advanced_features.get("risk_prediction_enabled", True):
        missing_by_track: Dict[int, List[str]] = {}
        for track_id, (x1, y1, x2, y2), class_name, conf, is_alerted in tracked_items:
            if class_name in UNSAFE_CLASSES:
                missing_by_track.setdefault(track_id, []).append(class_name)

        seen_tracks = set()
        for track_id, bbox, class_name, conf, is_alerted in tracked_items:
            if track_id in seen_tracks:
                continue
            seen_tracks.add(track_id)

            pr = next((p for p in pose_results if p.track_id == track_id), None)
            hs = next((s for s in scaffold_statuses if s.track_id == track_id), None)
            intrusions = zone_manager.check_bbox_intrusion(bbox)
            missing = missing_by_track.get(track_id, [])

            wri_res = risk_predictor.calculate_wri(
                track_id=track_id,
                worker_bbox=bbox,
                missing_ppe_items=missing,
                pose_result=pr,
                height_status=hs,
                intrusions=intrusions,
                zone_manager=zone_manager,
                relation_triplets=relation_triplets,
            )
            risk_assessments.append(wri_res)

        frame = risk_predictor.draw_risk_hud(frame, risk_assessments)

    risk_summary = {
        "total_tracked": len(risk_assessments),
        "safe_count": len([r for r in risk_assessments if r.risk_level == RiskLevel.SAFE]),
        "warning_count": len([r for r in risk_assessments if r.risk_level == RiskLevel.WARNING]),
        "danger_count": len([r for r in risk_assessments if r.risk_level == RiskLevel.DANGER]),
        "average_wri": round(
            sum(r.wri_score for r in risk_assessments) / max(1, len(risk_assessments)), 1
        ) if risk_assessments else 0.0,
        "assessments": [
            {
                "track_id": r.track_id,
                "wri": r.wri_score,
                "level": r.risk_level.value,
                "tags": r.active_hazard_tags,
                "recommendation": r.recommendation,
            }
            for r in risk_assessments
        ],
    }

    # 9. Mô phỏng Vật lý Tai nạn Thời gian thực (Drop Cone & Ghost Fall Trajectory)
    drop_simulations = []
    ghost_simulations = []
    if advanced_features.get("physics_simulation_enabled", True):
        all_worker_boxes = [(t[0], t[1]) for t in tracked_items]
        h_frame = frame.shape[0]

        # A. Chiếu Nón Nguy Hiểm Rơi (Hazard Drop Cone) nếu có công nhân trên cao hoặc cảnh báo vật rơi
        if advanced_features.get("drop_cone_enabled", True):
            for st in scaffold_statuses:
                if st.is_on_scaffold or st.violation_type:
                    wx1, wy1, wx2, wy2 = st.worker_bbox
                    sim_tool_box = (wx1, max(0, wy1 - 25), min(frame.shape[1], wx1 + 35), wy1)
                    drop_sim = physics_simulator.simulate_dropped_tool(
                        tool_bbox=sim_tool_box,
                        frame_height=h_frame,
                        tool_name="tool_generic",
                        worker_bboxes=all_worker_boxes,
                    )
                    drop_simulations.append(drop_sim)
                    break

        # B. Quét nguy cơ trượt ngã (Ghost Fall Trajectory)
        if advanced_features.get("ghost_fall_enabled", True):
            for pr in pose_results:
                if pr.is_bending_risk or pr.is_fallen or pr.torso_angle > 35.0:
                    ghost_sim = physics_simulator.simulate_worker_ghost_fall(
                        track_id=pr.track_id or 1,
                        worker_bbox=pr.bbox,
                        frame_height=h_frame,
                        fall_cause="POSTURE_LOSS" if not pr.is_fallen else "FALLEN_IMPACT",
                    )
                    ghost_simulations.append(ghost_sim)
                    break

        frame = physics_simulator.draw_physics_hud(frame, drop_simulations, ghost_simulations)

    simulation_summary = {
        "physics_enabled": advanced_features.get("physics_simulation_enabled", True),
        "drop_cones_count": len(drop_simulations),
        "ghost_falls_count": len(ghost_simulations),
        "active_simulations": [
            {
                "type": "drop_cone",
                "label": d.source_label,
                "height_m": d.estimated_height_m,
                "mass_kg": d.object_mass_kg,
                "impact_joules": d.impact_energy_joules,
                "velocity_kmh": d.impact_velocity_kmh,
                "severity": d.severity.value,
                "workers_at_risk": d.workers_at_risk,
            }
            for d in drop_simulations
        ] + [
            {
                "type": "ghost_fall",
                "track_id": g.track_id,
                "cause": g.fall_cause,
                "time_to_impact": g.time_to_impact_s,
                "impact_joules": g.simulated_impact_joules,
            }
            for g in ghost_simulations
        ],
    }

    # Hiển thị thông tin cảnh báo tổng quan góc trên bên trái
    if violations:
        violation_text = strip_accents(f"CANH BAO: {len(violations)} nguy co!")
        cv2.putText(frame, violation_text, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.75, COLORS["unsafe"], 2)
    else:
        cv2.putText(frame, "AN TOAN LAO DONG", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.75, COLORS["safe"], 2)

    return frame, violations, current_detections, raw_violations, risk_summary, simulation_summary


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
    elif source == "mock":
        video_source = "mock"
        logger.info("Khởi chạy luồng ảnh giả lập (Mock Stream).")
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
            loop_start = time.time()
            frame = None

            if cap is not None and cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    if isinstance(video_source, str):
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    else:
                        break

                # Nếu video gốc có tốc độ 60 FPS, bỏ qua 1 frame xen kẽ để phát chuẩn tốc độ 1x không bị chậm
                native_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                if native_fps > 45:
                    cap.grab()
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

            # Tối ưu kích thước khung hình: Resize về chiều rộng 720px để suy luận AI và truyền WebSocket cực nhanh (<15ms)
            h, w = frame.shape[:2]
            if w > 720:
                scale = 720.0 / w
                frame = cv2.resize(frame, (720, int(h * scale)), interpolation=cv2.INTER_AREA)

            current_config = load_notification_config()
            active_rules = current_config.get("active_rules", {
                "helmet": True, "vest": True, "boots": False, "gloves": False, "goggles": False
            })
            advanced_features = current_config.get("advanced_features", {
                "danger_zones_enabled": False,
                "fall_detection_enabled": True,
                "scaffold_harness_enabled": False,
                "risk_prediction_enabled": True,
            })

            # Xử lý khung hình với RobustViolationTracker và các module an toàn mở rộng
            frame_processed, violations, current_detections, raw_violations, risk_summary, simulation_summary = process_frame(
                frame, tracker=tracker, active_rules=active_rules, advanced_features=advanced_features
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

            # Nén ảnh thành định dạng JPG (chất lượng 70 giúp truyền mượt mà không chiếm băng thông)
            _, buffer = cv2.imencode(".jpg", frame_processed, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            jpg_as_text = base64.b64encode(buffer).decode("utf-8")

            # Gửi gói tin trạng thái cập nhật thời gian thực
            message = {
                "frame": f"data:image/jpeg;base64,{jpg_as_text}",
                "violations": violations,
                "current_detections": current_detections,
                "active_rules": active_rules,
                "advanced_features": advanced_features,
                "risk_summary": risk_summary,
                "simulation_summary": simulation_summary,
                "stats": db.get_stats()
            }
            await manager.send_json(message, websocket)
            
            # Tính toán độ trễ động (Dynamic delay) để luồng video phát mượt chuẩn thời gian thực (~30 FPS)
            loop_elapsed = time.time() - loop_start
            target_fps = 30.0
            sleep_needed = max(0.002, (1.0 / target_fps) - loop_elapsed)
            if cap is not None:
                await asyncio.sleep(sleep_needed)

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
