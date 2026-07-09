import os
import argparse
import torch
from ultralytics import YOLO

def run_validation(args):
    # 1. Tải mô hình YOLO
    model_path = args.model
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Không tìm thấy file trọng số của mô hình tại: {model_path}")
    
    model = YOLO(model_path)
    print(f"Đã tải thành công mô hình từ: {model_path}")
    
    # 2. Định vị đường dẫn tuyệt đối cho file data.yaml
    data_yaml_path = os.path.abspath(args.data)
    if not os.path.exists(data_yaml_path):
        raise FileNotFoundError(f"Không tìm thấy file cấu hình dữ liệu tại: {data_yaml_path}")

    print(f"Đang chạy đánh giá trên split: {args.split}")
    
    # 3. Đánh giá mô hình
    metrics = model.val(
        data=data_yaml_path,
        split=args.split,         # val, test, or train
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        project=args.project,
        name=args.name,
        exist_ok=True,
        save_json=True,           # Lưu kết quả định dạng JSON để phân tích thêm
        plots=True                # Tạo ra các biểu đồ PR curve, Confusion Matrix...
    )
    
    # 4. Hiển thị báo cáo kết quả tổng hợp ra terminal
    print("\n" + "=" * 50)
    print(f"KẾT QUẢ ĐÁNH GIÁ MÔ HÌNH (SPLIT: {args.split.upper()})")
    print("=" * 50)
    print(f"mAP50-95 (Độ chính xác toàn diện): {metrics.box.map:.4f}")
    print(f"mAP50 (Độ chính xác ở IoU=0.5):    {metrics.box.map50:.4f}")
    print(f"Precision (Độ chính xác dự báo):   {metrics.box.mp:.4f}")
    print(f"Recall (Khả năng phát hiện đúng):  {metrics.box.mr:.4f}")
    print(f"F1 Score (Trung bình điều hòa):    {metrics.box.f1.mean():.4f}")
    print("-" * 50)
    
    # Hiển thị chi tiết từng Class
    print("CHI TIẾT TRÊN TỪNG CLASS:")
    print(f"{'Class Name':<15} | {'Precision':<10} | {'Recall':<10} | {'mAP50':<10} | {'mAP50-95':<10}")
    print("-" * 65)
    
    # metrics.names chứa mapping của class index sang class name
    names = metrics.names
    # map_with_class chứa list mAP50-95 ứng với từng class
    for i, c_name in names.items():
        # Lấy các chỉ số tương ứng của lớp i
        p = metrics.box.class_result(i)[0]
        r = metrics.box.class_result(i)[1]
        map50 = metrics.box.class_result(i)[2]
        map50_95 = metrics.box.class_result(i)[3]
        print(f"{c_name:<15} | {p:<10.4f} | {r:<10.4f} | {map50:<10.4f} | {map50_95:<10.4f}")
        
    print("=" * 50)
    print(f"Biểu đồ Confusion Matrix và các Curves được lưu tại: {metrics.save_dir}")
    print("=" * 50)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YOLO11 Detailed Evaluation/Validation Script")
    
    parser.add_argument("--model", type=str, default="runs/detect/train_safety/weights/best.pt",
                        help="Đường dẫn tới mô hình cần đánh giá (.pt)")
    parser.add_argument("--data", type=str, default="data/ppe_dataset/data.yaml",
                        help="Đường dẫn đến file data.yaml")
    parser.add_argument("--split", type=str, default="test", choices=["val", "test", "train"],
                        help="Split tập dữ liệu dùng để đánh giá: 'val' (Validation) hoặc 'test' (Test)")
    parser.add_argument("--imgsz", type=int, default=640,
                        help="Kích thước ảnh đầu vào")
    parser.add_argument("--batch", type=int, default=16,
                        help="Batch size dùng khi validate")
    parser.add_argument("--device", type=str, default="0" if torch.cuda.is_available() else "cpu",
                        help="Thiết bị chạy: '0' cho GPU hoặc 'cpu' cho CPU")
    parser.add_argument("--workers", type=int, default=4,
                        help="Số lượng workers để nạp dữ liệu")
    parser.add_argument("--project", type=str, default="runs/val_results",
                        help="Thư mục cha lưu kết quả đánh giá")
    parser.add_argument("--name", type=str, default="val_report",
                        help="Tên thư mục lưu kết quả đánh giá chi tiết")

    parsed_args = parser.parse_args()
    
    run_validation(parsed_args)
