# backend/app.py
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import os
import uuid
from werkzeug.utils import secure_filename
from watermark_remover import WatermarkRemover
from detectors import AdvancedDetector
import json
from pathlib import Path

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

# Configuration
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB limit

remover = WatermarkRemover()
detector = AdvancedDetector()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def serve_frontend():
    return send_from_directory('../frontend', 'index.html')

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload image for processing."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400
    
    # Generate unique filename
    original_filename = secure_filename(file.filename)
    file_id = str(uuid.uuid4())
    filename = f"{file_id}_{original_filename}"
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)
    
    # Detect watermarks
    detections = remover.detect_watermark(file_path)
    
    # Advanced detection
    c2pa = detector.detect_c2pa(file_path)
    dwt_dct = detector.detect_dwt_dct(file_path)
    synthid = detector.detect_synthid(file_path)
    
    return jsonify({
        'file_id': file_id,
        'filename': original_filename,
        'file_path': file_path,
        'detections': detections,
        'advanced_detections': {
            'c2pa': c2pa,
            'dwt_dct': dwt_dct,
            'synthid': synthid
        }
    })

@app.route('/api/remove', methods=['POST'])
def remove_watermark():
    """Remove watermark from uploaded image."""
    data = request.json
    file_id = data.get('file_id')
    method = data.get('method', 'opencv')
    region = data.get('region', None)  # [x, y, width, height]
    
    if not file_id:
        return jsonify({'error': 'No file ID provided'}), 400
    
    # Find the uploaded file
    upload_dir = UPLOAD_FOLDER
    uploaded_file = None
    for f in os.listdir(upload_dir):
        if f.startswith(file_id):
            uploaded_file = f
            break
    
    if not uploaded_file:
        return jsonify({'error': 'File not found'}), 404
    
    input_path = os.path.join(UPLOAD_FOLDER, uploaded_file)
    output_filename = f"clean_{uploaded_file}"
    output_path = os.path.join(PROCESSED_FOLDER, output_filename)
    
    try:
        if region:
            # Remove from specific region
            result = remover.remove_visible_region(input_path, output_path, region)
        else:
            # Auto-detect and remove
            result = remover.remove_watermark(input_path, output_path, method)
        
        return jsonify({
            'success': True,
            'output_file': output_filename,
            'output_path': output_path,
            'download_url': f'/api/download/{output_filename}'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download/<filename>')
def download_file(filename):
    """Download processed image."""
    return send_from_directory(PROCESSED_FOLDER, filename, as_attachment=True)

@app.route('/api/batch', methods=['POST'])
def batch_process():
    """Process multiple images."""
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400
    
    files = request.files.getlist('files')
    method = request.form.get('method', 'opencv')
    
    results = []
    for file in files:
        if not allowed_file(file.filename):
            results.append({
                'filename': file.filename,
                'status': 'error',
                'error': 'File type not allowed'
            })
            continue
        
        filename = secure_filename(file.filename)
        file_id = str(uuid.uuid4())
        temp_path = os.path.join(UPLOAD_FOLDER, f"{file_id}_{filename}")
        file.save(temp_path)
        
        output_filename = f"clean_{file_id}_{filename}"
        output_path = os.path.join(PROCESSED_FOLDER, output_filename)
        
        try:
            remover.remove_watermark(temp_path, output_path, method)
            results.append({
                'filename': filename,
                'status': 'success',
                'download_url': f'/api/download/{output_filename}'
            })
        except Exception as e:
            results.append({
                'filename': filename,
                'status': 'error',
                'error': str(e)
            })
        
        # Cleanup temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    return jsonify({
        'results': results,
        'total': len(results),
        'successful': len([r for r in results if r['status'] == 'success'])
    })

@app.route('/api/detect', methods=['POST'])
def detect_only():
    """Detect watermarks without removal."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    filename = secure_filename(file.filename)
    file_id = str(uuid.uuid4())
    temp_path = os.path.join(UPLOAD_FOLDER, f"{file_id}_{filename}")
    file.save(temp_path)
    
    try:
        detections = remover.detect_watermark(temp_path)
        
        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        return jsonify({
            'detections': detections,
            'has_watermark': len(detections) > 0,
            'confidence': max([d.get('confidence', 0) for d in detections]) if detections else 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/info')
def get_info():
    """Get information about supported formats and methods."""
    return jsonify({
        'supported_formats': ['.png', '.jpg', '.jpeg', '.webp'],
        'methods': ['opencv', 'opencv_ns'],
        'features': [
            'visible watermark detection',
            'metadata stripping',
            'C2PA detection',
            'DWT-DCT detection',
            'SynthID detection'
        ]
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
