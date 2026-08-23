"""Notification dispatching module.

Hỗ trợ gửi thông báo tự động (Telegram Bot, Webhook, Email)
kèm hình ảnh snapshot vi phạm an toàn lao động tới quản lý.
"""

import os
import json
import logging
import requests
import asyncio
from typing import Dict, Any, Optional

logger = logging.getLogger("Notifier")

# Cấu hình cài đặt thông báo (mặc định đọc từ configs/settings.json)
CONFIG_FILE = os.path.abspath("configs/settings.json")


def load_notification_config() -> Dict[str, Any]:
    """Đọc cấu hình thông báo và quy định giám sát an toàn từ file JSON settings."""
    default_config = {
        "telegram_enabled": False,
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "webhook_enabled": False,
        "webhook_url": "",
        "notify_violations": ["no-helmet", "no-vest", "no-gloves", "no-boots", "no-goggles"],
        "active_rules": {
            "helmet": True,
            "vest": True,
            "boots": False,
            "gloves": False,
            "goggles": False
        }
    }
    if not os.path.exists(CONFIG_FILE):
        return default_config
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            loaded = {**default_config, **data.get("notifications", {})}
            # Đảm bảo active_rules luôn đủ các key
            if "active_rules" not in loaded or not isinstance(loaded["active_rules"], dict):
                loaded["active_rules"] = default_config["active_rules"]
            else:
                loaded["active_rules"] = {**default_config["active_rules"], **loaded["active_rules"]}
            return loaded
    except Exception as e:
        logger.error(f"Lỗi khi đọc file cấu hình notification: {e}")
        return default_config


def save_notification_config(config_data: Dict[str, Any]) -> bool:
    """Lưu cấu hình thông báo vào file JSON settings."""
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        existing = {}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        
        existing["notifications"] = config_data
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        logger.info("Đã cập nhật cấu hình thông báo mới thành công.")
        return True
    except Exception as e:
        logger.error(f"Lỗi khi lưu cấu hình notification: {e}")
        return False


def _send_telegram_sync(token: str, chat_id: str, message: str, image_path: Optional[str] = None) -> bool:
    """Gửi tin nhắn Telegram đồng bộ (chạy trong background thread)."""
    try:
        if image_path and os.path.exists(image_path):
            url = f"https://api.telegram.org/bot{token}/sendPhoto"
            with open(image_path, "rb") as photo:
                payload = {
                    "chat_id": chat_id,
                    "caption": message,
                    "parse_mode": "Markdown"
                }
                files = {"photo": photo}
                resp = requests.post(url, data=payload, files=files, timeout=10)
        else:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            resp = requests.post(url, data=payload, timeout=10)

        if resp.status_code == 200:
            logger.info("Đã gửi cảnh báo Telegram thành công!")
            return True
        else:
            logger.error(f"Gửi Telegram thất bại. Status code: {resp.status_code}, Response: {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Lỗi khi gửi cảnh báo qua Telegram: {e}")
        return False


def _send_webhook_sync(webhook_url: str, payload: Dict[str, Any]) -> bool:
    """Gửi Webhook đồng bộ (chạy trong background thread)."""
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code in (200, 201, 202, 204):
            logger.info("Đã gửi Webhook cảnh báo thành công!")
            return True
        else:
            logger.error(f"Gửi Webhook thất bại. Status code: {resp.status_code}")
            return False
    except Exception as e:
        logger.error(f"Lỗi khi gửi Webhook: {e}")
        return False


async def send_violation_alert(
    violation_type: str,
    confidence: float,
    snapshot_path: Optional[str] = None,
    track_id: Optional[int] = None
) -> None:
    """Gửi cảnh báo vi phạm qua Telegram / Webhook bất đồng bộ.

    Args:
        violation_type: Loại vi phạm (vd: no-helmet).
        confidence: Độ tin cậy (0.0 - 1.0).
        snapshot_path: Đường dẫn tới file ảnh snapshot vi phạm.
        track_id: ID theo dõi đối tượng.
    """
    config = load_notification_config()
    
    # Kiểm tra xem loại vi phạm này có trong danh sách cần thông báo không
    notify_list = config.get("notify_violations", [])
    if notify_list and violation_type not in notify_list:
        return

    # Tên tiếng Việt hiển thị
    labels_map = {
        "no-helmet": "🚨 KHÔNG ĐỘI MŨ BẢO HỘ",
        "no-vest": "🚨 KHÔNG MẶC ÁO PHẢN QUANG",
        "no-gloves": "⚠️ KHÔNG ĐEO GĂNG TAY",
        "no-boots": "⚠️ KHÔNG ĐI ỦNG BẢO HỘ",
        "no-goggles": "⚠️ KHÔNG ĐEO KÍNH BẢO HỘ"
    }
    violation_title = labels_map.get(violation_type, f"🚨 VI PHẠM: {violation_type.upper()}")
    track_str = f"\n🔹 *Đối tượng*: #{track_id}" if track_id is not None else ""

    message = (
        f"⚠️ *CẢNH BÁO AN TOÀN LAO ĐỘNG*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📌 *Hành vi*: {violation_title}\n"
        f"🎯 *Độ tin cậy*: `{confidence * 100:.1f}%`{track_str}\n"
        f"⏰ *Thời gian*: `{requests.utils.quote(time.strftime('%Y-%m-%d %H:%M:%S'))}`\n"
        f"🏢 *Hệ thống*: AI Safety Monitor (YOLO11s)\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👉 _Vui lòng kiểm tra và nhắc nhở nhân sự tại công trường!_"
    )

    # Chạy gửi thông báo trong thread riêng để không block event loop
    loop = asyncio.get_event_loop()

    if config.get("telegram_enabled") and config.get("telegram_bot_token") and config.get("telegram_chat_id"):
        loop.run_in_executor(
            None,
            _send_telegram_sync,
            config["telegram_bot_token"],
            config["telegram_chat_id"],
            message,
            snapshot_path
        )

    if config.get("webhook_enabled") and config.get("webhook_url"):
        webhook_payload = {
            "event": "SAFETY_VIOLATION",
            "type": violation_type,
            "confidence": confidence,
            "track_id": track_id,
            "timestamp": time.time(),
            "snapshot_url": snapshot_path
        }
        loop.run_in_executor(
            None,
            _send_webhook_sync,
            config["webhook_url"],
            webhook_payload
        )
