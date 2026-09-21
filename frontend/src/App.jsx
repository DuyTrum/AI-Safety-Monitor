import React, { useState, useEffect, useRef, useCallback } from "react";

const API_BASE = import.meta.env.VITE_API_URL || `${window.location.protocol}//${window.location.hostname || "localhost"}:8000`;
const WS_BASE = import.meta.env.VITE_WS_URL || `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.hostname || "localhost"}:8000`;

// Compact SVG Icons
const IconShield = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
  </svg>
);

const IconCamera = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
    <circle cx="12" cy="13" r="4"/>
  </svg>
);

const IconVolume = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
    <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/>
  </svg>
);

const IconVolumeMute = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
    <line x1="23" y1="9" x2="17" y2="15"/>
    <line x1="17" y1="9" x2="23" y2="15"/>
  </svg>
);

const IconExport = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
    <polyline points="7 10 12 15 17 10"/>
    <line x1="12" y1="15" x2="12" y2="3"/>
  </svg>
);

const IconGear = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3"/>
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
  </svg>
);

const IconSparkles = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/>
    <path d="M5 3v4"/>
    <path d="M19 17v4"/>
    <path d="M3 5h4"/>
    <path d="M17 19h4"/>
  </svg>
);

function App() {
  // Trạng thái nguồn video & WebSocket
  const [videoSource, setVideoSource] = useState("data/videos/real_ppe_site_01.mp4");
  const [availableVideos, setAvailableVideos] = useState([]);
  const [customPath, setCustomPath] = useState("");
  const [streamActive, setStreamActive] = useState(false);
  const [connected, setConnected] = useState(false);
  const [streamError, setStreamError] = useState(null);

  // Live Stream Frame & Data
  const [frame, setFrame] = useState(null);
  const [currentViolations, setCurrentViolations] = useState([]);
  const [currentDetections, setCurrentDetections] = useState({
    helmet: false,
    vest: false,
    gloves: false,
    boots: false,
    goggles: false
  });

  // Âm thanh cảnh báo (Mặc định tắt hoàn toàn theo yêu cầu)
  const [audioEnabled, setAudioEnabled] = useState(false);
  const audioContextRef = useRef(null);

  // Thống kê & Nhật ký
  const [stats, setStats] = useState({
    total_violations: 0,
    compliance_rate: 100.0,
    violations_today: 0,
    class_stats: {}
  });
  const [violationLog, setViolationLog] = useState([]);
  const [logFilter, setLogFilter] = useState("all");
  const [riskSummary, setRiskSummary] = useState({
    total_tracked: 0,
    safe_count: 0,
    warning_count: 0,
    danger_count: 0,
    average_wri: 0.0,
    assessments: []
  });

  // Mô phỏng Vật lý Tai nạn & Trợ lý What-If
  const [simulationSummary, setSimulationSummary] = useState({
    physics_enabled: true,
    drop_cones_count: 0,
    ghost_falls_count: 0,
    active_simulations: []
  });
  const [physicsSimEnabled, setPhysicsSimEnabled] = useState(true);
  const [showWhatIfModal, setShowWhatIfModal] = useState(false);
  const [whatIfLoading, setWhatIfLoading] = useState(false);
  const [whatIfScenario, setWhatIfScenario] = useState(null);
  const [selectedViolationForWhatIf, setSelectedViolationForWhatIf] = useState("tool_drop_hazard");

  // Modals
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showReportModal, setShowReportModal] = useState(false);
  const [selectedSnapshot, setSelectedSnapshot] = useState(null);

  // Cấu hình Cảnh báo & Quy định
  const [notifySettings, setNotifySettings] = useState({
    telegram_enabled: false,
    telegram_bot_token: "",
    telegram_chat_id: "",
    webhook_enabled: false,
    webhook_url: "",
    snapshot_cooldown: 15,
    active_rules: {
      helmet: true,
      vest: true,
      boots: false,
      gloves: false,
      goggles: false
    }
  });

  const [saveStatus, setSaveStatus] = useState("");
  const [testTelegramStatus, setTestTelegramStatus] = useState("");
  const [isTestingTelegram, setIsTestingTelegram] = useState(false);

  // Đồng hồ
  const wsRef = useRef(null);
  const [currentTime, setCurrentTime] = useState(new Date().toLocaleTimeString('vi-VN'));

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date().toLocaleTimeString('vi-VN'));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Còi báo âm thanh
  const playAlertSound = useCallback(() => {
    if (!audioEnabled) return;
    try {
      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
      }
      const ctx = audioContextRef.current;
      if (ctx.state === "suspended") ctx.resume();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(800, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(400, ctx.currentTime + 0.15);
      gain.gain.setValueAtTime(0.1, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.15);
    } catch (e) {
      console.warn("Audio error:", e);
    }
  }, [audioEnabled]);

  // REST API: Thống kê & Nhật ký
  const fetchStatsAndLogs = async () => {
    try {
      const statsRes = await fetch(`${API_BASE}/api/stats`);
      if (statsRes.ok) setStats(await statsRes.json());

      const logRes = await fetch(`${API_BASE}/api/violations`);
      if (logRes.ok) setViolationLog(await logRes.json());
    } catch (e) {
      console.error("API error:", e);
    }
  };

  const fetchSettings = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/settings/notifications`);
      if (res.ok) setNotifySettings(await res.json());
    } catch (e) {
      console.error("Settings load error:", e);
    }
  };

  const fetchVideos = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/videos`);
      if (res.ok) {
        const data = await res.json();
        if (data.videos && data.videos.length > 0) {
          setAvailableVideos(data.videos);
        }
      }
    } catch (e) {
      console.debug("Video load error:", e);
    }
  };

  useEffect(() => {
    fetchStatsAndLogs();
    fetchSettings();
    fetchVideos();
    const interval = setInterval(fetchStatsAndLogs, 4000);
    return () => clearInterval(interval);
  }, []);

  // Bật/Tắt Live Stream
  const handleToggleStream = () => {
    if (streamActive) {
      if (wsRef.current) wsRef.current.close();
      setStreamActive(false);
      setConnected(false);
      setFrame(null);
      setStreamError(null);
      setCurrentViolations([]);
    } else {
      setStreamError(null);
      const defaultCustom = "data/videos/real_fall_incident.mp4";
      const sourceParam = videoSource === "custom" ? (customPath.trim() || defaultCustom) : videoSource;
      const wsUrl = `${WS_BASE}/api/ws/stream?source=${encodeURIComponent(sourceParam)}`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      setStreamActive(true);

      ws.onopen = () => setConnected(true);

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.error) {
            setStreamError(data.error);
            setStreamActive(false);
            setConnected(false);
            setFrame(null);
            if (wsRef.current) wsRef.current.close();
            return;
          }
          setFrame(data.frame);
          if (data.violations && data.violations.length > 0) {
            setCurrentViolations(data.violations);
            if (audioEnabled) {
              playAlertSound();
            }
          } else {
            setCurrentViolations([]);
          }
          if (data.current_detections) setCurrentDetections(data.current_detections);
          if (data.active_rules) setNotifySettings((prev) => ({ ...prev, active_rules: data.active_rules }));
          if (data.risk_summary) setRiskSummary(data.risk_summary);
          if (data.simulation_summary) setSimulationSummary(data.simulation_summary);
          if (data.stats) setStats(data.stats);
        } catch (err) {
          console.error("WS Parse error:", err);
        }
      };

      ws.onerror = () => {
        setStreamError("Lỗi kết nối Backend :8000");
        setStreamActive(false);
        setConnected(false);
      };

      ws.onclose = () => {
        setConnected(false);
        setStreamActive(false);
      };
    }
  };

  // Tải dữ liệu ban đầu
  const fetchInitialData = useCallback(async () => {
    try {
      const [resStats, resLogs, resSettings] = await Promise.all([
        fetch(`${API_BASE}/api/stats`),
        fetch(`${API_BASE}/api/violations?limit=50`),
        fetch(`${API_BASE}/api/settings/notifications`)
      ]);
      if (resStats.ok) setStats(await resStats.json());
      if (resLogs.ok) setViolationLog(await resLogs.json());
      if (resSettings.ok) {
        const s = await resSettings.json();
        setNotifySettings(s);
        if (s.advanced_features && s.advanced_features.physics_simulation_enabled !== undefined) {
          setPhysicsSimEnabled(s.advanced_features.physics_simulation_enabled);
        }
      }
    } catch (e) {
      console.error("Lỗi tải dữ liệu ban đầu:", e);
    }
  }, []);

  useEffect(() => {
    fetchInitialData();
  }, [fetchInitialData]);

  // Bật/Tắt quy tắc an toàn
  const handleToggleRule = async (ruleKey) => {
    const updated = {
      ...notifySettings.active_rules,
      [ruleKey]: !notifySettings.active_rules[ruleKey]
    };
    const newSettings = { ...notifySettings, active_rules: updated };
    setNotifySettings(newSettings);

    try {
      await fetch(`${API_BASE}/api/settings/notifications`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newSettings)
      });
    } catch (e) {
      console.error("Lỗi cập nhật quy định:", e);
    }
  };

  // Xóa lịch sử vi phạm
  const handleClearHistory = async () => {
    if (!window.confirm("Bạn có chắc chắn muốn xóa toàn bộ lịch sử vi phạm không?")) return;
    try {
      const res = await fetch(`${API_BASE}/api/violations`, { method: "DELETE" });
      if (res.ok) {
        setViolationLog([]);
        setStats((prev) => ({ ...prev, total_violations: 0, violations_today: 0, compliance_rate: 100.0, class_stats: {} }));
      }
    } catch (e) {
      console.error("Lỗi khi xóa lịch sử:", e);
    }
  };

  // Lưu cấu hình Cảnh báo
  const handleSaveSettings = async (e) => {
    e.preventDefault();
    setSaveStatus("Đang lưu...");
    try {
      const res = await fetch(`${API_BASE}/api/settings/notifications`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(notifySettings)
      });
      const data = await res.json();
      setSaveStatus(res.ok && data.status === "success" ? "Đã lưu thành công!" : `Lỗi: ${data.message}`);
      setTimeout(() => setSaveStatus(""), 3000);
    } catch (err) {
      setSaveStatus(`Lỗi: ${err.message}`);
    }
  };

  // Test gửi Telegram
  const handleTestTelegram = async () => {
    setIsTestingTelegram(true);
    setTestTelegramStatus("Đang gửi test...");
    try {
      const res = await fetch(`${API_BASE}/api/settings/notifications/test-telegram`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token: notifySettings.telegram_bot_token.trim(),
          chat_id: notifySettings.telegram_chat_id.trim()
        })
      });
      const data = await res.json();
      setTestTelegramStatus(res.ok && data.status === "success" ? `OK: ${data.message}` : `Lỗi: ${data.message}`);
    } catch (err) {
      setTestTelegramStatus(`Lỗi: ${err.message}`);
    } finally {
      setIsTestingTelegram(false);
    }
  };

  // Xuất Excel
  const handleExportReport = (period) => {
    window.open(`${API_BASE}/api/reports/export?period=${period}&format=excel`, "_blank");
    setShowReportModal(false);
  };

  // Bật/Tắt mô phỏng vật lý
  const handleTogglePhysicsSim = async () => {
    const nextState = !physicsSimEnabled;
    setPhysicsSimEnabled(nextState);
    try {
      await fetch(`${API_BASE}/api/simulation/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ physics_simulation_enabled: nextState }),
      });
    } catch (err) {
      console.error("Lỗi cập nhật cấu hình mô phỏng:", err);
    }
  };

  // Kích hoạt phân tích What-If
  const handleTriggerWhatIf = async (hazardType = "tool_drop_hazard", context = {}) => {
    setShowWhatIfModal(true);
    setWhatIfLoading(true);
    setWhatIfScenario(null);
    setSelectedViolationForWhatIf(hazardType);

    try {
      const resp = await fetch(`${API_BASE}/api/simulation/what-if`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          violation_type: hazardType,
          context_data: context,
          image_base64: frame || null,
        }),
      });
      const data = await resp.json();
      if (data.status === "success") {
        setWhatIfScenario(data.scenario);
      } else {
        alert("Lỗi phân tích: " + (data.message || "Không xác định"));
      }
    } catch (err) {
      console.error("Lỗi gọi API What-If:", err);
    } finally {
      setWhatIfLoading(false);
    }
  };

  // Map tên vi phạm & mức độ
  const getViolationBadge = (type) => {
    switch (type) {
      case "no-helmet":
        return { label: "Không đội mũ bảo hộ", border: "border-danger", textCol: "var(--status-danger)" };
      case "no-vest":
        return { label: "Không mặc áo phản quang", border: "border-warning", textCol: "var(--status-warning)" };
      case "no-boots":
        return { label: "Không đi ủng bảo hộ", border: "border-safe", textCol: "var(--status-safe)" };
      case "no-gloves":
        return { label: "Không đeo găng tay", border: "border-safe", textCol: "var(--status-safe)" };
      case "no-goggles":
        return { label: "Không đeo kính bảo hộ", border: "border-safe", textCol: "var(--status-safe)" };
      default:
        return { label: type, border: "border-warning", textCol: "var(--status-warning)" };
    }
  };

  const filteredLogs = violationLog.filter((log) => {
    if (logFilter === "snapshot") return !!log.snapshot_url;
    if (logFilter === "critical") return log.type === "no-helmet";
    return true;
  });

  return (
    <div className="cctv-app">
      {/* 1. NAVBAR DÀNH CHO NGƯỜI GIÁM SÁT */}
      <header className="cctv-navbar">
        <div className="nav-left">
          <div className="brand-badge">
            <div className="brand-icon"><IconShield /></div>
            <span>AI SAFETY MONITOR</span>
          </div>
          <div className="live-beacon">
            <div className="live-dot" />
            <span>{connected ? "LIVE" : "STANDBY"}</span>
          </div>
        </div>

        <div className="nav-right">
          <div className="clock-text">{currentTime}</div>

          <button
            className={`c-btn c-btn-ghost ${physicsSimEnabled ? "btn-sim-active" : ""}`}
            onClick={handleTogglePhysicsSim}
            title={physicsSimEnabled ? "Tắt mô phỏng vật lý" : "Bật mô phỏng vật lý"}
          >
            <IconSparkles />
            <span>{physicsSimEnabled ? "Mô Phỏng: BẬT" : "Mô Phỏng: TẮT"}</span>
          </button>

          <button
            className="c-btn c-btn-ghost"
            onClick={() => handleTriggerWhatIf(currentViolations[0] || "tool_drop_hazard")}
            style={{ color: "#a78bfa", borderColor: "rgba(167, 139, 250, 0.4)" }}
            title="Kích hoạt phân tích kịch bản tai nạn What-If"
          >
            <IconSparkles />
            <span>Kịch Bản What-If</span>
          </button>

          <button
            className="c-btn c-btn-ghost c-btn-icon"
            onClick={() => setAudioEnabled(!audioEnabled)}
            title={audioEnabled ? "Tắt còi báo" : "Bật còi báo"}
          >
            {audioEnabled ? <IconVolume /> : <IconVolumeMute />}
          </button>

          <button className="c-btn c-btn-ghost" onClick={() => setShowReportModal(true)}>
            <IconExport />
            <span>Xuất Báo Cáo</span>
          </button>

          <button className="c-btn c-btn-ghost" onClick={() => setShowSettingsModal(true)}>
            <IconGear />
            <span>Cài Đặt</span>
          </button>
        </div>
      </header>

      {/* 2. CHỈ SỐ NHANH CHO GIÁM SÁT (4 THẺ GỌN GÀNG) */}
      <div className="supervisor-metrics">
        <div className="metric-box">
          <div className="metric-info">
            <span className="metric-title">Tuân Thủ An Toàn</span>
            <span className="metric-num" style={{ color: "var(--status-safe)" }}>{stats.compliance_rate}%</span>
          </div>
        </div>

        <div className="metric-box">
          <div className="metric-info">
            <span className="metric-title">Vi Phạm Hôm Nay</span>
            <span className="metric-num" style={{ color: stats.violations_today > 0 ? "var(--status-danger)" : "var(--status-safe)" }}>
              {stats.violations_today}
            </span>
          </div>
        </div>

        <div className="metric-box">
          <div className="metric-info">
            <span className="metric-title">Tốc Độ Xử Lý</span>
            <span className="metric-num">68.5 <small style={{ fontSize: "12px", color: "var(--text-dim)" }}>FPS</small></span>
          </div>
        </div>

        <div className="metric-box">
          <div className="metric-info">
            <span className="metric-title">Quy Định Đang Bật</span>
            <span className="metric-num" style={{ color: "var(--status-warning)" }}>
              {Object.values(notifySettings.active_rules || {}).filter(Boolean).length} / 5
            </span>
          </div>
        </div>
      </div>

      {/* 3. KHÔNG GIAN LÀM VIỆC CCTV CHÍNH */}
      <main className="cctv-grid">
        {/* CỘT TRÁI: CAMERA & BẢNG QUY ĐỊNH */}
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <div className="workspace-card">
            <div className="workspace-header">
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <IconCamera />
                <span>CAMERA GIÁM SÁT TRỰC TIẾP</span>
              </div>
            </div>

            {/* Màn hình Video */}
            <div className="feed-viewport">
              <div className="feed-hud-top">
                <span className="hud-tag">CAM-01 • 1080p</span>
                {streamActive && currentViolations.length > 0 && (
                  <span className="hud-alert">🚨 PHÁT HIỆN {currentViolations.length} VI PHẠM</span>
                )}
              </div>

              {frame ? (
                <img src={frame} alt="CCTV Feed" className="feed-img" />
              ) : (
                <div style={{ textAlign: "center", padding: "50px 20px" }}>
                  {streamError ? (
                    <div style={{ color: "var(--status-danger)", fontSize: "13px" }}>{streamError}</div>
                  ) : (
                    <div>
                      <p style={{ fontSize: "14px", fontWeight: "600", color: "#fff", marginBottom: "12px" }}>Camera đang tạm dừng</p>
                      <button className="c-btn c-btn-primary" onClick={handleToggleStream}>
                        Bật Giám Sát
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Thanh Điều Khiển Nguồn Camera */}
            <div className="feed-control-bar">
              <div className="control-group">
                <select
                  className="c-select"
                  value={videoSource}
                  onChange={(e) => setVideoSource(e.target.value)}
                  disabled={streamActive}
                  style={{ maxWidth: "360px" }}
                >
                  <optgroup label="🎥 Video Thực Tế Công Trường (Real Footage)">
                    {availableVideos
                      .filter((v) => v.filename.startsWith("real_") || v.filename.startsWith("worker_zone"))
                      .map((v) => (
                        <option key={v.path} value={v.path}>
                          {v.label} ({v.size_mb} MB)
                        </option>
                      ))}
                  </optgroup>

                  <optgroup label="⚙️ Kịch Bản Mô Phỏng Kiểm Thử (Benchmarks)">
                    {availableVideos
                      .filter((v) => !v.filename.startsWith("real_") && !v.filename.startsWith("worker_zone"))
                      .map((v) => (
                        <option key={v.path} value={v.path}>
                          {v.label} ({v.size_mb} MB)
                        </option>
                      ))}
                  </optgroup>

                  <optgroup label="📹 Nguồn Trực Tiếp & Giả Lập">
                    <option value="mock">Luồng Giả Lập Mẫu (Mock Slideshow)</option>
                    <option value="0">Webcam Máy Tính (ID 0)</option>
                    <option value="1">Webcam Ngoài USB (ID 1)</option>
                    <option value="custom">Camera IP (RTSP) / Đường dẫn tùy biến</option>
                  </optgroup>
                </select>

                {videoSource === "custom" && (
                  <input
                    type="text"
                    className="c-input"
                    placeholder="data/videos/...mp4 hoặc rtsp://..."
                    value={customPath}
                    onChange={(e) => setCustomPath(e.target.value)}
                    disabled={streamActive}
                    style={{ width: "260px" }}
                  />
                )}
              </div>

              <button
                className={`c-btn ${streamActive ? "c-btn-danger" : "c-btn-primary"}`}
                onClick={handleToggleStream}
              >
                {streamActive ? "Dừng Camera" : "Bật Giám Sát"}
              </button>
            </div>
          </div>

          {/* HÀNG BẬT/TẮT 5 QUY ĐỊNH BẢO HỘ (GỌN GÀNG, BẤM TRỰC TIẾP) */}
          <div className="workspace-card">
            <div className="workspace-header">
              <span>QUY ĐỊNH BẢO HỘ (BẤM ĐỂ BẬT/TẮT)</span>
            </div>

            <div className="ppe-pills-row">
              <RulePill
                name="Mũ Bảo Hộ"
                active={notifySettings.active_rules?.helmet ?? true}
                detected={currentDetections.helmet}
                onClick={() => handleToggleRule("helmet")}
              />
              <RulePill
                name="Áo Phản Quang"
                active={notifySettings.active_rules?.vest ?? true}
                detected={currentDetections.vest}
                onClick={() => handleToggleRule("vest")}
              />
              <RulePill
                name="Ủng Bảo Hộ"
                active={notifySettings.active_rules?.boots ?? false}
                detected={currentDetections.boots}
                onClick={() => handleToggleRule("boots")}
              />
              <RulePill
                name="Găng Tay"
                active={notifySettings.active_rules?.gloves ?? false}
                detected={currentDetections.gloves}
                onClick={() => handleToggleRule("gloves")}
              />
              <RulePill
                name="Kính Bảo Hộ"
                active={notifySettings.active_rules?.goggles ?? false}
                detected={currentDetections.goggles}
                onClick={() => handleToggleRule("goggles")}
              />
            </div>
          </div>
        </div>

        {/* CỘT PHẢI: LỊCH SỬ VI PHẠM & BIỂU ĐỒ GỌN GÀNG */}
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <div className="workspace-card incident-list-container">
            <div className="workspace-header">
              <span>NHẬT KÝ VI PHẠM ({violationLog.length})</span>
              <button
                onClick={handleClearHistory}
                style={{ background: "transparent", border: "none", color: "var(--status-danger)", fontSize: "11px", cursor: "pointer", fontWeight: "600" }}
              >
                Xóa
              </button>
            </div>

            {/* Filter Tabs */}
            <div className="incident-filter-bar">
              <button className={`filter-chip ${logFilter === "all" ? "active" : ""}`} onClick={() => setLogFilter("all")}>
                Tất Cả
              </button>
              <button className={`filter-chip ${logFilter === "critical" ? "active" : ""}`} onClick={() => setLogFilter("critical")}>
                Không Mũ
              </button>
              <button className={`filter-chip ${logFilter === "snapshot" ? "active" : ""}`} onClick={() => setLogFilter("snapshot")}>
                Có Ảnh
              </button>
            </div>

            {/* Danh sách cuộn */}
            <div className="incident-scroll">
              {filteredLogs.length === 0 ? (
                <div style={{ textAlign: "center", color: "var(--text-dim)", padding: "40px 10px", fontSize: "12px" }}>
                  Chưa có vi phạm nào
                </div>
              ) : (
                filteredLogs.map((log, idx) => {
                  const b = getViolationBadge(log.type);
                  const time = new Date(log.timestamp).toLocaleTimeString('vi-VN');
                  return (
                    <div key={`${log.id || 'log'}-${idx}`} className={`incident-row ${b.border}`}>
                      {log.snapshot_url && (
                        <div
                          className="incident-thumb-sq"
                          onClick={() => setSelectedSnapshot(`${API_BASE}${log.snapshot_url}`)}
                          title="Xem ảnh phóng to"
                        >
                          <img src={`${API_BASE}${log.snapshot_url}`} alt="Thumb" />
                        </div>
                      )}
                      <div className="incident-details">
                        <div className="incident-line1">
                          <span className="incident-tag" style={{ color: b.textCol }}>{b.label}</span>
                          <span className="incident-time">{time}</span>
                        </div>
                        <div className="incident-line2">
                          <span>Độ tin cậy: {Math.round(log.confidence * 100)}%</span>
                          <button
                            className="c-btn c-btn-ghost"
                            style={{ padding: "2px 8px", fontSize: "10px", height: "20px", color: "#c084fc", borderColor: "rgba(192, 132, 252, 0.4)" }}
                            onClick={() => handleTriggerWhatIf(log.type, { confidence: log.confidence })}
                            title="Mô phỏng kịch bản What-If cho vi phạm này"
                          >
                            🔮 What-If
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Mini Analytics Bars */}
            <div className="mini-analytics">
              <MiniBar label="Không Mũ" count={stats.class_stats["no-helmet"] || 0} total={stats.total_violations || 1} col="var(--status-danger)" />
              <MiniBar label="Không Áo" count={stats.class_stats["no-vest"] || 0} total={stats.total_violations || 1} col="var(--status-warning)" />
              <MiniBar label="Khác" count={(stats.class_stats["no-boots"] || 0) + (stats.class_stats["no-gloves"] || 0) + (stats.class_stats["no-goggles"] || 0)} total={stats.total_violations || 1} col="var(--status-safe)" />
            </div>
          </div>
        </div>
      </main>

      {/* MODAL XUẤT BÁO CÁO EXCEL */}
      {showReportModal && (
        <div className="modal-overlay" onClick={() => setShowReportModal(false)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <span>Xuất Báo Cáo Excel</span>
              <button className="c-btn c-btn-ghost c-btn-icon" onClick={() => setShowReportModal(false)}>✕</button>
            </div>
            <div className="modal-content">
              <p style={{ fontSize: "12px", color: "var(--text-dim)" }}>Chọn mốc thời gian để tải file Excel (.xlsx):</p>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                <button className="c-btn c-btn-ghost" onClick={() => handleExportReport("today")}>Hôm Nay</button>
                <button className="c-btn c-btn-ghost" onClick={() => handleExportReport("week")}>Tuần Này</button>
                <button className="c-btn c-btn-ghost" onClick={() => handleExportReport("month")}>Tháng Này</button>
                <button className="c-btn c-btn-ghost" onClick={() => handleExportReport("all")}>Toàn Bộ</button>
              </div>
            </div>
            <div className="modal-foot">
              <button className="c-btn c-btn-ghost" onClick={() => setShowReportModal(false)}>Đóng</button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL CÀI ĐẶT TELEGRAM */}
      {showSettingsModal && (
        <div className="modal-overlay" onClick={() => setShowSettingsModal(false)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <span>Cài Đặt Cảnh Báo Telegram</span>
              <button className="c-btn c-btn-ghost c-btn-icon" onClick={() => setShowSettingsModal(false)}>✕</button>
            </div>
            <form onSubmit={handleSaveSettings}>
              <div className="modal-content">
                <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", fontWeight: "600", cursor: "pointer", color: "#38bdf8" }}>
                  <input
                    type="checkbox"
                    checked={notifySettings.telegram_enabled}
                    onChange={(e) => setNotifySettings({ ...notifySettings, telegram_enabled: e.target.checked })}
                  />
                  Gửi Cảnh Báo Qua Telegram
                </label>

                {notifySettings.telegram_enabled && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    <div>
                      <div style={{ fontSize: "11px", color: "var(--text-dim)", marginBottom: "3px" }}>Bot Token:</div>
                      <input
                        type="text"
                        className="c-input"
                        style={{ width: "100%" }}
                        placeholder="7123456789:AA..."
                        value={notifySettings.telegram_bot_token}
                        onChange={(e) => setNotifySettings({ ...notifySettings, telegram_bot_token: e.target.value })}
                      />
                    </div>
                    <div>
                      <div style={{ fontSize: "11px", color: "var(--text-dim)", marginBottom: "3px" }}>Chat ID:</div>
                      <input
                        type="text"
                        className="c-input"
                        style={{ width: "100%" }}
                        placeholder="-100123456789"
                        value={notifySettings.telegram_chat_id}
                        onChange={(e) => setNotifySettings({ ...notifySettings, telegram_chat_id: e.target.value })}
                      />
                    </div>
                    <button
                      type="button"
                      className="c-btn c-btn-ghost"
                      style={{ alignSelf: "flex-start", marginTop: "4px" }}
                      onClick={handleTestTelegram}
                      disabled={isTestingTelegram}
                    >
                      {isTestingTelegram ? "Đang gửi..." : "Thử Gửi Tin Nhắn"}
                    </button>
                    {testTelegramStatus && (
                      <div style={{ fontSize: "11px", color: testTelegramStatus.startsWith("OK") ? "var(--status-safe)" : "var(--status-danger)" }}>
                        {testTelegramStatus}
                      </div>
                    )}
                  </div>
                )}

                <div style={{ borderTop: "1px solid var(--border-dim)", paddingTop: "10px", marginTop: "6px" }}>
                  <div style={{ fontSize: "12px", fontWeight: "700", color: "#c084fc", marginBottom: "4px" }}>
                    🧠 Trợ Lý What-If VLM (Tùy chọn)
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--text-dim)", marginBottom: "6px" }}>
                    Mặc định chạy ngoại tuyến (Offline Expert System). Nếu nhập Gemini API Key, AI sẽ phân tích ngữ cảnh hình ảnh chi tiết.
                  </div>
                  <div>
                    <div style={{ fontSize: "11px", color: "var(--text-dim)", marginBottom: "3px" }}>Google Gemini API Key:</div>
                    <input
                      type="password"
                      className="c-input"
                      style={{ width: "100%" }}
                      placeholder="AIzaSy..."
                      value={notifySettings.gemini_api_key || ""}
                      onChange={(e) => setNotifySettings({ ...notifySettings, gemini_api_key: e.target.value })}
                    />
                  </div>
                </div>

                {saveStatus && <div style={{ fontSize: "11px", color: "var(--status-safe)" }}>{saveStatus}</div>}
              </div>
              <div className="modal-foot">
                <button type="button" className="c-btn c-btn-ghost" onClick={() => setShowSettingsModal(false)}>Đóng</button>
                <button type="submit" className="c-btn c-btn-primary">Lưu</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 4. MODAL PHÂN TÍCH KỊCH BẢN TAI NẠN WHAT-IF */}
      {showWhatIfModal && (
        <div className="modal-overlay" onClick={() => setShowWhatIfModal(false)}>
          <div className="whatif-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <IconSparkles />
                <span>TRỢ LÝ AI: PHÂN TÍCH KỊCH BẢN TAI NẠN (WHAT-IF AUDITOR)</span>
              </div>
              <button
                onClick={() => setShowWhatIfModal(false)}
                style={{ background: "transparent", border: "none", color: "var(--text-dim)", cursor: "pointer", fontSize: "16px" }}
              >
                ✕
              </button>
            </div>

            <div className="modal-content" style={{ overflowY: "auto", maxHeight: "75vh" }}>
              {/* Thanh chọn nhanh nguy cơ để mô phỏng */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
                <span style={{ fontSize: "12px", color: "var(--text-dim)" }}>Chọn nhanh tình huống thử nghiệm:</span>
                <div className="whatif-quick-selector">
                  {[
                    { type: "tool_drop_hazard", label: "🔨 Rơi Dụng Cụ" },
                    { type: "on_scaffold_unhooked", label: "🧗 Không Móc Dây Neo" },
                    { type: "fall_detected", label: "🚨 Té Ngã Bất Động" },
                    { type: "zone_intrusion", label: "🚧 Vào Hố Móng / Vùng Cấm" },
                    { type: "no-helmet", label: "👷 Không Đội Mũ" },
                  ].map((item) => (
                    <button
                      key={item.type}
                      className={`whatif-chip-btn ${selectedViolationForWhatIf === item.type ? "whatif-chip-active" : ""}`}
                      onClick={() => handleTriggerWhatIf(item.type)}
                      disabled={whatIfLoading}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>

              {whatIfLoading ? (
                <div style={{ textAlign: "center", padding: "40px 20px" }}>
                  <div style={{ color: "var(--accent)", fontSize: "14px", fontWeight: "600", marginBottom: "8px" }}>
                    Đang phân tích chuỗi rủi ro & mô phỏng kịch bản tai nạn...
                  </div>
                  <div style={{ fontSize: "12px", color: "var(--text-dim)" }}>
                    Đang đối chiếu tiêu chuẩn OSHA 1926 & QCVN 18:2021/BXD
                  </div>
                </div>
              ) : whatIfScenario ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  {/* Banner Tên Kịch Bản & Cấp Độ */}
                  <div className="whatif-banner">
                    <div>
                      <div className="whatif-banner-title">
                        <span>⚠️ {whatIfScenario.title}</span>
                      </div>
                      <div style={{ fontSize: "12px", color: "var(--text-dim)", marginTop: "4px" }}>
                        Mã vi phạm: <strong style={{ color: "#fff" }}>{whatIfScenario.hazard_type}</strong> • Tiêu chuẩn: {whatIfScenario.osha_standard}
                      </div>
                      {whatIfScenario.statistical_basis && (
                        <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "4px", fontStyle: "italic" }}>
                          📊 Cơ sở định lượng: {whatIfScenario.statistical_basis}
                        </div>
                      )}
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "4px" }}>
                      <span className="whatif-badge-mode">{whatIfScenario.source_mode}</span>
                      <span style={{ fontSize: "13px", fontWeight: "700", color: "var(--status-danger)" }}>
                        Xác suất: {whatIfScenario.probability_pct}% ({whatIfScenario.probability_level})
                      </span>
                    </div>
                  </div>

                  {/* Thông số Động học / Vật lý nếu có */}
                  {whatIfScenario.impact_energy_joules && (
                    <div className="whatif-physics-callout">
                      <div className="whatif-metric-card">
                        <div className="whatif-metric-label">Động Năng Va Đập</div>
                        <div className="whatif-metric-val" style={{ color: "#f43f5e" }}>
                          {whatIfScenario.impact_energy_joules} J
                        </div>
                      </div>
                      <div className="whatif-metric-card">
                        <div className="whatif-metric-label">Ngưỡng Vỡ Sọ Não</div>
                        <div className="whatif-metric-val" style={{ color: "#f59e0b" }}>
                          ~50 J
                        </div>
                      </div>
                      <div className="whatif-metric-card">
                        <div className="whatif-metric-label">Cấp Độ Nguy Hiểm</div>
                        <div className="whatif-metric-val" style={{ color: "#f43f5e" }}>
                          {whatIfScenario.severity_level}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Chuỗi rủi ro (Hazard Chain) */}
                  <div>
                    <div style={{ fontSize: "13px", fontWeight: "700", color: "#fff", marginBottom: "6px" }}>
                      🔗 Chuỗi Rủi Ro & Cơ Chế Tai Nạn (Hazard Chain):
                    </div>
                    <div className="whatif-chain-container">
                      {whatIfScenario.root_cause_chain.map((step) => (
                        <div key={step.step} className="whatif-chain-step">
                          <div className="whatif-step-num">{step.step}</div>
                          <div style={{ flex: 1 }}>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                              <span style={{ fontSize: "13px", fontWeight: "700", color: "#fff" }}>{step.title}</span>
                              <span style={{ fontSize: "11px", fontFamily: "var(--font-mono)", color: "var(--status-warning)" }}>
                                {step.time_offset}
                              </span>
                            </div>
                            <p style={{ fontSize: "12px", color: "var(--text-body)", marginTop: "3px" }}>
                              {step.description}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Hậu quả mô phỏng */}
                  <div style={{ background: "var(--bg-surface-elevated)", padding: "10px 14px", borderRadius: "6px", border: "1px solid var(--border-dim)" }}>
                    <div style={{ fontSize: "13px", fontWeight: "700", color: "#f87171", marginBottom: "6px" }}>
                      💥 Hậu Quả & Chấn Thương Mô Phỏng:
                    </div>
                    <ul style={{ paddingLeft: "18px", fontSize: "12px", display: "flex", flexDirection: "column", gap: "4px" }}>
                      {whatIfScenario.simulated_consequences.map((cons, cIdx) => (
                        <li key={cIdx} style={{ color: "var(--text-body)" }}>{cons}</li>
                      ))}
                    </ul>
                  </div>

                  {/* Hành động khẩn cấp */}
                  <div className="whatif-actions-box">
                    <div className="whatif-actions-title">
                      <span>🛡️ Danh Mục Hành Động Khẩn Cấp (HSE Action Checklist):</span>
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: "6px", fontSize: "12px" }}>
                      {whatIfScenario.immediate_actions.map((act, aIdx) => (
                        <div key={aIdx} style={{ display: "flex", alignItems: "flex-start", gap: "6px" }}>
                          <span>{act}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : null}
            </div>

            <div className="modal-foot">
              <button
                type="button"
                className="c-btn c-btn-ghost"
                onClick={() => handleTriggerWhatIf(selectedViolationForWhatIf)}
                disabled={whatIfLoading}
              >
                🔄 Phân Tích Lại
              </button>
              <button
                type="button"
                className="c-btn c-btn-primary"
                onClick={() => setShowWhatIfModal(false)}
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}

      {/* LIGHTBOX XEM ẢNH */}
      {selectedSnapshot && (
        <div className="modal-overlay" onClick={() => setSelectedSnapshot(null)}>
          <div style={{ position: "relative", maxWidth: "85vw", maxHeight: "85vh" }} onClick={(e) => e.stopPropagation()}>
            <img src={selectedSnapshot} alt="Snapshot" style={{ width: "100%", maxHeight: "80vh", objectFit: "contain", borderRadius: "4px", border: "1px solid var(--border-main)" }} />
            <button
              onClick={() => setSelectedSnapshot(null)}
              style={{ position: "absolute", top: "-12px", right: "-12px", width: "26px", height: "26px", borderRadius: "50%", background: "var(--status-danger)", color: "#fff", border: "none", cursor: "pointer", fontWeight: "bold" }}
            >
              ✕
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// Sub-Component: Rule Pill
function RulePill({ name, active, detected, onClick }) {
  let cl = "ppe-pill";
  let badge = <span className="pill-badge pill-badge-off">TẮT</span>;

  if (!active) {
    cl += " pill-disabled";
  } else if (detected) {
    cl += " pill-safe";
    badge = <span className="pill-badge pill-badge-safe">ĐẠT</span>;
  } else {
    cl += " pill-danger";
    badge = <span className="pill-badge pill-badge-danger">LỖI</span>;
  }

  return (
    <div className={cl} onClick={onClick}>
      <span className="pill-title">{name}</span>
      {badge}
    </div>
  );
}

// Sub-Component: Mini Bar
function MiniBar({ label, count, total, col }) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0;
  return (
    <div className="bar-row">
      <div className="bar-label-line">
        <span>{label}</span>
        <span style={{ fontFamily: "var(--font-mono)" }}>{count} ({pct}%)</span>
      </div>
      <div className="bar-track">
        <div className="bar-val" style={{ width: `${pct}%`, background: col }} />
      </div>
    </div>
  );
}

export default App;
