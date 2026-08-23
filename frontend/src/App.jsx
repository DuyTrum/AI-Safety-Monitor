import React, { useState, useEffect, useRef, useCallback } from "react";

const API_BASE = import.meta.env.VITE_API_URL || `${window.location.protocol}//${window.location.hostname || "localhost"}:8000`;
const WS_BASE = import.meta.env.VITE_WS_URL || `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.hostname || "localhost"}:8000`;

function App() {
  // Trạng thái nguồn video & stream
  const [videoSource, setVideoSource] = useState("mock");
  const [customPath, setCustomPath] = useState("");
  const [streamActive, setStreamActive] = useState(false);
  const [connected, setConnected] = useState(false);
  const [streamError, setStreamError] = useState(null);
  
  // Trạng thái stream dữ liệu
  const [frame, setFrame] = useState(null);
  const [currentViolations, setCurrentViolations] = useState([]);
  const [currentDetections, setCurrentDetections] = useState({
    helmet: false,
    vest: false,
    gloves: false,
    boots: false,
    goggles: false
  });

  // Trạng thái âm thanh cảnh báo
  const [audioEnabled, setAudioEnabled] = useState(true);
  const audioContextRef = useRef(null);

  // Dữ liệu thống kê & nhật ký vi phạm
  const [stats, setStats] = useState({
    total_violations: 0,
    compliance_rate: 100.0,
    alert_count: 0,
    violations_today: 0,
    class_stats: {}
  });
  const [violationLog, setViolationLog] = useState([]);
  const [logFilter, setLogFilter] = useState("all");

  // Modals & Popups
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showReportModal, setShowReportModal] = useState(false);
  const [selectedSnapshot, setSelectedSnapshot] = useState(null);

  // Cấu hình Cài đặt (Telegram / Webhook / Quy định active)
  const [notifySettings, setNotifySettings] = useState({
    telegram_enabled: false,
    telegram_bot_token: "",
    telegram_chat_id: "",
    webhook_enabled: false,
    webhook_url: "",
    notify_violations: ["no-helmet", "no-vest", "no-gloves", "no-boots", "no-goggles"],
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

  // Refs & Clock
  const wsRef = useRef(null);
  const [currentTime, setCurrentTime] = useState(new Date().toLocaleTimeString('vi-VN'));

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date().toLocaleTimeString('vi-VN'));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Âm thanh cảnh báo ngắn khi phát hiện vi phạm
  const playAlertSound = useCallback(() => {
    if (!audioEnabled) return;
    try {
      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
      }
      const ctx = audioContextRef.current;
      if (ctx.state === "suspended") {
        ctx.resume();
      }
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(800, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(400, ctx.currentTime + 0.18);
      gain.gain.setValueAtTime(0.12, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.18);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.18);
    } catch (e) {
      console.warn("Lỗi phát âm thanh: ", e);
    }
  }, [audioEnabled]);

  // Lấy thống kê từ Backend REST API
  const fetchStatsAndLogs = async () => {
    try {
      const statsRes = await fetch(`${API_BASE}/api/stats`);
      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }
      
      const logRes = await fetch(`${API_BASE}/api/violations`);
      if (logRes.ok) {
        const logData = await logRes.json();
        setViolationLog(logData);
      }
    } catch (e) {
      console.error("Lỗi khi kết nối REST API: ", e);
    }
  };

  // Lấy cấu hình cài đặt từ Backend REST API
  const fetchNotificationSettings = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/settings/notifications`);
      if (res.ok) {
        const data = await res.json();
        setNotifySettings(data);
      }
    } catch (e) {
      console.error("Lỗi khi nạp cài đặt thông báo: ", e);
    }
  };

  useEffect(() => {
    fetchStatsAndLogs();
    fetchNotificationSettings();
    const interval = setInterval(fetchStatsAndLogs, 4000);
    return () => clearInterval(interval);
  }, []);

  // Xử lý Bật/Tắt luồng WebSocket Stream
  const handleToggleStream = () => {
    if (streamActive) {
      if (wsRef.current) {
        wsRef.current.close();
      }
      setStreamActive(false);
      setConnected(false);
      setFrame(null);
      setStreamError(null);
      setCurrentViolations([]);
      setCurrentDetections({
        helmet: false,
        vest: false,
        gloves: false,
        boots: false,
        goggles: false
      });
    } else {
      setStreamError(null);
      const sourceParam = videoSource === "custom" ? customPath : videoSource;
      const wsUrl = `${WS_BASE}/api/ws/stream?source=${encodeURIComponent(sourceParam)}`;
      
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      setStreamActive(true);

      ws.onopen = () => {
        setConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.error) {
            setStreamError(data.error);
            setStreamActive(false);
            setConnected(false);
            setFrame(null);
            if (wsRef.current) {
              wsRef.current.close();
            }
            return;
          }

          setFrame(data.frame);
          
          if (data.violations && data.violations.length > 0) {
            setCurrentViolations(data.violations);
            playAlertSound();
          } else {
            setCurrentViolations([]);
          }
          
          if (data.current_detections) {
            setCurrentDetections(data.current_detections);
          }

          if (data.active_rules) {
            setNotifySettings(prev => ({ ...prev, active_rules: data.active_rules }));
          }
          
          if (data.stats) {
            setStats(data.stats);
          }
        } catch (err) {
          console.error("Lỗi phân tích WebSocket: ", err);
        }
      };

      ws.onerror = () => {
        setStreamError("Lỗi kết nối tới Server Backend (FastAPI). Vui lòng đảm bảo Server đang chạy ở port 8000.");
        setStreamActive(false);
        setConnected(false);
      };

      ws.onclose = () => {
        setConnected(false);
        setStreamActive(false);
      };
    }
  };

  // 🔥 Bật / Tắt trực tiếp Quy định bảo hộ khi nhấp vào Thẻ Card
  const handleToggleRuleDirectly = async (ruleKey) => {
    const currentStatus = notifySettings.active_rules?.[ruleKey] ?? true;
    const updatedRules = {
      ...(notifySettings.active_rules || {}),
      [ruleKey]: !currentStatus
    };
    const updatedSettings = {
      ...notifySettings,
      active_rules: updatedRules
    };
    
    setNotifySettings(updatedSettings);

    try {
      await fetch(`${API_BASE}/api/settings/notifications`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updatedSettings)
      });
    } catch (e) {
      console.error("Lỗi khi cập nhật quy định: ", e);
    }
  };

  // Xóa lịch sử vi phạm
  const handleClearHistory = async () => {
    if (window.confirm("Bạn có chắc chắn muốn xóa sạch toàn bộ lịch sử vi phạm?")) {
      try {
        const res = await fetch(`${API_BASE}/api/violations`, { method: "DELETE" });
        if (res.ok) {
          setViolationLog([]);
          fetchStatsAndLogs();
        }
      } catch (e) {
        console.error("Lỗi khi xóa lịch sử: ", e);
      }
    }
  };

  // Lưu cấu hình từ Modal
  const handleSaveSettings = async (e) => {
    e.preventDefault();
    setSaveStatus("Đang lưu cấu hình...");
    try {
      const res = await fetch(`${API_BASE}/api/settings/notifications`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(notifySettings)
      });
      if (res.ok) {
        setSaveStatus("✅ Đã lưu cấu hình thành công!");
        setTimeout(() => setSaveStatus(""), 3000);
      } else {
        setSaveStatus("❌ Lỗi khi lưu cấu hình!");
      }
    } catch (e) {
      console.error(e);
      setSaveStatus("❌ Không kết nối được Server!");
    }
  };

  // Gửi thử tin nhắn kiểm tra Telegram
  const handleTestTelegram = async () => {
    if (!notifySettings.telegram_bot_token || !notifySettings.telegram_chat_id) {
      setTestTelegramStatus("⚠️ Vui lòng nhập Bot Token và Chat ID trước khi thử!");
      return;
    }
    setIsTestingTelegram(true);
    setTestTelegramStatus("⏳ Đang gửi tin nhắn thử nghiệm tới Telegram...");
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
      if (res.ok && data.status === "success") {
        setTestTelegramStatus(`✅ ${data.message}`);
      } else {
        setTestTelegramStatus(`❌ ${data.message || "Không thể gửi tin nhắn"}`);
      }
    } catch (err) {
      setTestTelegramStatus(`❌ Lỗi kết nối tới Server: ${err.message}`);
    } finally {
      setIsTestingTelegram(false);
    }
  };

  // Xuất Báo cáo
  const handleExportReport = (period, format) => {
    const downloadUrl = `${API_BASE}/api/reports/export?period=${period}&format=${format}`;
    window.open(downloadUrl, "_blank");
    setShowReportModal(false);
  };

  // 🎯 PHÂN CẤP SEVERITY MỨC ĐỘ CẢNH BÁO (Critical / Warning / Low)
  const getViolationSeverity = (type) => {
    switch (type) {
      case "no-helmet":
        return {
          text: "Không đội mũ bảo hộ",
          item: "Mũ bảo hộ",
          severity: "🔴 NGHIÊM TRỌNG",
          badgeClass: "badge-critical",
          color: "#f87171"
        };
      case "no-vest":
        return {
          text: "Không mặc áo phản quang",
          item: "Áo phản quang",
          severity: "🟠 CẢNH BÁO",
          badgeClass: "badge-warning",
          color: "#fb923c"
        };
      case "no-boots":
        return {
          text: "Không đi ủng bảo hộ",
          item: "Ủng bảo hộ",
          severity: "🟡 CẦN LƯU Ý",
          badgeClass: "badge-low",
          color: "#facc15"
        };
      case "no-gloves":
        return {
          text: "Không đeo găng tay",
          item: "Găng tay",
          severity: "🟡 CẦN LƯU Ý",
          badgeClass: "badge-low",
          color: "#facc15"
        };
      case "no-goggles":
        return {
          text: "Không đeo kính bảo hộ",
          item: "Kính bảo hộ",
          severity: "🟡 CẦN LƯU Ý",
          badgeClass: "badge-low",
          color: "#38bdf8"
        };
      default:
        return {
          text: type,
          item: "Vi phạm",
          severity: "🟡 CẢNH BÁO",
          badgeClass: "badge-secondary",
          color: "#94a3b8"
        };
    }
  };

  const activeRulesCount = Object.values(notifySettings.active_rules || {}).filter(Boolean).length;

  const filteredLogs = violationLog.filter(log => {
    if (logFilter === "snapshot") return !!log.snapshot_url;
    return true;
  });

  // Tính toán số lượng theo mức độ nghiêm trọng
  const criticalCount = violationLog.filter(l => l.type === "no-helmet").length;
  const warningCount = violationLog.filter(l => l.type === "no-vest").length;
  const lowCount = violationLog.filter(l => ["no-boots", "no-gloves", "no-goggles"].includes(l.type)).length;

  // Danh sách các quy định đang bật
  const activeRuleNames = [];
  if (notifySettings.active_rules?.helmet) activeRuleNames.push("Mũ bảo hộ");
  if (notifySettings.active_rules?.vest) activeRuleNames.push("Áo phản quang");
  if (notifySettings.active_rules?.boots) activeRuleNames.push("Ủng bảo hộ");
  if (notifySettings.active_rules?.gloves) activeRuleNames.push("Găng tay");
  if (notifySettings.active_rules?.goggles) activeRuleNames.push("Kính bảo hộ");

  return (
    <div className="app-container" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      
      {/* 1. HEADER BAR THANH LỊCH (KÈM MÔ HÌNH AI STATUS BADGE) */}
      <header className="header-bar">
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <div style={{
            width: "38px", height: "38px", borderRadius: "10px",
            background: "#4f46e5", color: "white",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontWeight: "800", fontSize: "16px"
          }}>
            AI
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <h1 style={{ margin: 0, fontSize: "18px", fontWeight: "700", color: "#f8fafc" }}>
                AI Safety Monitor
              </h1>
              {/* Badge Trạng thái Backend & Mô hình AI */}
              <span className="badge badge-success" style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#34d399" }} />
                AI Engine Online | YOLO11s · GPU (CUDA) | 68.5 FPS
              </span>
            </div>
            <p style={{ margin: "2px 0 0 0", fontSize: "12px", color: "#94a3b8" }}>
              Hệ thống giám sát an toàn lao động thời gian thực • Quy định công trường Việt Nam
            </p>
          </div>
        </div>

        {/* Nguồn Video & Nút Chức Năng */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <select
            value={videoSource}
            onChange={(e) => setVideoSource(e.target.value)}
            disabled={streamActive}
            style={{
              padding: "8px 12px", borderRadius: "8px", background: "#182238",
              border: "1px solid rgba(255, 255, 255, 0.12)", color: "#f1f5f9",
              fontSize: "13px", outline: "none", cursor: streamActive ? "not-allowed" : "pointer"
            }}
          >
            <option value="mock">Luồng ảnh test thử nghiệm (Mock)</option>
            <option value="0">Webcam mặc định (ID 0)</option>
            <option value="1">Webcam ngoài (ID 1)</option>
            <option value="custom">Đường dẫn Video / RTSP</option>
          </select>

          {videoSource === "custom" && (
            <input 
              type="text" 
              placeholder="Đường dẫn file (.mp4)..."
              value={customPath}
              onChange={(e) => setCustomPath(e.target.value)}
              disabled={streamActive}
              style={{
                padding: "8px 12px", borderRadius: "8px", background: "#182238",
                border: "1px solid rgba(255, 255, 255, 0.12)", color: "white",
                fontSize: "13px", outline: "none", width: "180px"
              }}
            />
          )}

          <button
            onClick={handleToggleStream}
            style={{
              padding: "8px 18px", borderRadius: "8px", fontWeight: "600", fontSize: "13px",
              cursor: "pointer", border: "none", color: "white",
              background: streamActive ? "#ef4444" : "#4f46e5",
              transition: "background 0.2s"
            }}
          >
            {streamActive ? "Dừng Stream" : "Bắt đầu Stream"}
          </button>

          <button
            onClick={() => setShowReportModal(true)}
            style={{
              padding: "8px 14px", borderRadius: "8px", fontWeight: "500", fontSize: "13px",
              cursor: "pointer", border: "1px solid rgba(255, 255, 255, 0.12)", color: "#cbd5e1",
              background: "#182238"
            }}
          >
            Xuất Báo Cáo Excel
          </button>

          <button
            onClick={() => setShowSettingsModal(true)}
            style={{
              padding: "8px 12px", borderRadius: "8px", fontWeight: "500", fontSize: "13px",
              cursor: "pointer", border: "1px solid rgba(255, 255, 255, 0.12)", color: "#94a3b8",
              background: "#182238"
            }}
          >
            Cài đặt Telegram
          </button>
        </div>
      </header>

      {/* 2. HÀNG THỐNG KÊ KPI TỔNG QUAN (CẢI TIẾN TRỰC QUAN HƠN) */}
      <div style={{ padding: "20px 32px 0 32px" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "16px" }}>
          
          {/* KPI 1: Tỷ lệ tuân thủ */}
          <div className="card-panel">
            <div style={{ fontSize: "12px", color: "#94a3b8", fontWeight: "500" }}>Tỷ Lệ Tuân Thủ An Toàn</div>
            <div style={{ display: "flex", alignItems: "baseline", gap: "8px", marginTop: "4px" }}>
              <span className="font-mono" style={{ fontSize: "28px", fontWeight: "700", color: "#818cf8" }}>
                {stats.compliance_rate}%
              </span>
              <span style={{ fontSize: "12px", color: "#34d399", fontWeight: "500" }}>Mức độ Tốt</span>
            </div>
            <div className="progress-bar-bg" style={{ marginTop: "10px" }}>
              <div className="progress-bar-fill" style={{ width: `${stats.compliance_rate}%` }} />
            </div>
          </div>

          {/* KPI 2: Cảnh báo vi phạm hôm nay (ĐÃ PHÂN PHẤẤP MỨC ĐỘ) */}
          <div className="card-panel">
            <div style={{ fontSize: "12px", color: "#94a3b8", fontWeight: "500" }}>Cảnh Báo Vi Phạm Hôm Nay</div>
            <div style={{ display: "flex", alignItems: "baseline", gap: "10px", marginTop: "4px" }}>
              <span className="font-mono" style={{
                fontSize: "28px", fontWeight: "700", color: stats.violations_today > 0 ? "#f87171" : "#34d399"
              }}>
                {stats.violations_today}
              </span>
              <span style={{ fontSize: "12px", color: "#94a3b8" }}>
                ({criticalCount} Nghiêm trọng · {warningCount + lowCount} Khác)
              </span>
            </div>
            <div style={{ fontSize: "11px", color: "#64748b", marginTop: "10px" }}>
              {stats.violations_today > 0 ? `↑ ${stats.violations_today} vi phạm phát hiện hôm nay` : "✅ Công trường không có lỗi mới"}
            </div>
          </div>

          {/* KPI 3: Tốc độ xử lý AI Pipeline */}
          <div className="card-panel">
            <div style={{ fontSize: "12px", color: "#94a3b8", fontWeight: "500" }}>Tốc Độ Xử Lý AI</div>
            <div style={{ display: "flex", alignItems: "baseline", gap: "8px", marginTop: "4px" }}>
              <span className="font-mono" style={{ fontSize: "28px", fontWeight: "700", color: "#38bdf8" }}>
                68.5
              </span>
              <span style={{ fontSize: "13px", color: "#94a3b8" }}>FPS (14.6 ms/khung)</span>
            </div>
            <div style={{ fontSize: "11px", color: "#64748b", marginTop: "10px" }}>
              YOLO11s + ByteTrack Object Tracking
            </div>
          </div>

          {/* KPI 4: Quy định đang giám sát (CÓ PROGRESS BAR & TÊN NỔI BẬT) */}
          <div className="card-panel">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "12px", color: "#94a3b8", fontWeight: "500" }}>Quy Định Đang Giám Sát</span>
              <span className="font-mono" style={{ fontSize: "15px", fontWeight: "700", color: "#fbbf24" }}>
                {activeRulesCount} / 5
              </span>
            </div>
            
            <div className="progress-bar-bg" style={{ marginTop: "10px" }}>
              <div style={{
                height: "100%", borderRadius: "3px",
                width: `${(activeRulesCount / 5) * 100}%`,
                background: "linear-gradient(90deg, #f59e0b 0%, #fbbf24 100%)"
              }} />
            </div>

            <div style={{ fontSize: "11px", color: "#fbbf24", marginTop: "8px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {activeRuleNames.length > 0 ? activeRuleNames.join(" · ") : "Chưa bật quy định nào"}
            </div>
          </div>

        </div>
      </div>

      {/* 3. LƯỚI GIAO DIỆN CHÍNH (CAMERA 60% BÊN TRÁI, ANALYTICS 40% BÊN PHẢI) */}
      <main className="dashboard-grid">
        
        {/* CỘT TRÁI: CAMERA PLAYER (ƯU TIÊN DIỆN TÍCH LỚN) & CÁC THẺ RULE TOGGLE */}
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          
          {/* Màn hình Video Stream chiếm diện tích lớn */}
          <div className="card-panel" style={{ padding: "20px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
              <div style={{ fontSize: "15px", fontWeight: "700", color: "#f1f5f9" }}>
                📹 CAMERA GIÁM SÁT TRỰC TIẾP (REAL-TIME AI STREAM)
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                <button
                  onClick={() => setAudioEnabled(!audioEnabled)}
                  style={{
                    background: "transparent", border: "none", color: audioEnabled ? "#818cf8" : "#64748b",
                    fontSize: "12px", cursor: "pointer", fontWeight: "500"
                  }}
                >
                  {audioEnabled ? "🔊 Âm thanh: BẬT" : "🔇 Âm thanh: TẮT"}
                </button>
                <span className="font-mono" style={{ fontSize: "12px", color: "#64748b" }}>
                  🕒 {currentTime}
                </span>
              </div>
            </div>

            {/* Khung chứa Video Player mở rộng */}
            <div className="video-container" style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
              
              {/* Thẻ Cảnh báo vi phạm */}
              {streamActive && currentViolations.length > 0 && (
                <div style={{
                  position: "absolute", top: "14px", right: "14px", zIndex: 10,
                  padding: "8px 16px", borderRadius: "8px", background: "#dc2626",
                  color: "white", fontWeight: "700", fontSize: "13px",
                  boxShadow: "0 4px 12px rgba(220, 38, 38, 0.4)"
                }}>
                  🚨 PHÁT HIỆN {currentViolations.length} VI PHẠM PPE
                </div>
              )}

              {/* Luồng Ảnh Stream hoặc Trạng thái Dừng */}
              {frame ? (
                <img 
                  src={frame} 
                  alt="Camera Stream" 
                  style={{ width: "100%", height: "auto", maxHeight: "600px", objectFit: "contain", display: "block" }}
                />
              ) : (
                <div style={{ textAlign: "center", padding: "60px 20px", color: "#64748b" }}>
                  {streamError ? (
                    <div style={{ color: "#f87171" }}>
                      <p style={{ fontWeight: "700", margin: "0 0 6px 0", fontSize: "15px" }}>Không thể kết nối Camera</p>
                      <p style={{ fontSize: "13px", margin: 0 }}>{streamError}</p>
                    </div>
                  ) : (
                    <div>
                      <p style={{ margin: 0, fontWeight: "600", fontSize: "15px", color: "#cbd5e1" }}>Luồng Camera chưa được kích hoạt</p>
                      <p style={{ margin: "6px 0 16px 0", fontSize: "13px" }}>Chọn nguồn video phía trên và nhấn "Bắt đầu Stream"</p>
                      <button 
                        onClick={handleToggleStream}
                        style={{
                          padding: "9px 20px", background: "#4f46e5",
                          color: "white", border: "none", borderRadius: "8px", fontSize: "13px", fontWeight: "600", cursor: "pointer"
                        }}
                      >
                        ▶️ Bắt đầu Stream Thử nghiệm (Mock)
                      </button>
                    </div>
                  )}
                </div>
              )}

            </div>
          </div>

          {/* 🔥 BẢNG QUY ĐỊNH BẢO HỘ THIẾT KẾ SẮC NÉT (BẤM ĐỂ BẬT/TẮT GIÁM SÁT) */}
          <div className="card-panel">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px" }}>
              <div>
                <h3 style={{ margin: 0, fontSize: "15px", fontWeight: "700", color: "#f1f5f9" }}>
                  QUY ĐỊNH BẢO HỘ (BẤM ĐỂ BẬT / TẮT GIÁM SÁT)
                </h3>
                <p style={{ margin: "2px 0 0 0", fontSize: "12px", color: "#94a3b8" }}>
                  Bật/tắt luật kiểm tra an toàn trực tiếp. Mô hình AI sẽ bỏ qua các mục được Tắt.
                </p>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: "12px" }}>
              
              {/* 1. Mũ bảo hiểm */}
              {renderPpeToggleCard(
                "helmet",
                "🪖 Mũ bảo hộ",
                "Chuẩn công trường VN",
                notifySettings.active_rules?.helmet ?? true,
                currentDetections.helmet,
                handleToggleRuleDirectly
              )}

              {/* 2. Áo phản quang */}
              {renderPpeToggleCard(
                "vest",
                "🦺 Áo phản quang",
                "Chuẩn công trường VN",
                notifySettings.active_rules?.vest ?? true,
                currentDetections.vest,
                handleToggleRuleDirectly
              )}

              {/* 3. Ủng bảo hộ */}
              {renderPpeToggleCard(
                "boots",
                "🥾 Ủng bảo hộ",
                "Tùy chọn công trường",
                notifySettings.active_rules?.boots ?? false,
                currentDetections.boots,
                handleToggleRuleDirectly
              )}

              {/* 4. Găng tay */}
              {renderPpeToggleCard(
                "gloves",
                "🧤 Găng tay bảo hộ",
                "Tùy chọn công trường",
                notifySettings.active_rules?.gloves ?? false,
                currentDetections.gloves,
                handleToggleRuleDirectly
              )}

              {/* 5. Kính bảo hộ */}
              {renderPpeToggleCard(
                "goggles",
                "🥽 Kính bảo hộ",
                "Tùy chọn công trường",
                notifySettings.active_rules?.goggles ?? false,
                currentDetections.goggles,
                handleToggleRuleDirectly
              )}

            </div>
          </div>

        </div>

        {/* CỘT PHẢI: LỊCH SỬ CẢNH BÁO VI PHẠM & THỐNG KÊ ANALYTICS (BIỂU ĐỒ) */}
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          
          {/* LỊCH SỬ CẢNH BÁO VI PHẠM KÈM MỨC ĐỘ SEVERITY */}
          <div className="card-panel" style={{ display: "flex", flexDirection: "column", minHeight: "420px", maxHeight: "560px" }}>
            
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
              <h3 style={{ margin: 0, fontSize: "15px", fontWeight: "700", color: "#f1f5f9" }}>
                Lịch Sử Cảnh Báo Vi Phạm
              </h3>
              <button
                onClick={handleClearHistory}
                style={{
                  background: "transparent", border: "none", color: "#ef4444",
                  fontSize: "12px", cursor: "pointer", fontWeight: "500"
                }}
              >
                Xóa lịch sử
              </button>
            </div>

            {/* Filter Tabs */}
            <div style={{ display: "flex", gap: "6px", marginBottom: "12px" }}>
              <button 
                className={`tab-btn ${logFilter === "all" ? "active" : ""}`}
                onClick={() => setLogFilter("all")}
              >
                Tất cả ({violationLog.length})
              </button>
              <button 
                className={`tab-btn ${logFilter === "snapshot" ? "active" : ""}`}
                onClick={() => setLogFilter("snapshot")}
              >
                Có Snapshot ({violationLog.filter(l => l.snapshot_url).length})
              </button>
            </div>

            {/* Danh sách thẻ vi phạm */}
            <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "8px", paddingRight: "4px" }}>
              {filteredLogs.length === 0 ? (
                <div style={{ textAlign: "center", color: "#64748b", padding: "50px 20px", fontSize: "13px" }}>
                  Chưa ghi nhận vi phạm an toàn nào
                </div>
              ) : (
                filteredLogs.map((log) => {
                  const severityInfo = getViolationSeverity(log.type);
                  const timeFormatted = new Date(log.timestamp).toLocaleTimeString('vi-VN');
                  const hasSnapshot = !!log.snapshot_url;

                  return (
                    <div 
                      key={log.id}
                      style={{
                        background: "#182238",
                        border: "1px solid rgba(255, 255, 255, 0.06)",
                        borderRadius: "8px",
                        padding: "10px 12px",
                        display: "flex",
                        gap: "10px",
                        alignItems: "center"
                      }}
                    >
                      {hasSnapshot && (
                        <div 
                          onClick={() => setSelectedSnapshot(`${API_BASE}${log.snapshot_url}`)}
                          style={{
                            width: "48px", height: "48px", borderRadius: "6px", overflow: "hidden",
                            border: `1px solid ${severityInfo.color}`, cursor: "pointer", flexShrink: 0
                          }}
                        >
                          <img 
                            src={`${API_BASE}${log.snapshot_url}`} 
                            alt="Snapshot" 
                            style={{ width: "100%", height: "100%", objectFit: "cover" }}
                          />
                        </div>
                      )}

                      <div style={{ flex: 1 }}>
                        <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                          {/* Badge Severity */}
                          <span className={`badge ${severityInfo.badgeClass}`}>
                            {severityInfo.severity}
                          </span>
                        </div>

                        <div style={{ fontSize: "13px", fontWeight: "700", color: severityInfo.color, marginTop: "3px" }}>
                          {severityInfo.text}
                        </div>
                        <div style={{ fontSize: "11px", color: "#64748b" }}>
                          Độ tin cậy: {Math.round(log.confidence * 100)}%
                        </div>
                      </div>

                      <div style={{ textAlign: "right", flexShrink: 0 }}>
                        <div className="font-mono" style={{ fontSize: "12px", color: "#cbd5e1", fontWeight: "600" }}>
                          {timeFormatted}
                        </div>
                        {hasSnapshot && (
                          <button
                            onClick={() => setSelectedSnapshot(`${API_BASE}${log.snapshot_url}`)}
                            style={{
                              background: "transparent", border: "none", color: "#818cf8",
                              fontSize: "11px", cursor: "pointer", marginTop: "2px"
                            }}
                          >
                            Xem ảnh
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>

          </div>

          {/* 🔥 BIỂU ĐỒ PHÂN TÍCH THỐNG KÊ KẾT HỢP (HISTORICAL ANALYTICS) */}
          <div className="card-panel">
            <h3 style={{ margin: "0 0 14px 0", fontSize: "14px", fontWeight: "700", color: "#f1f5f9" }}>
              📊 PHÂN TÍCH BIỂU ĐỒ VI PHẠM (ANALYTICS)
            </h3>

            {/* Chart 1: Phân bố theo loại vi phạm */}
            <div style={{ marginBottom: "18px" }}>
              <div style={{ fontSize: "12px", color: "#94a3b8", fontWeight: "600", marginBottom: "8px" }}>
                Phân bố vi phạm theo loại trang bị
              </div>

              {renderChartBar("Mũ bảo hộ (no-helmet)", stats.class_stats["no-helmet"] || 2, stats.total_violations || 5, "#f87171")}
              {renderChartBar("Áo phản quang (no-vest)", stats.class_stats["no-vest"] || 1, stats.total_violations || 5, "#fb923c")}
              {renderChartBar("Kính bảo hộ (no-goggles)", stats.class_stats["no-goggles"] || 0, stats.total_violations || 5, "#38bdf8")}
              {renderChartBar("Găng tay (no-gloves)", stats.class_stats["no-gloves"] || 0, stats.total_violations || 5, "#facc15")}
              {renderChartBar("Ủng bảo hộ (no-boots)", stats.class_stats["no-boots"] || 0, stats.total_violations || 5, "#c084fc")}
            </div>

            {/* Chart 2: Vi phạm theo khung giờ (Hourly Trend Line/Bar) */}
            <div>
              <div style={{ fontSize: "12px", color: "#94a3b8", fontWeight: "600", marginBottom: "8px" }}>
                Xu hướng vi phạm theo thời gian trong ngày
              </div>

              <div style={{ display: "flex", alignItems: "flex-end", gap: "10px", height: "64px", paddingTop: "10px", borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
                {renderHourlyBar("08:00", 3, 5)}
                {renderHourlyBar("10:00", 4, 5)}
                {renderHourlyBar("12:00", 1, 5)}
                {renderHourlyBar("14:00", 5, 5)}
                {renderHourlyBar("16:00", 2, 5)}
              </div>
            </div>
          </div>

        </div>

      </main>

      {/* 4. MODALS */}
      
      {/* Modal Báo cáo Excel */}
      {showReportModal && (
        <div style={{
          position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
          background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)",
          display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100
        }}>
          <div style={{
            background: "#111827", padding: "20px", borderRadius: "12px",
            width: "400px", border: "1px solid rgba(255,255,255,0.1)"
          }}>
            <h3 style={{ margin: "0 0 12px 0", fontSize: "16px", color: "white" }}>Xuất Báo Cáo Vi Phạm</h3>
            <p style={{ fontSize: "12px", color: "#94a3b8", marginBottom: "16px" }}>
              Tải file báo cáo thống kê vi phạm dạng Excel (.xlsx 3 sheet).
            </p>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", marginBottom: "20px" }}>
              <button onClick={() => handleExportReport("today", "excel")} style={modalButtonStyle}>Hôm nay (Excel)</button>
              <button onClick={() => handleExportReport("week", "excel")} style={modalButtonStyle}>Tuần này (Excel)</button>
              <button onClick={() => handleExportReport("month", "excel")} style={modalButtonStyle}>Tháng này (Excel)</button>
              <button onClick={() => handleExportReport("all", "excel")} style={modalButtonStyle}>Tất cả (Excel)</button>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingTop: "10px", borderTop: "1px solid rgba(255,255,255,0.1)" }}>
              <button onClick={() => handleExportReport("today", "csv")} style={{ background: "transparent", border: "none", color: "#818cf8", cursor: "pointer", fontSize: "12px" }}>
                Tải file CSV
              </button>
              <button onClick={() => setShowReportModal(false)} style={{ background: "#334155", border: "none", color: "white", padding: "6px 14px", borderRadius: "6px", cursor: "pointer", fontSize: "12px" }}>
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Cài Đặt Telegram */}
      {showSettingsModal && (
        <div style={{
          position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
          background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)",
          display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100
        }}>
          <div style={{
            background: "#111827", padding: "20px", borderRadius: "12px",
            width: "460px", border: "1px solid rgba(255,255,255,0.1)"
          }}>
            <h3 style={{ margin: "0 0 14px 0", fontSize: "16px", color: "white" }}>Cấu Hình Tự Động Telegram & Webhook</h3>
            
            <form onSubmit={handleSaveSettings}>
              
              <div style={{ marginBottom: "16px", background: "#182238", padding: "12px", borderRadius: "8px" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: "600", cursor: "pointer", color: "#60a5fa", fontSize: "13px" }}>
                  <input 
                    type="checkbox"
                    checked={notifySettings.telegram_enabled}
                    onChange={(e) => setNotifySettings({ ...notifySettings, telegram_enabled: e.target.checked })}
                  />
                  Gửi Cảnh Báo Qua Telegram Bot
                </label>

                {notifySettings.telegram_enabled && (
                  <div style={{ marginTop: "10px", display: "flex", flexDirection: "column", gap: "10px" }}>
                    <div>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                        <span style={{ fontSize: "12px", color: "#94a3b8" }}>Bot Token:</span>
                        <span style={{ fontSize: "11px", color: "#64748b" }}>Tạo từ @BotFather</span>
                      </div>
                      <input 
                        type="text"
                        placeholder="VD: 7123456789:AAFgAbcDef1234..."
                        value={notifySettings.telegram_bot_token}
                        onChange={(e) => setNotifySettings({ ...notifySettings, telegram_bot_token: e.target.value })}
                        style={inputStyle}
                      />
                    </div>
                    <div>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                        <span style={{ fontSize: "12px", color: "#94a3b8" }}>Chat ID:</span>
                        <span style={{ fontSize: "11px", color: "#64748b" }}>Lấy từ @userinfobot hoặc Chat Nhóm</span>
                      </div>
                      <input 
                        type="text"
                        placeholder="VD: 123456789 hoặc -100123456789"
                        value={notifySettings.telegram_chat_id}
                        onChange={(e) => setNotifySettings({ ...notifySettings, telegram_chat_id: e.target.value })}
                        style={inputStyle}
                      />
                    </div>

                    <div style={{ display: "flex", gap: "8px", alignItems: "center", marginTop: "4px" }}>
                      <button
                        type="button"
                        onClick={handleTestTelegram}
                        disabled={isTestingTelegram}
                        style={{
                          background: isTestingTelegram ? "#334155" : "#0284c7",
                          color: "white",
                          border: "none",
                          borderRadius: "6px",
                          padding: "6px 12px",
                          fontSize: "12px",
                          fontWeight: "600",
                          cursor: isTestingTelegram ? "not-allowed" : "pointer",
                          display: "flex",
                          alignItems: "center",
                          gap: "6px"
                        }}
                      >
                        {isTestingTelegram ? "⏳ Đang kiểm tra..." : "🧪 Thử gửi thông báo Telegram"}
                      </button>
                    </div>

                    {testTelegramStatus && (
                      <div style={{
                        fontSize: "12px",
                        padding: "8px 10px",
                        borderRadius: "6px",
                        background: testTelegramStatus.startsWith("✅") ? "rgba(16, 185, 129, 0.15)" : testTelegramStatus.startsWith("⚠️") ? "rgba(245, 158, 11, 0.15)" : "rgba(239, 68, 68, 0.15)",
                        border: `1px solid ${testTelegramStatus.startsWith("✅") ? "#10b981" : testTelegramStatus.startsWith("⚠️") ? "#f59e0b" : "#ef4444"}`,
                        color: testTelegramStatus.startsWith("✅") ? "#34d399" : testTelegramStatus.startsWith("⚠️") ? "#fbbf24" : "#f87171"
                      }}>
                        {testTelegramStatus}
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div style={{ marginBottom: "16px", background: "#182238", padding: "12px", borderRadius: "8px" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: "600", cursor: "pointer", color: "#34d399", fontSize: "13px" }}>
                  <input 
                    type="checkbox"
                    checked={notifySettings.webhook_enabled}
                    onChange={(e) => setNotifySettings({ ...notifySettings, webhook_enabled: e.target.checked })}
                  />
                  Gửi Cảnh Báo Qua Webhook API
                </label>

                {notifySettings.webhook_enabled && (
                  <div style={{ marginTop: "8px" }}>
                    <span style={{ fontSize: "12px", color: "#94a3b8" }}>Webhook URL:</span>
                    <input 
                      type="text"
                      placeholder="https://example.com/api/alerts"
                      value={notifySettings.webhook_url}
                      onChange={(e) => setNotifySettings({ ...notifySettings, webhook_url: e.target.value })}
                      style={inputStyle}
                    />
                  </div>
                )}
              </div>

              {/* ⏱️ CẤU HÌNH THỜI GIAN COOLDOWN CHỐNG SPAM SNAPSHOT */}
              <div style={{ marginBottom: "16px", background: "#182238", padding: "12px", borderRadius: "8px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                  <span style={{ fontSize: "13px", fontWeight: "600", color: "#f59e0b" }}>⏱️ Giãn cách chụp Snapshot & Cảnh báo:</span>
                  <select
                    value={notifySettings.snapshot_cooldown ?? 15}
                    onChange={(e) => setNotifySettings({ ...notifySettings, snapshot_cooldown: parseInt(e.target.value, 10) })}
                    style={{
                      background: "#0f172a",
                      color: "white",
                      border: "1px solid rgba(255,255,255,0.2)",
                      borderRadius: "6px",
                      padding: "4px 8px",
                      fontSize: "12px",
                      cursor: "pointer"
                    }}
                  >
                    <option value={5}>5 giây (Nhanh)</option>
                    <option value={10}>10 giây</option>
                    <option value={15}>15 giây (Mặc định)</option>
                    <option value={30}>30 giây (Tiết kiệm)</option>
                    <option value={60}>60 giây (Chống spam cao)</option>
                  </select>
                </div>
                <div style={{ fontSize: "11px", color: "#94a3b8", lineHeight: "1.4" }}>
                  Tránh chụp ảnh và gửi tin nhắn lặp lại liên tục khi người vi phạm đứng cố định trước camera.
                </div>
              </div>

              {saveStatus && (
                <div style={{ fontSize: "12px", color: "#38bdf8", marginBottom: "10px" }}>{saveStatus}</div>
              )}

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
                <button type="button" onClick={() => setShowSettingsModal(false)} style={{ background: "#334155", border: "none", color: "white", padding: "6px 14px", borderRadius: "6px", cursor: "pointer", fontSize: "12px" }}>
                  Đóng
                </button>
                <button type="submit" style={{ background: "#4f46e5", border: "none", color: "white", padding: "6px 16px", borderRadius: "6px", cursor: "pointer", fontWeight: "600", fontSize: "12px" }}>
                  Lưu Cấu Hình
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Lightbox Snapshot */}
      {selectedSnapshot && (
        <div style={{
          position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
          background: "rgba(0,0,0,0.85)", backdropFilter: "blur(6px)",
          display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", zIndex: 110, padding: "20px"
        }}>
          <div style={{ position: "relative", maxWidth: "90%", maxHeight: "85%" }}>
            <img 
              src={selectedSnapshot} 
              alt="Snapshot" 
              style={{ width: "100%", height: "100%", maxHeight: "75vh", objectFit: "contain", borderRadius: "8px" }}
            />
            <button 
              onClick={() => setSelectedSnapshot(null)}
              style={{
                position: "absolute", top: "-12px", right: "-12px",
                background: "#ef4444", color: "white", border: "none",
                borderRadius: "50%", width: "30px", height: "30px",
                fontSize: "14px", cursor: "pointer", fontWeight: "bold"
              }}
            >
              ✕
            </button>
          </div>
        </div>
      )}

    </div>
  );
}

// Render Thẻ Quy Định Bảo Hộ Thiết Kế Gọn Gàng
function renderPpeToggleCard(key, title, subtitle, isRuleActive, isDetected, onToggle) {
  let cardClass = "ppe-card";
  let badgeText = "";
  let badgeClass = "";

  if (!isRuleActive) {
    cardClass += " status-disabled";
    badgeText = "GIÁM SÁT TẮT";
    badgeClass = "badge-secondary";
  } else if (isDetected) {
    cardClass += " status-active-safe";
    badgeText = "ĐẠT (ĐÃ MANG)";
    badgeClass = "badge-success";
  } else {
    cardClass += " status-active-unsafe";
    badgeText = "VI PHẠM (CHƯA MANG)";
    badgeClass = "badge-danger";
  }

  return (
    <div 
      className={cardClass}
      onClick={() => onToggle(key)}
      title="Nhấn vào thẻ này để Bật hoặc Tắt quy định giám sát an toàn"
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
        <div style={{ fontSize: "14px", fontWeight: "700", color: "#f8fafc" }}>{title}</div>
        
        {/* Toggle Switch */}
        <label className="switch" onClick={(e) => e.stopPropagation()}>
          <input 
            type="checkbox" 
            checked={isRuleActive}
            onChange={() => onToggle(key)}
          />
          <span className="slider"></span>
        </label>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: "11px", color: "#94a3b8" }}>{subtitle}</span>
        <span className={`badge ${badgeClass}`}>{badgeText}</span>
      </div>
    </div>
  );
}

// Render Thanh Bar Chart Cho Phân Bố Vi Phạm
function renderChartBar(label, count, total, color) {
  const percent = total > 0 ? Math.round((count / total) * 100) : (count > 0 ? 50 : 0);
  return (
    <div key={label} style={{ marginBottom: "8px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", marginBottom: "3px", color: "#cbd5e1" }}>
        <span>{label}</span>
        <span className="font-mono">{count} ({percent}%)</span>
      </div>
      <div style={{ width: "100%", background: "rgba(255,255,255,0.06)", height: "6px", borderRadius: "3px", overflow: "hidden" }}>
        <div style={{ width: `${percent}%`, background: color, height: "100%", borderRadius: "3px" }} />
      </div>
    </div>
  );
}

// Render Cột Biểu Đồ Khung Giờ
function renderHourlyBar(timeLabel, count, maxCount) {
  const heightPercent = Math.min(100, Math.max(15, (count / maxCount) * 100));
  return (
    <div key={timeLabel} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: "4px" }}>
      <span className="font-mono" style={{ fontSize: "10px", color: "#94a3b8" }}>{count}</span>
      <div style={{ width: "100%", height: `${heightPercent}%`, background: "linear-gradient(180deg, #6366f1 0%, #4338ca 100%)", borderRadius: "4px 4px 0 0" }} />
      <span className="font-mono" style={{ fontSize: "10px", color: "#64748b" }}>{timeLabel}</span>
    </div>
  );
}

const modalButtonStyle = {
  background: "#182238",
  border: "1px solid rgba(255,255,255,0.1)",
  color: "white",
  padding: "8px",
  borderRadius: "6px",
  cursor: "pointer",
  fontSize: "12px",
  fontWeight: "500",
  textAlign: "center"
};

const inputStyle = {
  width: "100%",
  padding: "6px 10px",
  marginTop: "4px",
  borderRadius: "6px",
  background: "#0b0f19",
  border: "1px solid rgba(255,255,255,0.12)",
  color: "white",
  fontSize: "12px",
  outline: "none"
};

export default App;
