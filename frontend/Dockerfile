# --- STAGE 1: Build React/Vite app ---
FROM node:20-alpine AS build

WORKDIR /app

# Sao chép package.json và cài đặt dependencies
COPY package*.json ./
RUN npm install

# Sao chép toàn bộ mã nguồn frontend và xây dựng bundle
COPY . .
RUN npm run build

# --- STAGE 2: Serve static files with Nginx ---
FROM nginx:alpine

# Sao chép các tệp tĩnh đã xây dựng từ stage 1 vào thư mục html của Nginx
COPY --from=build /app/dist /usr/share/nginx/html

# Mở cổng 80 cho máy khách truy cập
EXPOSE 80

# Chạy Nginx trong chế độ không nền (foreground)
CMD ["nginx", "-g", "daemon off;"]
