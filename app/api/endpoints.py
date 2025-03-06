from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List
from ..services.image_service import ImageService
from fastapi.responses import JSONResponse

router = APIRouter()
image_service = ImageService()

@router.post("/upload/")
async def upload_image(file: UploadFile = File(...)):
    """Upload ảnh mới"""
    try:
        content = await file.read()
        result = await image_service.upload_image(content, file.filename)
        return JSONResponse(content=result, status_code=201)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/images/")
async def list_images():
    """Lấy danh sách tất cả các ảnh"""
    try:
        images = await image_service.list_images()
        return images
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/images/{filename}")
async def get_image_info(filename: str):
    """Lấy thông tin chi tiết của một ảnh"""
    try:
        info = await image_service.get_image_info(filename)
        return info
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/images/{filename}")
async def delete_image(filename: str):
    """Xóa một ảnh"""
    try:
        await image_service.delete_image(filename)
        return {"message": f"Đã xóa ảnh {filename} thành công"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/process/grayscale/")
async def convert_to_grayscale(file: UploadFile = File(...)):
    """Chuyển ảnh sang ảnh xám"""
    try:
        content = await file.read()
        result = await image_service.convert_to_grayscale(content, file.filename)
        return JSONResponse(content=result, status_code=201)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/process/crop/")
async def crop_image(
    file: UploadFile = File(...),
    left: int = 0,
    top: int = 0,
    right: int = 100,
    bottom: int = 100
):
    """Cắt ảnh theo tọa độ"""
    try:
        content = await file.read()
        result = await image_service.crop_image(content, file.filename, left, top, right, bottom)
        return JSONResponse(content=result, status_code=201)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 