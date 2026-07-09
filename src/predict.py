import os
import cv2
import argparse
import torch
from ultralytics import YOLO

# Định nghĩa các lớp vi phạm và an toàn
UNSAFE_CLASSES = {'no-boots', 'no-gloves', 'no-goggles', 'no-helmet', 'no-vest'}
SAFE_CLASSES = {'boots', 'gloves', 'goggles', 'helmet', 'vest'}

def run_inference(args):
    # 1. Tải mô hình YOLO
    model_path = args.model
    if not os.path.exists(model_path):
        print(f"Cảnh báo: Không tìm thấy checkpoint tại {model_path}. Chuyển sang dùng model pre-trained mặc định.")
        model_path = "yolo11s.pt"
    
    model = YOLO(model_path)
    print(f"Đã tải thành công mô hình từ: {model_path}")
    
    # 2. Xử lý nguồn dữ liệu đầu vào (Inference Source)
    source = args.source
    # Kiểm tra xem có phải là webcam hay không (0, 1, 2...)
    if source.isdigit():
        source = int(source)
        print(f"Đang mở Webcam: {source}")
    else:
        source = os.path.abspath(source)
        if not os.path.exists(source):
            raise FileNotFoundError(f"Không tìm thấy nguồn dữ liệu đầu vào: {source}")
        print(f"Đang chạy inference nguồn: {source}")

    # 3. Chạy dự đoán sử dụng generator stream=True của Ultralytics (Tiết kiệm RAM khi chạy video/webcam)
    results = model(
        source=source,
        conf=args.conf,
        device=args.device,
        stream=True,
        show=False  # Chúng ta sẽ tự quản lý việc hiển thị bằng OpenCV để tùy chỉnh bounding box
    )

    # Đảm bảo thư mục lưu kết quả tồn tại
    os.makedirs(args.output, exist_ok=True)
    
    # Thiết lập lưu video nếu nguồn đầu vào là video
    video_writer = None
    is_video = False
    
    if isinstance(source, str) and (source.lower().endswith(('.mp4', '.avi', '.mov', '.mkv'))):
        is_video = True

    # Duyệt qua từng khung hình (frame)
    frame_count = 0
    for result in results:
        frame_count += 1
        # Tạo bản sao của ảnh gốc để vẽ
        frame = result.orig_img.copy()
        
        # Lấy thông tin các hộp phát hiện (boxes)
        boxes = result.boxes
        violations = []
        
        for box in boxes:
            # Lấy toạ độ box (x1, y1, x2, y2)
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            
            # Lấy độ tin cậy (confidence)
            conf = float(box.conf[0])
            
            # Lấy ID lớp và tên lớp
            class_id = int(box.cls[0])
            class_name = model.names[class_id]
            
            # Phân loại màu sắc dựa trên mức độ an toàn
            # Vi phạm (Unsafe) -> Màu đỏ (BGR: 0, 0, 255)
            # An toàn (Safe) -> Màu xanh lá (BGR: 0, 255, 0)
            if class_name in UNSAFE_CLASSES:
                color = (0, 0, 255)  # Đỏ
                label = f"VI PHAM: {class_name} ({conf:.2f})"
                violations.append(class_name)
            else:
                color = (0, 255, 0)  # Xanh lá
                label = f"{class_name} ({conf:.2f})"
            
            # Vẽ bounding box lên frame
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            # Vẽ background cho text label
            text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
            cv2.rectangle(frame, (x1, y1 - 20), (x1 + text_size[0], y1), color, -1)
            
            # Viết chữ label lên frame
            cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # Hiển thị cảnh báo tổng hợp thời gian thực lên màn hình
        if violations:
            violation_text = f"CANH BAO: Phat hien {len(violations)} vi pham!"
            cv2.putText(frame, violation_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            print(f"[CẢNH BÁO] Khung hình {frame_count}: Phát hiện vi phạm an toàn! Chi tiết: {', '.join(violations)}")
        else:
            cv2.putText(frame, "AN TOAN LAO DONG", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        # 4. Lưu kết quả
        if args.save:
            if is_video:
                # Thiết lập VideoWriter nếu chưa có
                if video_writer is None:
                    height, width, _ = frame.shape
                    fps = 30  # FPS mặc định
                    save_path = os.path.join(args.output, "result_video.mp4")
                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                    video_writer = cv2.VideoWriter(save_path, fourcc, fps, (width, height))
                    print(f"Đang lưu kết quả video tại: {save_path}")
                video_writer.write(frame)
            else:
                # Lưu ảnh đơn
                if isinstance(source, int):
                    save_path = os.path.join(args.output, f"webcam_frame_{frame_count}.jpg")
                else:
                    filename = os.path.basename(result.path)
                    save_path = os.path.join(args.output, filename)
                cv2.imwrite(save_path, frame)
                print(f"Đã lưu kết quả ảnh tại: {save_path}")

        # 5. Hiển thị màn hình preview live
        if args.show:
            cv2.imshow("Safety Monitoring System - YOLO11 Demo", frame)
            # Nhấn 'q' để thoát sớm
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("Đã nhận lệnh thoát từ người dùng.")
                break

    # Giải phóng tài nguyên sau khi xong
    if video_writer is not None:
        video_writer.release()
    cv2.destroyAllWindows()
    print("Quá trình chạy inference đã kết thúc.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YOLO11 Real-time PPE Safety Inference Script")
    
    parser.add_argument("--model", type=str, default="runs/detect/train_safety/weights/best.pt",
                        help="Đường dẫn đến file trọng số .pt của mô hình đã train")
    parser.add_argument("--source", type=str, default="data/ppe_dataset/test/images",
                        help="Nguồn đầu vào: Đường dẫn ảnh, thư mục ảnh, file video (.mp4) hoặc số '0' cho Webcam")
    parser.add_argument("--conf", type=float, default=0.25,
                        help="Ngưỡng độ tin cậy để hiển thị phát hiện (Confidence Threshold)")
    parser.add_argument("--device", type=str, default="0" if torch.cuda.is_available() else "cpu",
                        help="Thiết bị chạy: '0' cho GPU hoặc 'cpu' cho CPU")
    parser.add_argument("--show", action="store_true", default=False,
                        help="Bật cửa sổ hiển thị trực tiếp (Không nên dùng khi chạy trên server headless)")
    parser.add_argument("--save", action="store_true", default=True,
                        help="Lưu kết quả dự đoán (ảnh/video) vào ổ đĩa")
    parser.add_argument("--output", type=str, default="runs/predict_results",
                        help="Thư mục lưu kết quả inference")

    parsed_args = parser.parse_args()
    
    # Hỗ trợ nhận diện tùy chọn hiển thị trực tiếp khi chạy webcam
    if parsed_args.source == "0" or parsed_args.source == 0:
        parsed_args.show = True
        
    run_inference(parsed_args)
