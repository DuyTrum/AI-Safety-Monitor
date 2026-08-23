"""Violation report generator module.

Hỗ trợ trích xuất báo cáo vi phạm an toàn lao động theo định dạng Excel (.xlsx) / CSV
với các bộ lọc thời gian (Hôm nay, Tuần này, Tháng này, Toàn bộ).
"""

import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd

logger = logging.getLogger("ReportGenerator")

REPORTS_DIR = os.path.abspath("data/reports")


def ensure_reports_dir() -> str:
    """Đảm bảo thư mục lưu báo cáo tồn tại."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    return REPORTS_DIR


def generate_violation_report(
    violations_data: List[Dict[str, Any]],
    stats_data: Dict[str, Any],
    period: str = "today",
    file_format: str = "excel"
) -> Dict[str, str]:
    """Tạo báo cáo vi phạm an toàn dưới dạng Excel hoặc CSV.

    Args:
        violations_data: Danh sách các dict vi phạm từ Database (id, timestamp, type, confidence, snapshot_url).
        stats_data: Thống kê tổng quan từ Database.
        period: Thời gian lọc ('today', 'week', 'month', 'all').
        file_format: Định dạng tệp ('excel' hoặc 'csv').

    Returns:
        Dict chứa 'file_path' và 'filename'.
    """
    ensure_reports_dir()
    now = datetime.now()
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")

    # Map nhãn hiển thị tiếng Việt
    violation_labels = {
        "no-helmet": "Không đội mũ bảo hộ",
        "no-vest": "Không mặc áo phản quang",
        "no-gloves": "Không đeo găng tay",
        "no-boots": "Không đi ủng bảo hộ",
        "no-goggles": "Không đeo kính bảo hộ"
    }

    # Lọc dữ liệu theo period
    filtered_list = []
    for item in violations_data:
        try:
            item_dt = datetime.fromisoformat(str(item["timestamp"]).replace("Z", "+00:00"))
        except Exception:
            item_dt = now

        if period == "today" and item_dt.date() != now.date():
            continue
        elif period == "week" and (now - item_dt).days > 7:
            continue
        elif period == "month" and (now - item_dt).days > 30:
            continue

        filtered_list.append({
            "Mã sự kiện": item.get("id", ""),
            "Thời gian vi phạm": item_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "Loại vi phạm (Mã)": item.get("type", ""),
            "Tên vi phạm": violation_labels.get(item.get("type", ""), item.get("type", "")),
            "Độ tin cậy (%)": round(float(item.get("confidence", 0)) * 100, 1),
            "Ảnh snapshot": item.get("snapshot_url", "N/A")
        })

    df_details = pd.DataFrame(filtered_list)

    if file_format == "csv":
        filename = f"baocao_vipham_{period}_{timestamp_str}.csv"
        file_path = os.path.join(REPORTS_DIR, filename)
        df_details.to_csv(file_path, index=False, encoding="utf-8-sig")
        logger.info(f"Đã xuất báo cáo CSV: {file_path}")
        return {"file_path": file_path, "filename": filename}

    # Export Excel (.xlsx)
    filename = f"baocao_vipham_{period}_{timestamp_str}.xlsx"
    file_path = os.path.join(REPORTS_DIR, filename)

    try:
        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            # Sheet 1: Tổng quan Thống kê
            summary_info = [
                {"Chỉ số": "Ngày xuất báo cáo", "Giá trị": now.strftime("%Y-%m-%d %H:%M:%S")},
                {"Chỉ số": "Kỳ báo cáo", "Giá trị": period.upper()},
                {"Chỉ số": "Tổng số vi phạm trong kỳ", "Giá trị": len(filtered_list)},
                {"Chỉ số": "Tỷ lệ tuân thủ hiện tại", "Giá trị": f"{stats_data.get('compliance_rate', 100)}%"},
                {"Chỉ số": "Tổng số vi phạm tích lũy", "Giá trị": stats_data.get("total_violations", 0)}
            ]
            df_summary = pd.DataFrame(summary_info)
            df_summary.to_excel(writer, sheet_name="Tổng Quan", index=False)

            # Sheet 2: Danh sách chi tiết vi phạm
            df_details.to_excel(writer, sheet_name="Chi Tiết Vi Phạm", index=False)

            # Sheet 3: Phân bổ theo loại lỗi
            class_counts = []
            for code, name in violation_labels.items():
                count = sum(1 for item in filtered_list if item["Loại vi phạm (Mã)"] == code)
                class_counts.append({"Mã lỗi": code, "Tên lỗi vi phạm": name, "Số lượng": count})
            df_class = pd.DataFrame(class_counts)
            df_class.to_excel(writer, sheet_name="Thống Kê Theo Lỗi", index=False)

        logger.info(f"Đã xuất báo cáo Excel thành công: {file_path}")
        return {"file_path": file_path, "filename": filename}
    except Exception as e:
        # Fallback to CSV if openpyxl fails or isn't installed
        logger.warning(f"Xuất Excel không khả dụng ({e}), chuyển sang định dạng CSV.")
        filename_csv = f"baocao_vipham_{period}_{timestamp_str}.csv"
        file_path_csv = os.path.join(REPORTS_DIR, filename_csv)
        df_details.to_csv(file_path_csv, index=False, encoding="utf-8-sig")
        return {"file_path": file_path_csv, "filename": filename_csv}
