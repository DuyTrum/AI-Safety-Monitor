"""Notification dispatching module.

Hỗ trợ gửi thông báo tự động (Telegram Bot, Webhook)
kèm hình ảnh snapshot vi phạm an toàn lao động tới quản lý.
"""

import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
import requests

logger = logging.getLogger("Notifier")

# Cấu hình cài đặt thông báo (mặc định đọc từ configs/settings.json)
CONFIG_FILE = os.path.abspath("configs/settings.json")


def load_notification_config() -> Dict[str, Any]:
    """Đọc cấu hình thông báo và quy định giám sát an toàn từ file JSON settings.

    Returns:
        Dict[str, Any]: Từ điển cấu hình cài đặt thông báo.
    """
    default_config: Dict[str, Any] = {
        "telegram_enabled": False,
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "webhook_enabled": False,
        "webhook_url": "",
        "snapshot_cooldown": 15,
        "notify_violations": ["no-helmet", "no-vest", "no-gloves", "no-boots", "no-goggles"],
        "active_rules": {
            "helmet": True,
            "vest": True,
            "boots": False,
            "gloves": False,
            "goggles": False,
        },
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
    """Lưu cấu hình thông báo vào file JSON settings.

    Args:
        config_data: Từ điển dữ liệu cấu hình cần lưu.

    Returns:
        bool: True nếu lưu thành công, ngược lại False.
    """
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


def _send_telegram_sync(
    token: str, chat_id: str, message: str, image_path: Optional[str] = None
) -> Tuple[bool, str]:
    """Gửi tin nhắn Telegram đồng bộ.

    Args:
        token: Bot token Telegram.
        chat_id: ID nhóm/kênh/người dùng nhận tin nhắn.
        message: Nội dung tin nhắn định dạng HTML.
        image_path: Đường dẫn ảnh đính kèm (nếu có).

    Returns:
        Tuple[bool, str]: (Thành công hay không, Thông báo kết quả / lỗi chi tiết).
    """
    if not token or not chat_id:
        return False, "Thiếu Bot Token hoặc Chat ID."

    token = token.strip()
    chat_id = chat_id.strip()

    try:
        if image_path and os.path.exists(image_path) and os.path.getsize(image_path) > 0:
            url = f"https://api.telegram.org/bot{token}/sendPhoto"
            with open(image_path, "rb") as photo:
                payload = {
                    "chat_id": chat_id,
                    "caption": message,
                    "parse_mode": "HTML",
                }
                files = {"photo": photo}
                resp = requests.post(url, data=payload, files=files, timeout=12)
        else:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
            }
            resp = requests.post(url, data=payload, timeout=12)

        if resp.status_code == 200:
            logger.info("Đã gửi thông báo Telegram thành công!")
            return True, "Gửi thông báo Telegram thành công!"
        else:
            try:
                err_data = resp.json()
                err_desc = err_data.get("description", resp.text)
            except Exception:
                err_desc = resp.text
            logger.error(f"Gửi Telegram thất bại (Mã {resp.status_code}): {err_desc}")
            return False, f"Telegram API lỗi ({resp.status_code}): {err_desc}"
    except requests.exceptions.Timeout:
        logger.error("Hết thời gian chờ kết nối tới Telegram API (Timeout).")
        return False, "Hết thời gian chờ kết nối tới Telegram API (Timeout)."
    except Exception as e:
        logger.error(f"Lỗi khi gửi tin nhắn qua Telegram: {e}")
        return False, f"Lỗi kết nối Telegram: {str(e)}"


def send_test_telegram(
    token: Optional[str] = None, chat_id: Optional[str] = None
) -> Tuple[bool, str]:
    """Gửi tin nhắn kiểm tra kết nối Telegram Bot.

    Args:
        token: Bot Token (nếu không truyền sẽ lấy từ cấu hình đã lưu).
        chat_id: Chat ID (nếu không truyền sẽ lấy từ cấu hình đã lưu).

    Returns:
        Tuple[bool, str]: (Thành công hay không, Thông báo kết quả).
    """
    if not token or not chat_id:
        cfg = load_notification_config()
        token = token or cfg.get("telegram_bot_token", "")
        chat_id = chat_id or cfg.get("telegram_chat_id", "")

    if not token or not chat_id:
        return False, "Vui lòng nhập đầy đủ Telegram Bot Token và Chat ID!"

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    msg = (
        "🔔 <b>AI SAFETY MONITOR - KIỂM TRA KẾT NỐI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ <b>Trạng thái:</b> Kết nối Telegram Bot thành công!\n"
        f"⏰ <b>Thời gian:</b> <code>{now_str}</code>\n"
        "🏢 <b>Hệ thống:</b> AI Safety Monitor (YOLO11s Real-time)\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "👉 <i>Hệ thống đã sẵn sàng gửi cảnh báo vi phạm PPE tự động kèm ảnh chụp camera!</i>"
    )

    return _send_telegram_sync(token, chat_id, msg)


def _send_webhook_sync(webhook_url: str, payload: Dict[str, Any]) -> Tuple[bool, str]:
    """Gửi Webhook đồng bộ (chạy trong background thread).

    Args:
        webhook_url: URL Webhook đích.
        payload: Dữ liệu JSON cảnh báo.

    Returns:
        Tuple[bool, str]: (Thành công hay không, Thông báo kết quả).
    """
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code in (200, 201, 202, 204):
            logger.info("Đã gửi Webhook cảnh báo thành công!")
            return True, "Đã gửi Webhook thành công!"
        else:
            logger.error(f"Gửi Webhook thất bại. Status code: {resp.status_code}")
            return False, f"Webhook trả về lỗi mã {resp.status_code}"
    except Exception as e:
        logger.error(f"Lỗi khi gửi Webhook: {e}")
        return False, f"Lỗi gửi Webhook: {str(e)}"


async def send_violation_alert(
    violation_type: str,
    confidence: float,
    snapshot_path: Optional[str] = None,
    track_id: Optional[int] = None,
) -> None:
    """Gửi cảnh báo vi phạm qua Telegram / Webhook bất đồng bộ.

    Args:
        violation_type: Loại vi phạm (vd: no-helmet).
        confidence: Độ tin cậy (0.0 - 1.0).
        snapshot_path: Đường dẫn tới file ảnh snapshot vi phạm.
        track_id: ID theo dõi đối tượng (ByteTrack).
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
        "no-goggles": "⚠️ KHÔNG ĐEO KÍNH BẢO HỘ",
    }
    violation_title = labels_map.get(violation_type, f"🚨 VI PHẠM: {violation_type.upper()}")
    track_str = f"\n🔹 <b>Đối tượng:</b> #{track_id}" if track_id is not None else ""
    time_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    message = (
        "⚠️ <b>CẢNH BÁO AN TOÀN LAO ĐỘNG</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>Hành vi:</b> {violation_title}\n"
        f"🎯 <b>Độ tin cậy:</b> <code>{confidence * 100:.1f}%</code>{track_str}\n"
        f"⏰ <b>Thời gian:</b> <code>{time_str}</code>\n"
        "🏢 <b>Hệ thống:</b> AI Safety Monitor (YOLO11s)\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "👉 <i>Vui lòng kiểm tra và nhắc nhở nhân sự tại công trường!</i>"
    )

    # Chạy gửi thông báo trong thread riêng để không block asyncio event loop
    loop = asyncio.get_event_loop()

    if (
        config.get("telegram_enabled")
        and config.get("telegram_bot_token")
        and config.get("telegram_chat_id")
    ):
        loop.run_in_executor(
            None,
            _send_telegram_sync,
            config["telegram_bot_token"],
            config["telegram_chat_id"],
            message,
            snapshot_path,
        )

    if config.get("webhook_enabled") and config.get("webhook_url"):
        webhook_payload = {
            "event": "SAFETY_VIOLATION",
            "type": violation_type,
            "confidence": confidence,
            "track_id": track_id,
            "timestamp": datetime.now().isoformat(),
            "snapshot_url": snapshot_path,
        }
        loop.run_in_executor(
            None,
            _send_webhook_sync,
            config["webhook_url"],
            webhook_payload,
        )
