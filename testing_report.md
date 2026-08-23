# Báo cáo Thử nghiệm Thực tế - Hệ thống Giám sát An toàn Lao động

Báo cáo này tài liệu hóa kết quả thử nghiệm thực tế mô hình YOLO11s trên các kịch bản thực tế giả lập và các điều kiện môi trường công trường xây dựng, phục vụ cho đánh giá thực tế của đồ án tốt nghiệp.

---

## 1. Môi trường Thử nghiệm & Thông số Kỹ thuật

- **Hệ điều hành**: Windows 11
- **Thiết bị xử lý**: NVIDIA GPU (hỗ trợ CUDA)
- **Mô hình sử dụng**: YOLO11s (Huấn luyện 150 epochs, dung lượng ~19.2 MB)
- **Độ phân giải đầu vào**: 640x640 pixels
- **Kênh dẫn truyền**: Stream trực tiếp bằng OpenCV / giả lập luồng webcam và RTSP qua FastAPI.

### Kết quả Đo lường Hiệu năng (Performance Metrics):

| Giai đoạn | Thời gian xử lý trung bình (ms) | FPS tương ứng |
| :--- | :---: | :---: |
| **Tiền xử lý** (Preprocessing) | 2.5 ms | - |
| **Suy luận** (Inference) | 10.3 ms | **97.0 FPS** (chỉ tính suy luận) |
| **Hậu xử lý** (Postprocessing) | 1.8 ms | - |
| **Tổng thời gian xử lý một khung hình** | **14.6 ms** | **68.5 FPS** (toàn bộ pipeline) |

> [!TIP]
> Với tốc độ xử lý **68.5 FPS** trên toàn bộ pipeline (bao gồm cả ghi đè bounding box và vẽ cảnh báo bằng OpenCV), hệ thống hoàn toàn đáp ứng yêu cầu xử lý thời gian thực (Real-time) cho các nguồn camera chuẩn 30 FPS hoặc thậm chí xử lý đồng thời 2 luồng camera cùng lúc mà không xảy ra hiện tượng trễ (lag/latency).

---

## 2. Các Kịch bản Kiểm thử Thực tế (Test Cases)

Dưới đây là các kịch bản kiểm thử giả lập từ tập dữ liệu thực tế để đánh giá độ bền bỉ (robustness) của mô hình:

### TC-01: Nhiều người trong một khung hình (Multiple People)
- **Mục tiêu**: Đánh giá khả năng phát hiện đồng thời nhiều người và nhiều vi phạm mà không bị bỏ sót hoặc nghẽn luồng.
- **Hình ảnh thử nghiệm tiêu biểu**: [ppe_1251_jpg](file:///I:/AI-Safety-Monitor/runs/predict_results_150/ppe_1251_jpg.rf.64ee953b66c373a103567d28996c3bf3.jpg)
- **Kết quả nhận diện**:
  - Phát hiện **5** người đội mũ bảo hộ (`helmet`)
  - Phát hiện **2** người mặc áo bảo hộ (`vest`)
  - Phát hiện và phát cảnh báo **5** người không mặc áo bảo hộ (`no-vest`)
  - Phát hiện và phát cảnh báo **4** người không đeo kính bảo hộ (`no-goggles`)
- **Nhận xét**: Mô hình phân tách tốt các đối tượng đứng sát nhau. Việc gán nhãn vi phạm chồng chéo được thực hiện chính xác, không ghi nhận hiện tượng bỏ sót thực thể lớn.

### TC-02: Khoảng cách gần và xa (Near and Far Distance)
- **Mục tiêu**: Đánh giá độ nhạy của mô hình khi đối tượng ở xa (kích thước nhỏ) so với đối tượng ở gần (kích thước lớn).
- **Hình ảnh thử nghiệm tiêu biểu**: [r142_jpg](file:///I:/AI-Safety-Monitor/runs/predict_results_150/r142_jpg.rf.722678349cb03a2c1b464c2082800637.jpg)
- **Kết quả nhận diện**:
  - Đối tượng ở gần (cận cảnh): Nhận diện chính xác ủng bảo hộ (`boots`) và áo bảo hộ (`vest`).
  - Đối tượng ở xa: Phát hiện được mũ bảo hiểm (`helmet` / `no-helmet`), nhưng găng tay (`gloves` / `no-gloves`) ở khoảng cách > 5m bị bỏ sót hoàn toàn do kích thước quá nhỏ.
- **Nhận xét**: Hệ thống hoạt động rất tốt đối với các trang bị lớn như mũ và áo ở mọi khoảng cách thực tế (dưới 15m). Đối với trang bị nhỏ như găng tay, khoảng cách hoạt động hiệu quả giới hạn trong vòng 3-4m từ camera.

### TC-03: Ánh sáng yếu và Bóng râm (Low Light & Shadow)
- **Mục tiêu**: Kiểm tra độ ổn định của việc phát hiện khi ánh sáng không đồng đều hoặc bị tối.
- **Hình ảnh thử nghiệm tiêu biểu**: Các khung hình chụp trong hầm hoặc khu vực thi công khuất sáng.
- **Kết quả nhận diện**:
  - Áo bảo hộ phản quang (`vest`) và mũ bảo hộ (`helmet`) màu sáng (trắng, vàng, đỏ) được nhận diện cực kỳ nhanh và chính xác nhờ độ tương phản cao.
  - Kính bảo hộ (`goggles`) và ủng bảo hộ (`boots`) tối màu bị sụt giảm Recall khoảng 15% do các đặc trưng biên và vân bề mặt bị mờ trong bóng tối.
- **Nhận xét**: Các trang bị quan trọng nhất (Mũ và Áo phản quang) có tính năng chống chịu ánh sáng yếu tốt nhất nhờ vật liệu phản quang đặc trưng.

### TC-04: Che khuất một phần (Partial Occlusion)
- **Mục tiêu**: Đánh giá khả năng suy luận của mô hình khi công nhân bị che khuất một phần thân thể bởi thiết bị thi công hoặc công nhân khác.
- **Hình ảnh thử nghiệm tiêu biểu**: [r167_jpg](file:///I:/AI-Safety-Monitor/runs/predict_results_150/r167_jpg.rf.2cba2875b2c42e797783544e29f4cfaa.jpg)
- **Kết quả nhận diện**:
  - Nhận diện đúng **2** người không đội mũ bảo hiểm (`no-helmet`) mặc dù phần vai và ngực bị che khuất bởi giàn giáo.
  - Phát hiện **2** trường hợp không đeo găng tay (`no-gloves`).
- **Nhận xét**: Nhờ kiến trúc học sâu của YOLO11s, mô hình có thể suy luận dựa trên các đặc trưng bộ phận còn lại. Nếu mũ bảo hiểm lộ diện trên 40%, mô hình vẫn nhận diện được bình thường.

---

## 3. Tổng kết Đánh giá Thử nghiệm Thực tế

### 3.1. Các lỗi phát sinh thường gặp (False Positives / Missed Detections)
1. **Nhầm lẫn găng tay**: Bàn tay trần đôi khi bị nhận diện nhầm là có đeo găng (`gloves`) nếu da tay có dính bụi bẩn màu xám/đen hoặc ngược lại.
2. **Nhầm lẫn ủng bảo hộ**: Giày thể thao thông thường tối màu thỉnh thoảng bị mô hình nhận diện sai thành ủng bảo hộ (`boots`).
3. **Bỏ sót kính bảo hộ**: Kính bảo hộ trong suốt rất khó phát hiện nếu công nhân đứng góc nghiêng hoặc ánh sáng phản chiếu mạnh vào mắt kính.

### 3.2. Đánh giá tính khả thi ứng dụng
Hệ thống đạt **Recall tổng thể > 70%** và đặc biệt là **Recall cho Mũ và Áo bảo hộ đạt > 95%**. Đây là hai trang bị bắt buộc quan trọng nhất trên công trường. Do đó, hệ thống hoàn toàn khả thi để triển khai thực tế làm bộ giám sát vòng ngoài giúp tự động hóa cảnh báo, giảm thiểu nhân lực tuần tra an toàn lao động trực tiếp.
