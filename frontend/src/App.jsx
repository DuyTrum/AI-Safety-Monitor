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

function App() {
  // Trạng thái nguồn video & WebSocket
  const [videoSource, setVideoSource] = useState("mock");
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

  // Âm thanh cảnh báo
  const [audioEnabled, setAudioEnabled] = useState(true);
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

  useEffect(() => {
    fetchStatsAndLogs();
    fetchSettings();
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
      const sourceParam = videoSource === "custom" ? customPath : videoSource;
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
            playAlertSound();
          } else {
            setCurrentViolations([]);
          }
          if (data.current_detections) setCurrentDetections(data.current_detections);
          if (data.active_rules) setNotifySettings((prev) => ({ ...prev, active_rules: data.active_rules }));
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

  // Toggle nhanh quy định an toàn
  const handleToggleRule = async (ruleKey) => {
    const current = notifySettings.active_rules?.[ruleKey] ?? true;
    const updatedRules = {
      ...(notifySettings.active_rules || {}),
      [ruleKey]: !current
    };
    const updated = { ...notifySettings, active_rules: updatedRules };
    setNotifySettings(updated);

    try {
      await fetch(`${API_BASE}/api/settings/notifications`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updated)
      });
    } catch (e) {
      console.error("Update rule error:", e);
    }
  };

  // Xóa nhật ký
  const handleClearHistory = async () => {
    if (window.confirm("Xóa toàn bộ nhật ký vi phạm hiện tại?")) {
      try {
        const res = await fetch(`${API_BASE}/api/violations`, { method: "DELETE" });
        if (res.ok) {
          setViolationLog([]);
          fetchStatsAndLogs();
        }
      } catch (e) {
        console.error("Clear error:", e);
      }
    }
  };

  // Lưu cấu hình Telegram
  const handleSaveSettings = async (e) => {
    e.preventDefault();
    setSaveStatus("Đang lưu...");
    try {
      const res = await fetch(`${API_BASE}/api/settings/notifications`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(notifySettings)
      });
      if (res.ok) {
        setSaveStatus("Đã lưu thành công!");
        setTimeout(() => setSaveStatus(""), 2500);
      }
    } catch (e) {
      setSaveStatus("Lỗi kết nối.");
    }
  };

  // Test Telegram
  const handleTestTelegram = async () => {
    if (!notifySettings.telegram_bot_token || !notifySettings.telegram_chat_id) {
      setTestTelegramStatus("Nhập đủ Token và Chat ID.");
      return;
    }
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
                >
                  <option value="mock">Video Mẫu (Mock)</option>
                  <option value="0">Webcam Máy Tính (ID 0)</option>
                  <option value="1">Webcam Ngoài (ID 1)</option>
                  <option value="custom">Camera IP (RTSP/File)</option>
                </select>

                {videoSource === "custom" && (
                  <input
                    type="text"
                    className="c-input"
                    placeholder="rtsp://..."
                    value={customPath}
                    onChange={(e) => setCustomPath(e.target.value)}
                    disabled={streamActive}
                    style={{ width: "160px" }}
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
                filteredLogs.map((log) => {
                  const b = getViolationBadge(log.type);
                  const time = new Date(log.timestamp).toLocaleTimeString('vi-VN');
                  return (
                    <div key={log.id} className={`incident-row ${b.border}`}>
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
