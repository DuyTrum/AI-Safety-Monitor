# Sử dụng Python 3.11-slim làm base image để tối ưu dung lượng
FROM python:3.11-slim

# Thiết lập các biến môi trường
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Thiết lập thư mục làm việc trong container
WORKDIR /app

# Cài đặt các thư viện hệ thống cần thiết cho OpenCV và các dependencies khác
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Sao chép và cài đặt các phụ thuộc Python
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Sao chép mã nguồn, cấu hình, trọng số mô hình và dữ liệu mẫu
COPY src/ /app/src/
COPY configs/ /app/configs/
COPY weights/ /app/weights/
COPY data/sample_images/ /app/data/sample_images/

# Tạo các thư mục lưu trữ runtime
RUN mkdir -p /app/runs /app/data/violations /app/data/reports

# Mở cổng 8000 cho FastAPI
EXPOSE 8000

# Lệnh khởi chạy server uvicorn
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
