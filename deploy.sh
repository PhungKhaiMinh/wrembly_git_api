#!/bin/bash

# Cài đặt các dependencies cơ bản trước
pip install --no-cache-dir -r requirements.txt

# Cài đặt các dependencies OCR
pip install --no-cache-dir -r requirements-ocr.txt

# Khởi động ứng dụng
python -m uvicorn main:app --host 0.0.0.0 --port 8000 