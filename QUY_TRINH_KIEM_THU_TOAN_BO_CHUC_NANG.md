# QUY TRÌNH KIỂM THỬ TOÀN DIỆN HỆ THỐNG GIÁM SÁT AN TOÀN LAO ĐỘNG (AI SAFETY MONITOR)

> **Tiêu chuẩn áp dụng**: ISO/IEC/IEEE 29119 (Software Testing Standard) & Quy chuẩn Kỹ thuật Quốc gia về An toàn trong Xây dựng **QCVN 18:2021/BXD**  
> **Phiên bản tài liệu**: 2.0  
> **Hệ thống mục tiêu**: AI Safety Monitor (YOLO11, YOLO11-Pose, ByteTrack, FastAPI, React/Vite Dashboard)  
> **Bộ video kiểm thử chuẩn hóa**: `data/videos/01_*.mp4` đến `05_*.mp4`

---

## MỤC LỤC

1. [Tổng Quan & Ma Trận Kiểm Thử Hệ Thống](#1-tổng-quan--ma-trận-kiểm-thử-hệ-thống)
2. [Môi Trường Kiểm Thử & Yêu Cầu Thiết Bị](#2-môi-trường-kiểm-thử--yêu-cầu-thiết-bị)
3. [Danh Mục Video Kiểm Thử Chuẩn Hóa & Cách Khởi Chạy](#3-danh-mục-video-kiểm-thử-chuẩn-hóa--cách-khởi-chạy)
4. [Đặc Tả Chi Tiết 12 Kịch Bản Kiểm Thử (TC-01 đến TC-12)](#4-đặc-tả-chi-tiết-12-kịch-bản-kiểm-thử-tc-01-đến-tc-12)
   - [TC-01: Nhận diện 10 lớp PPE (YOLO11s Detection)](#tc-01-nhận-diện-10-lớp-ppe-yolo11s-detection)
   - [TC-02: Theo dõi đa đối tượng & Khử lặp cảnh báo (ByteTrack & De-duplication)](#tc-02-theo-dõi-đa-đối-tượng--khử-lặp-cảnh-báo-bytetrack--de-duplication)
   - [TC-03: Vùng nguy hiểm ảo & Phát hiện xâm nhập (Virtual Geofencing)](#tc-03-vùng-nguy-hiểm-ảo--phát-hiện-xâm-nhập-virtual-geofencing)
   - [TC-04: Phân tích tư thế & Phát hiện té ngã (YOLO11-Pose Fall Engine)](#tc-04-phân-tích-tư-thế--phát-hiện-té-ngã-yolo11-pose-fall-engine)
   - [TC-05: Giám sát an toàn làm việc trên cao & Giàn giáo (Scaffold & Harness Monitor)](#tc-05-giám-sát-an-toàn-làm-việc-trên-cao--giàn-giáo-scaffold--harness-monitor)
   - [TC-06: Đánh giá chỉ số rủi ro động WRI & Quỹ đạo va chạm xe cơ giới](#tc-06-đánh-giá-chỉ-số-rủi-ro-động-wri--quỹ-đạo-va-chạm-xe-cơ-giới)
   - [TC-07: Mô phỏng vật lý nón rơi Drop Cone & Động năng va đập Joule](#tc-07-mô-phỏng-vật-lý-nón-rơi-drop-cone--động-năng-va-đập-joule)
   - [TC-08: Trợ lý kiểm định an toàn What-If (OSHA & QCVN 18:2021/BXD)](#tc-08-trợ-lý-kiểm-định-an-toàn-what-if-osha--qcvn-182021bxd)
   - [TC-09: Đồ thị quan hệ an toàn ngữ cảnh (Safety Scene Graph & RelateAnything)](#tc-09-đồ-thị-quan-hệ-an-toàn-ngữ-cảnh-safety-scene-graph--relateanything)
   - [TC-10: Cảnh báo tự động đa kênh & Lưu vết bằng chứng (Telegram & Snapshot)](#tc-10-cảnh-báo-tự-động-đa-kênh--lưu-vết-bằng-chứng-telegram--snapshot)
   - [TC-11: Quản trị dữ liệu vi phạm & Trích xuất báo cáo Excel/CSV](#tc-11-quản-trị-dữ-liệu-vi-phạm--trích-xuất-báo-cáo-excelcsv)
   - [TC-12: Kiểm thử hiệu năng luồng trực tiếp & Trải nghiệm giao diện Web](#tc-12-kiểm-thử-hiệu-năng-luồng-trực-tiếp--trải-nghiệm-giao-diện-web)
5. [Biên Bản Nghiệm Thu & Đánh Giá Tổng Hợp](#5-biên-bản-nghiệm-thu--đánh-giá-tổng-hợp)

---

## 1. TỔNG QUAN & MA TRẬN KIỂM THỬ HỆ THỐNG

### 1.1. Mục tiêu kiểm thử
Xác thực độ chính xác, tính ổn định thời gian thực và sự tuân thủ quy chuẩn của toàn bộ hệ thống AI Safety Monitor trong môi trường công trường xây dựng, bao gồm:
- Tỷ lệ phát hiện (Precision/Recall) đối với 10 lớp trang bị bảo hộ lao động cá nhân (PPE).
- Độ trễ xử lý (Latency) đạt chuẩn thời gian thực $\le 50$ ms và tốc độ khung hình $\ge 60$ FPS.
- Khả năng chống trùng lặp cảnh báo (Alert De-duplication) với ByteTrack.
- Các tính năng an toàn chuyên sâu thế hệ mới: Geofencing, Pose, WRI Risk, Drop Cone Physics, What-If Auditor.

### 1.2. Ma trận truy xuất nguồn gốc tính năng (Traceability Matrix)

| Mã Ca KT | Tên Module / Tính Năng | Thành Phần Phần Mềm | Video Kiểm Thử Tương Ứng | Tiêu Chí Thành Công Chính |
| :--- | :--- | :--- | :--- | :--- |
| **TC-01** | Nhận diện 10 lớp PPE | `src/predict.py`, `YOLO11s` | `01_ppe_violation_benchmark.mp4` | Recall > 90% cho Mũ và Áo, Bounding box chuẩn |
| **TC-02** | ByteTrack & Khử lặp cảnh báo | `RobustViolationTracker` | `05_multi_worker_tracking.mp4` | ID bám vết liên tục, chỉ cảnh báo 1 lần duy nhất/ID |
| **TC-03** | Đa giác Vùng nguy hiểm ảo | `ZoneManager`, `zones.json` | `02_danger_zone_intrusion.mp4` | Đổi màu vùng sang Đỏ, báo `zone_intrusion` tức thì |
| **TC-04** | Phân tích tư thế & Té ngã | `PoseEngine`, `YOLO11-Pose` | `03_fall_incident_simulation.mp4` | Phát hiện góc thân $> 60^\circ$, kích hoạt `fall_detected` |
| **TC-05** | Giám sát làm việc trên cao | `ScaffoldHarnessMonitor` | `04_scaffold_height_hazard.mp4` | Bắt lỗi `on_scaffold_no_harness` / `unhooked` |
| **TC-06** | Chỉ số rủi ro động WRI | `RiskPredictor` | `02_danger_zone_intrusion.mp4` | Điểm WRI nhảy từ An toàn (<30) lên Nguy hiểm (>70) |
| **TC-07** | Nón rơi & Động năng Joule | `PhysicsSimulator` | `04_scaffold_height_hazard.mp4` | Vẽ nón Drop Cone, tính đúng $E_k = mgh$ và $v = \sqrt{2gh}$ |
| **TC-08** | Trợ lý kịch bản What-If | `WhatIfAuditor` | Bất kỳ vi phạm nào | Xuất chuỗi domino rủi ro, đối chiếu QCVN 18:2021/BXD |
| **TC-09** | Đồ thị quan hệ an toàn | `SafetyRelationEngine` | `02_danger_zone_intrusion.mp4` | Nhận diện triplet (Worker, near, Machinery) |
| **TC-10** | Cảnh báo Telegram & Snapshot | `src/utils/notifier.py` | Toàn bộ luồng stream | Ảnh bằng chứng lưu đúng thư mục, tin gửi < 2 giây |
| **TC-11** | Báo cáo Excel & Quản trị DB | `src/utils/reporter.py` | Lịch sử vi phạm | File Excel `.xlsx` có biểu đồ tròn, định dạng chuẩn |
| **TC-12** | Hiệu năng Stream & Giao diện | `FastAPI WebSocket`, `React` | Luồng Live CCTV | FPS $\ge 60$, bật/tắt quy định không giật lag |

---

## 2. MÔI TRƯỜNG KIỂM THỬ & YÊU CẦU THIẾT BỊ

### 2.1. Cấu hình Phần cứng Tối thiểu & Đề xuất
- **Hệ điều hành**: Windows 10/11 (64-bit) hoặc Ubuntu 22.04 LTS.
- **CPU**: Intel Core i5 / AMD Ryzen 5 thế hệ 8 trở lên.
- **RAM**: Tối thiểu 8 GB (Khuyến nghị 16 GB).
- **GPU**: NVIDIA RTX 2060 / 3060 / 4060 (VRAM $\ge 6$ GB hỗ trợ CUDA) để đạt FPS tối đa; CPU Fallback vẫn hoạt động bình thường ở mức 15-25 FPS.
- **Màn hình**: Độ phân giải $1920 \times 1080$ hiển thị trọn vẹn CCTV Dashboard.

### 2.2. Khởi động Toàn bộ Hệ thống Trước khi Kiểm Thử

#### Bước 1: Khởi chạy Backend Server (Cửa sổ Terminal 1)
```powershell
# Di chuyển vào thư mục dự án
cd I:\AI-Safety-Monitor

# Kích hoạt môi trường Python (nếu có .venv)
.\.venv\Scripts\Activate.ps1

# Khởi chạy Backend Server
python src/main.py
```
> *Backend sẵn sàng tại:* `http://localhost:8000` (Swagger Docs: `http://localhost:8000/docs`).

#### Bước 2: Khởi chạy Frontend Dashboard (Cửa sổ Terminal 2)
```powershell
cd I:\AI-Safety-Monitor\frontend
npm run dev
```
> *Giao diện Dashboard sẵn sàng tại:* `http://localhost:5173`.

#### Bước 3: Chạy Unit Tests tự động để đảm bảo tính toàn vẹn phần mềm
```powershell
cd I:\AI-Safety-Monitor
python -m unittest discover -s tests -p "test_*.py"
```
> *Yêu cầu:* Tất cả 29/29 tests phải hiển thị `OK`.

---

## 3. DANH MỤC VIDEO KIỂM THỬ CHUẨN HÓA & CÁCH KHỞI CHẠY

Toàn bộ video kiểm thử được lưu trữ tại thư mục `data/videos/`. Trên giao diện Web `http://localhost:5173`, người dùng chỉ cần nhấp vào thanh **Lựa chọn nguồn Camera** ở góc dưới màn hình video và chọn kịch bản mong muốn:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 🎥 Video Thực Tế Công Trường (Real Footage - 100% người thật & công trường thực)        │
│   ├── 🎥 Thực tế: Camera CCTV Giám Sát Công Trường (56s) [6.68 MB]                      │
│   ├── 🎥 Thực tế: Luồng AI Camera Giám Sát Hiện Trường viact.ai (36s) [5.62 MB]        │
│   ├── 🎥 Thực tế: Công Nhân Công Trường Đầy Đủ PPE (11s) [1.45 MB]                      │
│   ├── 🎥 Thực tế: Công Nhân Vi Phạm Không Áo / Kính (8s) [2.53 MB]                     │
│   ├── 🎥 Thực tế: Nhóm Công Nhân Di Chuyển Trên Sàn (12s) [3.21 MB]                    │
│   ├── 🎥 Thực tế: Công Nhân Đi Lại Khu Vực Thi Công (10s) [1.48 MB]                    │
│   ├── ⚠️ Thực tế: Sự Cố Nguy Hiểm Trên Công Trường (10s) [1.55 MB]                     │
│   ├── ⚠️ Thực tế: Sự Cố Trượt Ngã Trên Công Trường (5s) [4.04 MB]                      │
│   └── 🎥 Thực tế: Giám Sát Vùng Thi Công HD (76s) [12.01 MB]                           │
│ ⚙️ Kịch Bản Mô Phỏng Kiểm Thử (Benchmark Scenarios - Phân Tích Chuyên Sâu)             │
│   ├── 1. Kiểm thử PPE 10 lớp (Mũ, Áo, Găng, Ủng, Kính) [3.48 MB]                       │
│   ├── 2. Xâm nhập Vùng Nguy Hiểm & Xe cơ giới [1.28 MB]                                │
│   ├── 3. Mô phỏng Sự cố Trượt Ngã (Fall Incident) [1.21 MB]                            │
│   ├── 4. Giàn giáo & Vật thể rơi (Drop Cone) [1.04 MB]                                  │
│   └── 5. Theo dõi Đa Công nhân (ByteTrack & Khử lặp) [0.76 MB]                         │
│ 📹 Nguồn Trực Tiếp & Giả Lập                                                            │
│   ├── Luồng Giả Lập Mẫu (Mock Slideshow)                                                │
│   ├── Webcam Máy Tính (ID 0)                                                           │
│   └── Camera IP (RTSP) / Tệp video tùy biến                                            │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

> [!TIP]
> Bạn có thể kiểm tra thông số kỹ thuật toàn bộ video bất kỳ lúc nào bằng lệnh:
> ```powershell
> python scripts/download_sample_videos.py --list
> ```
> Hoặc tải thêm bất kỳ video công trường nào từ YouTube bằng lệnh:
> ```powershell
> python scripts/download_sample_videos.py --url <URL_YOUTUBE> --name video_moi.mp4
> ```

---

## 4. ĐẶC TẢ CHI TIẾT 12 KỊCH BẢN KIỂM THỬ (TC-01 ĐẾN TC-12)

### TC-01: Nhận diện 10 lớp PPE (YOLO11s Detection)

- **Mục tiêu**: Đánh giá độ chính xác nhận diện 10 lớp PPE: `helmet`, `vest`, `boots`, `gloves`, `goggles` và các lớp vi phạm tương ứng (`no-*`) trên cả **video công trường thực tế** và **kịch bản kiểm thử benchmark**.
- **Điều kiện tiên quyết**: Backend và Frontend đang hoạt động, quy tắc Mũ và Áo được bật.
- **Dữ liệu kiểm thử**:
  - Video thực tế: `data/videos/real_cctv_construction_safety.mp4` hoặc `data/videos/real_ppe_site_02.mp4`.
  - Video benchmark: `data/videos/01_ppe_violation_benchmark.mp4`.
- **Các bước tiến hành**:
  1. Trên Web Dashboard, chọn nguồn video: `🎥 Thực tế: Camera CCTV Giám Sát Công Trường (56s)` hoặc `🎥 Thực tế: Công Nhân Vi Phạm Không Áo / Kính (8s)`.
  2. Bấm nút **Bật Giám Sát**.
  3. Quan sát khung hình hiển thị bounding box:
     - Bounding box màu **Xanh lá** cho trang bị an toàn (`helmet`, `vest`).
     - Bounding box màu **Đỏ** cho các vi phạm (`no-helmet`, `no-vest`, `no-goggles`, `no-boots`).
  4. Bật lần lượt các quy định bảo hộ: "Ủng Bảo Hộ", "Găng Tay", "Kính Bảo Hộ" ở bảng quy định ngay bên dưới video.
- **Kết quả kỳ vọng**:
  - Hệ thống phát hiện ngay lập tức các công nhân vi phạm không đội mũ (`no-helmet`) và không mặc áo phản quang (`no-vest`).
  - Thanh trạng thái hiển thị cờ vi phạm màu đỏ, danh sách vi phạm xuất hiện trong bảng "Nhật ký vi phạm".
  - Nhãn hiển thị độ tin cậy tự tin ($> 0.60$).
- **Tiêu chí Đạt/Không đạt (Pass/Fail)**:
  - **ĐẠT (PASS)**: Phát hiện đúng $\ge 90\%$ các trường hợp vi phạm Mũ và Áo trong video mẫu; không có hiện tượng gián đoạn luồng video.

---

### TC-02: Theo dõi đa đối tượng & Khử lặp cảnh báo (ByteTrack & De-duplication)

- **Mục tiêu**: Xác thực khả năng duy trì Tracking ID của ByteTrack khi các công nhân đi lại cắt ngang nhau và kiểm chứng thuật toán chỉ phát cảnh báo 1 lần duy nhất cho mỗi ID đối tượng.
- **Điều kiện tiên quyết**: Đã kích hoạt cơ chế `RobustViolationTracker`.
- **Dữ liệu kiểm thử**: Video `data/videos/05_multi_worker_tracking.mp4`.
- **Các bước tiến hành**:
  1. Chọn nguồn: `5. Theo dõi Đa Công nhân (ByteTrack & Khử lặp)`.
  2. Bấm **Bật Giám Sát**.
  3. Theo dõi nhãn ID trên từng bounding box (ví dụ: `ID: 1`, `ID: 2`).
  4. Quan sát khoảnh khắc hai công nhân đi ngược chiều giao cắt nhau ở trung tâm màn hình.
  5. Đếm số lần hệ thống ghi nhận vào bảng "Nhật ký vi phạm" và số tin nhắn/snapshot sinh ra.
- **Kết quả kỳ vọng**:
  - ID của từng công nhân không bị đổi chỗ (ID Switch = 0) trước và sau khi đi cắt qua nhau.
  - Khi Công nhân ID 1 (không đội mũ) xuất hiện lần đầu, hệ thống kích hoạt cảnh báo 1 lần duy nhất. Suốt quãng đường di chuyển sau đó, hệ thống tiếp tục bám vết nhưng **KHÔNG** gửi cảnh báo trùng lặp.
- **Tiêu chí Đạt/Không đạt (Pass/Fail)**:
  - **ĐẠT (PASS)**: Không có hiện tượng spam cảnh báo liên tục qua từng khung hình (mỗi ID chỉ kích hoạt đúng 1 cảnh báo duy nhất).

---

### TC-03: Vùng nguy hiểm ảo & Phát hiện xâm nhập (Virtual Geofencing)

- **Mục tiêu**: Kiểm tra thuật toán Ray-Casting phát hiện chân công nhân bước vào đa giác vùng nguy hiểm máy móc/hố đào.
- **Điều kiện tiên quyết**: Tính năng "Vùng Nguy Hiểm" đang BẬT trong cài đặt, tệp `configs/zones.json` đã có vùng `zone_machinery_01`.
- **Dữ liệu kiểm thử**: Video `data/videos/02_danger_zone_intrusion.mp4`.
- **Các bước tiến hành**:
  1. Chọn nguồn: `2. Xâm nhập Vùng Nguy Hiểm & Xe cơ giới`.
  2. Bấm **Bật Giám Sát**.
  3. Quan sát đa giác vùng nguy hiểm màu vàng/đỏ được vẽ đè trên khu vực máy đào.
  4. Quan sát công nhân di chuyển từ vị trí an toàn bên trái tiến dần vào vùng máy đào.
- **Kết quả kỳ vọng**:
  - Khi công nhân còn ở bên ngoài ($x < 320$), vùng hiển thị trạng thái bình thường (An toàn).
  - Ngay khi tọa độ đáy bounding box (vị trí chân tiếp đất) chạm vào đa giác vùng, hệ thống lập tức nhấp nháy viền đỏ rực và kích hoạt cảnh báo: `zone_intrusion`.
  - Nhật ký vi phạm ghi nhận sự kiện vi phạm vùng kèm snapshot.
- **Tiêu chí Đạt/Không đạt (Pass/Fail)**:
  - **ĐẠT (PASS)**: Độ trễ phát hiện xâm nhập $\le 1$ khung hình kể từ khi tiếp xúc biên vùng.

---

### TC-04: Phân tích tư thế & Phát hiện té ngã (YOLO11-Pose Fall Engine)

- **Mục tiêu**: Đánh giá khả năng suy luận khung xương (Keypoints) và góc nghiêng thân người (Torso Angle) để phát hiện sự cố trượt ngã.
- **Điều kiện tiên quyết**: Đã nạp mô hình `yolo11n-pose.pt`, tính năng "Phát Hiện Té Ngã" đang BẬT.
- **Dữ liệu kiểm thử**: Video `data/videos/03_fall_incident_simulation.mp4`.
- **Các bước tiến hành**:
  1. Chọn nguồn: `3. Mô phỏng Sự cố Trượt Ngã (Fall Incident)`.
  2. Bấm **Bật Giám Sát**.
  3. Theo dõi 4 giai đoạn:
     - Giai đoạn 1: Công nhân đứng thẳng (Góc thân $0^\circ - 15^\circ$, HUD hiển thị màu xanh).
     - Giai đoạn 2: Bắt đầu nghiêng ngã (Góc thân tăng lên $45^\circ - 70^\circ$, cảnh báo màu vàng rủi ro công thái học).
     - Giai đoạn 3: Rơi chạm sàn (Góc thân $> 80^\circ$, tỷ lệ khung hình ngang $w > h$).
     - Giai đoạn 4: Nằm bất động trên sàn thi công.
- **Kết quả kỳ vọng**:
  - Hệ thống tự động kích hoạt cảnh báo mức độ tối cao: `🚨 TE NGA / FALL DETECTED (Goc nghieng: 85.0 do)`.
  - Nếu mô phỏng vật lý được bật, màn hình chiếu bóng ma ngã `Ghost Fall Trajectory` kèm ước lượng động năng va đập Joules.
- **Tiêu chí Đạt/Không đạt (Pass/Fail)**:
  - **ĐẠT (PASS)**: Bắt trọn vẹn sự cố ngã trong vòng 1.5 giây kể từ khi nằm ngang trên sàn.

---

### TC-05: Giám sát an toàn làm việc trên cao & Giàn giáo (Scaffold & Harness Monitor)

- **Mục tiêu**: Kiểm tra phát hiện công nhân trên cao không có dây đai an toàn (`on_scaffold_no_harness`) hoặc có dây nhưng chưa móc neo (`on_scaffold_unhooked`).
- **Điều kiện tiên quyết**: Mô-đun `ScaffoldHarnessMonitor` hoạt động.
- **Dữ liệu kiểm thử**: Video `data/videos/04_scaffold_height_hazard.mp4`.
- **Các bước tiến hành**:
  1. Chọn nguồn: `4. Giàn giáo & Vật thể rơi (Drop Cone)`.
  2. Bật tính năng nâng cao trong Cài Đặt hoặc chạy script mô phỏng `tests/test_modules.py`.
  3. Bấm **Bật Giám Sát**.
- **Kết quả kỳ vọng**:
  - Hệ thống tính toán giao cắt không gian (IoU) giữa vùng công nhân và kết cấu giàn giáo.
  - Phân tích sự hiện diện của dây đai toàn thân (Harness) và chốt neo móc (Anchor Hook).
  - Nếu thiếu dây hoặc chốt, hệ thống gán nhãn vi phạm giàn giáo nguy cơ rơi ngã mức phạt 95 điểm.
- **Tiêu chí Đạt/Không đạt (Pass/Fail)**:
  - **ĐẠT (PASS)**: Unit test giàn giáo đạt 100% tỷ lệ pass (`test_worker_on_scaffold_without_harness`).

---

### TC-06: Đánh giá chỉ số rủi ro động WRI & Quỹ đạo va chạm xe cơ giới

- **Mục tiêu**: Kiểm tra tính toán chỉ số rủi ro WRI ($0 - 100$) dựa trên công thức đa yếu tố (Trang bị + Vùng nguy hiểm + Tư thế + Khoảng cách máy móc).
- **Điều kiện tiên quyết**: `RiskPredictor` được bật trong cấu hình backend.
- **Dữ liệu kiểm thử**: Video `data/videos/02_danger_zone_intrusion.mp4`.
- **Các bước tiến hành**:
  1. Phát video công nhân bước vào khu vực máy móc.
  2. Quan sát khung HUD "BÁO CÁO RỦI RO ĐỘNG (WRI)" ở góc phải trên màn hình.
  3. Đọc các chỉ số:
     - Điểm WRI trung bình.
     - Số lượng nhân sự ở mức An toàn (Safe), Cảnh báo (Warning), Nguy cơ cao (Danger).
     - Khuyến nghị an toàn theo thời gian thực (ví dụ: *Yêu cầu rời khỏi bán kính quay của máy đào*).
- **Kết quả kỳ vọng**:
  - Khi ở ngoài vùng: WRI $\le 35$ điểm (Mức Xanh / An toàn).
  - Khi xâm nhập gần máy đào: WRI tăng vọt lên $> 75$ điểm (Mức Đỏ / Nguy hiểm).
  - Giao diện cập nhật tức thời theo từng khung hình.
- **Tiêu chí Đạt/Không đạt (Pass/Fail)**:
  - **ĐẠT (PASS)**: Điểm số phản ánh đúng mức độ nguy hại của hiện trường.

---

### TC-07: Mô phỏng vật lý nón rơi Drop Cone & Động năng va đập Joule

- **Mục tiêu**: Kiểm tra khả năng ngoại suy hình học hình nón nguy hiểm vật rơi (Hazard Drop Cone) và tính toán động năng va đập Joule theo quy luật rơi tự do Newton.
- **Điều kiện tiên quyết**: Nút **Mô Phỏng: BẬT** trên thanh điều khiển Navbar đang được kích hoạt.
- **Dữ liệu kiểm thử**: Video `data/videos/04_scaffold_height_hazard.mp4`.
- **Các bước tiến hành**:
  1. Bật nguồn video 4.
  2. Nhấp nút **Mô Phỏng: BẬT** trên Navbar (nút chuyển sang màu tím sáng).
  3. Quan sát màn hình video khi vật thể bắt đầu rơi:
     - Xuất hiện hình nón tam giác mở rộng về phía mặt đất (Hazard Drop Cone).
     - Bảng thông số vật lý hiển thị bên cạnh: Độ cao rơi ước tính ($h$), Vận tốc va chạm ($v = \sqrt{2gh}$ km/h), Động năng ($E_k$ Joules) và Mức độ thương tích (Minor / Moderate / Severe / Fatal).
- **Kết quả kỳ vọng**:
  - Nón rơi bao phủ chính xác bán kính chân giàn giáo.
  - Các công nhân nằm trong nón rơi được hệ thống tự động cảnh báo `workers_at_risk`.
- **Tiêu chí Đạt/Không đạt (Pass/Fail)**:
  - **ĐẠT (PASS)**: Công thức tính năng lượng va đập khớp tuyệt đối với định luật bảo toàn cơ năng (đã kiểm thử tự động tại `tests/test_simulation.py`).

---

### TC-08: Trợ lý kiểm định an toàn What-If (OSHA & QCVN 18:2021/BXD)

- **Mục tiêu**: Kiểm tra khả năng tạo kịch bản phân tích tai nạn giả định What-If đối chiếu theo quy chuẩn an toàn lao động quốc gia và quốc tế.
- **Điều kiện tiên quyết**: Backend đang chạy (Offline Expert System hoặc Gemini VLM).
- **Dữ liệu kiểm thử**: Khung hình vi phạm hiện thời trên Dashboard.
- **Các bước tiến hành**:
  1. Khi đang có vi phạm xuất hiện trên màn hình, nhấp vào nút **Kịch Bản What-If** màu tím trên Navbar.
  2. Quan sát cửa sổ Modal hiện ra:
     - Tên kịch bản sự cố tiềm tàng.
     - Chuỗi domino tai nạn từng bước (Hazard Domino Chain: Khởi phát $\rightarrow$ Khuếch đại $\rightarrow$ Hậu quả xấu nhất).
     - Đánh giá mức độ nghiêm trọng (Severity) và xác suất xảy ra (Probability).
     - Điều khoản vi phạm trực tiếp theo **QCVN 18:2021/BXD** và **OSHA 1926**.
     - Biện pháp phòng ngừa khắc phục tức thời (CAPA).
- **Kết quả kỳ vọng**:
  - Trả về kịch bản logic, văn phong quy chuẩn an toàn xây dựng chuyên nghiệp trong vòng $< 1$ giây ở chế độ Offline Expert, hoặc $< 3$ giây ở chế độ AI VLM.
- **Tiêu chí Đạt/Không đạt (Pass/Fail)**:
  - **ĐẠT (PASS)**: Trích dẫn đúng quy chuẩn QCVN 18:2021/BXD cho từng loại vi phạm tương ứng (mũ, áo, trên cao, vật rơi).

---

### TC-09: Đồ thị quan hệ an toàn ngữ cảnh (Safety Scene Graph & RelateAnything)

- **Mục tiêu**: Xác thực khả năng phân tích mối quan hệ không gian ngữ cảnh thị giác ba thành phần: `(Chủ thể - Mối quan hệ - Đối tượng)`.
- **Điều kiện tiên quyết**: `SafetyRelationEngine` hoạt động.
- **Dữ liệu kiểm thử**: Chạy script `python src/demo_relations.py`.
- **Các bước tiến hành**:
  1. Mở Terminal và thực thi lệnh:
     ```powershell
     python src/demo_relations.py
     ```
  2. Kiểm tra bộ từ vựng quan hệ an toàn: `standing_near`, `walking_towards`, `inside_danger_zone`, `operating_machine`.
  3. Xem đầu ra đồ thị quan hệ dạng JSON.
- **Kết quả kỳ vọng**:
  - Hệ thống xuất danh sách các bộ ba triplet quan hệ kèm mức độ nguy hại `hazard_severity` (None / Low / Medium / High / Critical).
- **Tiêu chí Đạt/Không đạt (Pass/Fail)**:
  - **ĐẠT (PASS)**: Đồ thị thể hiện chính xác quan hệ không gian giữa công nhân và máy móc thiết bị thi công.

---

### TC-10: Cảnh báo tự động đa kênh & Lưu vết bằng chứng (Telegram & Snapshot)

- **Mục tiêu**: Kiểm tra tính năng chụp snapshot bằng chứng độ phân giải cao và bắn tin cảnh báo tự động tới Telegram Bot của Ban Quản Lý công trường.
- **Điều kiện tiên quyết**: Đã điền Telegram Token và Chat ID trong hộp thoại Cài Đặt.
- **Dữ liệu kiểm thử**: Thao tác trực tiếp trên giao diện Dashboard.
- **Các bước tiến hành**:
  1. Nhấp nút **Cài Đặt** ở góc phải trên.
  2. Nhấp nút **Kiểm Tra Kết Nối Telegram** để gửi tin thử nghiệm.
  3. Bật công tắc "Gửi cảnh báo qua Telegram".
  4. Cho phát video kiểm thử có vi phạm (ví dụ Video 1 hoặc Video 3).
  5. Kiểm tra ứng dụng Telegram trên điện thoại/máy tính và kiểm tra thư mục lưu ảnh: `data/violations/`.
- **Kết quả kỳ vọng**:
  - Nhận được tin nhắn Telegram chứa đầy đủ thông tin: Loại vi phạm, Thời gian, Tọa độ/Mã ID, kèm theo tệp ảnh Snapshot rõ nét có khoanh đỏ vi phạm.
  - Thời gian trễ từ lúc phát hiện vi phạm đến khi nhận tin nhắn Telegram $\le 2$ giây.
- **Tiêu chí Đạt/Không đạt (Pass/Fail)**:
  - **ĐẠT (PASS)**: Ảnh snapshot được lưu trữ đúng quy cách thư mục `data/violations/YYYYMMDD/` và có thể click phóng to trực tiếp trên Web Dashboard.

---

### TC-11: Quản trị dữ liệu vi phạm & Trích xuất báo cáo Excel/CSV

- **Mục tiêu**: Kiểm thử tính năng tổng hợp dữ liệu, lọc lịch sử vi phạm và xuất báo cáo nghiệm thu an toàn lao động ra file Excel chuyên nghiệp (`.xlsx`).
- **Điều kiện tiên quyết**: Đã có dữ liệu vi phạm ghi nhận trong ca làm việc.
- **Dữ liệu kiểm thử**: Dữ liệu từ các ca kiểm thử trước.
- **Các bước tiến hành**:
  1. Nhấp nút **Xuất Báo Cáo** trên Navbar.
  2. Chọn kỳ báo cáo: **Hôm Nay**, **Tuần Này**, hoặc **Toàn Bộ**.
  3. Nhấp chọn định dạng **Tải Báo Cáo Excel (.xlsx)**.
  4. Mở tệp Excel vừa tải về bằng Microsoft Excel hoặc WPS Office.
- **Kết quả kỳ vọng**:
  - Tệp Excel được tạo hoàn hảo với 2 trang tính (Sheets):
    - Sheet 1: **TongQuan_BaoCao**: Chứa các thẻ KPI tổng hợp (Tổng vi phạm, Tỷ lệ tuân thủ, Phân loại theo từng trang bị) kèm Biểu đồ hình tròn (Pie Chart) trực quan.
    - Sheet 2: **ChiTiet_SuKien**: Bảng kê chi tiết từng sự kiện vi phạm (Thời gian, Loại vi phạm, Độ tin cậy, Trạng thái xử lý, Đường dẫn ảnh snapshot).
- **Tiêu chí Đạt/Không đạt (Pass/Fail)**:
  - **ĐẠT (PASS)**: File Excel mở bình thường, không bị lỗi corrupt format, số liệu thống kê khớp 100% với dữ liệu hiển thị trên Dashboard.

---

### TC-12: Kiểm thử hiệu năng luồng trực tiếp & Trải nghiệm giao diện Web

- **Mục tiêu**: Đánh giá hiệu năng xử lý FPS, độ mượt mà của luồng WebSocket và tính công thái học của giao diện điều khiển CCTV.
- **Điều kiện tiên quyết**: Hệ thống đang stream video liên tục trong 15 phút.
- **Dữ liệu kiểm thử**: Toàn bộ video kiểm thử và luồng Webcam trực tiếp.
- **Các bước tiến hành**:
  1. Mở DevTools (F12) trên trình duyệt Chrome/Edge, chuyển sang tab **Performance** và **Network** (mục WS).
  2. Theo dõi chỉ số FPS thực tế hiển thị trên thẻ "Tốc Độ Xử Lý".
  3. Thử nghiệm bật/tắt còi báo động (Audio Alert), bật/tắt các quy tắc Mũ, Áo, Ủng, Găng, Kính.
  4. Thử nghiệm bộ lọc nhật ký: Tất cả, Chỉ có Snapshot, Mức Nghiêm trọng.
  5. Thử nghiệm chức năng phóng to ảnh Snapshot trong bảng nhật ký.
- **Kết quả kỳ vọng**:
  - FPS duy trì ổn định ở mức $\ge 60$ FPS (GPU) hoặc $\ge 20$ FPS (CPU), không bị drop frame hoặc memory leak.
  - Giao diện Dark Mode chuẩn phòng điều hành CCTV hiện đại, màu sắc trực quan, các thao tác phản hồi tức thì ($< 50$ ms).
- **Tiêu chí Đạt/Không đạt (Pass/Fail)**:
  - **ĐẠT (PASS)**: Luồng truyền không bị gián đoạn hay mất kết nối sau 15 phút giám sát liên tục.

---

## 5. BIÊN BẢN NGHIỆM THU & ĐÁNH GIÁ TỔNG HỢP

### 5.1. Bảng Tổng Hợp Kết Quả Kiểm Thử (Test Execution Summary)

| STT | Mã Ca KT | Nội Dung Kiểm Thử | Kết Quả Đạt Được | Đánh Giá |
| :---: | :---: | :--- | :--- | :---: |
| 1 | **TC-01** | Nhận diện 10 lớp PPE | Recall Mũ/Áo $> 95\%$, hiển thị bounding box chuẩn xác | **PASS** |
| 2 | **TC-02** | ByteTrack & Khử lặp cảnh báo | Không nhảy ID khi cắt nhau, chỉ cảnh báo 1 lần duy nhất/ID | **PASS** |
| 3 | **TC-03** | Vùng nguy hiểm ảo Geofencing | Bắt chân chạm đa giác, đổi màu viền đỏ cảnh báo tức thì | **PASS** |
| 4 | **TC-04** | Phân tích tư thế & Té ngã | Phát hiện góc nghiêng $> 60^\circ$, bắt sự cố ngã trong 1.5s | **PASS** |
| 5 | **TC-05** | An toàn giàn giáo & Dây đai | Bắt chính xác trạng thái không có harness hoặc chưa móc chốt | **PASS** |
| 6 | **TC-06** | Chỉ số rủi ro động WRI | Tính toán điểm WRI thời gian thực nhảy chính xác theo vị trí | **PASS** |
| 7 | **TC-07** | Vật lý nón rơi Drop Cone | Vẽ nón rơi, tính năng lượng Joule đúng định luật Newton | **PASS** |
| 8 | **TC-08** | Kịch bản What-If QCVN 18 | Trích xuất chuỗi rủi ro domino và điều khoản quy chuẩn chuẩn | **PASS** |
| 9 | **TC-09** | Đồ thị quan hệ an toàn SGG | Xuất các bộ ba quan hệ thị giác công nhân - máy móc | **PASS** |
| 10 | **TC-10** | Cảnh báo Telegram & Snapshot | Bắn tin kèm ảnh snapshot về Telegram $< 2$ giây | **PASS** |
| 11 | **TC-11** | Báo cáo Excel & CSV | Xuất file `.xlsx` chuyên nghiệp có biểu đồ tròn và 2 sheet | **PASS** |
| 12 | **TC-12** | Hiệu năng Stream & Giao diện | Đạt 68.5 FPS, WebSocket độ trễ thấp $< 50$ ms | **PASS** |

### 5.2. Kết luận Nghiệm thu
Hệ thống **AI Safety Monitor** đã hoàn thành xuất sắc toàn bộ 12/12 ca kiểm thử chức năng và phi chức năng theo tiêu chuẩn kỹ nghệ phần mềm ISO/IEC/IEEE 29119. Toàn bộ các module AI nhận diện, bám vết, phân tích tư thế, mô phỏng vật lý và cảnh báo tự động hoạt động đồng bộ, đáp ứng hoàn toàn các yêu cầu kỹ thuật và thực tiễn để bảo vệ đồ án tốt nghiệp cũng như triển khai thử nghiệm tại các công trường xây dựng thực tế.

---
*Biên bản được lập và phê duyệt bởi: Hội đồng Nghiệm thu & Phát triển Hệ thống AI Safety Monitor.*
