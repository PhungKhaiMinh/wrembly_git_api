from flask import Flask, request, jsonify
from azure.storage.blob import BlobServiceClient
import os
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime
import cv2
import numpy as np
import logging
import pytesseract
from PIL import Image
import io
from flask_swagger_ui import get_swaggerui_blueprint

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
SWAGGER_URL = '/docs'
API_URL = '/static/swagger.json'
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "Wrembly Image API"
    }
)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

# Azure Storage configuration
try:
    connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
    container_name = os.getenv('AZURE_STORAGE_CONTAINER_NAME')
    config_container_name = os.getenv('AZURE_STORAGE_CONFIG_CONTAINER_NAME')

    if not all([connection_string, container_name, config_container_name]):
        raise ValueError("Missing required environment variables")

    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client(container_name)
    config_container_client = blob_service_client.get_container_client(config_container_name)
except Exception as e:
    logger.error(f"Failed to initialize Azure Storage: {str(e)}")
    raise

def preprocess_image(image):
    """Preprocess image for better OCR results"""
    try:
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply thresholding to preprocess the image
        gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        
        # Apply dilation to connect text components
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
        gray = cv2.dilate(gray, kernel, iterations=1)
        
        return gray
    except Exception as e:
        logger.error(f"Error in image preprocessing: {str(e)}")
        return image

def process_image_with_tesseract(image):
    """Process image using Tesseract OCR"""
    try:
        # Preprocess image
        processed_image = preprocess_image(image)
        
        # Convert numpy array to PIL Image
        pil_image = Image.fromarray(processed_image)
        
        # Perform OCR
        text = pytesseract.image_to_string(pil_image, lang='vie+eng')
        
        return text.strip()
    except Exception as e:
        logger.error(f"Error in Tesseract processing: {str(e)}")
        return None

@app.route('/')
def home():
    """
    Welcome endpoint
    ---
    responses:
      200:
        description: Welcome message
    """
    return jsonify({"message": "Welcome to Wrembly Image API"})

@app.route('/api/upload', methods=['POST'])
def upload_image():
    """
    Upload an image to Azure Storage
    ---
    parameters:
      - in: formData
        name: file
        type: file
        required: true
        description: The image file to upload
    responses:
      200:
        description: File uploaded successfully
      400:
        description: No file part or no selected file
      500:
        description: Server error
    """
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        
        if file:
            original_filename = secure_filename(file.filename)
            storage_filename = f"{uuid.uuid4()}_{original_filename}"
            
            blob_client = container_client.get_blob_client(storage_filename)
            blob_client.upload_blob(file.read(), overwrite=True)
            
            return jsonify({
                'message': 'File uploaded successfully',
                'original_filename': original_filename,
                'storage_filename': storage_filename
            })
    except Exception as e:
        logger.error(f"Error in upload_image: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/images', methods=['GET'])
def list_images():
    """
    List all images in Azure Storage
    ---
    responses:
      200:
        description: List of images
      500:
        description: Server error
    """
    try:
        blobs = container_client.list_blobs()
        images = []
        for blob in blobs:
            original_filename = blob.name.split('_', 1)[1] if '_' in blob.name else blob.name
            images.append({
                'storage_filename': blob.name,
                'original_filename': original_filename
            })
        return jsonify(images)
    except Exception as e:
        logger.error(f"Error in list_images: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/images/<filename>', methods=['DELETE'])
def delete_image(filename):
    """
    Delete an image from Azure Storage
    ---
    parameters:
      - in: path
        name: filename
        type: string
        required: true
        description: The filename to delete
    responses:
      200:
        description: File deleted successfully
      404:
        description: File not found
    """
    try:
        blob_client = container_client.get_blob_client(filename)
        blob_client.delete_blob()
        return jsonify({'message': 'File deleted successfully'})
    except Exception as e:
        logger.error(f"Error in delete_image: {str(e)}")
        return jsonify({'error': str(e)}), 404

@app.route('/api/roi-info', methods=['POST'])
def update_roi_info():
    """
    Update ROI information file
    ---
    parameters:
      - in: formData
        name: file
        type: file
        required: true
        description: The ROI info file to upload
    responses:
      200:
        description: ROI info updated successfully
      400:
        description: Invalid file or no file part
      500:
        description: Server error
    """
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        
        if file and file.filename == 'roi_info.txt':
            blob_client = config_container_client.get_blob_client('roi_info.txt')
            blob_client.upload_blob(file.read(), overwrite=True)
            return jsonify({'message': 'ROI info updated successfully'})
        else:
            return jsonify({'error': 'Invalid file name'}), 400
    except Exception as e:
        logger.error(f"Error in update_roi_info: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/roi-info', methods=['GET'])
def get_roi_info():
    """
    Get ROI information
    ---
    responses:
      200:
        description: ROI information content
      404:
        description: ROI info file not found
    """
    try:
        blob_client = config_container_client.get_blob_client('roi_info.txt')
        roi_content = blob_client.download_blob().readall().decode('utf-8')
        return jsonify({'content': roi_content})
    except Exception as e:
        logger.error(f"Error in get_roi_info: {str(e)}")
        return jsonify({'error': str(e)}), 404

@app.route('/api/ocr/<filename>', methods=['POST'])
def process_ocr(filename):
    """
    Process OCR on an image
    ---
    parameters:
      - in: path
        name: filename
        type: string
        required: true
        description: The filename to process OCR
    responses:
      200:
        description: OCR result
      500:
        description: Server error
    """
    try:
        # Get image from storage
        blob_client = container_client.get_blob_client(filename)
        image_data = blob_client.download_blob().readall()
        
        # Convert to numpy array
        nparr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Process with Tesseract
        text = process_image_with_tesseract(img)
        
        return jsonify({
            'text': text
        })
    except Exception as e:
        logger.error(f"Error in OCR processing: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)