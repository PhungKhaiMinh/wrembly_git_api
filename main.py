from flask import Flask, request, jsonify
from azure.storage.blob import BlobServiceClient
import os
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime
import cv2
import numpy as np
import easyocr
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

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

@app.route('/')
def home():
    return jsonify({"message": "Welcome to Wrembly Image API"})

@app.route('/api/upload', methods=['POST'])
def upload_image():
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
    try:
        blob_client = container_client.get_blob_client(filename)
        blob_client.delete_blob()
        return jsonify({'message': 'File deleted successfully'})
    except Exception as e:
        logger.error(f"Error in delete_image: {str(e)}")
        return jsonify({'error': str(e)}), 404

@app.route('/api/roi-info', methods=['POST'])
def update_roi_info():
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
    try:
        blob_client = config_container_client.get_blob_client('roi_info.txt')
        roi_content = blob_client.download_blob().readall().decode('utf-8')
        return jsonify({'content': roi_content})
    except Exception as e:
        logger.error(f"Error in get_roi_info: {str(e)}")
        return jsonify({'error': str(e)}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)