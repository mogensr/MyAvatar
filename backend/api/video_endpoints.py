from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import json
import uuid
import sys
from werkzeug.utils import secure_filename

# Add the integrations directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'integrations'))
from hf_video_processor import MyAvatarVideoProcessor

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for frontend integration

# Configuration
UPLOAD_FOLDER = './temp'
OUTPUT_FOLDER = './output'
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB max file size

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Initialize video processor
HF_SPACE_URL = "https://MogensR-VideoBackgroundReplacer.hf.space"
video_processor = MyAvatarVideoProcessor(HF_SPACE_URL, UPLOAD_FOLDER, OUTPUT_FOLDER)

# In-memory job tracking (replace with database in production)
active_jobs = {}

def allowed_file(filename, file_type):
    """Check if uploaded file type is allowed"""
    video_extensions = {'mp4', 'avi', 'mov', 'mkv', 'webm'}
    image_extensions = {'jpg', 'jpeg', 'png', 'gif', 'bmp'}
    
    if '.' not in filename:
        return False
    
    extension = filename.rsplit('.', 1)[1].lower()
    
    if file_type == 'video':
        return extension in video_extensions
    elif file_type == 'image':
        return extension in image_extensions
    
    return False

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'MyAvatar Video Processing API',
        'version': '1.0.0'
    })

@app.route('/api/video/process', methods=['POST'])
def process_video():
    """
    Process video with background replacement
    Expected: multipart/form-data with 'video' and 'background' files
    """
    try:
        # Validate request
        if 'video' not in request.files or 'background' not in request.files:
            return jsonify({
                'error': 'Missing required files',
                'required': ['video', 'background']
            }), 400
        
        video_file = request.files['video']
        background_file = request.files['background']
        
        # Validate filenames
        if video_file.filename == '' or background_file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Validate file types
        if not allowed_file(video_file.filename, 'video'):
            return jsonify({
                'error': 'Invalid video file type',
                'allowed': ['mp4', 'avi', 'mov', 'mkv', 'webm']
            }), 400
        
        if not allowed_file(background_file.filename, 'image'):
            return jsonify({
                'error': 'Invalid background image type',
                'allowed': ['jpg', 'jpeg', 'png', 'gif', 'bmp']
            }), 400
        
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        user_id = request.form.get('user_id', 'anonymous')
        
        # Read file data
        video_data = video_file.read()
        background_data = background_file.read()
        
        # Start processing (this will run synchronously for now)
        # In production, you'd want to run this in a background queue
        result = video_processor.process_video(video_data, background_data, job_id)
        
        if result['success']:
            # Store job info
            active_jobs[job_id] = {
                'status': 'completed',
                'output_file': result['output_file'],
                'processing_time': result.get('processing_time', 0),
                'user_id': user_id
            }
            
            return jsonify({
                'success': True,
                'job_id': job_id,
                'status': 'completed',
                'message': 'Video processed successfully',
                'processing_time': result.get('processing_time', 0),
                'download_url': f'/api/video/download/{job_id}'
            })
        else:
            active_jobs[job_id] = {
                'status': 'failed',
                'error': result['error'],
                'user_id': user_id
            }
            
            return jsonify({
                'success': False,
                'job_id': job_id,
                'status': 'failed',
                'error': result['error']
            }), 500
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Processing failed: {str(e)}'
        }), 500

@app.route('/api/video/status/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Get processing job status"""
    if job_id not in active_jobs:
        return jsonify({
            'error': 'Job not found',
            'job_id': job_id
        }), 404
    
    job_info = active_jobs[job_id]
    
    response = {
        'job_id': job_id,
        'status': job_info['status']
    }
    
    if job_info['status'] == 'completed':
        response.update({
            'download_url': f'/api/video/download/{job_id}',
            'processing_time': job_info.get('processing_time', 0)
        })
    elif job_info['status'] == 'failed':
        response['error'] = job_info.get('error', 'Unknown error')
    
    return jsonify(response)

@app.route('/api/video/download/<job_id>', methods=['GET'])
def download_video(job_id):
    """Download processed video"""
    if job_id not in active_jobs:
        return jsonify({
            'error': 'Job not found',
            'job_id': job_id
        }), 404
    
    job_info = active_jobs[job_id]
    
    if job_info['status'] != 'completed':
        return jsonify({
            'error': 'Job not completed',
            'status': job_info['status']
        }), 400
    
    output_file = job_info['output_file']
    
    if not os.path.exists(output_file):
        return jsonify({
            'error': 'Output file not found',
            'job_id': job_id
        }), 404
    
    return send_file(
        output_file,
        as_attachment=True,
        download_name=f'processed_video_{job_id}.mp4',
        mimetype='video/mp4'
    )

@app.route('/api/video/jobs', methods=['GET'])
def list_jobs():
    """List all jobs (for admin/debugging)"""
    return jsonify({
        'jobs': [
            {
                'job_id': job_id,
                'status': info['status'],
                'user_id': info.get('user_id', 'unknown')
            }
            for job_id, info in active_jobs.items()
        ]
    })

@app.route('/api/video/cleanup/<job_id>', methods=['DELETE'])
def cleanup_job(job_id):
    """Clean up job files and data"""
    if job_id in active_jobs:
        job_info = active_jobs[job_id]
        
        # Remove output file if it exists
        if 'output_file' in job_info and os.path.exists(job_info['output_file']):
            try:
                os.remove(job_info['output_file'])
            except:
                pass
        
        # Remove job from memory
        del active_jobs[job_id]
        
        return jsonify({
            'success': True,
            'message': f'Job {job_id} cleaned up successfully'
        })
    
    return jsonify({
        'error': 'Job not found',
        'job_id': job_id
    }), 404

if __name__ == '__main__':
    # Create directories if they don't exist
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    
    # Run development server
    app.run(debug=True, host='0.0.0.0', port=5000)
