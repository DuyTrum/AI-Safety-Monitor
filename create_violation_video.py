"""Create a realistic Construction Safety Violation & Incident Simulation Video.

Tạo tệp video MP4 mô phỏng các tình huống vi phạm thực tế tại công trường:
1. Công nhân không đội mũ bảo hộ (no-helmet).
2. Công nhân không mặc áo phản quang (no-vest).
3. Sự cố công nhân trượt ngã trên sàn thi công (Slip / Fall Incident) kích hoạt báo động khẩn cấp.
"""

import os
import glob
import cv2
import numpy as np

OUTPUT_PATH = "data/videos/construction_violation_demo.mp4"
os.makedirs("data/videos", exist_ok=True)

# 1. Tìm các ảnh có vi phạm thực tế
candidate_imgs = glob.glob("data/sample_images/*.jpg") + glob.glob("data/ppe_dataset/test/images/*.jpg")
selected_imgs = []

for p in candidate_imgs:
    img = cv2.imread(p)
    if img is not None:
        selected_imgs.append(img)
    if len(selected_imgs) >= 8:
        break

if not selected_imgs:
    print("Không tìm thấy ảnh mẫu!")
    exit(1)

# Chuẩn hóa kích thước khung hình về 720x480
target_w, target_h = 720, 480
fps = 25
fourcc = cv2.VideoWriter_fourcc(*"mp4v")
writer = cv2.VideoWriter(OUTPUT_PATH, fourcc, fps, (target_w, target_h))

print(f"Creating violation demo video: {OUTPUT_PATH}...")

# PHẦN 1: Chuỗi các khung cảnh công nhân vi phạm PPE (Không mũ, Không áo)
for idx, raw_img in enumerate(selected_imgs):
    # Resize fit chuẩn
    resized = cv2.resize(raw_img, (target_w, target_h))
    
    # Mỗi cảnh kéo dài khoảng 2.0s (50 frames)
    for f in range(50):
        # Tạo hiệu ứng chuyển động nhẹ của camera giám sát CCTV
        shift_x = int(np.sin(f * 0.1) * 3)
        M = np.float32([[1, 0, shift_x], [0, 1, 0]])
        frame = cv2.warpAffine(resized, M, (target_w, target_h))
        writer.write(frame)

# PHẦN 2: Mô phỏng Sự cố Công nhân Trượt Ngã (Slip & Fall Simulation)
# Sử dụng 1 ảnh người và tạo chuỗi chuyển động ngã dần từ đứng thẳng sang nằm ngang
base_person_img = selected_imgs[0]
base_h, base_w = base_person_img.shape[:2]
base_resized = cv2.resize(base_person_img, (target_w, target_h))

# Giai đoạn đứng (1.0s = 25 frames)
for f in range(25):
    writer.write(base_resized)

# Giai đoạn ngã dần (góc nghiêng tăng từ 0 độ lên 85 độ trong 15 frames)
for angle in range(0, 85, 6):
    center = (target_w // 2, target_h // 2 + 50)
    rot_mat = cv2.getRotationMatrix2D(center, -float(angle), 1.0)
    rotated = cv2.warpAffine(base_resized, rot_mat, (target_w, target_h), borderMode=cv2.BORDER_REPLICATE)
    writer.write(rotated)

# Giai đoạn nằm bất động sau khi ngã (3.0s = 75 frames để hệ thống bắt trọn vẹn TE NGA)
center = (target_w // 2, target_h // 2 + 50)
rot_mat = cv2.getRotationMatrix2D(center, -85.0, 1.0)
fallen_frame = cv2.warpAffine(base_resized, rot_mat, (target_w, target_h), borderMode=cv2.BORDER_REPLICATE)

for f in range(75):
    # Thêm nhiễu nhẹ như camera thực tế
    noise = np.random.randint(-2, 3, fallen_frame.shape, dtype=np.int16)
    noisy_frame = np.clip(fallen_frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    writer.write(noisy_frame)

writer.release()
print(f"Generated video: {OUTPUT_PATH}")
