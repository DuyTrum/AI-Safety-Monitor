import os
import sys
import argparse
import torch
from ultralytics import YOLO

def check_system():
    """
    Kiểm tra cấu hình hệ thống: CPU, GPU, CUDA và dung lượng VRAM.
    Điều này giúp xác định cấu hình huấn luyện phù hợp.
    """
    print("=" * 50)
    print("KIỂM TRA HỆ THỐNG PHẦN CỨNG")
    print("=" * 50)
    print(f"Phiên bản Python: {sys.version}")
    print(f"Phiên bản PyTorch: {torch.__version__}")
    
    cuda_available = torch.cuda.is_available()
    print(f"Hỗ trợ CUDA (GPU): {'CÓ' if cuda_available else 'KHÔNG'}")
    
    if cuda_available:
        device_count = torch.cuda.device_count()
        print(f"Số lượng GPU khả dụng: {device_count}")
        for i in range(device_count):
            device_name = torch.cuda.get_device_name(i)
            # Lấy thông tin VRAM (tính bằng GB)
            total_memory = torch.cuda.get_device_properties(i).total_memory / (1024 ** 3)
            print(f"  - GPU [{i}]: {device_name} ({total_memory:.2f} GB VRAM)")
    else:
        print("CẢNH BÁO: Không tìm thấy GPU CUDA! Tiến hành chạy bằng CPU sẽ rất chậm.")
    print("=" * 50 + "\n")

def run_training(args):
    """
    Hàm khởi tạo và thực thi quá trình huấn luyện YOLO11.
    """
    # 1. Định vị đường dẫn tuyệt đối cho file data.yaml
    # Nếu file data.yaml truyền vào là đường dẫn tương đối, chuyển nó thành tuyệt đối
    data_yaml_path = os.path.abspath(args.data)
    if not os.path.exists(data_yaml_path):
        raise FileNotFoundError(f"Không tìm thấy file cấu hình dữ liệu tại: {data_yaml_path}")
        
    print(f"Đang sử dụng dataset tại: {data_yaml_path}")
    print(f"Kiểu mô hình huấn luyện: {args.model}")
    print(f"Các thông số chính: Epochs={args.epochs}, Batch size={args.batch}, Image size={args.imgsz}")

    # 2. Khởi tạo mô hình YOLO11
    # Ultralytics sẽ tự động tải weights pre-trained từ server nếu chưa có sẵn ở thư mục hiện tại
    model = YOLO(args.model)

    # 3. Tiến hành huấn luyện (Fine-tuning)
    # Các hyperparameter được cấu hình tối ưu dựa trên cấu hình GPU RTX 2060 Super 8GB
    results = model.train(
        data=data_yaml_path,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        optimizer=args.optimizer,
        lr0=args.lr0,
        lrf=args.lrf,
        momentum=args.momentum,
        weight_decay=args.weight_decay,
        patience=args.patience,
        cache=args.cache,
        cos_lr=args.cos_lr,
        close_mosaic=args.close_mosaic,
        project=args.project,
        name=args.name,
        exist_ok=True,
        # Các tham số augmentation nâng cao
        mosaic=args.mosaic,
        mixup=args.mixup,
        hsv_h=args.hsv_h,
        hsv_s=args.hsv_s,
        hsv_v=args.hsv_v,
        fliplr=args.fliplr
    )
    
    print("\n" + "=" * 50)
    print("HUẤN LUYỆN HOÀN TẤT THÀNH CÔNG!")
    print("=" * 50)
    # Lấy thư mục chứa kết quả train gần nhất
    save_dir = results.save_dir
    print(f"Kết quả huấn luyện (log, plot, weights) được lưu tại: {save_dir}")
    print(f"Trọng số mô hình tốt nhất (Best weights): {os.path.join(save_dir, 'weights', 'best.pt')}")
    print(f"Trọng số mô hình cuối cùng (Last weights): {os.path.join(save_dir, 'weights', 'last.pt')}")
    print("=" * 50)

if __name__ == "__main__":
    # Điểm mấu chốt trên Windows để tránh lỗi Spawn lặp vô chậm (RunTimeError) khi chạy đa tiến trình
    check_system()

    parser = argparse.ArgumentParser(description="YOLO11 Training Script for PPE Safety Detection")
    
    # Cấu hình đường dẫn và mô hình
    parser.add_argument("--model", type=str, default="yolo11s.pt", 
                        help="Tên phiên bản mô hình YOLO11 (yolo11n.pt, yolo11s.pt, yolo11m.pt, yolo11l.pt)")
    parser.add_argument("--data", type=str, default="data/ppe_dataset/data.yaml", 
                        help="Đường dẫn đến file data.yaml")
    parser.add_argument("--project", type=str, default="runs/detect", 
                        help="Thư mục cha lưu kết quả huấn luyện")
    parser.add_argument("--name", type=str, default="train_safety", 
                        help="Tên thư mục lưu kết quả cụ thể của phiên huấn luyện này")

    # Hyperparameters cho huấn luyện
    parser.add_argument("--epochs", type=int, default=100, 
                        help="Số lượng epochs huấn luyện (Đề xuất: 100-150 để hội tụ tốt)")
    parser.add_argument("--imgsz", type=int, default=640, 
                        help="Kích thước ảnh đầu vào (Nên giữ mặc định 640)")
    parser.add_argument("--batch", type=int, default=16, 
                        help="Số lượng batch size (Đề xuất: 16 cho RTX 2060 Super 8GB)")
    parser.add_argument("--device", type=str, default="0", 
                        help="Thiết bị sử dụng để train: '0' cho GPU đầu tiên, 'cpu' cho CPU")
    parser.add_argument("--workers", type=int, default=4, 
                        help="Số luồng CPU nạp dữ liệu (Workers). Trên Windows nên để 2 hoặc 4")
    parser.add_argument("--optimizer", type=str, default="AdamW", choices=["SGD", "Adam", "AdamW", "RMSProp"],
                        help="Thuật toán tối ưu hóa (Đề xuất: AdamW cho độ hội tụ mượt mà)")
    parser.add_argument("--lr0", type=float, default=0.01, 
                        help="Tốc độ học ban đầu (Initial learning rate)")
    parser.add_argument("--lrf", type=float, default=0.01, 
                        help="Tỷ lệ tốc độ học tối thiểu ở epoch cuối cùng (Final learning rate fraction)")
    parser.add_argument("--momentum", type=float, default=0.937, 
                        help="Hệ số momentum của optimizer")
    parser.add_argument("--weight_decay", type=float, default=0.0005, 
                        help="Tham số Weight Decay để tránh Overfitting")
    parser.add_argument("--patience", type=int, default=20, 
                        help="Early Stopping: Dừng sớm nếu sau N epoch liên tiếp mAP không tăng")
    parser.add_argument("--cache", action="store_true", default=False, 
                        help="Lưu cache dataset vào RAM để tăng tốc. Tắt đi nếu RAM của máy yếu (< 16GB)")
    parser.add_argument("--cos_lr", action="store_true", default=True, 
                        help="Sử dụng Cosine Annealing learning rate schedule để giảm dần LR mượt mà")
    parser.add_argument("--close_mosaic", type=int, default=10, 
                        help="Số epochs cuối cùng sẽ TẮT Mosaic augmentation để mô hình tinh chỉnh chính xác")

    # Augmentations (Dữ liệu tăng cường)
    parser.add_argument("--mosaic", type=float, default=1.0, 
                        help="Tỷ lệ áp dụng Mosaic Augmentation (Ghép 4 ảnh thành 1) (0.0 đến 1.0)")
    parser.add_argument("--mixup", type=float, default=0.0, 
                        help="Tỷ lệ áp dụng MixUp Augmentation (Trộn 2 ảnh với nhau) (Nên dùng cho model lớn)")
    parser.add_argument("--hsv_h", type=float, default=0.015, 
                        help="Tăng cường phổ màu HSV - Hue (0.0 - 1.0)")
    parser.add_argument("--hsv_s", type=float, default=0.7, 
                        help="Tăng cường phổ màu HSV - Saturation (0.0 - 1.0)")
    parser.add_argument("--hsv_v", type=float, default=0.4, 
                        help="Tăng cường phổ màu HSV - Value (Độ sáng) (0.0 - 1.0)")
    parser.add_argument("--fliplr", type=float, default=0.5, 
                        help="Xác suất lật ảnh theo chiều ngang (0.0 đến 1.0)")

    parsed_args = parser.parse_args()
    
    # Chạy hàm huấn luyện chính
    run_training(parsed_args)
