# Wrembly Image Processing API

API xử lý ảnh được triển khai trên Azure Web App với Python 3.9, sử dụng Azure Blob Storage để lưu trữ.

## Tính năng

- Upload ảnh
- Xem danh sách ảnh
- Xem thông tin chi tiết ảnh
- Xóa ảnh
- Chuyển ảnh sang ảnh xám
- Cắt ảnh theo tọa độ

## Cài đặt và Triển khai

### 1. Chuẩn bị môi trường

1. Tạo Azure Storage Account:
   - Đăng nhập vào Azure Portal
   - Tạo Storage Account mới
   - Tạo container mới với tên "images"
   - Lưu connection string

2. Tạo Azure Web App:
   - Chọn Runtime stack: Python 3.9
   - Pricing plan: Free F1 (Dev/Test)

### 2. Cấu hình môi trường

Tạo file `.env` với nội dung:

```env
AZURE_STORAGE_CONNECTION_STRING=your_storage_connection_string
AZURE_STORAGE_CONTAINER_NAME=images
```

### 3. Cài đặt dependencies

```bash
pip install -r requirements.txt
```

### 4. Chạy ứng dụng locally

```bash
uvicorn app.main:app --reload
```

### 5. Triển khai lên Azure

1. Đăng nhập Azure CLI:
```bash
az login
```

2. Triển khai code:
```bash
az webapp up --runtime PYTHON:3.9 --sku F1 --name your-app-name
```

## API Endpoints

### Upload ảnh
```http
POST /api/v1/upload/
```

### Xem danh sách ảnh
```http
GET /api/v1/images/
```

### Xem thông tin ảnh
```http
GET /api/v1/images/{filename}
```

### Xóa ảnh
```http
DELETE /api/v1/images/{filename}
```

### Chuyển ảnh sang ảnh xám
```http
POST /api/v1/process/grayscale/
```

### Cắt ảnh
```http
POST /api/v1/process/crop/
```
Params:
- left: int
- top: int
- right: int
- bottom: int

## Tài liệu API

Truy cập `/docs` hoặc `/redoc` để xem tài liệu API chi tiết. 