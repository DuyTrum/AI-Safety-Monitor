import os
import argparse
from ultralytics import YOLO

def export_model(args):
    # 1. Tải mô hình YOLO với trọng số tốt nhất đã huấn luyện
    model_path = args.model
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Không tìm thấy file trọng số mô hình tại: {model_path}")
        
    model = YOLO(model_path)
    print(f"Đã tải thành công mô hình từ: {model_path}")

    # 2. Thực hiện export sang định dạng đích
    print(f"Đang tiến hành xuất mô hình sang định dạng: {args.format.upper()}...")
    
    # model.export hỗ trợ nhiều định dạng như 'onnx', 'engine' (TensorRT), 'openvino', 'tflite'...
    exported_path = model.export(
        format=args.format,
        imgsz=args.imgsz,
        half=args.half,        # Sử dụng FP16 (Half precision) để tăng tốc và giảm dung lượng model
        dynamic=args.dynamic,  # Hỗ trợ kích thước ảnh đầu vào thay đổi linh hoạt (Dynamic input shape)
        simplify=True         # Tối ưu hóa cấu trúc đồ thị ONNX (ONNX-Simplifier)
    )
    
    print("\n" + "=" * 50)
    print("XUẤT MÔ HÌNH THÀNH CÔNG!")
    print("=" * 50)
    print(f"Định dạng đích: {args.format.upper()}")
    print(f"File mô hình xuất bản được lưu tại: {exported_path}")
    print("=" * 50)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YOLO11 Model Export Script for Production Deployment")
    
    parser.add_argument("--model", type=str, default="runs/detect/runs/detect/train_safety/weights/best.pt",
                        help="Đường dẫn đến file best.pt cần export")
    parser.add_argument("--format", type=str, default="onnx", choices=["onnx", "engine", "openvino", "tflite"],
                        help="Định dạng xuất bản (Đề xuất: 'onnx' cho CPU/Đa nền tảng hoặc 'engine' cho GPU Nvidia)")
    parser.add_argument("--imgsz", type=int, default=640,
                        help="Kích thước ảnh đầu vào của mô hình")
    parser.add_argument("--half", action="store_true", default=False,
                        help="Kích thước FP16 (Giảm bộ nhớ và tăng tốc độ suy luận)")
    parser.add_argument("--dynamic", action="store_true", default=True,
                        help="Hỗ trợ dynamic batch và dynamic image size")

    parsed_args = parser.parse_args()
    export_model(parsed_args)
