import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.lines import Line2D

# Configure font and quality
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['axes.edgecolor'] = '#D3D3D3'

def draw_architecture_diagram():
    fig, ax = plt.subplots(figsize=(14, 10), dpi=300)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10)
    ax.axis('off')
    
    # Title
    ax.text(7, 9.6, 'SƠ ĐỒ KIẾN TRÚC TỔNG THỂ HỆ THỐNG AI SAFETY MONITOR', 
            ha='center', va='center', fontsize=15, fontweight='bold', color='#1B365D')
    ax.text(7, 9.2, 'Enterprise Modular Multi-Layered Architecture for Real-Time Safety Surveillance', 
            ha='center', va='center', fontsize=10, style='italic', color='#555555')

    # Color Palette
    bg_colors = ['#EBF3FA', '#E8F5E9', '#FFF3E0', '#F3E5F5', '#E0F2F1']
    header_colors = ['#1B365D', '#2E7D32', '#E65100', '#6A1B9A', '#00695C']
    
    layers = [
        ("TẦNG 1: NGUỒN DỮ LIỆU ĐẦU VÀO (INPUT & CAPTURE LAYER)", 7.8, 1.0, [
            ("Webcam USB / Laptop\n(Direct Video Index 0/1)", 0.8, 2.8),
            ("Camera IP Công trường\n(RTSP Stream H.264/H.265)", 4.0, 3.0),
            ("Tệp Video / Ảnh kiểm thử\n(.mp4, .avi, .jpg, .png)", 7.4, 3.0),
            ("Bộ dữ liệu Giả lập\n(Mock Dataset Stream)", 10.8, 2.4)
        ], bg_colors[0], header_colors[0]),
        
        ("TẦNG 2: XỬ LÝ TRÍ TUỆ NHÂN TẠO & THEO DÕI (AI INFERENCE & TRACKING PIPELINE)", 6.0, 1.4, [
            ("Khung hình BGR\n(OpenCV Frame Grabber)", 0.8, 2.5),
            ("Tiền xử lý & Chuẩn hóa\n(Resize 640x640, RGB Tensor)", 3.7, 3.0),
            ("YOLO11s PPE Inference\n(10 Lớp Safe / Unsafe ~10.3ms)", 7.1, 3.2),
            ("ByteTrack Tracking Engine\n(Multi-Object Track ID)", 10.7, 2.5)
        ], bg_colors[1], header_colors[1]),
        
        ("TẦNG 3: LOGIC NGHIỆP VỤ & QUY TẮC AN TOÀN (BUSINESS LOGIC & SAFETY ENGINE)", 4.2, 1.4, [
            ("Kiểm tra Quy tắc An toàn\n(Dynamic Rules: Mũ, Áo, Găng, Ủng)", 0.8, 3.6),
            ("Bộ lọc Khử trùng lặp Vi phạm\n(Spatial Deduplication & Cooldown)", 4.8, 4.0),
            ("Quản lý Bằng chứng Snapshot\n(Auto Crop, Timestamp & BBox Stamp)", 9.2, 4.0)
        ], bg_colors[2], header_colors[2]),
        
        ("TẦNG 4: LƯU TRỮ DỮ LIỆU & TRUYỀN THÔNG (DATA PERSISTENCE & SERVICES)", 2.4, 1.4, [
            ("PostgreSQL CSDL Quan hệ\n(Violations, Rules, Audit Logs)", 0.8, 3.0),
            ("In-Memory Fallback Cache\n(Đảm bảo High Availability)", 4.2, 2.8),
            ("Thư mục Lưu Bằng chứng\n(/data/violations/YYYY-MM-DD)", 7.4, 3.2),
            ("Trích xuất Báo cáo Nghiệm thu\n(OpenPyXL Excel / CSV Engine)", 11.0, 2.2)
        ], bg_colors[3], header_colors[3]),
        
        ("TẦNG 5: TRUYỀN TẢI & GIAO DIỆN NGƯỜI DÙNG (PRESENTATION & INTEGRATION)", 0.6, 1.4, [
            ("WebSocket Stream Gateway\n(FastAPI Server Latency < 50ms)", 0.8, 3.6),
            ("Giao diện Dashboard Giám sát\n(React + Vite Dark Mode UI)", 4.8, 4.2),
            ("Kênh Cảnh báo Tức thời\n(Telegram Bot API & Webhooks)", 9.4, 3.8)
        ], bg_colors[4], header_colors[4])
    ]

    for title, y_top, height, items, bg_col, h_col in layers:
        # Layer Container
        rect = patches.FancyBboxPatch((0.5, y_top - height), 13.0, height + 0.15,
                                      boxstyle="round,pad=0.08,rounding_size=0.15",
                                      facecolor=bg_col, edgecolor=h_col, linewidth=1.5, alpha=0.9)
        ax.add_patch(rect)
        
        # Layer Header Banner
        header_rect = patches.FancyBboxPatch((0.5, y_top), 13.0, 0.35,
                                             boxstyle="round,pad=0.02,rounding_size=0.1",
                                             facecolor=h_col, edgecolor=h_col, linewidth=1)
        ax.add_patch(header_rect)
        ax.text(7, y_top + 0.17, title, ha='center', va='center', fontsize=9.5, fontweight='bold', color='#FFFFFF')
        
        # Inner Component Boxes
        for item_text, x_pos, width in items:
            box = patches.FancyBboxPatch((x_pos, y_top - height + 0.1), width, height - 0.25,
                                         boxstyle="round,pad=0.05,rounding_size=0.1",
                                         facecolor='#FFFFFF', edgecolor='#B0BEC5', linewidth=1.2)
            ax.add_patch(box)
            ax.text(x_pos + width/2, y_top - height/2 + 0.05, item_text,
                    ha='center', va='center', fontsize=8.5, color='#263238', fontweight='bold', multialignment='center')

    # Draw Inter-layer Flow Arrows
    arrow_props = dict(facecolor='#1B365D', edgecolor='#1B365D', width=1.5, headwidth=6, headlength=6, shrink=0.05)
    for y_arrow in [7.7, 5.9, 4.1, 2.3]:
        ax.annotate('', xy=(7, y_arrow - 0.2), xytext=(7, y_arrow + 0.1), arrowprops=arrow_props)
        ax.annotate('', xy=(3, y_arrow - 0.2), xytext=(3, y_arrow + 0.1), arrowprops=arrow_props)
        ax.annotate('', xy=(11, y_arrow - 0.2), xytext=(11, y_arrow + 0.1), arrowprops=arrow_props)

    plt.tight_layout()
    plt.savefig('architecture_diagram.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("architecture_diagram.png generated successfully.")

def draw_data_flow_diagram():
    fig, ax = plt.subplots(figsize=(14, 9), dpi=300)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 9)
    ax.axis('off')
    
    ax.text(7, 8.6, 'SƠ ĐỒ LUỒNG DỮ LIỆU (DATA FLOW DIAGRAM - DFD CẤP 1)', 
            ha='center', va='center', fontsize=15, fontweight='bold', color='#1B365D')
    ax.text(7, 8.2, 'Quy trình thu nhận, suy luận AI, lưu vết vi phạm và phát tán cảnh báo đa kênh', 
            ha='center', va='center', fontsize=10, style='italic', color='#555555')

    # External Entities
    entities = [
        ("CAMERA GIÁM SÁT\n(Webcam / RTSP)", 0.6, 6.0, 2.2, 1.2, '#E3F2FD', '#1565C0'),
        ("CÁN BỘ AN TOÀN\n(Safety Supervisor)", 11.2, 6.0, 2.2, 1.2, '#E8F5E9', '#2E7D32'),
        ("QUẢN TRỊ VIÊN\n(Administrator)", 11.2, 1.5, 2.2, 1.2, '#FFF3E0', '#E65100'),
        ("TELEGRAM BOT API\n(Async Webhook)", 0.6, 1.5, 2.2, 1.2, '#F3E5F5', '#7B1FA2')
    ]
    for name, x, y, w, h, bg, border in entities:
        rect = patches.Rectangle((x, y), w, h, facecolor=bg, edgecolor=border, linewidth=2)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2, name, ha='center', va='center', fontsize=9, fontweight='bold', color=border, multialignment='center')

    # Processes (Circles/Rounded)
    processes = [
        ("1.0\nThu nhận &\nGiải mã Video", 3.8, 6.2, 1.8, 1.0, '#BBDEFB', '#0D47A1'),
        ("2.0\nSuy luận YOLO11s\n& ByteTrack ID", 6.2, 6.2, 2.0, 1.0, '#C8E6C9', '#1B5E20'),
        ("3.0\nĐánh giá Quy tắc\n& Khử trùng lặp", 8.8, 6.2, 2.0, 1.0, '#FFE0B2', '#E65100'),
        ("4.0\nLưu Snapshot\n& Ghi CSDL", 7.5, 3.8, 2.2, 1.0, '#E1BEE7', '#4A148C'),
        ("5.0\nPhát Cảnh báo\nTelegram / Web", 4.0, 3.8, 2.2, 1.0, '#B2DFDB', '#004D40'),
        ("6.0\nXuất Báo cáo\nExcel / CSV", 7.5, 1.5, 2.2, 1.0, '#CFD8DC', '#37474F')
    ]
    for name, x, y, w, h, bg, border in processes:
        rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08,rounding_size=0.2",
                                      facecolor=bg, edgecolor=border, linewidth=1.8)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2, name, ha='center', va='center', fontsize=8.5, fontweight='bold', color=border, multialignment='center')

    # Data Stores
    stores = [
        ("D1: Bằng chứng Snapshot (/data/violations/)", 0.6, 4.0, 2.8, 0.7),
        ("D2: CSDL Vi phạm & Cấu hình (PostgreSQL)", 4.0, 2.5, 3.2, 0.7)
    ]
    for name, x, y, w, h in stores:
        line1 = Line2D([x, x + w], [y + h, y + h], color='#37474F', linewidth=2)
        line2 = Line2D([x, x + w], [y, y], color='#37474F', linewidth=2)
        ax.add_line(line1)
        ax.add_line(line2)
        ax.fill_between([x, x + w], y, y + h, color='#ECEFF1')
        ax.text(x + w/2, y + h/2, name, ha='center', va='center', fontsize=8, fontweight='bold', color='#263238')

    # Draw Connections
    def draw_flow(x1, y1, x2, y2, label="", rad=0.0):
        ax.annotate(label, xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color="#37474F", lw=1.5,
                                    connectionstyle=f"arc3,rad={rad}"),
                    fontsize=7.5, color="#1A237E", fontweight='bold',
                    ha='center', va='center',
                    bbox=dict(boxstyle="round,pad=0.2", fc="#FFFFFF", ec="none", alpha=0.8) if label else None)

    draw_flow(2.8, 6.6, 3.8, 6.6, "Khung hình thô")
    draw_flow(5.6, 6.7, 6.2, 6.7, "RGB Tensor")
    draw_flow(8.2, 6.7, 8.8, 6.7, "BBoxes & TrackID")
    draw_flow(10.8, 6.7, 11.2, 6.7, "Live Stream + BBox")
    draw_flow(9.5, 6.2, 8.6, 4.8, "Sự kiện Vi phạm mới")
    draw_flow(7.5, 4.3, 3.4, 4.3, "Lưu file JPEG")
    draw_flow(7.5, 3.8, 5.6, 3.2, "Insert Record")
    draw_flow(7.5, 4.3, 6.2, 4.3, "Kích hoạt Cảnh báo")
    draw_flow(4.0, 4.3, 2.8, 2.2, "Gửi Tin + Snapshot")
    draw_flow(5.1, 4.8, 11.2, 6.3, "Alert Flash / Sound", rad=-0.2)
    draw_flow(11.2, 2.0, 9.7, 2.0, "Yêu cầu Xuất Báo cáo")
    draw_flow(7.5, 2.0, 5.6, 2.5, "Query Logs")
    draw_flow(8.6, 2.5, 11.2, 5.8, "Tải tệp .xlsx", rad=0.2)
    draw_flow(11.2, 1.8, 7.2, 2.8, "Cập nhật Quy tắc", rad=-0.1)

    plt.tight_layout()
    plt.savefig('data_flow_diagram.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("data_flow_diagram.png generated successfully.")

def draw_usecase_diagram():
    fig, ax = plt.subplots(figsize=(15, 11), dpi=300)
    ax.set_xlim(0, 15)
    ax.set_ylim(0, 11)
    ax.axis('off')

    ax.text(7.5, 10.6, 'SƠ ĐỒ USE CASE TỔNG THỂ HỆ THỐNG AI SAFETY MONITOR', 
            ha='center', va='center', fontsize=16, fontweight='bold', color='#1B365D')
    ax.text(7.5, 10.2, 'Mô hình hóa tương tác giữa 3 Tác nhân và 12 Chức năng cốt lõi theo 5 Phân hệ', 
            ha='center', va='center', fontsize=10.5, style='italic', color='#555555')

    # System Boundary
    boundary = patches.FancyBboxPatch((3.2, 0.4), 8.6, 9.5, boxstyle="round,pad=0.1,rounding_size=0.2",
                                     facecolor='#FAFAFA', edgecolor='#1B365D', linewidth=2.5, linestyle='--')
    ax.add_patch(boundary)
    ax.text(7.5, 9.6, 'HỆ THỐNG GIÁM SÁT AN TOÀN LAO ĐỘNG (AI SAFETY MONITOR)', 
            ha='center', va='center', fontsize=11, fontweight='bold', color='#1B365D')

    # Subsystems
    subsystems = [
        ("PHÂN HỆ GIÁM SÁT & CẢNH BÁO TỨC THỜI", 3.5, 7.2, 8.0, 2.1, '#E3F2FD'),
        ("PHÂN HỆ NHẬT KÝ VI PHẠM & BÁO CÁO", 3.5, 4.9, 8.0, 2.1, '#E8F5E9'),
        ("PHÂN HỆ CẤU HÌNH QUY TẮC & KÊNH BÁO ĐỘNG", 3.5, 2.7, 8.0, 2.0, '#FFF3E0'),
        ("PHÂN HỆ QUẢN TRỊ & KIỂM TOÁN", 3.5, 0.6, 8.0, 1.9, '#F3E5F5')
    ]
    for title, x, y, w, h, bg in subsystems:
        rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08,rounding_size=0.15",
                                      facecolor=bg, edgecolor='#B0BEC5', linewidth=1.2, alpha=0.7)
        ax.add_patch(rect)
        ax.text(x + 0.2, y + h - 0.25, title, ha='left', va='center', fontsize=8.5, fontweight='bold', color='#37474F')

    # Use Cases (Ovals)
    usecases = {
        'UC01': ("UC-01: Giám sát luồng video thời gian thực\n(Live Stream Surveillance)", 5.2, 8.7, 3.0, 0.65),
        'UC02': ("UC-02: Xem checklist & chỉ số KPI tức thời\n(Real-time PPE KPI & Checklist)", 9.2, 8.7, 3.0, 0.65),
        'UC03': ("UC-03: Tiếp nhận cảnh báo đa kênh tức thời\n(Multi-channel Instant Alerting)", 7.2, 7.7, 3.2, 0.65),
        
        'UC04': ("UC-04: Tra cứu & lọc nhật ký vi phạm\n(Query & Filter Violation Logs)", 5.2, 6.3, 3.0, 0.65),
        'UC05': ("UC-05: Xem ảnh snapshot bằng chứng\n(View Evidence Snapshot Lightbox)", 9.2, 6.3, 3.0, 0.65),
        'UC06': ("UC-06: Xác nhận & xử lý sự cố vi phạm\n(Resolve Violation Event Status)", 5.2, 5.3, 3.0, 0.65),
        'UC07': ("UC-07: Xuất báo cáo thống kê Excel / CSV\n(Export Safety Reports .xlsx)", 9.2, 5.3, 3.0, 0.65),
        
        'UC08': ("UC-08: Cấu hình quy tắc kiểm tra PPE\n(Dynamic PPE Inspection Rules)", 5.2, 3.7, 3.0, 0.65),
        'UC09': ("UC-09: Cấu hình Telegram & Webhook\n(Notification Bot & Cooldown)", 9.2, 3.7, 3.0, 0.65),
        'UC10': ("UC-10: Quản lý & đổi nguồn Camera\n(Source Selector: RTSP / Cam / Mock)", 7.2, 3.0, 3.4, 0.60),
        
        'UC11': ("UC-11: Quản lý người dùng & phân quyền\n(User Management & RBAC)", 5.4, 1.8, 3.2, 0.65),
        'UC12': ("UC-12: Tra cứu nhật ký kiểm toán hệ thống\n(Audit Trail Log Inspection)", 9.2, 1.8, 3.0, 0.65),
        
        'UCAI': ("UC-AI: Tự động phát hiện YOLO11s,\nByteTrack & Khử trùng lặp Snapshot", 7.2, 1.0, 3.6, 0.65)
    }

    for ucid, (text, cx, cy, w, h) in usecases.items():
        ellipse = patches.Ellipse((cx, cy), w, h, facecolor='#FFFFFF', edgecolor='#1565C0', linewidth=1.5)
        ax.add_patch(ellipse)
        ax.text(cx, cy, text, ha='center', va='center', fontsize=7.5, color='#0D47A1', fontweight='bold', multialignment='center')

    # Draw Actors
    def draw_actor(ax, cx, cy, label, color):
        # Head
        ax.add_patch(patches.Circle((cx, cy + 0.35), 0.2, facecolor=color, edgecolor='#000000', linewidth=1.2))
        # Body
        ax.plot([cx, cx], [cy + 0.15, cy - 0.25], color='#000000', lw=2)
        # Arms
        ax.plot([cx - 0.3, cx + 0.3], [cy + 0.05, cy + 0.05], color='#000000', lw=2)
        # Legs
        ax.plot([cx, cx - 0.25], [cy - 0.25, cy - 0.6], color='#000000', lw=2)
        ax.plot([cx, cx + 0.25], [cy - 0.25, cy - 0.6], color='#000000', lw=2)
        # Text
        ax.text(cx, cy - 0.85, label, ha='center', va='top', fontsize=9, fontweight='bold', color=color, multialignment='center')

    draw_actor(ax, 1.5, 7.5, "CÁN BỘ AN TOÀN\n(Safety Officer)", '#1565C0')
    draw_actor(ax, 1.5, 2.8, "QUẢN TRỊ VIÊN\n(System Admin)", '#E65100')
    draw_actor(ax, 13.5, 4.5, "AI ENGINE WORKER\n(System Engine)", '#2E7D32')

    # Connecting Lines
    def connect_actor_uc(x_act, y_act, ucid):
        cx, cy = usecases[ucid][1], usecases[ucid][2]
        ax.plot([x_act, cx], [y_act, cy], color='#78909C', lw=1.2, linestyle='-')

    # Safety Officer lines
    for uc in ['UC01', 'UC02', 'UC03', 'UC04', 'UC05', 'UC06', 'UC07', 'UC10']:
        connect_actor_uc(1.8, 7.5, uc)

    # Admin lines
    for uc in ['UC01', 'UC04', 'UC07', 'UC08', 'UC09', 'UC10', 'UC11', 'UC12']:
        connect_actor_uc(1.8, 2.8, uc)

    # AI Engine lines
    for uc in ['UC01', 'UC03', 'UCAI']:
        connect_actor_uc(13.2, 4.5, uc)

    plt.tight_layout()
    plt.savefig('usecase_diagram.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("usecase_diagram.png generated successfully.")

if __name__ == "__main__":
    draw_architecture_diagram()
    draw_data_flow_diagram()
    draw_usecase_diagram()
