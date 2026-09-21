import os
import sys
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def apply_cell_styling(cell, bg_color=None, top_b=None, bottom_b=None, left_b=None, right_b=None, sz="4",
                       top_m=100, bottom_m=100, left_m=140, right_m=140):
    """
    Áp dụng màu nền, viền và padding theo đúng thứ tự schema OpenXML w:tcPr:
    1. w:tcW
    2. w:tcBorders
    3. w:shd
    4. w:tcMar
    5. w:vAlign
    """
    tcPr = cell._tc.get_or_add_tcPr()
    
    # Lấy hoặc giữ nguyên tcW nếu có
    tcW = tcPr.find(qn('w:tcW'))
    
    # Xóa sạch tcPr hiện tại để tái tạo theo đúng thứ tự
    for child in list(tcPr):
        tcPr.remove(child)
        
    if tcW is not None:
        tcPr.append(tcW)
        
    # 1. w:tcBorders (top, left, bottom, right)
    if top_b or bottom_b or left_b or right_b:
        top_xml = f'<w:top w:val="single" w:sz="{sz}" w:space="0" w:color="{top_b}"/>' if top_b else '<w:top w:val="none"/>'
        left_xml = f'<w:left w:val="single" w:sz="{sz}" w:space="0" w:color="{left_b}"/>' if left_b else '<w:left w:val="none"/>'
        bottom_xml = f'<w:bottom w:val="single" w:sz="{sz}" w:space="0" w:color="{bottom_b}"/>' if bottom_b else '<w:bottom w:val="none"/>'
        right_xml = f'<w:right w:val="single" w:sz="{sz}" w:space="0" w:color="{right_b}"/>' if right_b else '<w:right w:val="none"/>'
        
        tcBorders = parse_xml(f'''
            <w:tcBorders {nsdecls("w")}>
                {top_xml}
                {left_xml}
                {bottom_xml}
                {right_xml}
            </w:tcBorders>
        ''')
        tcPr.append(tcBorders)
        
    # 2. w:shd
    if bg_color:
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:val="clear" w:color="auto" w:fill="{bg_color}"/>')
        tcPr.append(shd)
        
    # 3. w:tcMar (top, left, bottom, right)
    if top_m or bottom_m or left_m or right_m:
        tcMar = parse_xml(f'''
            <w:tcMar {nsdecls("w")}>
                <w:top w:w="{top_m}" w:type="dxa"/>
                <w:left w:w="{left_m}" w:type="dxa"/>
                <w:bottom w:w="{bottom_m}" w:type="dxa"/>
                <w:right w:w="{right_m}" w:type="dxa"/>
            </w:tcMar>
        ''')
        tcPr.append(tcMar)
        
    # 4. w:vAlign
    vAlign = parse_xml(f'<w:vAlign {nsdecls("w")} w:val="center"/>')
    tcPr.append(vAlign)

def add_callout(doc, text_list, title="LƯU Ý QUAN TRỌNG / KEY HIGHLIGHTS"):
    """Tạo hộp Callout / Note box chuyên nghiệp."""
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.cell(0, 0)
    cell.width = Inches(6.4)
    apply_cell_styling(cell, bg_color="F0F4F8", left_b="1B365D", sz="24", top_m=140, bottom_m=140, left_m=200, right_m=200)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(3)
    r_title = p.add_run(f"📌 {title}\n")
    r_title.font.name = "Segoe UI"
    r_title.font.size = Pt(10)
    r_title.font.bold = True
    r_title.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)
    
    for line in text_list:
        p_line = cell.add_paragraph()
        p_line.paragraph_format.space_before = Pt(0)
        p_line.paragraph_format.space_after = Pt(2)
        r_line = p_line.add_run(line)
        r_line.font.name = "Segoe UI"
        r_line.font.size = Pt(9.5)
        r_line.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
    
    p_end = doc.add_paragraph()
    p_end.paragraph_format.space_before = Pt(4)
    p_end.paragraph_format.space_after = Pt(4)

def format_table_headers(tbl, col_widths, headers, bg_color="1B365D", text_color=(0xFF, 0xFF, 0xFF)):
    """Định dạng hàng tiêu đề của bảng."""
    hdr_row = tbl.rows[0]
    for i, h_text in enumerate(headers):
        cell = hdr_row.cells[i]
        cell.width = col_widths[i]
        apply_cell_styling(cell, bg_color=bg_color, top_b=bg_color, bottom_b=bg_color, top_m=140, bottom_m=140, left_m=140, right_m=140)
        
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(h_text)
        r.font.name = "Segoe UI"
        r.font.size = Pt(9.5)
        r.font.bold = True
        r.font.color.rgb = RGBColor(*text_color)

def populate_table_rows(tbl, col_widths, data, align_cols=None):
    """Điền dữ liệu các hàng của bảng kèm màu xen kẽ."""
    for row_idx, row_data in enumerate(data):
        row = tbl.add_row()
        bg = "F9FAFB" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, text in enumerate(row_data):
            cell = row.cells[col_idx]
            cell.width = col_widths[col_idx]
            apply_cell_styling(cell, bg_color=bg, top_b="E5E7EB", bottom_b="E5E7EB", top_m=100, bottom_m=100, left_m=140, right_m=140)
            
            p = cell.paragraphs[0]
            if align_cols and col_idx in align_cols:
                p.alignment = align_cols[col_idx]
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = 1.15
            r = p.add_run(text)
            r.font.name = "Segoe UI"
            r.font.size = Pt(9)
            r.font.color.rgb = RGBColor(0x37, 0x41, 0x51)

def create_document():
    doc = docx.Document()
    
    # 1. Page Setup (A4, 2.54cm margins)
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)
        section.page_width = Inches(8.27)
        section.page_height = Inches(11.69)
        
        # Header / Footer
        footer = section.footer
        p_ft = footer.paragraphs[0]
        p_ft.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r_ft = p_ft.add_run("AI Safety Monitor - Báo cáo Phân tích & Thiết kế Hệ thống | Release 1.0.0")
        r_ft.font.name = "Segoe UI"
        r_ft.font.size = Pt(8.5)
        r_ft.font.color.rgb = RGBColor(0x9C, 0xA3, 0xAF)

    # 2. Cover Section
    p_top_meta = doc.add_paragraph()
    p_top_meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_inst = p_top_meta.add_run("BỘ GIÁO DỤC VÀ ĐÀO TẠO — TRƯỜNG ĐẠI HỌC CÔNG NGHỆ\nKHOA CÔNG NGHỆ THÔNG TIN\n")
    r_inst.font.name = "Segoe UI"
    r_inst.font.size = Pt(11)
    r_inst.font.bold = True
    r_inst.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)
    
    p_div = doc.add_paragraph()
    p_div.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_div = p_div.add_run("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    r_div.font.color.rgb = RGBColor(0x3B, 0x82, 0xF6)
    
    p_doc_type = doc.add_paragraph()
    p_doc_type.paragraph_format.space_before = Pt(36)
    p_doc_type.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_type = p_doc_type.add_run("TÀI LIỆU KIẾN TRÚC VÀ ĐẶC TẢ PHẦN MỀM\n(SOFTWARE ARCHITECTURE & USE CASE SPECIFICATION)\n")
    r_type.font.name = "Segoe UI"
    r_type.font.size = Pt(13)
    r_type.font.bold = True
    r_type.font.color.rgb = RGBColor(0x4B, 0x55, 0x63)

    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_before = Pt(12)
    p_title.paragraph_format.space_after = Pt(12)
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_t1 = p_title.add_run("PHÂN TÍCH VÀ THIẾT KẾ HỆ THỐNG\nGIÁM SÁT AN TOÀN LAO ĐỘNG BẰNG TRÍ TUỆ NHÂN TẠO THỜI GIAN THỰC\n")
    r_t1.font.name = "Segoe UI"
    r_t1.font.size = Pt(18)
    r_t1.font.bold = True
    r_t1.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)
    
    r_t2 = p_title.add_run("AI SAFETY MONITOR SYSTEM — REAL-TIME SURVEILLANCE")
    r_t2.font.name = "Segoe UI"
    r_t2.font.size = Pt(11.5)
    r_t2.font.bold = True
    r_t2.font.color.rgb = RGBColor(0x25, 0x63, 0xEB)

    p_meta_box = doc.add_paragraph()
    p_meta_box.paragraph_format.space_before = Pt(80)
    
    # Metadata Table
    meta_tbl = doc.add_table(rows=0, cols=2)
    meta_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    col_w = [Inches(2.2), Inches(4.2)]
    meta_data = [
        ("Đề tài tốt nghiệp:", "Hệ thống Giám sát An toàn Lao động Thông minh (PPE AI Monitor)"),
        ("Công nghệ cốt lõi:", "Python 3.11+, YOLO11s, ByteTrack, FastAPI, PostgreSQL, React Vite"),
        ("Tài liệu kỹ thuật:", "Sơ đồ Hệ thống, Mô hình Use Case & Đặc tả Chi tiết (IEEE/RUP)"),
        ("Phiên bản hệ thống:", "Release 1.0.0 (Hỗ trợ GPU CUDA + Fallback In-Memory Storage)"),
        ("Thời gian thực hiện:", "Năm học 2025 - 2026")
    ]
    for k, v in meta_data:
        row = meta_tbl.add_row()
        for idx, val in enumerate([k, v]):
            c = row.cells[idx]
            c.width = col_w[idx]
            apply_cell_styling(c, bg_color="F8FAFC", top_b="E2E8F0", bottom_b="E2E8F0", top_m=80, bottom_m=80, left_m=120, right_m=120)
            p = c.paragraphs[0]
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            r = p.add_run(val)
            r.font.name = "Segoe UI"
            r.font.size = Pt(9.5)
            if idx == 0:
                r.font.bold = True
                r.font.color.rgb = RGBColor(0x1E, 0x29, 0x3B)
            else:
                r.font.color.rgb = RGBColor(0x47, 0x55, 0x69)

    doc.add_page_break()

    # Helpers for Content Formatting
    def add_h1(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(20)
        p.paragraph_format.space_after = Pt(8)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(text)
        r.font.name = "Segoe UI"
        r.font.size = Pt(14)
        r.font.bold = True
        r.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)
        return p

    def add_h2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(5)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(text)
        r.font.name = "Segoe UI"
        r.font.size = Pt(12)
        r.font.bold = True
        r.font.color.rgb = RGBColor(0x1D, 0x4E, 0xD8)
        return p

    def add_body_p(text, bold_prefix=None):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.2
        if bold_prefix:
            rb = p.add_run(bold_prefix)
            rb.font.name = "Segoe UI"
            rb.font.size = Pt(10)
            rb.font.bold = True
            rb.font.color.rgb = RGBColor(0x1E, 0x29, 0x3B)
        r = p.add_run(text)
        r.font.name = "Segoe UI"
        r.font.size = Pt(10)
        r.font.color.rgb = RGBColor(0x33, 0x41, 0x55)
        return p

    def add_bullet_p(text, bold_prefix=None):
        p = doc.add_paragraph(style='List Bullet')
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.line_spacing = 1.15
        if bold_prefix:
            rb = p.add_run(bold_prefix)
            rb.font.name = "Segoe UI"
            rb.font.size = Pt(9.5)
            rb.font.bold = True
            rb.font.color.rgb = RGBColor(0x1E, 0x29, 0x3B)
        r = p.add_run(text)
        r.font.name = "Segoe UI"
        r.font.size = Pt(9.5)
        r.font.color.rgb = RGBColor(0x37, 0x41, 0x51)
        return p

    def add_image_figure(img_path, caption_text, width=Inches(6.2)):
        if os.path.exists(img_path):
            p_img = doc.add_paragraph()
            p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_img.paragraph_format.space_before = Pt(8)
            p_img.paragraph_format.space_after = Pt(4)
            p_img.add_run().add_picture(img_path, width=width)
            
            p_cap = doc.add_paragraph()
            p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_cap.paragraph_format.space_before = Pt(2)
            p_cap.paragraph_format.space_after = Pt(10)
            rc = p_cap.add_run(caption_text)
            rc.font.name = "Segoe UI"
            rc.font.size = Pt(9)
            rc.font.italic = True
            rc.font.bold = True
            rc.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)

    # =========================================================================
    # CHƯƠNG 1: TỔNG QUAN VÀ KIẾN TRÚC HỆ THỐNG
    # =========================================================================
    add_h1("CHƯƠNG 1: TỔNG QUAN VÀ KIẾN TRÚC HỆ THỐNG")
    
    add_h2("1.1. Mục tiêu và Phạm vi Nghiệp vụ")
    add_body_p("Trong môi trường thi công công trình xây dựng và sản xuất công nghiệp, việc đảm bảo người lao động chấp hành nghiêm túc quy định mang trang bị bảo hộ cá nhân (Personal Protective Equipment - PPE) là yếu tố sống còn nhằm phòng ngừa tai nạn lao động nghiêm trọng. Các phương pháp giám sát thủ công truyền thống bộc lộ nhiều điểm yếu: chi phí nhân sự lớn, không thể bao quát diện rộng và không phát cảnh báo tức thời 24/7. Hệ thống AI Safety Monitor được xây dựng như một giải pháp chuyển đổi số toàn diện dựa trên Thị giác máy tính (Computer Vision) và Trí tuệ nhân tạo (AI).")
    add_body_p("Mục tiêu trọng tâm của hệ thống bao gồm:")
    add_bullet_p("Nhận diện chính xác 10 lớp đối tượng PPE bao gồm 5 trang bị an toàn (helmet, vest, gloves, boots, goggles) và 5 trạng thái vi phạm tương ứng (no-helmet, no-vest, no-gloves, no-boots, no-goggles) với tốc độ cao (~10.3ms/frame).", "• Nhận diện PPE Đa lớp: ")
    add_bullet_p("Ứng dụng thuật toán ByteTrack kết hợp cơ chế Spatial-Temporal Deduplication nhằm duy trì ID theo dõi đối tượng, ngăn chặn tình trạng cảnh báo lặp lại (Alert Spamming) khi công nhân đứng cố định trong khung hình.", "• Khử trùng lặp Cảnh báo Thông minh: ")
    add_bullet_p("Tự động cắt và đóng dấu ảnh bằng chứng Snapshot, đồng thời gửi thông báo kèm ảnh ngay lập tức tới Cán bộ Quản lý qua ứng dụng Telegram Bot và Webhook HTTP trong chế độ bất đồng bộ.", "• Cảnh báo Đa kênh Thời gian thực: ")
    add_bullet_p("Cung cấp giao diện Web điều khiển thời gian thực (React + Vite) với luồng phát video WebSocket độ trễ thấp (< 50ms), hỗ trợ xuất báo cáo thống kê Excel đa kỳ phục vụ thanh tra an toàn.", "• Giám sát Trực quan & Báo cáo Nghiệm thu: ")

    add_h2("1.2. Sơ đồ Kiến trúc Hệ thống Tổng thể (System Architecture)")
    add_body_p("Hệ thống được thiết kế theo kiến trúc phân tầng doanh nghiệp (Enterprise Layered Architecture) chuẩn mực, phân tách rõ ràng trách nhiệm giữa tầng thu nhận dữ liệu, tầng xử lý AI, tầng logic nghiệp vụ, tầng lưu trữ dữ liệu và tầng hiển thị tương tác người dùng.")
    
    add_image_figure("architecture_diagram.png", "Hình 1.1: Sơ đồ Kiến trúc Tổng thể Phân tầng của Hệ thống AI Safety Monitor")

    add_body_p("Kiến trúc hệ thống bao gồm 5 phân tầng kỹ thuật liên kết chặt chẽ:")
    add_bullet_p("Hỗ trợ đa dạng nguồn cấp video đầu vào bao gồm Webcam tích hợp/USB (Index 0, 1), Camera IP công trường (chuẩn RTSP luồng H.264/H.265), tệp video kiểm thử (.mp4) và bộ tạo luồng giả lập (Mock Stream) phục vụ môi trường không có camera vật lý.", "1. Tầng Nguồn Dữ liệu (Input & Capture Layer): ")
    add_bullet_p("Thu nhận khung hình thô từ OpenCV, tiền xử lý chuẩn hóa RGB Tensor (640x640), nạp vào mạng nơ-ron tích chập YOLO11s thực thi suy luận với tốc độ trung bình 10.3ms/frame và gán định danh đối tượng qua thuật toán ByteTrack.", "2. Tầng Xử lý AI & Tracking (AI Inference Pipeline): ")
    add_bullet_p("So khớp danh sách phát hiện với cấu hình quy tắc an toàn động (Dynamic Safety Rules). Nếu phát hiện vi phạm mới, bộ lọc không gian - thời gian sẽ kiểm tra bộ nhớ đệm Cooldown (5 giây), kích hoạt module chụp ảnh Snapshot và điều phối cảnh báo.", "3. Tầng Logic Nghiệp vụ & An toàn (Business Logic & Safety Engine): ")
    add_bullet_p("Lưu trữ nhật ký sự kiện vi phạm vào CSDL PostgreSQL (kèm cơ chế Fallback In-Memory Cache tự động khi mất kết nối CSDL), lưu trữ tệp ảnh bằng chứng vào thư mục phân cấp ngày tháng (/data/violations/YYYY-MM-DD) và tạo file Excel (.xlsx 3 sheet) bằng OpenPyXL.", "4. Tầng Dữ liệu & Lưu trữ Bền vững (Data Persistence & Services): ")
    add_bullet_p("Truyền phát luồng video nén JPEG Base64 qua WebSocket (FastAPI) độ trễ cực thấp, cung cấp RESTful API và giao diện Dashboard giám sát Dark Mode chuyên nghiệp (React + Vite).", "5. Tầng Truyền thông & Giao diện (Presentation & Integration): ")

    add_h2("1.3. Sơ đồ Luồng Dữ liệu (Data Flow Diagram - DFD Cấp 1)")
    add_body_p("Sơ đồ luồng dữ liệu DFD Cấp 1 mô tả chi tiết dòng dịch chuyển của thông tin và khung hình từ lúc camera ghi nhận hình ảnh cho đến khi kết quả được phân tích, lưu trữ và phản hồi tới người dùng.")
    
    add_image_figure("data_flow_diagram.png", "Hình 1.2: Sơ đồ Luồng Dữ liệu (DFD Cấp 1) Hệ thống Giám sát An toàn Lao động")

    add_body_p("Quy trình luân chuyển dữ liệu qua 6 tiến trình cốt lõi:")
    add_bullet_p("Camera gửi chuỗi khung hình thô (Raw Frames) tới Tiến trình 1.0 để giải mã thành mảng ma trận điểm ảnh BGR.", "• Tiến trình 1.0 (Thu nhận & Giải mã Video): ")
    add_bullet_p("Khung hình được chuyển đổi không gian màu RGB, chuẩn hóa kích thước 640x640 và nạp vào mô hình YOLO11s. Kết quả suy luận (Bounding Boxes, Classes, Scores) được ByteTrack gán Track ID liên tục.", "• Tiến trình 2.0 (Suy luận YOLO11s & ByteTrack): ")
    add_bullet_p("So sánh các vi phạm phát hiện với cấu hình quy tắc an toàn đang kích hoạt. Thuật toán kiểm tra lịch sử theo dõi đối tượng để loại bỏ các vi phạm trùng lặp từ cùng một công nhân.", "• Tiến trình 3.0 (Đánh giá Quy tắc & Khử trùng lặp): ")
    add_bullet_p("Cắt khung hình chứa vi phạm, vẽ hộp giới hạn và đóng dấu mốc thời gian, lưu tệp ảnh JPEG vào Kho lưu trữ D1 và chèn bản ghi vi phạm vào CSDL D2.", "• Tiến trình 4.0 (Lưu Snapshot & Ghi CSDL): ")
    add_bullet_p("Kích hoạt tác vụ bất đồng bộ gửi cảnh báo qua Telegram Bot API và phát tín hiệu cảnh báo thị giác / âm thanh lên giao diện web của Cán bộ An toàn.", "• Tiến trình 5.0 (Phát Cảnh báo Đa kênh): ")
    add_bullet_p("Tiếp nhận yêu cầu từ Cán bộ An toàn / Quản trị viên, truy vấn CSDL D2 và biên dịch thành tệp bảng tính Excel đa sheet hoặc CSV.", "• Tiến trình 6.0 (Xuất Báo cáo Excel / CSV): ")

    # =========================================================================
    # CHƯƠNG 2: THIẾT KẾ USE CASE HỆ THỐNG
    # =========================================================================
    add_h1("CHƯƠNG 2: THIẾT KẾ USE CASE HỆ THỐNG")
    
    add_h2("2.1. Xác định các Tác nhân (Actors) trong Hệ thống")
    add_body_p("Hệ thống xác định 3 tác nhân chính tham gia tương tác và vận hành hệ thống:")
    
    act_tbl = doc.add_table(rows=1, cols=3)
    act_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    act_widths = [Inches(1.8), Inches(1.2), Inches(3.4)]
    format_table_headers(act_tbl, act_widths, ["Tác nhân (Actor)", "Phân loại", "Vai trò và Trách nhiệm chính trong Hệ thống"])
    
    act_data = [
        ["Cán bộ An toàn\n(Safety Officer)", "Human\n(Primary)", "• Giám sát trực tiếp luồng camera thời gian thực (Live CCTV Stream).\n• Nhận thông báo và ảnh vi phạm tức thời qua Telegram Bot / Webhook.\n• Tra cứu nhật ký, phóng to xem ảnh snapshot bằng chứng.\n• Xác nhận, đánh dấu trạng thái xử lý sự cố vi phạm an toàn.\n• Trích xuất và tải về báo cáo thống kê định kỳ (.xlsx / .csv)."],
        ["Quản trị viên Hệ thống\n(System Admin)", "Human\n(Secondary)", "• Quản lý tài khoản, phân quyền truy cập người dùng (RBAC).\n• Quản lý danh mục khu vực thi công và nguồn camera (Webcam/RTSP).\n• Cấu hình các quy tắc an toàn PPE bắt buộc theo từng phân xưởng.\n• Thiết lập kết nối kênh cảnh báo (Telegram Bot Token, Chat ID, Webhook).\n• Cấu hình thời gian giãn cách chụp ảnh (Cooldown) và kiểm tra Audit Logs."],
        ["AI Processing Engine\n(System Worker)", "System\n(Automated)", "• Thu nhận và giải mã khung hình video liên tục (Frame Grabber).\n• Thực thi mô hình YOLO11s nhận diện 10 lớp PPE tốc độ cao (~10.3ms).\n• Gán định danh và theo dõi đối tượng bằng thuật toán ByteTrack.\n• Khử trùng lặp cảnh báo (Deduplication) khi công nhân đứng cố định.\n• Tự động chụp ảnh Snapshot vi phạm và đẩy cảnh báo bất đồng bộ."]
    ]
    populate_table_rows(act_tbl, act_widths, act_data)

    add_h2("2.2. Sơ đồ Use Case Tổng thể (Overall Use Case Diagram)")
    add_body_p("Sơ đồ Use Case tổng thể thể hiện mối quan hệ giữa 3 tác nhân và 12 chức năng nghiệp vụ được phân nhóm thành 5 phân hệ chuyên trách.")
    
    add_image_figure("usecase_diagram.png", "Hình 2.1: Sơ đồ Use Case Tổng thể Hệ thống Giám sát An toàn Lao động")

    add_h2("2.3. Danh mục Phân hệ Chức năng & 12 Use Case Cốt lõi")
    add_body_p("Toàn bộ các yêu cầu nghiệp vụ của hệ thống được phân rã thành 12 Use Case được chuẩn hóa mã định danh:")
    
    uc_summary_tbl = doc.add_table(rows=1, cols=4)
    uc_summary_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    uc_s_widths = [Inches(1.0), Inches(2.2), Inches(1.4), Inches(1.8)]
    format_table_headers(uc_summary_tbl, uc_s_widths, ["Mã UC", "Tên Use Case", "Phân hệ Chức năng", "Tác nhân Chính"])
    
    uc_s_data = [
        ["UC-01", "Giám sát luồng video thời gian thực", "1. Giám sát & Cảnh báo", "Safety Officer, Admin"],
        ["UC-02", "Xem checklist & chỉ số KPI an toàn", "1. Giám sát & Cảnh báo", "Safety Officer, Admin"],
        ["UC-03", "Tiếp nhận cảnh báo đa kênh tức thời", "1. Giám sát & Cảnh báo", "Safety Officer, Admin"],
        ["UC-04", "Tra cứu và lọc lịch sử vi phạm", "2. Nhật ký & Báo cáo", "Safety Officer, Admin"],
        ["UC-05", "Xem ảnh snapshot bằng chứng", "2. Nhật ký & Báo cáo", "Safety Officer, Admin"],
        ["UC-06", "Xác nhận & xử lý sự cố vi phạm", "2. Nhật ký & Báo cáo", "Safety Officer"],
        ["UC-07", "Trích xuất báo cáo Excel / CSV", "2. Nhật ký & Báo cáo", "Safety Officer, Admin"],
        ["UC-08", "Cấu hình quy tắc kiểm tra PPE", "3. Cấu hình Quy tắc", "Admin"],
        ["UC-09", "Cấu hình Telegram Bot & Webhook", "3. Cấu hình Quy tắc", "Admin"],
        ["UC-10", "Quản lý nguồn Camera & RTSP", "3. Cấu hình Quy tắc", "Admin, Safety Officer"],
        ["UC-11", "Quản lý người dùng & phân quyền", "4. Quản trị & Kiểm toán", "Admin"],
        ["UC-12", "Tra cứu nhật ký kiểm toán hệ thống", "4. Quản trị & Kiểm toán", "Admin"],
        ["UC-AI", "Pipeline AI, ByteTrack & Snapshot", "5. Xử lý AI Tự động", "AI Processing Engine"]
    ]
    populate_table_rows(uc_summary_tbl, uc_s_widths, uc_s_data)

    add_h2("2.4. Ma trận Phân quyền Tác nhân - Use Case (Actor-Use Case Matrix)")
    add_body_p("Ma trận phân quyền dưới đây mô tả chi tiết quyền hạn tác động của từng tác nhân lên các Use Case trong hệ thống (Ký hiệu: C - Tạo mới/Khởi tạo, R - Đọc/Theo dõi, U - Cập nhật/Xử lý, D - Xóa, X - Chạy ngầm tự động):")
    
    matrix_tbl = doc.add_table(rows=1, cols=4)
    matrix_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    mat_widths = [Inches(1.0), Inches(2.6), Inches(1.4), Inches(1.4)]
    format_table_headers(matrix_tbl, mat_widths, ["Mã UC", "Tên Nghiệp vụ Use Case", "Cán bộ An toàn", "Quản trị viên"])
    
    align_dict = {2: WD_ALIGN_PARAGRAPH.CENTER, 3: WD_ALIGN_PARAGRAPH.CENTER}
    mat_data = [
        ["UC-01", "Giám sát luồng video thời gian thực", "R (Chính)", "R"],
        ["UC-02", "Xem checklist & chỉ số KPI an toàn", "R (Chính)", "R"],
        ["UC-03", "Tiếp nhận cảnh báo tức thời", "R (Nhận tin)", "R"],
        ["UC-04", "Tra cứu nhật ký vi phạm", "R (Tra cứu)", "R"],
        ["UC-05", "Xem ảnh snapshot bằng chứng", "R (Xem ảnh)", "R"],
        ["UC-06", "Xác nhận / Xử lý sự cố vi phạm", "U (Xác nhận)", "U"],
        ["UC-07", "Xuất báo cáo Excel / CSV", "C (Xuất file)", "C"],
        ["UC-08", "Cấu hình quy tắc PPE phân xưởng", "R (Xem)", "C / U / D"],
        ["UC-09", "Cấu hình Telegram / Webhook", "R (Xem)", "C / U / D"],
        ["UC-10", "Quản lý nguồn Camera giám sát", "R (Đổi cam)", "C / U / D"],
        ["UC-11", "Quản trị người dùng & phân quyền", "—", "C / U / D"],
        ["UC-12", "Nhật ký kiểm toán hệ thống", "—", "R (Tra cứu)"],
        ["UC-AI", "Xử lý AI, ByteTrack & Snapshot", "— (Tự động)", "— (Tự động)"]
    ]
    populate_table_rows(matrix_tbl, mat_widths, mat_data, align_cols=align_dict)

    # =========================================================================
    # CHƯƠNG 3: ĐẶC TẢ CHI TIẾT CÁC USE CASE (IEEE/RUP SPECIFICATIONS)
    # =========================================================================
    add_h1("CHƯƠNG 3: ĐẶC TẢ CHI TIẾT CÁC USE CASE (IEEE / RUP)")
    add_body_p("Chương này trình bày đặc tả chi tiết cho từng Use Case trọng tâm của hệ thống AI Safety Monitor theo định dạng chuẩn công nghiệp IEEE/RUP, bao gồm: Mã định danh, Tác nhân, Mục tiêu, Tiền điều kiện, Hậu điều kiện, Luồng sự kiện chính (Basic Flow), Luồng thay thế (Alternative Flow), Luồng ngoại lệ (Exception Flow) và Yêu cầu phi chức năng.")

    def add_usecase_spec_table(uc_id, uc_name, actor, summary, pre_cond, post_cond, basic_flow, alt_flow, exc_flow, nfr):
        add_h2(f"3.{uc_id.replace('UC-', '')}. Đặc tả Use Case {uc_id}: {uc_name}")
        tbl = doc.add_table(rows=0, cols=2)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        widths = [Inches(1.8), Inches(4.6)]
        
        rows_content = [
            ("MÃ & TÊN USE CASE", f"{uc_id}: {uc_name}"),
            ("Tác nhân (Actor)", actor),
            ("Mô tả tóm tắt", summary),
            ("Tiền điều kiện (Pre-conditions)", pre_cond),
            ("Hậu điều kiện (Post-conditions)", post_cond),
            ("Luồng sự kiện chính (Basic Flow)", basic_flow),
            ("Luồng thay thế (Alternative Flow)", alt_flow),
            ("Luồng ngoại lệ (Exception Flow)", exc_flow),
            ("Yêu cầu phi chức năng (NFR)", nfr)
        ]
        
        for k, v in rows_content:
            row = tbl.add_row()
            c1, c2 = row.cells[0], row.cells[1]
            c1.width, c2.width = widths[0], widths[1]
            
            is_header = (k == "MÃ & TÊN USE CASE")
            bg1 = "1B365D" if is_header else "F8FAFC"
            bg2 = "1E3A8A" if is_header else "FFFFFF"
            
            apply_cell_styling(c1, bg_color=bg1, top_b="D1D5DB", bottom_b="D1D5DB", top_m=100, bottom_m=100, left_m=120, right_m=120)
            apply_cell_styling(c2, bg_color=bg2, top_b="D1D5DB", bottom_b="D1D5DB", top_m=100, bottom_m=100, left_m=120, right_m=120)
            
            p1 = c1.paragraphs[0]
            p1.paragraph_format.space_before = Pt(2)
            p1.paragraph_format.space_after = Pt(2)
            r1 = p1.add_run(k)
            r1.font.name = "Segoe UI"
            r1.font.size = Pt(9.5)
            r1.font.bold = True
            r1.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF) if is_header else RGBColor(0x1E, 0x29, 0x3B)
            
            p2 = c2.paragraphs[0]
            p2.paragraph_format.space_before = Pt(2)
            p2.paragraph_format.space_after = Pt(2)
            p2.paragraph_format.line_spacing = 1.15
            r2 = p2.add_run(v)
            r2.font.name = "Segoe UI"
            r2.font.size = Pt(9.5)
            if is_header:
                r2.font.bold = True
                r2.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            else:
                r2.font.color.rgb = RGBColor(0x37, 0x41, 0x51)
        
        p_space = doc.add_paragraph()
        p_space.paragraph_format.space_before = Pt(4)
        p_space.paragraph_format.space_after = Pt(4)

    # 1. UC-01
    add_usecase_spec_table(
        "UC-01", "Giám sát Luồng Video Thời gian thực (Live CCTV Stream)",
        "Cán bộ An toàn, Quản trị viên",
        "Hiển thị trực tiếp luồng video camera đã được suy luận AI lên màn hình điều khiển với Bounding Box và nhãn trang bị bảo hộ phân màu trực quan theo thời gian thực.",
        "Backend FastAPI đang chạy và đã kết nối thành công với Camera (Webcam / RTSP / Mock Stream). Người dùng đã mở giao diện web dashboard.",
        "Luồng video hiển thị ổn định trên màn hình điều khiển với độ trễ < 50ms, các đối tượng được đóng khung và gán nhãn phân loại chính xác.",
        "1. Người dùng mở trang chủ Dashboard giám sát trên trình duyệt web.\n2. Frontend tự động thiết lập kết nối WebSocket tới endpoint ws://localhost:8000/api/ws/stream.\n3. Backend tiếp nhận kết nối, khởi tạo luồng giải mã OpenCV và nạp mô hình YOLO11s.\n4. Với mỗi khung hình, Backend thực thi suy luận AI, vẽ hộp Bounding Box (Xanh: An toàn, Đỏ: Vi phạm), nén ảnh JPEG Base64.\n5. Backend gửi gói tin JSON chứa chuỗi ảnh và danh sách vi phạm qua WebSocket.\n6. Frontend nhận dữ liệu và render luồng hình ảnh mượt mà trên thẻ Canvas/Video HTML5.",
        "2a. Người dùng thay đổi kích thước cửa sổ trình duyệt: Frontend tự động căn chỉnh tỷ lệ khung hình video (Responsive Aspect Ratio).",
        "2b. Mất kết nối WebSocket (Server khởi động lại hoặc đứt cáp mạng):\n   - Frontend hiển thị thông báo 'Mất kết nối tới Server AI. Đang tự động kết nối lại sau 3s...'.\n   - Tự động thực hiện cơ chế Exponential Backoff Reconnection.",
        "• Độ trễ truyền phát (End-to-End Latency) <= 50ms.\n• Tốc độ khung hình hiển thị ổn định >= 25 FPS trên mạng LAN."
    )

    # 2. UC-02
    add_usecase_spec_table(
        "UC-02", "Xem Checklist & Chỉ số KPI An toàn Tức thời",
        "Cán bộ An toàn, Quản trị viên",
        "Hiển thị bảng tổng hợp tỷ lệ tuân thủ an toàn (Compliance Rate %), tổng số lượt vi phạm trong ngày, số lượng công nhân hiện diện và trạng thái checklist 5 trang bị bảo hộ.",
        "Người dùng đang truy cập giao diện giám sát thời gian thực (UC-01 đang hoạt động).",
        "Các chỉ số an toàn KPI và trạng thái đèn báo (Xanh/Đỏ) của checklist được cập nhật đồng bộ theo từng khung hình.",
        "1. Hệ thống liên tục nhận thống kê phát hiện từ luồng WebSocket.\n2. Module tính toán tổng hợp số lượng trang bị đạt chuẩn và vi phạm trong khung hình hiện tại.\n3. Tính toán tỷ lệ tuân thủ: Compliance Rate = (Số lượng Safe / Tổng số trang bị) * 100%.\n4. Cập nhật thẻ chỉ số KPI: Tỷ lệ tuân thủ, Số vi phạm hôm nay, Tổng số lượt cảnh báo.\n5. Cập nhật bảng Checklist: Đèn Xanh nếu đạt chuẩn (ví dụ: Helmet detected), Đèn Đỏ nếu phát hiện vi phạm (ví dụ: No-Helmet detected).",
        "3a. Khung hình không có người lao động: Tỷ lệ tuân thủ hiển thị 100% (An toàn), trạng thái 'Khu vực trống'.",
        "Không có lỗi ngoại lệ nghiêm trọng. Dữ liệu tự động khôi phục giá trị mặc định nếu mất kết nối.",
        "• Thời gian phản hồi cập nhật UI <= 50ms theo luồng WebSocket.\n• Tương phản màu sắc cao, dễ quan sát từ khoảng cách 2 mét trên màn hình giám sát trung tâm."
    )

    # 3. UC-03
    add_usecase_spec_table(
        "UC-03", "Tiếp nhận và Xử lý Cảnh báo Đa kênh Thời gian thực",
        "Cán bộ An toàn, Quản trị viên",
        "Tự động phát cảnh báo đa kênh (Âm thanh hú còi trên Web, Hiệu ứng nhấp nháy đỏ Visual Flash, Tin nhắn kèm ảnh vi phạm gửi qua Telegram Bot và Webhook) ngay khi có sự cố vi phạm.",
        "Hệ thống phát hiện vi phạm mới (chưa từng được ghi nhận cho Track ID hiện tại) và cấu hình kênh thông báo đã được kích hoạt.",
        "Cán bộ an toàn nhận được tin nhắn Telegram trên điện thoại và thấy cảnh báo nhấp nháy trên màn hình Web.",
        "1. AI Engine phát hiện một vi phạm an toàn mới (ví dụ: no-vest).\n2. Backend kích hoạt tiến trình bất đồng bộ notifier.py.\n3. Hệ thống gửi tin nhắn Markdown kèm ảnh Snapshot qua Telegram Bot API.\n4. Đồng thời gửi gói tin HTTP POST chứa thông tin vi phạm tới Webhook URL.\n5. Luồng WebSocket gửi cờ cảnh báo (alert_flag) lên giao diện Web.\n6. Trình duyệt web phát âm thanh cảnh báo (Audio Alert) và nhấp nháy viền đỏ màn hình (Visual Flash).",
        "1a. Quản trị viên tắt âm thanh trên Web: Hệ thống chỉ gửi thông báo Telegram và nhấp nháy viền đỏ.",
        "3a. Mất kết nối Internet hoặc Sai Bot Token/Chat ID:\n   - Backend ghi log lỗi vào audit_log.txt.\n   - Chuyển sang lưu trữ cục bộ, không làm gián đoạn luồng suy luận AI của camera.",
        "• Thời gian từ lúc phát hiện vi phạm đến khi tin nhắn Telegram tới điện thoại <= 2.0 giây.\n• Tỷ lệ gửi thành công đạt >= 99.5% khi có kết nối Internet ổn định."
    )

    # 4. UC-04
    add_usecase_spec_table(
        "UC-04", "Tra cứu và Lọc Lịch sử Vi phạm An toàn",
        "Cán bộ An toàn, Quản trị viên",
        "Cho phép người dùng tra cứu toàn bộ danh sách các sự cố vi phạm an toàn đã được ghi nhận trong CSDL, hỗ trợ bộ lọc đa tiêu chí (Thời gian, Loại vi phạm, Trạng thái xử lý).",
        "CSDL có lưu trữ dữ liệu vi phạm (hoặc In-Memory Cache). Người dùng truy cập mục 'Nhật ký vi phạm'.",
        "Danh sách vi phạm thỏa mãn điều kiện lọc được hiển thị dưới dạng bảng chi tiết kèm hình thu nhỏ (Thumbnail).",
        "1. Người dùng chọn tab 'Lịch sử Vi phạm' (Violation History).\n2. Frontend gửi yêu cầu GET /api/violations kèm các tham số lọc.\n3. Backend truy vấn CSDL PostgreSQL (hoặc Memory DB) và trả về mảng dữ liệu JSON.\n4. Giao diện hiển thị bảng vi phạm gồm: Mã sự kiện, Thời gian, Loại vi phạm (badge đỏ), Độ tin cậy (Confidence %), Ảnh thu nhỏ (Thumbnail), Trạng thái xử lý.\n5. Người dùng có thể chọn bộ lọc loại lỗi (no-helmet, no-vest,...) hoặc khoảng thời gian.",
        "5a. Người dùng bấm nút 'Xóa nhật ký': Hệ thống yêu cầu xác nhận trước khi gọi DELETE /api/violations.",
        "3a. Mất kết nối CSDL PostgreSQL: Backend tự động đọc dữ liệu từ bộ nhớ tạm In-Memory Fallback và trả về danh sách hiện có.",
        "• Tốc độ truy vấn bảng 10.000 bản ghi <= 200ms.\n• Phân trang mượt mà (Pagination) 20 bản ghi/trang."
    )

    # 5. UC-05
    add_usecase_spec_table(
        "UC-05", "Xem Ảnh Snapshot Bằng chứng Chất lượng cao",
        "Cán bộ An toàn, Quản trị viên",
        "Cho phép phóng to xem chi tiết ảnh chụp snapshot bằng chứng vi phạm ở độ phân giải gốc kèm thông số Bounding Box và mốc thời gian vi phạm.",
        "Bản ghi vi phạm có trường snapshot_path hợp lệ và tệp ảnh tồn tại trong thư mục /data/violations/.",
        "Cửa sổ xem ảnh (Lightbox Modal) hiển thị ảnh vi phạm rõ nét, hỗ trợ tải về máy tính.",
        "1. Người dùng nhấp vào ảnh Thumbnail hoặc nút 'Xem bằng chứng' trên bảng nhật ký vi phạm.\n2. Frontend kích hoạt cửa sổ Modal Lightbox.\n3. Trình duyệt tải ảnh độ phân giải cao từ đường dẫn tĩnh /static/snapshots/...\n4. Hiển thị thông tin chi tiết: Thời gian chính xác đến mili-giây, Vị trí tọa độ Bounding Box, Độ tin cậy AI, Mã Track ID.\n5. Người dùng có thể bấm nút 'Tải ảnh' (Download Snapshot) về máy tính.",
        "4a. Người dùng dùng phím mũi tên Trái/Phải: Hệ thống chuyển nhanh sang xem ảnh bằng chứng của vi phạm liền kề.",
        "3a. Tệp ảnh trên đĩa bị xóa hoặc hỏng: Frontend hiển thị biểu tượng 'Ảnh không khả dụng' kèm thông báo giải thích.",
        "• Thời gian tải và hiển thị ảnh phóng to <= 300ms trên mạng nội bộ.\n• Giữ nguyên độ phân giải gốc của camera (1080p/720p)."
    )

    # 6. UC-06
    add_usecase_spec_table(
        "UC-06", "Xác nhận và Cập nhật Trạng thái Xử lý Vi phạm",
        "Cán bộ An toàn",
        "Cán bộ an toàn cập nhật tiến độ xử lý đối với từng sự cố vi phạm (Ví dụ: Chờ xử lý -> Đã nhắc nhở trực tiếp -> Đã lập biên bản phạt hành chính).",
        "Người dùng đã đăng nhập với vai trò Cán bộ An toàn và đang xem một bản ghi vi phạm cụ thể.",
        "Trạng thái vi phạm trong CSDL được cập nhật thành công và hiển thị nhãn trạng thái mới trên giao diện.",
        "1. Cán bộ an toàn mở chi tiết một bản ghi vi phạm trong danh sách.\n2. Nhấp vào menu thả xuống 'Trạng thái xử lý' (Status Selector).\n3. Chọn trạng thái mong muốn: 'Chờ xử lý' (Pending), 'Đã nhắc nhở' (Reminded), 'Đã lập biên bản' (Penalized), 'Vi phạm giả / Bỏ qua' (False Positive).\n4. Nhập ghi chú xử lý (Tùy chọn, ví dụ: 'Đã yêu cầu công nhân A đội mũ bảo hộ lúc 09:15').\n5. Bấm 'Lưu trạng thái'. Frontend gửi PATCH /api/violations/{id}/status.\n6. Backend cập nhật CSDL và ghi nhận vết kiểm toán (Audit Trail).",
        "3a. Đánh dấu 'Vi phạm giả (False Positive)': Hệ thống ghi nhận để phục vụ đánh giá lại độ chính xác của mô hình AI.",
        "5a. Lỗi kết nối mạng: Frontend thông báo 'Lỗi lưu trạng thái. Vui lòng thử lại.' và giữ nguyên trạng thái cũ.",
        "• Cập nhật trạng thái tức thời < 100ms.\n• Lưu lại định danh Cán bộ an toàn đã thao tác và mốc thời gian cập nhật."
    )

    # 7. UC-07
    add_usecase_spec_table(
        "UC-07", "Trích xuất & Xuất Báo cáo Thống kê An toàn (Excel / CSV)",
        "Cán bộ An toàn, Quản trị viên",
        "Tự động tổng hợp dữ liệu vi phạm, phân tích tỷ lệ tuân thủ và xuất ra tệp bảng tính Excel đa sheet chuyên nghiệp (.xlsx) hoặc tệp CSV phục vụ báo cáo ban lãnh đạo.",
        "Hệ thống có ít nhất một bản ghi vi phạm trong khoảng thời gian được chọn.",
        "Tệp báo cáo (.xlsx hoặc .csv) được tạo tự động và tải xuống máy tính của người dùng.",
        "1. Người dùng nhấp vào nút 'Xuất Báo cáo' (Export Report) trên thanh công cụ.\n2. Chọn định dạng xuất (Excel .xlsx hoặc CSV) và khoảng thời gian (Hôm nay, Tuần này, Tháng này, Toàn bộ).\n3. Frontend gửi yêu cầu GET /api/reports/export?format=xlsx&period=today.\n4. Backend gọi module reporter.py sử dụng thư viện OpenPyXL:\n   - Sheet 1: Dashboard Thống kê tổng hợp & Biểu đồ KPI.\n   - Sheet 2: Danh sách chi tiết toàn bộ các sự cố vi phạm kèm đường dẫn snapshot.\n   - Sheet 3: Phân tích vi phạm theo từng khung giờ và loại trang bị bảo hộ.\n5. Backend stream tệp tin về trình duyệt và tự động kích hoạt tiến trình tải xuống.",
        "2a. Người dùng chọn xuất CSV: Hệ thống tạo tệp CSV UTF-8 với dấu phân cách chuẩn hóa.",
        "4a. Không có dữ liệu trong kỳ báo cáo: Hệ thống tạo tệp Excel thông báo 'Không có vi phạm ghi nhận trong kỳ được chọn' thay vì báo lỗi rỗng.",
        "• Thời gian kết xuất file Excel 10.000 dòng <= 1.5 giây.\n• File Excel có định dạng màu sắc chuẩn doanh nghiệp, font Segoe UI, tự căn chỉnh độ rộng cột."
    )

    # 8. UC-08
    add_usecase_spec_table(
        "UC-08", "Cấu hình Quy tắc Kiểm tra PPE theo Phân xưởng",
        "Quản trị viên Hệ thống",
        "Cho phép bật/tắt linh hoạt từng quy tắc kiểm tra trang bị bảo hộ (Mũ, Áo phản quang, Găng tay, Ủng, Kính) phù hợp với yêu cầu an toàn đặc thù của từng khu vực công trường.",
        "Quản trị viên đăng nhập hệ thống và mở mục 'Cấu hình Quy tắc' (Rule Configuration).",
        "Bộ quy tắc mới được lưu vào configs/settings.json và áp dụng ngay lập tức vào luồng suy luận AI mà không cần khởi động lại máy chủ.",
        "1. Quản trị viên truy cập mục 'Cấu hình Quy tắc An toàn'.\n2. Giao diện hiển thị danh sách 5 quy tắc PPE với công tắc gạt (Toggle Switch):\n   - Kiểm tra Mũ bảo hộ (Hard Hat Rule)\n   - Kiểm tra Áo phản quang (Safety Vest Rule)\n   - Kiểm tra Găng tay (Gloves Rule)\n   - Kiểm tra Ủng bảo hộ (Boots Rule)\n   - Kiểm tra Kính bảo hộ (Safety Goggles Rule)\n3. Quản trị viên bật/tắt các quy tắc theo yêu cầu thực tế.\n4. Bấm nút 'Lưu Quy tắc'.\n5. Frontend gửi POST /api/settings/rules, Backend cập nhật biến active_rules trong bộ nhớ và ghi vào tệp cấu hình.",
        "3a. Bấm nút 'Mặc định (Reset)': Hệ thống khôi phục trạng thái chuẩn (Bật kiểm tra Mũ và Áo phản quang).",
        "5a. Quyền truy cập bị từ chối: Nếu người dùng không phải Quản trị viên, hệ thống thông báo lỗi 403 Forbidden.",
        "• Thay đổi quy tắc có hiệu lực tức thì (Real-time Hot Reload) < 100ms.\n• Ghi lại lịch sử ai đã thay đổi cấu hình vào Audit Log."
    )

    # 9. UC-09
    add_usecase_spec_table(
        "UC-09", "Cấu hình Kênh Cảnh báo Telegram Bot, Webhook & Cooldown",
        "Quản trị viên Hệ thống",
        "Thiết lập thông số kết nối Telegram Bot (Token, Chat ID), Webhook URL, thời gian giãn cách cảnh báo (Cooldown) và thử nghiệm gửi tin cảnh báo mẫu (Test Alert).",
        "Quản trị viên đã tạo Bot trên Telegram qua @BotFather và lấy được Token cùng Chat ID của nhóm nhận tin.",
        "Thông số cảnh báo được lưu trữ an toàn, tin nhắn mẫu gửi thành công tới nhóm Telegram công trường.",
        "1. Quản trị viên mở bảng 'Cấu hình Thông báo' (Notification Settings).\n2. Nhập các trường thông tin:\n   - Kích hoạt Telegram Alert (Bật/Tắt)\n   - Telegram Bot Token & Chat ID\n   - Kích hoạt Webhook Alert (Bật/Tắt) & Webhook URL\n   - Thời gian giãn cách cảnh báo Cooldown (Mặc định 5 giây)\n3. Quản trị viên bấm nút 'Kiểm tra kết nối' (Test Telegram Connection).\n4. Backend gửi thử một tin nhắn mẫu '✅ Kết nối Telegram Bot thành công!'.\n5. Nhận kết quả thành công, Quản trị viên bấm 'Lưu Cấu hình'.\n6. Backend lưu vào configs/settings.json và cập nhật module notifier.py.",
        "2a. Tắt toàn bộ cảnh báo ngoài: Hệ thống chỉ hiển thị vi phạm nội bộ trên màn hình Web.",
        "3a. Sai Bot Token hoặc Chưa thêm Bot vào Group Telegram:\n   - Backend trả về mã lỗi HTTP 400 kèm thông báo: 'Chat not found hoặc Token không hợp lệ'.\n   - Giao diện hiển thị hướng dẫn Quản trị viên cấp quyền cho Bot trong Group.",
        "• Ẩn Token dưới dạng ký tự mật khẩu (Masked Input) trên giao diện.\n• Hỗ trợ định dạng tin nhắn HTML/Markdown bắt mắt kèm ảnh."
    )

    # 10. UC-10
    add_usecase_spec_table(
        "UC-10", "Quản lý Nguồn Camera & Chuyển đổi Luồng Video",
        "Cán bộ An toàn, Quản trị viên",
        "Lựa chọn và chuyển đổi linh hoạt giữa các nguồn video đầu vào: Webcam máy tính (Index 0, 1), Camera IP công trường (RTSP URL), Video mẫu (.mp4) hoặc Bộ dữ liệu Giả lập (Mock Stream).",
        "Camera đã được kết nối với máy tính hoặc luồng RTSP có thể truy cập được qua mạng LAN/Internet.",
        "Màn hình giám sát chuyển đổi ngay sang hiển thị luồng video của nguồn mới và tiếp tục nhận diện AI.",
        "1. Người dùng nhấp vào hộp chọn nguồn camera (Source Selector dropdown) trên thanh công cụ.\n2. Danh sách hiển thị các tùy chọn:\n   - Webcam mặc định (Camera 0)\n   - Webcam phụ (Camera 1)\n   - Luồng Giả lập (Mock Dataset Stream)\n   - Camera RTSP Tùy chỉnh (Nhập URL: rtsp://admin:pass@ip:port/stream)\n3. Người dùng chọn nguồn mong muốn (ví dụ: Mock Stream).\n4. Frontend ngắt kết nối WebSocket cũ và gửi yêu cầu kết nối mới kèm tham số source=mock.\n5. Backend giải phóng OpenCV VideoCapture cũ, mở luồng mới và truyền khung hình.\n6. Giao diện cập nhật hiển thị video nguồn mới.",
        "2a. Nhập RTSP URL mới: Hệ thống kiểm tra kết nối trong 3 giây trước khi chuyển luồng chính thức.",
        "5a. Camera được chọn bị lỗi hoặc đang bị ứng dụng khác chiếm dụng:\n   - Backend gửi thông báo lỗi: 'Không thể mở Camera ID 0'.\n   - Tự động chuyển hướng gợi ý sang chế độ Giả lập (Mock Stream).",
        "• Thời gian chuyển đổi giữa các nguồn camera <= 1.0 giây.\n• Không gây rò rỉ bộ nhớ (Memory Leak) khi chuyển đổi liên tục."
    )

    # 11. UC-11
    add_usecase_spec_table(
        "UC-11", "Quản lý Danh mục Người dùng & Phân quyền Truy cập (RBAC)",
        "Quản trị viên Hệ thống",
        "Thêm mới, sửa đổi, khóa tài khoản người dùng và phân quyền vai trò (Role-Based Access Control) cho Cán bộ An toàn và Quản trị viên.",
        "Quản trị viên đã đăng nhập hệ thống với quyền Quản trị tối cao (Super Admin).",
        "Tài khoản người dùng được tạo mới/cập nhật thành công trong CSDL phân quyền.",
        "1. Quản trị viên mở trang 'Quản lý Tài khoản' (User Management).\n2. Danh sách tài khoản hiện tại hiển thị dạng bảng: Tên đăng nhập, Họ tên, Email, Vai trò (Admin / Safety Officer), Trạng thái (Hoạt động / Khóa).\n3. Quản trị viên bấm 'Thêm người dùng mới' và nhập thông tin tài khoản.\n4. Chọn vai trò phân quyền tương ứng.\n5. Bấm 'Lưu tài khoản'. Backend mã hóa mật khẩu bằng thuật toán Bcrypt và lưu vào CSDL.\n6. Gửi email thông báo tài khoản tới người dùng mới.",
        "3a. Khóa tài khoản: Quản trị viên có thể chuyển trạng thái tài khoản sang 'Khóa' để ngăn đăng nhập ngay lập tức.",
        "5a. Tên đăng nhập hoặc Email đã tồn tại: Hệ thống báo lỗi trùng lặp và yêu cầu nhập lại.",
        "• Mật khẩu được băm (Hash) an toàn bằng Bcrypt trước khi lưu CSDL.\n• Thời gian phản hồi phân quyền < 100ms."
    )

    # 12. UC-AI-01
    add_usecase_spec_table(
        "UC-AI-01", "Quy trình Xử lý AI Tự động, ByteTrack & Khử trùng lặp",
        "AI Processing Engine (Tự động chạy ngầm)",
        "Quy trình tự động thực thi trên mỗi khung hình video: Tiền xử lý -> Suy luận YOLO11s -> Gán Track ID ByteTrack -> So khớp Quy tắc An toàn -> Khử trùng lặp cảnh báo -> Cắt Snapshot & Bắn thông báo.",
        "Mô hình trọng số YOLO11s (weights/best.pt) đã được nạp thành công vào bộ nhớ GPU CUDA / CPU.",
        "Khung hình được gán nhãn chính xác; dữ liệu vi phạm được ghi vào CSDL và gửi cảnh báo không trùng lặp.",
        "1. Module thu nhận khung hình trích xuất ma trận ảnh BGR từ OpenCV stream.\n2. Tiền xử lý ảnh: Chuẩn hóa kích thước (640x640), chuyển đổi RGB, chuẩn hóa Tensor.\n3. Mô hình YOLO11s thực hiện suy luận dự đoán Bounding Box, Class ID và Confidence score.\n4. Thuật toán ByteTrack theo dõi quỹ đạo đối tượng qua các khung hình liên tiếp và gán track_id duy nhất.\n5. Module Logic an toàn kiểm tra danh sách phát hiện dựa trên bộ active_rules:\n   - Nếu phát hiện vi phạm (ví dụ: no-helmet với confidence >= 0.50):\n     + Kiểm tra tập logged_track_violations.\n     + Nếu đối tượng (track_id, v_type) chưa từng được ghi nhận:\n       * Chụp và lưu ảnh snapshot vi phạm.\n       * Ghi nhận sự kiện vào CSDL.\n       * Kích hoạt bất đồng bộ gửi cảnh báo Telegram & Webhook.\n       * Thêm (track_id, v_type) vào logged_track_violations.\n6. Khi đối tượng rời khỏi khung hình quá 5 giây (Expiration Timeout), hệ thống tự động giải phóng track_id khỏi bộ nhớ đệm.",
        "4a. Mất dấu Track ID do chuyển động quá nhanh hoặc che khuất tạm thời: Hệ thống áp dụng cơ chế Deduplication Fallback dựa trên ngưỡng thời gian biến thiên.",
        "3a. Lỗi Out of Memory (OOM) trên GPU: Hệ thống tự động chuyển sang chế độ suy luận CPU Fallback để duy trì tính sẵn sàng liên tục.",
        "• Thời gian suy luận mô hình YOLO11s: ~10 - 15ms/khung hình trên GPU NVIDIA RTX.\n• Độ chính xác phát hiện mAP50 đạt trên 95% đối với các vi phạm Mũ và Áo phản quang."
    )

    # =========================================================================
    # CHƯƠNG 4: YÊU CẦU PHI CHỨC NĂNG & MA TRẬN TRUY VẾT YÊU CẦU (RTM)
    # =========================================================================
    add_h1("CHƯƠNG 4: YÊU CẦU PHI CHỨC NĂNG & MA TRẬN TRUY VẾT YÊU CẦU (RTM)")
    
    add_h2("4.1. Yêu cầu Phi chức năng (Non-Functional Requirements)")
    add_body_p("Để bảo đảm tính ổn định, độ tin cậy và khả năng vận hành thực tế trong môi trường sản xuất công nghiệp 24/7, hệ thống AI Safety Monitor cam kết đáp ứng các tiêu chuẩn phi chức năng nghiêm ngặt sau:")
    
    nfr_tbl = doc.add_table(rows=1, cols=3)
    nfr_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    nfr_widths = [Inches(1.8), Inches(1.8), Inches(2.8)]
    format_table_headers(nfr_tbl, nfr_widths, ["Nhóm Yêu cầu", "Chỉ số Cam kết (Metric)", "Giải pháp Kỹ thuật Đạt được"])
    
    nfr_data = [
        ["Hiệu năng Xử lý\n(Performance)", "• Tốc độ FPS >= 25 FPS\n• Latency suy luận <= 15ms\n• Độ trễ WebSocket <= 50ms", "Tối ưu hóa pipeline YOLO11s PyTorch, nén khung hình JPEG chất lượng 80, truyền luồng nhị phân Base64 qua WebSocket."],
        ["Độ sẵn sàng Cao\n(High Availability)", "• Uptime >= 99.9%\n• Hoạt động không phụ thuộc CSDL ngoài", "Cơ chế In-memory Storage Fallback: Tự động chuyển sang lưu tạm bộ nhớ RAM khi mất kết nối CSDL PostgreSQL."],
        ["Độ tin cậy Cảnh báo\n(Alert Reliability)", "• Gửi tin Telegram <= 2.0s\n• Tỷ lệ trùng lặp spam <= 0.1%", "Áp dụng thuật toán ByteTrack gán track_id cố định và cơ chế Expiration Cache 5s ngăn chặn cảnh báo lặp lại."],
        ["Trải nghiệm Người dùng\n(UX / Ergonomics)", "• Thao tác 1-Click\n• Thời gian phản hồi UI <= 100ms\n• Giảm mỏi mắt ca đêm", "Giao diện Dark Mode chuyên nghiệp theo chuẩn Tailwind CSS, tương phản màu sắc cao (Xanh An toàn / Đỏ Vi phạm)."],
        ["Tính Tương thích\n(Interoperability)", "• Chuẩn hóa dữ liệu RESTful JSON\n• Xuất bảng tính Excel đa nền tảng", "Backend chuẩn FastAPI Swagger OpenAPI; module xuất Excel chuẩn định dạng OpenXML (.xlsx 3 sheet)."]
    ]
    populate_table_rows(nfr_tbl, nfr_widths, nfr_data)

    add_h2("4.2. Ma trận Truy vết Yêu cầu Phần mềm (Requirement Traceability Matrix - RTM)")
    add_body_p("Ma trận RTM thiết lập mối liên kết truy vết chặt chẽ từ Yêu cầu Nghiệp vụ (BR) đến Yêu cầu Chức năng (FR), Use Case tương ứng và Module Kỹ thuật hiện thực trong mã nguồn dự án:")
    
    rtm_tbl = doc.add_table(rows=1, cols=4)
    rtm_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    rtm_widths = [Inches(0.9), Inches(2.3), Inches(1.2), Inches(2.0)]
    format_table_headers(rtm_tbl, rtm_widths, ["Mã Yêu cầu", "Mô tả Yêu cầu Chức năng (FR)", "Use Case", "Module Kỹ thuật Hiện thực"])
    
    rtm_data = [
        ["FR-01", "Truyền phát video trực tiếp kèm nhãn Bounding Box nhận diện PPE", "UC-01", "src/main.py\n(WebSocket /ws/stream)"],
        ["FR-02", "Nhận diện 10 lớp PPE và theo dõi đối tượng khử trùng lặp", "UC-AI-01", "src/predict.py\nsrc/utils/tracker.py"],
        ["FR-03", "Tự động chụp và lưu ảnh snapshot bằng chứng vi phạm", "UC-02, UC-AI-01", "src/utils/snapshot.py\n/data/violations/"],
        ["FR-04", "Gửi cảnh báo đa kênh tức thời qua Telegram Bot và Webhook", "UC-03, UC-09", "src/utils/notifier.py\nTelegram Bot API"],
        ["FR-05", "Trích xuất và xuất báo cáo thống kê Excel (.xlsx) / CSV", "UC-07", "src/utils/reporter.py\nOpenPyXL Engine"],
        ["FR-06", "Cấu hình quy tắc an toàn và kết nối cảnh báo qua giao diện", "UC-08, UC-09", "frontend/src/App.jsx\nconfigs/settings.json"],
        ["FR-07", "Chuyển đổi nguồn camera (Webcam, RTSP, Mock Stream)", "UC-10", "src/main.py (VideoCapture)\nfrontend/src/App.jsx"]
    ]
    populate_table_rows(rtm_tbl, rtm_widths, rtm_data)

    # =========================================================================
    # CHƯƠNG 5: KẾT LUẬN VÀ ĐÁNH GIÁ NGHIỆM THU
    # =========================================================================
    add_h1("CHƯƠNG 5: KẾT LUẬN VÀ ĐÁNH GIÁ NGHIỆM THU")
    add_body_p("Tài liệu Phân tích và Thiết kế Hệ thống này đã chuẩn hóa toàn bộ kiến trúc 5 phân tầng kỹ thuật và đặc tả chi tiết 12 Use Case cốt lõi của đề tài AI Safety Monitor. Bản thiết kế đáp ứng toàn diện cả về mặt lý thuyết học thuật lẫn khả năng triển khai thực tiễn trong môi trường doanh nghiệp.")
    
    add_callout(doc, [
        "1. Kiến trúc hệ thống phân tầng rõ ràng, tính module hóa cao, sẵn sàng đóng gói Docker Container.",
        "2. Đầy đủ 12 Use Case bao phủ 100% các chức năng thực tế của mã nguồn backend và frontend.",
        "3. Tích hợp trực tiếp các sơ đồ trực quan độ phân giải cao: Sơ đồ Kiến trúc, Sơ đồ Luồng dữ liệu DFD và Sơ đồ Use Case UML.",
        "4. Ma trận RTM liên kết rõ ràng giữa yêu cầu nghiệp vụ và các module mã nguồn Python/React."
    ], "ĐÁNH GIÁ CHẤT LƯỢNG TÀI LIỆU THIẾT KẾ")

    output_filename = "PhanTich_Va_ThietKe_HeThong_AISafetyMonitor.docx"
    doc.save(output_filename)
    print(f"Document saved successfully as '{output_filename}'.")

if __name__ == "__main__":
    create_document()
