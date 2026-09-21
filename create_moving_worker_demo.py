"""Generate a realistic moving worker & machinery conflict demo video.

Tạo tệp video MP4 với nhân vật công nhân di chuyển liên tục qua các vị trí:
1. Tiếp cận vùng nguy hiểm của xe cơ giới (Approaching Danger Zone).
2. Đi cắt ngang đường xe di chuyển (Walking in Path of Vehicle).
3. Đứng vào góc khuất điểm mù phía sau xe (Standing in Blind Spot).
"""

import os
import cv2
import numpy as np

OUTPUT_PATH = "data/videos/moving_worker_hazard_demo.mp4"
os.makedirs("data/videos", exist_ok=True)

# Lấy ảnh hiện trường công trường có xe cơ giới và công nhân
base_path = "data/sample_images/00100_jpg.rf.87e0894580a4f957424704b89d2d1451.jpg"
if not os.path.exists(base_path):
    base_path = "data/sample_images/00048_jpg.rf.65a252196defed676f4b1940fae3eec5.jpg"

base_img = cv2.imread(base_path)
h, w = base_img.shape[:2]

# Trích xuất 1 công nhân mẫu từ ảnh gốc để làm thực thể di chuyển
# Ở ảnh 00100, công nhân ở khu vực trung tâm (ví dụ box 330, 200, 430, 480)
# Tạo vùng nhân vật
wx1, wy1, wx2, wy2 = int(w * 0.45), int(h * 0.35), int(w * 0.60), int(h * 0.75)
worker_patch = base_img[wy1:wy2, wx1:wx2].copy()
pw_h, pw_w = worker_patch.shape[:2]

# Tạo mặt nạ mềm (smooth alpha mask) để hòa trộn tự nhiên
mask = np.ones((pw_h, pw_w), dtype=np.float32)
cv2.rectangle(mask, (0, 0), (pw_w - 1, pw_h - 1), 0, 8)
mask = cv2.GaussianBlur(mask, (15, 15), 0)
mask_3ch = cv2.merge([mask, mask, mask])

# Tạo nền sạch bằng cách inpaint nhẹ khu vực nhân vật ban đầu
inpaint_mask = np.zeros((h, w), dtype=np.uint8)
cv2.rectangle(inpaint_mask, (wx1, wy1), (wx2, wy2), 255, -1)
clean_background = cv2.inpaint(base_img, inpaint_mask, inpaintRadius=7, flags=cv2.INPAINT_TELEA)

fps = 25
num_frames = 150  # 6 giây
fourcc = cv2.VideoWriter_fourcc(*"mp4v")
writer = cv2.VideoWriter(OUTPUT_PATH, fourcc, fps, (w, h))

print(f"Generating moving worker demo video: {OUTPUT_PATH}...")

# Quỹ đạo di chuyển: Đi từ bên trái (x=50) qua giữa (x=w/2) và sang điểm mù bên phải (x=w-pw_w-40)
start_x = 40
end_x = w - pw_w - 50
start_y = int(h * 0.38)
end_y = int(h * 0.35)

for f in range(num_frames):
    t = f / float(num_frames)
    
    # Tọa độ X di chuyển mượt mà (Linear + Ease)
    cur_x = int(start_x + (end_x - start_x) * t)
    
    # Mô phỏng nhịp bước chân đi bộ tự nhiên (Walking Gait: nhấp nhô sin theo trục Y)
    step_bob = int(np.sin(f * 0.4) * 4)
    cur_y = int(start_y + (end_y - start_y) * t) + step_bob
    
    # Khung hình hiện tại
    frame = clean_background.copy()
    
    # Vị trí dán worker
    x1, y1 = max(0, cur_x), max(0, cur_y)
    x2, y2 = min(w, cur_x + pw_w), min(h, cur_y + pw_h)
    
    patch_w = x2 - x1
    patch_h = y2 - y1
    
    if patch_w > 0 and patch_h > 0:
        sub_patch = worker_patch[:patch_h, :patch_w].astype(np.float32)
        sub_mask = mask_3ch[:patch_h, :patch_w]
        bg_roi = frame[y1:y2, x1:x2].astype(np.float32)
        
        # Alpha blend mượt mà
        blended = sub_patch * sub_mask + bg_roi * (1.0 - sub_mask)
        frame[y1:y2, x1:x2] = np.clip(blended, 0, 255).astype(np.uint8)
        
    writer.write(frame)

writer.release()
print(f"Finished creating video: {OUTPUT_PATH} ({num_frames} frames, {w}x{h}, {fps} fps).")
