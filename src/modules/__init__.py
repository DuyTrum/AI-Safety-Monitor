"""AI Safety Monitor Modules Package.

Cung cấp các module phân tích và mô phỏng nâng cao cho hệ thống giám sát an toàn:
- pose_engine: Phân tích tư thế, phát hiện té ngã và rủi ro công thái học bằng YOLO11-Pose.
- zone_manager: Quản lý đa giác vùng nguy hiểm ảo (Virtual Danger Geofencing).
- scaffold_harness_monitor: Giám sát an toàn giàn giáo, dây đai an toàn và chốt móc neo.
- risk_predictor: Tính toán chỉ số rủi ro động WRI và ngoại suy quỹ đạo tai nạn thời gian thực.
- physics_simulator: Mô phỏng động học rơi tự do, nón va chạm (Drop Cone), động năng Joule và bóng ma ngã.
- whatif_auditor: Phân tích kịch bản tai nạn What-If theo chuẩn OSHA & QCVN 18:2021/BXD (Offline + Multimodal VLM).
- relation_engine: Nhận thức quan hệ ngữ cảnh thị giác và đồ thị an toàn (Safety Scene Graph) bằng RelateAnything.
"""

from .zone_manager import ZoneManager, SafetyZone, ZoneType
from .pose_engine import PoseEngine, PoseAnalysisResult
from .scaffold_harness_monitor import ScaffoldHarnessMonitor, HeightSafetyStatus
from .risk_predictor import RiskPredictor, RiskAssessmentResult
from .physics_simulator import (
    PhysicsSimulator,
    DroppedObjectSimulation,
    GhostFallSimulation,
    ImpactSeverity,
)
from .whatif_auditor import (
    WhatIfAuditor,
    WhatIfScenario,
    HazardChainStep,
    ScenarioSeverity,
)
from .relation_engine import (
    SafetyRelationEngine,
    SafetyRelationTriplet,
    RelationHazardSeverity,
)

__all__ = [
    "ZoneManager",
    "SafetyZone",
    "ZoneType",
    "PoseEngine",
    "PoseAnalysisResult",
    "ScaffoldHarnessMonitor",
    "HeightSafetyStatus",
    "RiskPredictor",
    "RiskAssessmentResult",
    "PhysicsSimulator",
    "DroppedObjectSimulation",
    "GhostFallSimulation",
    "ImpactSeverity",
    "WhatIfAuditor",
    "WhatIfScenario",
    "HazardChainStep",
    "ScenarioSeverity",
    "SafetyRelationEngine",
    "SafetyRelationTriplet",
    "RelationHazardSeverity",
]
