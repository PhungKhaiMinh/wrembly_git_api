from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from azure.storage.blob import BlobServiceClient
from PIL import Image
import io
import uuid
from datetime import datetime
import os
import cv2
import numpy as np
import easyocr

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Azure Storage configuration
connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
container_name = "images"
config_container_name = "configs"

def get_blob_client():
    """Get blob client for images container"""
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client(container_name)
    return container_client

def get_config_client():
    """Get blob client for config container"""
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    try:
        container_client = blob_service_client.get_container_client(config_container_name)
        container_client.get_container_properties()
    except Exception:
        # Create container if it doesn't exist
        container_client = blob_service_client.create_container(config_container_name)
    return container_client

@app.get("/")
def read_root():
    return {"message": "Hello from Wrembly Image API"}

@app.post("/api/v1/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        container_client = get_blob_client()
        
        # Read file content
        contents = await file.read()
        
        # Verify if it's an image
        try:
            img = Image.open(io.BytesIO(contents))
        except Exception:
            raise HTTPException(status_code=400, detail="Uploaded file is not a valid image")
        
        # Generate unique filename
        file_extension = os.path.splitext(file.filename)[1]
        blob_name = f"{uuid.uuid4()}{file_extension}"
        
        # Upload to Azure Storage
        blob_client = container_client.get_blob_client(blob_name)
        blob_client.upload_blob(contents, blob_type="BlockBlob", metadata={"original_filename": file.filename})
        
        return JSONResponse(
            status_code=200,
            content={
                "message": "File uploaded successfully",
                "filename": file.filename,
                "blob_name": blob_name
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/images/")
async def list_images(container_client = Depends(get_blob_client)):
    try:
        # Lấy danh sách blob kèm theo metadata
        blobs = list(container_client.list_blobs(include=['metadata']))
        result = []
        
        for blob in blobs:
            # Lấy thông tin từ metadata
            original_filename = blob.metadata.get('original_filename', blob.name) if blob.metadata else blob.name
            
            # Lấy URL của blob
            blob_client = container_client.get_blob_client(blob.name)
            
            # Tạo thông tin chi tiết cho mỗi ảnh
            image_info = {
                "storage_filename": blob.name,  # Tên file trong storage
                "original_filename": original_filename,  # Tên file gốc
                "size": blob.size,
                "url": blob_client.url,
                "created_at": blob.creation_time.isoformat(),
                "content_type": blob.content_settings.content_type if blob.content_settings else None
            }
            result.append(image_info)
        
        # Sắp xếp theo thời gian tạo, mới nhất lên đầu
        result.sort(key=lambda x: x['created_at'], reverse=True)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi khi lấy danh sách ảnh: {str(e)}")

@app.get("/api/v1/download/{filename}")
async def download_file(filename: str):
    try:
        container_client = get_blob_client()
        
        # Find blob by original filename
        blob_list = list(container_client.list_blobs(include=['metadata']))
        storage_blob = None
        
        for blob in blob_list:
            if (blob.metadata and 'original_filename' in blob.metadata and 
                blob.metadata['original_filename'] == filename):
                storage_blob = blob
                break
        
        if not storage_blob:
            raise HTTPException(status_code=404, detail=f"File not found: {filename}")
        
        # Download blob
        blob_client = container_client.get_blob_client(storage_blob.name)
        download_stream = blob_client.download_blob()
        
        return StreamingResponse(
            download_stream.chunks(),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v1/images/{filename}")
async def delete_image(filename: str, container_client = Depends(get_blob_client)):
    """Xóa một ảnh"""
    try:
        # Liệt kê tất cả các blob và tìm blob phù hợp
        blob_list = list(container_client.list_blobs(include=['metadata']))
        storage_blob = None
        
        for blob in blob_list:
            if (blob.metadata and 'original_filename' in blob.metadata and 
                blob.metadata['original_filename'] == filename):
                storage_blob = blob
                break
        
        if not storage_blob:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy ảnh: {filename}")
            
        # Xóa blob
        blob_client = container_client.get_blob_client(storage_blob.name)
        blob_client.delete_blob()
        
        return {
            "message": f"Đã xóa ảnh {filename} thành công",
            "filename": filename,
            "deleted_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Lỗi khi xóa ảnh: {str(e)}")

@app.post("/api/v1/process/grayscale/")
async def convert_to_grayscale(
    file: UploadFile = File(...),
    container_client = Depends(get_blob_client)
):
    try:
        content = await file.read()
        image = Image.open(io.BytesIO(content))
        original_filename = file.filename
        
        gray_image = image.convert('L')
        
        img_byte_arr = io.BytesIO()
        gray_image.save(img_byte_arr, format=image.format or 'JPEG')
        img_byte_arr = img_byte_arr.getvalue()
        
        new_filename = f"gray_{os.path.splitext(original_filename)[0]}{os.path.splitext(original_filename)[1]}"
        storage_filename = f"gray_{uuid.uuid4()}{os.path.splitext(original_filename)[1]}"
        
        blob_client = container_client.get_blob_client(storage_filename)
        blob_client.upload_blob(img_byte_arr, metadata={"original_filename": new_filename})
        
        return {
            "filename": new_filename,
            "url": blob_client.url,
            "processed_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/v1/process/crop/")
async def crop_image(
    file: UploadFile = File(...),
    left: int = 0,
    top: int = 0,
    right: int = 100,
    bottom: int = 100,
    container_client = Depends(get_blob_client)
):
    try:
        content = await file.read()
        image = Image.open(io.BytesIO(content))
        original_filename = file.filename
        
        cropped_image = image.crop((left, top, right, bottom))
        
        img_byte_arr = io.BytesIO()
        cropped_image.save(img_byte_arr, format=image.format or 'JPEG')
        img_byte_arr = img_byte_arr.getvalue()
        
        new_filename = f"cropped_{os.path.splitext(original_filename)[0]}{os.path.splitext(original_filename)[1]}"
        storage_filename = f"cropped_{uuid.uuid4()}{os.path.splitext(original_filename)[1]}"
        
        blob_client = container_client.get_blob_client(storage_filename)
        blob_client.upload_blob(img_byte_arr, metadata={"original_filename": new_filename})
        
        return {
            "filename": new_filename,
            "url": blob_client.url,
            "processed_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/v1/config/roi-info")
async def upload_roi_info(file: UploadFile = File(...)):
    try:
        if file.filename != "roi_info.txt":
            raise HTTPException(status_code=400, detail="File must be named roi_info.txt")
        
        container_client = get_config_client()
        contents = await file.read()
        
        # Upload to Azure Storage
        blob_client = container_client.get_blob_client("roi_info.txt")
        blob_client.upload_blob(contents, blob_type="BlockBlob", overwrite=True)
        
        return JSONResponse(
            status_code=200,
            content={"message": "ROI info uploaded successfully"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/config/roi-info")
async def get_roi_info():
    try:
        container_client = get_config_client()
        blob_client = container_client.get_blob_client("roi_info.txt")
        
        # Download and read content
        download_stream = blob_client.download_blob()
        content = download_stream.readall().decode('utf-8')
        
        return JSONResponse(
            status_code=200,
            content={"content": content}
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"ROI info not found: {str(e)}")

@app.post("/api/v1/process/ocr/{filename}")
async def process_ocr(
    filename: str,
    set_number: int,
    container_client = Depends(get_blob_client),
    config_client = Depends(get_config_client)
):
    """Xử lý OCR cho một ảnh đã có trong storage sử dụng ROI từ roi_info.txt"""
    try:
        # 1. Lấy ảnh từ storage
        blob_list = list(container_client.list_blobs(include=['metadata']))
        storage_blob = None
        
        for blob in blob_list:
            if (blob.metadata and 'original_filename' in blob.metadata and 
                blob.metadata['original_filename'] == filename):
                storage_blob = blob
                break
        
        if not storage_blob:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy ảnh: {filename}")
        
        # Download ảnh
        blob_client = container_client.get_blob_client(storage_blob.name)
        image_data = blob_client.download_blob().readall()
        
        # Chuyển đổi sang định dạng numpy array
        nparr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # 2. Lấy thông tin ROI từ roi_info.txt
        config_blob_client = config_client.get_blob_client("roi_info.txt")
        roi_content = config_blob_client.download_blob().readall().decode('utf-8')
        
        # Parse ROI info
        roi_sets = []
        current_set = None
        for line in roi_content.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            if line.startswith("Bộ khung"):
                if current_set:
                    roi_sets.append(current_set)
                current_set = {
                    "regions": []
                }
            elif line.startswith("("):
                coords = tuple(map(int, line.strip("()\n").split(',')))
                current_set["regions"].append({
                    "x1": coords[0],
                    "y1": coords[1],
                    "x2": coords[2],
                    "y2": coords[3]
                })
        
        if current_set:
            roi_sets.append(current_set)
            
        # Kiểm tra set_number hợp lệ
        if set_number < 0 or set_number >= len(roi_sets):
            raise HTTPException(status_code=400, detail=f"set_number không hợp lệ. Phải từ 0 đến {len(roi_sets)-1}")
            
        # 3. Khởi tạo EasyOCR
        reader = easyocr.Reader(['vi'])
        
        # 4. Xử lý từng vùng ROI và thực hiện OCR
        results = []
        for idx, roi in enumerate(roi_sets[set_number]["regions"]):
            # Cắt ảnh theo ROI
            x1, y1, x2, y2 = roi["x1"], roi["y1"], roi["x2"], roi["y2"]
            roi_img = img[y1:y2, x1:x2]
            
            # Thực hiện OCR
            ocr_result = reader.readtext(roi_img)
            
            # Lấy text từ kết quả OCR
            text = " ".join([res[1] for res in ocr_result]) if ocr_result else ""
            
            results.append({
                "region_index": idx,
                "coordinates": f"({x1},{y1},{x2},{y2})",
                "text": text
            })
        
        return {
            "filename": filename,
            "set_number": set_number,
            "results": results,
            "processed_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi khi xử lý OCR: {str(e)}")