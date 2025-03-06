import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME = "Wrembly Image Processing API"
    PROJECT_VERSION = "1.0.0"
    
    # Azure Storage settings
    AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    AZURE_STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "images")
    
    # API settings
    API_V1_STR = "/api/v1"
    
    # CORS settings
    BACKEND_CORS_ORIGINS = [
        "http://localhost",
        "http://localhost:8000",
        "*"  # Trong môi trường phát triển, cho phép tất cả các origin
    ]

settings = Settings() 