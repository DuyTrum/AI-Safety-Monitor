"""Multimodal 'What-If' Accident Scenario Simulation & Safety Auditor Module.

Module phân tích kịch bản tai nạn giả định ("What-If Safety Auditor"):
1. Xây dựng chuỗi nguyên nhân sự cố (Hazard Chain) và dự đoán hậu quả tiềm tàng.
2. Đánh giá động năng va đập, chấn thương mô phỏng và tiêu chuẩn an toàn (OSHA & QCVN 18:2021/BXD).
3. Đề xuất danh mục hành động khẩn cấp (Immediate Action Checklist) cho cán bộ HSE.
4. Hỗ trợ 2 chế độ vận hành:
   - Offline Expert System: Chạy ngoại tuyến tức thì với bộ tri thức an toàn công trường tích hợp sẵn.
   - Online Multimodal VLM: Kết nối Google Gemini API để phân tích ngữ cảnh hình ảnh thực tế.
"""

import json
import logging
import math
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger("WhatIfAuditor")


class ScenarioSeverity(str, Enum):
    """Mức độ nghiêm trọng của kịch bản tai nạn."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class HazardChainStep:
    """Một mắt xích trong chuỗi rủi ro tai nạn."""

    step: int
    title: str
    description: str
    time_offset: str  # Ví dụ: "0.0s", "+1.2s", "+2.5s"


@dataclass
class WhatIfScenario:
    """Kịch bản mô phỏng tai nạn giả định chi tiết."""

    scenario_id: str
    title: str
    hazard_type: str
    probability_pct: float
    probability_level: str
    severity_level: ScenarioSeverity
    root_cause_chain: List[HazardChainStep]
    simulated_consequences: List[str]
    impact_energy_joules: Optional[float]
    osha_standard: str
    immediate_actions: List[str]
    source_mode: str  # "OFFLINE_EXPERT_SYSTEM" | "ONLINE_MULTIMODAL_VLM"
    timestamp: str
    statistical_basis: str = field(
        default="Mô hình Logit FMEA chuẩn hóa theo tỷ suất nền OSHA Construction Fatal Four & đặc trưng đo lường từ hiện trường"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Chuyển đổi kịch bản thành Dictionary."""
        data = asdict(self)
        data["severity_level"] = self.severity_level.value
        return data


class WhatIfAuditor:
    """Chuyên gia an toàn AI phân tích kịch bản tai nạn giả định What-If."""

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        vlm_model_name: str = "gemini-2.5-flash",
    ) -> None:
        """Khởi tạo WhatIfAuditor.

        Args:
            gemini_api_key: Khóa API Google Gemini (tùy chọn).
            vlm_model_name: Tên mô hình VLM sử dụng khi có API key.
        """
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        self.vlm_model_name = vlm_model_name

    @staticmethod
    def calculate_dynamic_probability(
        violation_type: str,
        ctx: Optional[Dict[str, Any]] = None,
    ) -> Tuple[float, str, str]:
        """Tính toán xác suất tai nạn theo hàm Logit kết hợp tỷ suất nền OSHA và đặc trưng hiện trường.

        Công thức:
            P(Accident) = 1 / (1 + exp(-z))
            z = beta_0 + beta_height * phi(h) + beta_tilt * phi(theta) + beta_edge * phi(d_edge) + beta_speed * phi(v)

        Nền tảng dịch tễ học an toàn lao động (Ground Truth / Dataset Reference):
        - OSHA Fatal Four (Bureau of Labor Statistics): Ngã cao (Falls - 36.5%), Vật rơi (Struck-by - 15.4%),
          Kẹp/Nghiền nát (Caught-in - 7.3%), Điện giật (Electrocution - 7.2%).
        - Tỷ suất cơ sở (Base Log-Odds) được định chuẩn từ tần suất thống kê trên kết hợp các hệ số khuếch đại vật lý.

        Args:
            violation_type: Loại vi phạm.
            ctx: Ngữ cảnh trích xuất từ khung hình (độ cao h, góc nghiêng theta, khoảng cách mép, vận tốc v).

        Returns:
            probability_pct: Xác suất dự báo (%).
            level: Phân loại ("Rất cao", "Cao", "Trung bình", "Thấp").
            basis_description: Giải trình phương pháp luận tính toán.
        """
        ctx = ctx or {}
        v_norm = violation_type.lower()

        # Log-odds tỷ suất nền (OSHA Baseline Log-Odds)
        if "fall" in v_norm:
            base_z = 1.3  # Xác suất nền khi phát hiện tư thế ngã ~78.6%
        elif "tool" in v_norm or "drop" in v_norm:
            base_z = 1.0  # Vật dụng đặt mép cao ~73.1%
        elif "scaffold" in v_norm or "harness" in v_norm or "unhooked" in v_norm:
            base_z = 1.1  # Làm việc trên cao không neo ~75.0%
        elif "zone" in v_norm or "pit" in v_norm or "intrusion" in v_norm:
            base_z = 0.7  # Xâm nhập vùng nguy hiểm ~66.8%
        elif "no-helmet" in v_norm:
            base_z = 0.6  # Không đội mũ trong công trường ~64.5%
        else:
            base_z = 0.3  # Vi phạm bảo hộ thông thường ~57.4%

        # 1. Hệ số độ cao: h >= 2m (QCVN 18:2021 bắt buộc neo dây)
        height_m = float(ctx.get("height_m", 2.0))
        height_factor = min(1.8, max(0.0, (height_m - 2.0) * 0.22))

        # 2. Hệ số góc nghiêng cơ thể (Torso Tilt)
        torso_angle = float(ctx.get("torso_angle", 15.0))
        tilt_factor = min(1.4, max(0.0, (torso_angle - 25.0) * 0.04)) if torso_angle > 25.0 else -0.15

        # 3. Hệ số khoảng cách mép nguy hiểm (Distance to Hazard Edge)
        dist_edge_m = float(ctx.get("distance_to_edge_m", 1.5))
        edge_factor = 1.0 if dist_edge_m < 0.8 else (0.4 if dist_edge_m < 1.5 else -0.25)

        # 4. Hệ số vận tốc tiếp cận (Approach Speed)
        approach_speed = float(ctx.get("approach_speed_ms", 0.5))
        speed_factor = min(0.8, approach_speed * 0.35)

        z = base_z + height_factor + tilt_factor + edge_factor + speed_factor
        prob = 1.0 / (1.0 + math.exp(-z))
        prob_pct = round(prob * 100.0, 1)

        if prob_pct >= 85.0:
            level = "Rất cao (Nguy cấp)"
        elif prob_pct >= 70.0:
            level = "Cao"
        elif prob_pct >= 50.0:
            level = "Trung bình"
        else:
            level = "Thấp"

        basis_desc = (
            f"Mô hình Logit FMEA động (OSHA Fatal Four Base Odds + Tác nhân đo lường: "
            f"h={height_m:.1f}m, theta={torso_angle:.0f}°, d_edge={dist_edge_m:.1f}m)"
        )
        return prob_pct, level, basis_desc

    def set_api_key(self, api_key: str) -> None:
        """Cập nhật khóa API Gemini."""
        self.gemini_api_key = api_key.strip()

    def generate_scenario(
        self,
        violation_type: str,
        context_data: Optional[Dict[str, Any]] = None,
        image_base64: Optional[str] = None,
    ) -> WhatIfScenario:
        """Tạo kịch bản tai nạn What-If dựa trên vi phạm và ngữ cảnh.

        Tự động ưu tiên sử dụng VLM trực tuyến nếu có API key và ảnh;
        ngược lại tự động sử dụng Hệ chuyên gia an toàn lao động ngoại tuyến (Zero downtime).

        Args:
            violation_type: Tên mã vi phạm (vd: "no-helmet", "tool_drop_hazard", "fall_detected").
            context_data: Thông tin ngữ cảnh bổ sung (độ cao, khối lượng, ID công nhân, WRI).
            image_base64: Ảnh khung hình hiện trường dạng base64 (nếu có).

        Returns:
            WhatIfScenario: Kịch bản mô phỏng chi tiết.
        """
        ctx = context_data or {}

        # Nếu có API key và ảnh base64, thử chạy với Gemini VLM
        if self.gemini_api_key and image_base64:
            try:
                scenario = self._generate_vlm_scenario(violation_type, ctx, image_base64)
                if scenario:
                    return scenario
            except Exception as e:
                logger.warning(f"Lỗi khi gọi VLM trực tuyến: {e}. Tự động fallback sang Hệ chuyên gia ngoại tuyến.")

        # Mặc định sử dụng Hệ chuyên gia tri thức an toàn ngoại tuyến
        return self._generate_offline_expert_scenario(violation_type, ctx)

    def _generate_offline_expert_scenario(
        self,
        violation_type: str,
        ctx: Dict[str, Any],
    ) -> WhatIfScenario:
        """Sinh kịch bản bằng Hệ tri thức chuyên gia chuẩn OSHA 1926 & QCVN 18:2021/BXD kết hợp xác suất động."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        v_norm = violation_type.lower().strip()
        scen_id = f"whatif_{int(time.time() * 1000)}"

        # Tính toán xác suất động dựa trên hàm Logit FMEA và các đại lượng đo lường hiện trường
        prob_pct, prob_level, stat_basis = self.calculate_dynamic_probability(violation_type, ctx)

        # 1. KỊCH BẢN: RƠI DỤNG CỤ TỪ TRÊN CAO (TOOL DROP HAZARD)
        if "tool" in v_norm or "drop" in v_norm:
            height = ctx.get("height_m", 7.5)
            mass = ctx.get("mass_kg", 1.5)
            joules = round(mass * 9.8 * height, 1)

            return WhatIfScenario(
                scenario_id=scen_id,
                title="Sự cố Rơi Dụng Cụ Lao Động Từ Giàn Giáo Cao Độ",
                hazard_type=violation_type,
                probability_pct=prob_pct,
                probability_level=prob_level,
                severity_level=ScenarioSeverity.CRITICAL,
                impact_energy_joules=joules,
                osha_standard="OSHA 1926.451(h) & QCVN 18:2021/BXD Mục 2.6.4 (Bảo vệ chống vật rơi)",
                root_cause_chain=[
                    HazardChainStep(
                        step=1,
                        title="Vật dụng đặt sát mép sàn",
                        description=f"Dụng cụ {mass}kg được đặt chênh vênh ở độ cao {height}m, không gắn dây buộc cổ tay (Tool Lanyard).",
                        time_offset="0.0s",
                    ),
                    HazardChainStep(
                        step=2,
                        title="Rung chấn cơ học hoặc vô ý gạt chân",
                        description="Công nhân thao tác làm rung sàn thao tác, khiến dụng cụ mất thăng bằng và trượt khỏi mép giàn giáo.",
                        time_offset="+0.6s",
                    ),
                    HazardChainStep(
                        step=3,
                        title="Rơi tự do theo gia tốc trọng trường",
                        description=f"Dụng cụ đạt vận tốc {int((2 * 9.8 * height) ** 0.5 * 3.6)} km/h khi chạm đất với bán kính tản nón 2.2m.",
                        time_offset=f"+{round((2 * height / 9.8) ** 0.5, 1)}s",
                    ),
                    HazardChainStep(
                        step=4,
                        title="Va chạm trực diện vào công nhân bên dưới",
                        description=f"Động năng va đập {joules} Joules giáng xuống đầu/vai của người đứng trong vùng chân giàn giáo.",
                        time_offset="Thời điểm va chạm",
                    ),
                ],
                simulated_consequences=[
                    f"Động năng va đập cực lớn: {joules} Joules (Ngưỡng gây nứt xương sọ là ~50 Joules).",
                    "Nếu công nhân bên dưới không đội mũ bảo hộ: Chấn thương sọ não hở, nguy cơ tử vong tức thì.",
                    "Nếu có đội mũ bảo hộ: Mũ có thể vỡ nứt, gây chấn động đốt sống cổ và chấn thương vai nghiêm trọng.",
                ],
                immediate_actions=[
                    "🔴 Thiết lập rào chắn và biển cảnh báo 'VÙNG NGUY HIỂM VẬT RƠI' dưới chân giàn giáo ngay lập tức.",
                    "🟡 Bắt buộc lắp tấm chắn chân giàn giáo (Toe-board) cao tối thiểu 150mm và lưới hứng vật rơi (Debris Net).",
                    "🟢 Trang bị túi đựng dụng cụ chuyên dụng và dây buộc chống rơi (Tool Lanyards) cho tất cả công nhân làm việc trên cao.",
                ],
                source_mode="OFFLINE_EXPERT_SYSTEM",
                timestamp=now_str,
                statistical_basis=stat_basis,
            )

        # 2. KỊCH BẢN: TRÊN GIÀN GIÁO KHÔNG CÓ DÂY AN TOÀN HOẶC CHƯA MÓC CHỐT NEO
        elif "scaffold" in v_norm or "harness" in v_norm or "unhooked" in v_norm:
            return WhatIfScenario(
                scenario_id=scen_id,
                title="Nguy cơ Rơi Ngã Từ Trên Cao Do Không Neo Dây An Toàn",
                hazard_type=violation_type,
                probability_pct=prob_pct,
                probability_level=prob_level,
                severity_level=ScenarioSeverity.CRITICAL,
                impact_energy_joules=3400.0,
                osha_standard="OSHA 1926.501(b)(1) & QCVN 18:2021/BXD Mục 2.2 (An toàn làm việc trên cao)",
                root_cause_chain=[
                    HazardChainStep(
                        step=1,
                        title="Thao tác trên cao không có điểm neo giữ",
                        description="Công nhân làm việc trên sàn giàn giáo độ cao > 2m mà không móc dây đai toàn thân vào dây cứu sinh (Lifeline).",
                        time_offset="0.0s",
                    ),
                    HazardChainStep(
                        step=2,
                        title="Mất thăng bằng do với tầm với hoặc gió lốc",
                        description="Khi thực hiện thao tác vươn người hoặc gặp cơn gió giật, trọng tâm cơ thể lệch ra ngoài lan can bảo vệ.",
                        time_offset="+0.8s",
                    ),
                    HazardChainStep(
                        step=3,
                        title="Rơi ngã tự do không có cơ chế giảm chấn",
                        description="Không có cuộn dây hãm rơi tự động (Fall Arrester), công nhân rơi trực diện xuống sàn bê tông.",
                        time_offset="+1.3s",
                    ),
                ],
                simulated_consequences=[
                    "Va đập toàn thân với năng lượng trên 3,000 Joules.",
                    "Gãy xương đa chấn thương, tổn thương tủy sống hoặc tử vong tại chỗ.",
                    "Dừng thi công toàn bộ phân khu dự án để điều tra tai nạn lao động nghiêm trọng.",
                ],
                immediate_actions=[
                    "🔴 Yêu cầu công nhân dừng ngay thao tác và móc khóa an toàn vào dầm kết cấu/dây cứu sinh độc lập.",
                    "🟡 Kiểm tra lắp đặt đầy đủ lan can 2 tầng (Top rail 1.1m, Mid rail 0.6m) trên sàn thao tác giàn giáo.",
                    "🟢 Cán bộ an toàn lập biên bản đình chỉ nếu phát hiện cố tình không tuân thủ quy tắc 100% Tie-Off.",
                ],
                source_mode="OFFLINE_EXPERT_SYSTEM",
                timestamp=now_str,
                statistical_basis=stat_basis,
            )

        # 3. KỊCH BẢN: TÉ NGÃ / BẤT ĐỘNG TẠI HIỆN TRƯỜNG (FALL DETECTED)
        elif "fall" in v_norm:
            return WhatIfScenario(
                scenario_id=scen_id,
                title="Sự Cố Té Ngã Bất Động / Sốc Nhiệt / Tai Nạn Khẩn Cấp",
                hazard_type=violation_type,
                probability_pct=prob_pct,
                probability_level=prob_level,
                severity_level=ScenarioSeverity.CRITICAL,
                impact_energy_joules=None,
                osha_standard="OSHA 1926.50 & QCVN 18:2021/BXD Mục 1.4 (Sơ cấp cứu y tế công trường)",
                root_cause_chain=[
                    HazardChainStep(
                        step=1,
                        title="Mất khả năng vận động tư thế đứng",
                        description="AI Pose phát hiện góc thân mình song song mặt đất và nằm bất động quá thời gian cho phép.",
                        time_offset="0.0s",
                    ),
                    HazardChainStep(
                        step=2,
                        title="Nguy cơ ngạt thở hoặc mất máu thứ phát",
                        description="Nếu không được tiếp cận sơ cứu trong 'thời gian vàng' 3 - 5 phút, nguy cơ tổn thương não không hồi phục.",
                        time_offset="+180s",
                    ),
                ],
                simulated_consequences=[
                    "Chấn thương sọ não kín hoặc chấn thương cột sống cổ.",
                    "Tử vong do sốc mất máu hoặc đột quỵ nhiệt nếu không có can thiệp y tế tức thời.",
                ],
                immediate_actions=[
                    "🔴 Phát loa báo động khẩn cấp và cử đội cứu thương công trường tiếp cận hiện trường ngay lập tức.",
                    "🟡 Giữ nguyên hiện trường và không di chuyển nạn nhân bừa bãi khi chưa cố định đốt sống cổ.",
                    "🟢 Gọi số điện thoại cấp cứu 115 và thông báo Chỉ huy trưởng công trường.",
                ],
                source_mode="OFFLINE_EXPERT_SYSTEM",
                timestamp=now_str,
                statistical_basis=stat_basis,
            )

        # 4. KỊCH BẢN: XÂM NHẬP VÙNG NGUY HIỂM (GEOFENCING INTRUSION)
        elif "zone" in v_norm or "intrusion" in v_norm or "pit" in v_norm:
            return WhatIfScenario(
                scenario_id=scen_id,
                title="Xâm Nhập Hố Móng Sâu / Vùng Bán Kính Quay Xe Cơ Giới",
                hazard_type=violation_type,
                probability_pct=prob_pct,
                probability_level=prob_level,
                severity_level=ScenarioSeverity.HIGH,
                impact_energy_joules=None,
                osha_standard="OSHA 1926.651 (Hào rãnh, hố móng) & OSHA 1926.600 (Thiết bị cơ giới)",
                root_cause_chain=[
                    HazardChainStep(
                        step=1,
                        title="Bước vào phạm vi cảnh giới nguy hiểm",
                        description="Công nhân đi qua vạch phân cách an toàn, tiến sát mép taluy hố móng hoặc điểm mù máy xúc.",
                        time_offset="0.0s",
                    ),
                    HazardChainStep(
                        step=2,
                        title="Sụt lún vách đất hoặc va quẹt cần gầu",
                        description="Tải trọng rung từ máy thi công gây sạt lở vách hố móng, vùi lấp hoặc gầu xúc quay va chạm thân người.",
                        time_offset="+2.0s",
                    ),
                ],
                simulated_consequences=[
                    "Bị đất đá vùi lấp dẫn đến ngạt thở.",
                    "Chấn thương đè nén (Crush Injury) do kẹp giữa xe cơ giới và công trình cố định.",
                ],
                immediate_actions=[
                    "🔴 Còi báo hiệu tự động phát âm thanh cảnh báo xua đuổi công nhân ra khỏi vùng nguy hiểm.",
                    "🟡 Lắp đặt rào cứng kiên cố cao 1.2m quanh miệng hố móng sâu trên 1.5m.",
                    "🟢 Bố trí phụ xe / cảnh giới an toàn (Signalman) hướng dẫn máy đào di chuyển.",
                ],
                source_mode="OFFLINE_EXPERT_SYSTEM",
                timestamp=now_str,
                statistical_basis=stat_basis,
            )

        # 5. KỊCH BẢN: VA CHẠM PHƯƠNG TIỆN CƠ GIỚI & ĐIỂM MÙ (STRUCK-BY VEHICLE / BLIND SPOT)
        elif any(k in v_norm for k in ["blind_spot", "struck_by", "vehicle", "forklift", "crane", "machinery"]):
            return WhatIfScenario(
                scenario_id=scen_id,
                title="Xung Đột Người - Xe: Đứng Trong Điểm Mù Hoặc Cắt Ngang Đường Xe Cơ Giới",
                hazard_type=violation_type,
                probability_pct=prob_pct,
                probability_level=prob_level,
                severity_level=ScenarioSeverity.CRITICAL,
                impact_energy_joules=1200.0,
                osha_standard="OSHA 1926.600 & 1926.601 (Phương tiện & Máy móc cơ giới thi công)",
                root_cause_chain=[
                    HazardChainStep(
                        step=1,
                        title="Đi vào vùng điểm mù / cắt ngang hướng di chuyển",
                        description="Mô hình RelateAnything phát hiện công nhân tiếp cận góc khuất của xe nâng/xe tải đang vận hành.",
                        time_offset="0.0s",
                    ),
                    HazardChainStep(
                        step=2,
                        title="Tài xế mất tầm nhìn quan sát",
                        description="Tài xế xe cơ giới không thể nhìn thấy công nhân qua gương chiếu hậu do chướng ngại vật hàng hóa.",
                        time_offset="+0.8s",
                    ),
                    HazardChainStep(
                        step=3,
                        title="Va quẹt hoặc kẹp nén thân thể",
                        description="Phương tiện lùi hoặc chuyển hướng đột ngột dẫn đến tai nạn đè nát (Caught-in/between) hoặc va đập mạnh.",
                        time_offset="+1.8s",
                    ),
                ],
                simulated_consequences=[
                    "Gãy xương chi, chấn thương dập nát nội tạng vùng bụng/ngực.",
                    "Tử vong do bị phương tiện tải trọng lớn chèn qua.",
                ],
                immediate_actions=[
                    "🔴 Dừng ngay phương tiện và kích hoạt còi cảnh báo lùi.",
                    "🟡 Thiết lập lối đi riêng cho người đi bộ (Pedestrian Walkway) cách biệt luồng xe cơ giới.",
                    "🟢 Trang bị áo phản quang tiêu chuẩn EN ISO 20471 / TCVN cho toàn bộ nhân sự công trường.",
                ],
                source_mode="OFFLINE_EXPERT_SYSTEM",
                timestamp=now_str,
                statistical_basis=stat_basis,
            )

        # 6. KỊCH BẢN: THIẾU MŨ BẢO HỘ (NO-HELMET)
        elif "no-helmet" in v_norm:
            return WhatIfScenario(
                scenario_id=scen_id,
                title="Thiếu Mũ Bảo Hộ Trong Khu Vực Đang Thi Công",
                hazard_type=violation_type,
                probability_pct=prob_pct,
                probability_level=prob_level,
                severity_level=ScenarioSeverity.HIGH,
                impact_energy_joules=75.0,
                osha_standard="OSHA 1926.100 & QCVN 18:2021/BXD Mục 2.1 (Mũ bảo hộ công nghiệp)",
                root_cause_chain=[
                    HazardChainStep(
                        step=1,
                        title="Đầu trần không trang bị bảo hộ đạt chuẩn",
                        description="Công nhân cởi bỏ mũ bảo hộ hoặc không cài quai nón đúng quy định khi làm việc.",
                        time_offset="0.0s",
                    ),
                    HazardChainStep(
                        step=2,
                        title="Vật thể rơi tự do hoặc va đập vào giàn giáo",
                        description="Mạt vữa, bu-lông rơi từ sàn tầng trên hoặc công nhân va đầu vào thanh giằng giàn giáo khi đứng lên.",
                        time_offset="+1.5s",
                    ),
                ],
                simulated_consequences=[
                    "Một viên ốc vít 50g rơi từ tầng 4 có thể xuyên rách da đầu gây mất máu nhiều.",
                    "Va đập vào dầm thép gây rách màng não hoặc chấn thương sọ não kín.",
                ],
                immediate_actions=[
                    "🔴 Nhắc nhở và yêu cầu đội mũ bảo hộ cài quai ngay lập tức trước khi tiếp tục làm việc.",
                    "🟡 Kiểm tra tem kiểm định an toàn của mũ (chống va đập theo TCVN 6407).",
                ],
                source_mode="OFFLINE_EXPERT_SYSTEM",
                timestamp=now_str,
                statistical_basis=stat_basis,
            )

        # 6. KỊCH BẢN MẶC ĐỊNH CHO CÁC VI PHẠM PPE KHÁC
        else:
            return WhatIfScenario(
                scenario_id=scen_id,
                title=f"Nguy Cơ Tai Nạn Do Vi Phạm Quy Định An Toàn: {violation_type.upper()}",
                hazard_type=violation_type,
                probability_pct=prob_pct,
                probability_level=prob_level,
                severity_level=ScenarioSeverity.MEDIUM,
                impact_energy_joules=None,
                osha_standard="OSHA 1926.95 & QCVN 18:2021/BXD (Trang thiết bị bảo hộ cá nhân)",
                root_cause_chain=[
                    HazardChainStep(
                        step=1,
                        title="Không trang bị đầy đủ PPE chuyên dụng",
                        description=f"Công nhân đang hoạt động nhưng thiếu trang bị bảo hộ thiết yếu: {violation_type}.",
                        time_offset="0.0s",
                    ),
                    HazardChainStep(
                        step=2,
                        title="Tác động trực tiếp từ môi trường độc hại/nguy hiểm",
                        description="Yếu tố rủi ro tại hiện trường tiếp xúc trực tiếp với cơ thể công nhân không qua lớp chắn bảo vệ.",
                        time_offset="+1.0s",
                    ),
                ],
                simulated_consequences=[
                    "Tổn thương các bộ phận cơ thể (mắt, tay, chân, da).",
                    "Giảm sút năng suất lao động và gián đoạn ca làm việc.",
                ],
                immediate_actions=[
                    f"🔴 Bổ sung trang bị bảo hộ {violation_type.upper()} đạt chuẩn cho công nhân.",
                    "🟡 Cán bộ giám sát an toàn tăng cường kiểm tra đầu giờ làm việc (Toolbox Meeting).",
                ],
                source_mode="OFFLINE_EXPERT_SYSTEM",
                timestamp=now_str,
                statistical_basis=stat_basis,
            )

    def _generate_vlm_scenario(
        self,
        violation_type: str,
        ctx: Dict[str, Any],
        image_base64: str,
    ) -> Optional[WhatIfScenario]:
        """Gọi Google Gemini VLM API để diễn giải ngữ cảnh hình ảnh thực tế."""
        if not self.gemini_api_key:
            return None

        prompt = f"""
Bạn là Chuyên gia Cao cấp về An toàn Lao động Xây dựng (HSE Lead Auditor) theo chuẩn OSHA 1926 và QCVN 18:2021/BXD.
Hãy phân tích bức ảnh hiện trường công trường xây dựng đính kèm và nguy cơ an toàn được phát hiện: "{violation_type}".
Bối cảnh bổ sung: {json.dumps(ctx, ensure_ascii=False)}

Hãy mô phỏng kịch bản tai nạn ("What-If Scenario") có thể xảy ra trong 2-5 giây tới nếu không can thiệp.
YÊU CẦU TRẢ VỀ DUY NHẤT ĐỊNH DẠNG JSON HỢP LỆ VỚI CÁC TRƯỜNG SAU:
{{
  "title": "Tên kịch bản sự cố cụ thể",
  "probability_pct": 85.0,
  "probability_level": "Rất cao" | "Cao" | "Trung bình",
  "severity_level": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
  "impact_energy_joules": 150.0 (hoặc null nếu không phải vật rơi/ngã cao),
  "osha_standard": "Điều khoản OSHA và QCVN vi phạm",
  "root_cause_chain": [
    {{"step": 1, "title": "...", "description": "...", "time_offset": "0.0s"}},
    {{"step": 2, "title": "...", "description": "...", "time_offset": "+1.2s"}},
    {{"step": 3, "title": "...", "description": "...", "time_offset": "+2.5s"}}
  ],
  "simulated_consequences": ["Hậu quả 1", "Hậu quả 2", "Hậu quả 3"],
  "immediate_actions": ["Hành động 1", "Hành động 2", "Hành động 3"]
}}
Chỉ trả về JSON thuần, không thêm markdown hay bất kỳ lời giải thích nào khác.
"""
        # Làm sạch base64 nếu có tiền tố data:image
        clean_b64 = image_base64
        mime_type = "image/jpeg"
        if "," in clean_b64:
            header, clean_b64 = clean_b64.split(",", 1)
            if "png" in header:
                mime_type = "image/png"

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.vlm_model_name}:generateContent?key={self.gemini_api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": clean_b64,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1024,
            },
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=8.0)
        if resp.status_code == 200:
            data = resp.json()
            raw_text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
            raw_text = raw_text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]

            parsed = json.loads(raw_text.strip())
            chain = []
            for item in parsed.get("root_cause_chain", []):
                chain.append(
                    HazardChainStep(
                        step=item.get("step", 1),
                        title=item.get("title", ""),
                        description=item.get("description", ""),
                        time_offset=item.get("time_offset", ""),
                    )
                )

            sev_str = parsed.get("severity_level", "HIGH").upper()
            severity_enum = ScenarioSeverity[sev_str] if sev_str in ScenarioSeverity.__members__ else ScenarioSeverity.HIGH

            return WhatIfScenario(
                scenario_id=f"whatif_vlm_{int(time.time() * 1000)}",
                title=parsed.get("title", f"Kịch bản Nguy cơ: {violation_type}"),
                hazard_type=violation_type,
                probability_pct=float(parsed.get("probability_pct", 80.0)),
                probability_level=parsed.get("probability_level", "Cao"),
                severity_level=severity_enum,
                root_cause_chain=chain,
                simulated_consequences=parsed.get("simulated_consequences", []),
                impact_energy_joules=parsed.get("impact_energy_joules"),
                osha_standard=parsed.get("osha_standard", "OSHA 1926 & QCVN 18:2021/BXD"),
                immediate_actions=parsed.get("immediate_actions", []),
                source_mode="ONLINE_MULTIMODAL_VLM",
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
        else:
            logger.warning(f"Google Gemini VLM API trả về mã lỗi {resp.status_code}: {resp.text[:200]}")
            return None
