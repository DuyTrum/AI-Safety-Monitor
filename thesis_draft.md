# ĐỒ ÁN TỐT NGHIỆP: NGHIÊN CỨU VÀ XÂY DỰNG HỆ THỐNG GIÁM SÁT AN TOÀN LAO ĐỘNG SỬ DỤNG TRÍ TUỆ NHÂN TẠO THỜI GIAN THỰC

---

## CHƯƠNG 1: MỞ ĐẦU

### 1.1. Lý do chọn đề tài
Tai nạn lao động tại các công trường xây dựng và nhà máy công nghiệp vẫn là một vấn đề nghiêm trọng, đe dọa đến tính mạng con người và gây tổn thất lớn về kinh tế. Nguyên nhân chủ yếu xuất phát từ việc người lao động không tuân thủ các quy định về sử dụng trang thiết bị bảo hộ cá nhân (Personal Protective Equipment - PPE) như mũ bảo hiểm, áo phản quang, kính bảo hộ, găng tay và ủng. Việc giám sát thủ công bằng con người gặp nhiều hạn chế do diện tích công trường lớn, nhân lực tuần tra mỏng và không thể bao quát liên tục 24/7. Vì vậy, việc nghiên cứu và xây dựng một hệ thống tự động giám sát an toàn lao động bằng trí tuệ nhân tạo (Computer Vision) kết hợp cảnh báo thời gian thực là vô cùng cần thiết và mang tính thực tiễn cao.

### 1.2. Mục tiêu nghiên cứu
- Huấn luyện mô hình học sâu tối ưu dựa trên kiến trúc YOLO11 để phát hiện chính xác các lớp trang bị bảo hộ (Safe) và các trường hợp vi phạm không mang bảo hộ tương ứng (Unsafe).
- Xây dựng hệ thống backend hiệu năng cao, độ trễ thấp và hỗ trợ truyền tải video trực tiếp qua giao thức mạng (WebSocket/RTSP).
- Thiết kế giao diện Dashboard trực quan, hiển thị luồng video thời gian thực, bảng kiểm tra trang bị và thống kê lịch sử cảnh báo vi phạm.
- Container hóa toàn bộ hệ thống bằng Docker để dễ dàng triển khai trên các hạ tầng khác nhau.

---

## CHƯƠNG 2: KIẾN TRÚC MÔ HÌNH VÀ PHƯƠNG PHÁP NGHIÊN CỨU

### 2.1. Tổng quan về YOLO11
YOLO11 (You Only Look Once phiên bản 11) là thế hệ mô hình phát hiện đối tượng mới nhất từ Ultralytics, mang lại những cải tiến đáng kể về độ chính xác và tốc độ xử lý so với các phiên bản tiền nhiệm. YOLO11 tối ưu hóa cấu trúc backbone và neck để trích xuất đặc trưng tốt hơn, tích hợp các cơ chế chú ý (attention mechanisms) giúp nâng cao khả năng phát hiện các đối tượng có kích thước nhỏ hoặc bị che khuất một phần.

### 2.2. Kiến trúc hệ thống đề xuất
Hệ thống giám sát an toàn lao động được thiết kế theo mô hình client-server doanh nghiệp modular, bao gồm các thành phần cốt lõi sau:

```
+------------------+     Luồng Video     +------------------------------------------+
|  Camera giám sát | ------------------> |            FastAPI Backend               |
| (Webcam/IP/RTSP) |                     |  - YOLO11 + ByteTrack (Object Tracking)  |
|                  |                     |  - Deduplication Engine (Chống lặp lỗi)   |
+------------------+                     |  - Snapshot Manager (Tự động chụp ảnh)   |
                                         |  - Telegram Bot & Webhook Alert Notifier |
                                         |  - Excel/CSV Report Generator            |
                                         +------------------------------------------+
                                                      |                  |
                                         Ghi dữ liệu |                  | WebSockets / REST
                                                      v                  v
                                         +------------------+   +-------------------+
                                         | PostgreSQL DB    |   |  React Dashboard  |
                                         | & Snapshot Files |   | - Live Stream     |
                                         +------------------+   | - Snapshot Preview|
                                                                | - Excel Export UI |
                                                                +-------------------+
```

1. **Inference & Tracking Engine (YOLO11s + ByteTrack)**: Tiếp nhận các khung hình từ luồng camera, chạy suy luận phát hiện đối tượng và gán định danh `track_id` cho từng công nhân. Cơ chế lọc trùng (Deduplication) đảm bảo một người đứng liên tục trong khung hình chỉ tạo ra **1 sự kiện vi phạm duy nhất** trên CSDL thay vì spammed dữ liệu.
2. **Snapshot Manager**: Tự động chụp và lưu trữ khung hình chứa vi phạm dạng JPEG vào thư mục `data/violations/YYYY-MM-DD/` kèm Bounding Box và nhãn vi phạm.
3. **Alert Notifier Subsystem**: Tự động gửi tin nhắn cảnh báo định dạng Markdown kèm hình ảnh snapshot thực tế tới ứng dụng Telegram (Telegram Bot API) hoặc Webhook HTTP của cán bộ an toàn trong chế độ bất đồng bộ (Async Background).
4. **Report Generator Subsystem**: Trích xuất dữ liệu vi phạm theo mốc thời gian (*Hôm nay, Tuần này, Tháng này, Tất cả*) ra tệp báo cáo Excel (`.xlsx` 3 sheet chuyên nghiệp) hoặc CSV phục vụ công tác nghiệm thu.
5. **FastAPI Web Server & PostgreSQL DB**: Cung cấp API REST, truyền luồng video WebSocket thời gian thực, lưu vết lịch sử vi phạm kèm URL snapshot vào PostgreSQL.
6. **React Frontend Dashboard**: Nhận dữ liệu truyền từ WebSocket, hiển thị luồng stream kèm nhãn ByteTrack, xem trực tiếp ảnh snapshot dạng Lightbox popup, xuất báo cáo Excel và cấu hình Telegram Bot ngay trên giao diện.

---

## CHƯƠNG 3: TẬP DỮ LIỆU VÀ QUÁ TRÌNH HUẤN LUYỆN

### 3.1. Mô tả tập dữ liệu (PPE Dataset)
Tập dữ liệu sử dụng được thu thập từ nền tảng Roboflow, bao gồm các hình ảnh thực tế tại các công trường xây dựng với sự đa dạng về góc chụp, ánh sáng và khoảng cách. Tập dữ liệu thử nghiệm (Test set) được sử dụng để đánh giá hiệu năng mô hình bao gồm **517 hình ảnh** và **2.073 thực thể** được gán nhãn thuộc 10 lớp đối tượng cụ thể.

Số lượng nhãn phân bố trên các lớp đối tượng thể hiện sự mất cân bằng dữ liệu tự nhiên:
- Các lớp an toàn (Safe): `helmet` (609 nhãn), `vest` (563 nhãn), `boots` (412 nhãn), `gloves` (136 nhãn), `goggles` (57 nhãn).
- Các lớp vi phạm (Unsafe): `no-vest` (116 nhãn), `no-goggles` (88 nhãn), `no-helmet` (42 nhãn), `no-gloves` (31 nhãn), `no-boots` (19 nhãn).

### 3.2. Cấu hình huấn luyện
Quá trình huấn luyện (fine-tuning) được thực hiện trên GPU NVIDIA trong **150 epochs** với các tham số cấu hình chính như sau:
- **Optimizer**: AdamW với tốc độ học ban đầu (lr0) là 0.01.
- **Image Size**: 640x640 pixels.
- **Batch Size**: 16.
- **Learning Rate Schedule**: Sử dụng Cosine Annealing (cos_lr=True) giúp giảm dần tốc độ học mượt mà ở các epochs cuối.
- **Data Augmentation**: Mosaic augmentation (tỷ lệ 1.0) được kích hoạt và tự động tắt ở 10 epochs cuối (close_mosaic=10) để tinh chỉnh mô hình ổn định.

---

## CHƯƠNG 4: KẾT QUẢ THỰC NGHIỆM VÀ ĐÁNH GIÁ

### 4.1. Đánh giá định lượng trên tập dữ liệu Test
Mô hình sau khi hoàn thành 150 epochs huấn luyện được chạy đánh giá độc lập trên tập dữ liệu Test. Các chỉ số thu được cụ thể như sau:

*Bảng 4.1: Chỉ số hiệu năng tổng hợp của mô hình YOLO11s trên tập dữ liệu Test*

| Chỉ số đánh giá | Giá trị |
| :--- | :---: |
| **Precision** (Độ chính xác) | 0.4610 |
| **Recall** (Độ nhạy) | 0.7009 |
| **mAP50** (IoU=0.5) | **0.5443** |
| **mAP50-95** (Toàn diện) | 0.3380 |
| **F1-Score** | 0.5384 |

Để hiểu rõ hơn về hiệu năng phân loại, Bảng 4.2 dưới đây trình bày chi tiết các chỉ số trên từng lớp đối tượng:

*Bảng 4.2: Chi tiết chỉ số hiệu năng trên từng lớp đối tượng*

| Lớp đối tượng | Precision | Recall | mAP50 | mAP50-95 | Phân nhóm |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **boots** (Ủng) | 0.8577 | 0.9976 | **0.9809** | 0.7946 | An toàn (Safe) |
| **helmet** (Mũ) | 0.8889 | 0.9524 | **0.9587** | 0.6474 | An toàn (Safe) |
| **vest** (Áo phản quang) | 0.8465 | 0.9538 | **0.9603** | 0.7792 | An toàn (Safe) |
| **no-vest** (Không mặc áo) | 0.5417 | 0.8362 | 0.7327 | 0.3290 | Vi phạm (Unsafe) |
| **goggles** (Kính) | 0.4260 | 0.6902 | 0.5297 | 0.2463 | An toàn (Safe) |
| **no-goggles** (Không kính) | 0.3417 | 0.7159 | 0.4272 | 0.1544 | Vi phạm (Unsafe) |
| **no-helmet** (Không mũ) | 0.2428 | 0.7143 | 0.3498 | 0.1287 | Vi phạm (Unsafe) |
| **gloves** (Găng tay) | 0.1943 | 0.2794 | 0.2780 | 0.1493 | An toàn (Safe) |
| **no-boots** (Không ủng) | 0.1435 | 0.5789 | 0.1419 | 0.1165 | Vi phạm (Unsafe) |
| **no-gloves** (Không găng) | 0.1264 | 0.2903 | 0.0836 | 0.0350 | Vi phạm (Unsafe) |

### 4.2. Phân tích kết quả
1. **Hiệu năng vượt trội của các lớp trang bị cơ bản**: Mô hình đạt mAP50 trên **95%** đối với các lớp `boots`, `helmet`, và `vest`. Đây là kết quả của việc các lớp này có kích thước vật thể trung bình đến lớn, đặc trưng trực quan rõ ràng (màu sắc nổi bật của áo phản quang, hình dáng tròn của mũ bảo hiểm) và số lượng dữ liệu mẫu huấn luyện dồi dào.
2. **Khả năng cảnh báo nhạy bén (Recall cao)**: Lớp `no-vest` đạt Recall **83.62%** và mAP50 đạt **73.27%**. Độ nhạy của các lớp vi phạm như `no-helmet` (71.43%) và `no-goggles` (71.59%) đều cao, đảm bảo hệ thống hiếm khi bỏ sót các lỗi vi phạm nghiêm trọng trong thực tế.
3. **Thách thức đối với các vật thể nhỏ và mất cân bằng nhãn**:
   - Chỉ số của lớp `gloves` (mAP50 = 27.8%) và `no-gloves` (mAP50 = 8.36%) rất thấp do găng tay là đối tượng kích thước nhỏ, dễ bị nhầm lẫn với bàn tay trần hoặc môi trường xung quanh.
   - Các lớp vi phạm thiểu số như `no-boots` (19 thực thể) và `no-gloves` (31 thực thể) có Precision rất thấp (dưới 15%), là hệ quả trực tiếp của việc mất cân bằng dữ liệu huấn luyện khiến mô hình có xu hướng dự đoán sai các đối tượng tương tự thành vi phạm để tăng độ phủ Recall.

---

## CHƯƠNG 5: THỬ NGHIỆM THỰC TẾ VÀ TRIỂN KHAI HỆ THỐNG

### 5.1. Thử nghiệm thời gian thực và đo lường độ trễ
Hệ thống được đưa vào vận hành thử nghiệm trên máy tính trạm với GPU hỗ trợ CUDA. Tốc độ suy luận đo được trung bình là **10.3 ms/khung hình** (tương đương với tốc độ xử lý độc lập ~97 FPS). Tổng thời gian xử lý toàn bộ pipeline bao gồm tiền xử lý ảnh, suy luận YOLO + ByteTrack, tự động cắt ảnh snapshot, vẽ bounding box bằng OpenCV và truyền tải dữ liệu qua WebSocket là **14.6 ms/khung hình** (~68.5 FPS). Tốc độ này đáp ứng vượt trội yêu cầu xử lý thời gian thực mà không gây trễ luồng camera giám sát.

### 5.2. Đánh giá tính bền bỉ (Robustness) và khử trùng lặp vi phạm
- **Thuật toán Khử trùng lặp (Deduplication with ByteTrack)**: Khi 1 công nhân vi phạm đứng cố định trong khung hình camera trong thời gian dài, hệ thống theo dõi ID đối tượng (`track_id`) và chỉ ghi nhận **1 sự kiện vi phạm duy nhất** vào PostgreSQL và gửi 1 thông báo duy nhất tới Telegram. Tránh hoàn toàn việc tràn bộ nhớ hoặc rác nhật ký.
- **Nhiều đối tượng (Multiple Objects)**: Hệ thống xử lý mượt mà khi có nhiều công nhân xuất hiện đồng thời trong một khung hình (ví dụ khung hình 494 phát hiện và phân loại chính xác 5 mũ bảo hiểm, 2 áo bảo hộ, 5 không mặc áo bảo hộ và 4 không đeo kính).
- **Môi trường ánh sáng yếu**: Nhờ tính chất phản quang mạnh của áo phản quang (`vest`) và mũ bảo hộ sáng màu, mô hình vẫn nhận diện tốt trong điều kiện tối hoặc ngược sáng nhẹ.
- **Hiện tượng che khuất**: Mô hình có khả năng nhận diện tốt khi công nhân bị che khuất một phần cơ thể (trên 40% phần đầu lộ diện vẫn nhận biết được mũ bảo hộ), tuy nhiên nếu bị che khuất hoàn toàn thân dưới thì không thể suy luận ủng bảo hộ.

### 5.3. Triển khai bằng Docker Container & CSDL PostgreSQL
Toàn bộ hệ thống được đóng gói thành các container độc lập sử dụng Docker Compose:
- **Container Database**: PostgreSQL 15 Alpine lưu trữ bảng `violations` bền vững (volume `postgres_data`).
- **Container Backend**: Chạy FastAPI ứng dụng, YOLO11s, ByteTrack, Notifier và Report Generator. Cổng mở: 8000.
- **Container Frontend**: Xây dựng mã nguồn React bằng Node.js và serve tĩnh bằng Nginx. Cổng mở: 3000.
Thiết lập này giúp hệ thống hoạt động đồng bộ, dễ dàng nhân rộng và triển khai chỉ bằng một câu lệnh đơn giản (`docker-compose up --build`).

---

## CHƯƠNG 6: KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN

### 6.1. Các kết quả đã đạt được
- Huấn luyện thành công mô hình YOLO11s đạt độ chính xác mAP50 trên 95% ở các trang bị an toàn chính và độ nhạy Recall cao ở các lớp vi phạm nghiêm trọng.
- Xây dựng hoàn chỉnh luồng xử lý video trực tiếp qua WebSocket từ backend sang frontend dashboard với độ trễ < 15ms.
- Hoàn thành thiết kế Dashboard giám sát an toàn lao động với giao diện UI hiện đại, tích hợp âm thanh cảnh báo tự động.
- Triển khai thành công bằng Docker Container hóa giúp rút ngắn thời gian cài đặt và vận hành hệ thống.

### 6.2. Hướng phát triển tiếp theo
- **Cải thiện tập dữ liệu**: Tiếp tục thu thập và dán nhãn bổ sung cho các lớp dữ liệu bị thiếu hụt nghiêm trọng như `no-boots` và `no-gloves` để nâng cao Precision.
- **Nâng cấp mô hình**: Thử nghiệm huấn luyện các phiên bản YOLO lớn hơn (`yolo11m` hoặc `yolo11l`) và chạy ở độ phân giải cao hơn (`imgsz=1280`) để cải thiện hiệu năng nhận diện găng tay và kính bảo hộ.
- **Tích hợp cơ sở dữ liệu doanh nghiệp**: Kết nối lưu trữ nhật ký vi phạm vào PostgreSQL/MySQL và gửi cảnh báo tự động tới Telegram/Email của cán bộ quản lý an toàn.
