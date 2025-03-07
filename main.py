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
import json

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
    set_order_container_name = os.getenv('AZURE_STORAGE_SET_ORDER_CONTAINER_NAME')
    ocr_results_container_name = os.getenv('AZURE_STORAGE_OCR_RESULTS_CONTAINER_NAME')

    if not all([connection_string, container_name, config_container_name, 
                set_order_container_name, ocr_results_container_name]):
        raise ValueError("Missing required environment variables")

    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client(container_name)
    config_container_client = blob_service_client.get_container_client(config_container_name)
    set_order_container_client = blob_service_client.get_container_client(set_order_container_name)
    ocr_results_container_client = blob_service_client.get_container_client(ocr_results_container_name)
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

def get_roi_coordinates(set_order):
    """Get ROI coordinates for the specified set order"""
    try:
        # Get ROI info content
        roi_blob_client = config_container_client.get_blob_client('roi_info.txt')
        roi_content = roi_blob_client.download_blob().readall().decode('utf-8')
        
        # Parse ROI content
        lines = roi_content.strip().split('\n')
        current_set = None
        coordinates = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('Bộ khung'):
                # Extract set number from "Bộ khung X: Y vùng"
                set_parts = line.split(':')
                if len(set_parts) >= 1:
                    set_number = set_parts[0].split()[2]  # Get the number after "Bộ khung"
                    try:
                        current_set = int(set_number)
                        coordinates = []  # Reset coordinates for new set
                    except ValueError:
                        logger.error(f"Invalid set number format: {set_number}")
                        continue
            elif line.startswith('('):
                try:
                    # Parse coordinates (x1, y1, x2, y2)
                    coords = line.strip('()').split(',')
                    if len(coords) == 4:
                        coords = [int(x.strip()) for x in coords]
                        coordinates.append(coords)
                except (ValueError, IndexError) as e:
                    logger.error(f"Error parsing coordinates: {line}, Error: {str(e)}")
                    continue
            
            # If we've found the target set and have coordinates, return them
            if current_set == set_order and coordinates:
                return coordinates
        
        raise ValueError(f"Set order {set_order} not found in ROI info or no coordinates found")
    except Exception as e:
        logger.error(f"Error getting ROI coordinates: {str(e)}")
        raise

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

@app.route('/api/ocr', methods=['POST'])
def process_ocr():
    """
    Process OCR on an image using ROI coordinates based on current set order
    ---
    parameters:
      - in: formData
        name: file
        type: file
        required: true
        description: The image file to process OCR
    responses:
      200:
        description: OCR results
      400:
        description: Invalid input
      500:
        description: Server error
    """
    try:
        # Get current set order
        set_order_blob_client = set_order_container_client.get_blob_client('set_order.txt')
        set_order_str = set_order_blob_client.download_blob().readall().decode('utf-8').strip()
        try:
            set_order = int(set_order_str)
        except ValueError:
            logger.error(f"Invalid set order value: {set_order_str}")
            return jsonify({'error': 'Invalid set order value'}), 400
        
        # Get ROI coordinates for current set order
        try:
            roi_coordinates = get_roi_coordinates(set_order)
        except ValueError as e:
            logger.error(f"Error getting ROI coordinates: {str(e)}")
            return jsonify({'error': str(e)}), 400
        
        # Get image from request
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        
        # Read and process image
        image_data = file.read()
        nparr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return jsonify({'error': 'Invalid image file'}), 400
        
        # Process OCR for each ROI
        results = []
        for i, coords in enumerate(roi_coordinates):
            try:
                x1, y1, x2, y2 = coords
                # Ensure coordinates are within image bounds
                x1 = max(0, min(x1, img.shape[1]))
                y1 = max(0, min(y1, img.shape[0]))
                x2 = max(0, min(x2, img.shape[1]))
                y2 = max(0, min(y2, img.shape[0]))
                
                roi = img[y1:y2, x1:x2]
                if roi.size == 0:
                    logger.warning(f"Empty ROI at coordinates {coords}")
                    continue
                    
                text = process_image_with_tesseract(roi)
                results.append({
                    'roi_index': i + 1,
                    'coordinates': coords,
                    'text': text if text else ''
                })
            except Exception as e:
                logger.error(f"Error processing ROI {i + 1}: {str(e)}")
                continue
        
        if not results:
            return jsonify({'error': 'No valid ROIs processed'}), 400
        
        # Save results to OCR results container
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        result_filename = f"ocr_result_{timestamp}.json"
        result_blob_client = ocr_results_container_client.get_blob_client(result_filename)
        result_blob_client.upload_blob(json.dumps(results, ensure_ascii=False), overwrite=True)
        
        return jsonify({
            'set_order': set_order,
            'results': results,
            'result_file': result_filename
        })
    except Exception as e:
        logger.error(f"Error in OCR processing: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ocr-results/<filename>', methods=['GET'])
def get_ocr_result(filename):
    """
    Get OCR result from a specific file
    ---
    parameters:
      - in: path
        name: filename
        type: string
        required: true
        description: The OCR result file to retrieve
    responses:
      200:
        description: OCR result content
      404:
        description: Result file not found
      500:
        description: Server error
    """
    try:
        blob_client = ocr_results_container_client.get_blob_client(filename)
        result_content = blob_client.download_blob().readall().decode('utf-8')
        return jsonify(json.loads(result_content))
    except Exception as e:
        logger.error(f"Error getting OCR result: {str(e)}")
        return jsonify({'error': str(e)}), 404

@app.route('/api/set-order', methods=['POST'])
def update_set_order():
    """
    Update set order value
    ---
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - value
          properties:
            value:
              type: integer
              description: The new set order value
    responses:
      200:
        description: Set order updated successfully
      400:
        description: Invalid input
      500:
        description: Server error
    """
    try:
        data = request.get_json()
        if not data or 'value' not in data:
            return jsonify({'error': 'Missing value in request body'}), 400
        
        value = data['value']
        if not isinstance(value, int):
            return jsonify({'error': 'Value must be an integer'}), 400

        blob_client = set_order_container_client.get_blob_client('set_order.txt')
        blob_client.upload_blob(str(value), overwrite=True)
        
        return jsonify({
            'message': 'Set order updated successfully',
            'value': value
        })
    except Exception as e:
        logger.error(f"Error in update_set_order: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/set-order', methods=['GET'])
def get_set_order():
    """
    Get current set order value
    ---
    responses:
      200:
        description: Current set order value
      404:
        description: Set order not found
      500:
        description: Server error
    """
    try:
        blob_client = set_order_container_client.get_blob_client('set_order.txt')
        value = blob_client.download_blob().readall().decode('utf-8')
        return jsonify({'value': int(value)})
    except Exception as e:
        logger.error(f"Error in get_set_order: {str(e)}")
        return jsonify({'error': str(e)}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)