from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from azure.storage.blob import BlobServiceClient
from PIL import Image
import io
import uuid
from datetime import datetime
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_blob_client():
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "images")
    
    if not conn_str:
        raise HTTPException(status_code=500, detail="Azure Storage connection string not found")
    
    try:
        blob_service = BlobServiceClient.from_connection_string(conn_str)
        container_client = blob_service.get_container_client(container_name)
        return container_client
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to Azure Storage: {str(e)}")

@app.get("/")
def read_root():
    return {"message": "Hello from Wrembly Image API"}

@app.post("/api/v1/upload/")
async def upload_image(
    file: UploadFile = File(...),
    container_client = Depends(get_blob_client)
):
    try:
        content = await file.read()
        original_filename = file.filename
        storage_filename = f"{uuid.uuid4()}{os.path.splitext(original_filename)[1]}"
        
        blob_client = container_client.get_blob_client(storage_filename)
        blob_client.upload_blob(content, metadata={"original_filename": original_filename})
        
        return {
            "filename": original_filename,
            "url": blob_client.url,
            "uploaded_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/v1/images/")
async def list_images(container_client = Depends(get_blob_client)):
    try:
        blobs = container_client.list_blobs()
        return [{
            "filename": blob.metadata.get('original_filename', blob.name) if blob.metadata else blob.name,
            "size": blob.size,
            "created_at": blob.creation_time.isoformat()
        } for blob in blobs]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/v1/images/{filename}")
async def get_image_info(filename: str, container_client = Depends(get_blob_client)):
    try:
        blobs = container_client.list_blobs()
        storage_blob = None
        
        for blob in blobs:
            if blob.metadata and blob.metadata.get('original_filename') == filename:
                storage_blob = blob
                break
        
        if not storage_blob:
            raise HTTPException(status_code=404, detail="Image not found")
            
        blob_client = container_client.get_blob_client(storage_blob.name)
        properties = blob_client.get_blob_properties()
        
        return {
            "filename": filename,
            "url": blob_client.url,
            "size": properties.size,
            "created_at": properties.creation_time.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/api/v1/download/{filename}")
async def download_image(filename: str, container_client = Depends(get_blob_client)):
    """Tải ảnh về từ storage"""
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
            
        # Lấy blob client và download ảnh
        blob_client = container_client.get_blob_client(storage_blob.name)
        download_stream = blob_client.download_blob()
        
        # Xác định content type dựa trên phần mở rộng của file
        content_type = "image/jpeg"  # default
        if filename.lower().endswith('.png'):
            content_type = "image/png"
        elif filename.lower().endswith('.gif'):
            content_type = "image/gif"
        elif filename.lower().endswith('.bmp'):
            content_type = "image/bmp"
        
        # Trả về response dạng stream
        return StreamingResponse(
            download_stream.chunks(),
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": content_type
            }
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Lỗi khi tải ảnh: {str(e)}")

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