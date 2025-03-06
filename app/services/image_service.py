from azure.storage.blob import BlobServiceClient
from PIL import Image
import io
import uuid
from datetime import datetime
from ..core.config import settings

class ImageService:
    def __init__(self):
        self.connection_string = settings.AZURE_STORAGE_CONNECTION_STRING
        self.container_name = settings.AZURE_STORAGE_CONTAINER_NAME
        self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
        self.container_client = self.blob_service_client.get_container_client(self.container_name)

    async def upload_image(self, file_content: bytes, filename: str):
        """Upload ảnh lên Azure Blob Storage"""
        # Tạo tên file duy nhất
        extension = filename.split('.')[-1]
        unique_filename = f"{uuid.uuid4()}.{extension}"
        
        # Upload file
        blob_client = self.container_client.get_blob_client(unique_filename)
        blob_client.upload_blob(file_content)
        
        return {
            "filename": unique_filename,
            "url": blob_client.url,
            "uploaded_at": datetime.utcnow().isoformat()
        }

    async def get_image_info(self, filename: str):
        """Lấy thông tin của ảnh"""
        blob_client = self.container_client.get_blob_client(filename)
        properties = blob_client.get_blob_properties()
        
        return {
            "filename": filename,
            "url": blob_client.url,
            "size": properties.size,
            "created_at": properties.creation_time.isoformat(),
            "last_modified": properties.last_modified.isoformat()
        }

    async def delete_image(self, filename: str):
        """Xóa ảnh từ storage"""
        blob_client = self.container_client.get_blob_client(filename)
        blob_client.delete_blob()

    async def list_images(self):
        """Lấy danh sách tất cả các ảnh"""
        blobs = self.container_client.list_blobs()
        return [{
            "filename": blob.name,
            "size": blob.size,
            "created_at": blob.creation_time.isoformat()
        } for blob in blobs]

    async def convert_to_grayscale(self, file_content: bytes, filename: str):
        """Chuyển ảnh sang ảnh xám"""
        # Đọc ảnh từ bytes
        image = Image.open(io.BytesIO(file_content))
        
        # Chuyển sang ảnh xám
        gray_image = image.convert('L')
        
        # Chuyển ảnh xám thành bytes
        img_byte_arr = io.BytesIO()
        gray_image.save(img_byte_arr, format=image.format)
        img_byte_arr = img_byte_arr.getvalue()
        
        # Upload ảnh xám
        extension = filename.split('.')[-1]
        gray_filename = f"gray_{uuid.uuid4()}.{extension}"
        
        blob_client = self.container_client.get_blob_client(gray_filename)
        blob_client.upload_blob(img_byte_arr)
        
        return {
            "filename": gray_filename,
            "url": blob_client.url,
            "processed_at": datetime.utcnow().isoformat()
        }

    async def crop_image(self, file_content: bytes, filename: str, left: int, top: int, right: int, bottom: int):
        """Cắt ảnh theo tọa độ"""
        # Đọc ảnh từ bytes
        image = Image.open(io.BytesIO(file_content))
        
        # Cắt ảnh
        cropped_image = image.crop((left, top, right, bottom))
        
        # Chuyển ảnh đã cắt thành bytes
        img_byte_arr = io.BytesIO()
        cropped_image.save(img_byte_arr, format=image.format)
        img_byte_arr = img_byte_arr.getvalue()
        
        # Upload ảnh đã cắt
        extension = filename.split('.')[-1]
        cropped_filename = f"cropped_{uuid.uuid4()}.{extension}"
        
        blob_client = self.container_client.get_blob_client(cropped_filename)
        blob_client.upload_blob(img_byte_arr)
        
        return {
            "filename": cropped_filename,
            "url": blob_client.url,
            "processed_at": datetime.utcnow().isoformat()
        } 