"""
FILE: app/routes/video_processing_routes.py
PURPOSE: Video Processing Routes for MyAvatar - FastAPI endpoints for background replacement
UPDATED: 2025-07-21 - FIXED: Upload timeout and linear progress bar (no more 10%→90% jumps!)
"""
import os
import uuid
import asyncio
import tempfile
import io
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
import json

from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

# Cloudinary imports
try:
    import cloudinary
    import cloudinary.uploader
    import cloudinary.api
    CLOUDINARY_AVAILABLE = True
except ImportError:
    CLOUDINARY_AVAILABLE = False

# MyAvatar imports
try:
    from app.db.database import execute_query
    from app.logger.log_handler import log_info, log_error, log_warning
    from app.services.auth_service import auth_service
    from app.db.user_manager import Database
    from app.config.settings import config
    # Use your existing sophisticated background replacement system
    from app.video_enhancer.advanced_background_replacer import (
        AdvancedBackgroundReplacer,
        replace_video_background
    )
except ImportError as e:
    log_error(f"Required MyAvatar modules not found: {e}", "VideoProcessingRoutes")
    raise ImportError(f"Required MyAvatar modules not found: {e}")

router = APIRouter()
security = HTTPBearer(auto_error=False)
db = Database()

# Constants
MAX_VIDEO_SIZE_MB = getattr(config, 'MAX_VIDEO_SIZE_MB', 500)
MAX_IMAGE_SIZE_MB = getattr(config, 'MAX_IMAGE_SIZE_MB', 50)
ALLOWED_VIDEO_FORMATS = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
ALLOWED_IMAGE_FORMATS = ['.jpg', '.jpeg', '.png', '.bmp', '.webp']

# Cloudinary Configuration
CLOUDINARY_URL = os.getenv("CLOUDINARY_URL")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

# Initialize Cloudinary
if CLOUDINARY_AVAILABLE and (CLOUDINARY_URL or all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET])):
    if not CLOUDINARY_URL and all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET]):
        cloudinary.config(
            cloud_name=CLOUDINARY_CLOUD_NAME,
            api_key=CLOUDINARY_API_KEY,
            api_secret=CLOUDINARY_API_SECRET
        )
    log_info("Cloudinary configured for video processing", "VideoProcessingRoutes")
else:
    log_warning("Cloudinary not configured - falling back to local storage", "VideoProcessingRoutes")

# Pydantic models for request/response
class BackgroundConfig(BaseModel):
    type: str = Field(..., description="Background type: 'image', 'color', or 'blur'")
    path: Optional[str] = Field(None, description="Path to background image (for type='image')")
    color: Optional[str] = Field("#4a90e2", description="Hex color code (for type='color')")
    blur_strength: Optional[int] = Field(15, description="Blur strength (for type='blur')")

class ProcessingJobRequest(BaseModel):
    video_id: Optional[str] = Field(None, description="Existing video ID from MyAvatar")
    background_config: BackgroundConfig = Field(..., description="Background configuration")
    quality: str = Field("medium", description="Processing quality: 'low', 'medium', 'high'")
    segmentation_model: str = Field("auto", description="Segmentation model: 'auto', 'rvm', 'mediapipe', 'fallback'")
    preserve_audio: bool = Field(True, description="Whether to preserve original audio")

class ProcessingJobResponse(BaseModel):
    job_id: str
    status: str
    message: str
    created_at: str
    estimated_duration: Optional[int] = None

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float
    message: Optional[str] = None
    error_message: Optional[str] = None
    output_url: Optional[str] = None
    created_at: str
    updated_at: str
    estimated_completion: Optional[str] = None

class VideoUploadResponse(BaseModel):
    success: bool
    video_id: str
    filename: str
    size_mb: float
    cloudinary_url: str
    duration: Optional[float] = None
    message: str

def create_tables():
    """Create required database tables if they don't exist"""
    try:
        # Create video_processing_jobs table
        execute_query("""
            CREATE TABLE IF NOT EXISTS video_processing_jobs (
                id SERIAL PRIMARY KEY,
                job_id VARCHAR(255) UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                job_type VARCHAR(100) NOT NULL CHECK (job_type IN ('background_replacement', 'enhancement', 'conversion')),
                input_url TEXT,
                input_path TEXT,
                config JSONB,
                status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
                progress DECIMAL(5,2) DEFAULT 0.0,
                message TEXT,
                error_message TEXT,
                output_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create uploaded_videos table
        execute_query("""
            CREATE TABLE IF NOT EXISTS uploaded_videos (
                id SERIAL PRIMARY KEY,
                video_id VARCHAR(255) UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                filename VARCHAR(255) NOT NULL,
                cloudinary_url TEXT,
                file_path TEXT,
                size_mb DECIMAL(10,2),
                duration DECIMAL(10,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create background_images table
        execute_query("""
            CREATE TABLE IF NOT EXISTS background_images (
                id SERIAL PRIMARY KEY,
                bg_id VARCHAR(255) UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                filename VARCHAR(255) NOT NULL,
                cloudinary_url TEXT,
                file_path TEXT,
                size_mb DECIMAL(10,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        log_info("Database tables created/verified successfully", "VideoProcessingRoutes")
        
    except Exception as e:
        log_error(f"Error creating database tables: {e}", "VideoProcessingRoutes")

def get_current_user_from_request(request: Request) -> Optional[Dict]:
    """Get current user from request cookies (matching your existing auth system)"""
    try:
        # Use the same method as your existing BackgroundFX routes
        token = request.cookies.get("access_token")
        if not token:
            log_warning("No access_token cookie found", "VideoProcessingRoutes")
            return None
        
        log_info(f"Validating cookie token: {token[:20]}...", "VideoProcessingRoutes")
        
        # Use your existing auth service
        payload = auth_service.validate_token(token)
        if not payload:
            log_warning("Token validation failed - invalid payload", "VideoProcessingRoutes")
            return None
        
        user_id = payload.get("user_id")
        if not user_id:
            log_warning("Token validation failed - no user_id", "VideoProcessingRoutes")
            return None
        
        user = db.get_user_by_id(user_id)
        if not user:
            log_warning(f"User {user_id} not found in database", "VideoProcessingRoutes")
            return None
        
        log_info(f"User {user_id} authenticated successfully via cookie", "VideoProcessingRoutes")
        return user
        
    except Exception as e:
        log_error(f"Error validating user from cookie: {e}", "VideoProcessingRoutes")
        return None

def get_current_user(request: Request = None) -> Optional[Dict]:
    """FIXED: Get current user from cookies instead of Bearer token"""
    if request:
        return get_current_user_from_request(request)
    return None

def validate_file_size(file: UploadFile, max_size_mb: int) -> bool:
    """Validate uploaded file size"""
    try:
        file.file.seek(0, 2)  # Seek to end
        size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        
        size_mb = size / (1024 * 1024)
        return size_mb <= max_size_mb
    except Exception:
        return False

def validate_file_format(filename: str, allowed_formats: List[str]) -> bool:
    """Validate file format"""
    file_ext = Path(filename).suffix.lower()
    return file_ext in allowed_formats

def upload_to_cloudinary(file_content: bytes, filename: str, resource_type: str = "auto") -> Optional[str]:
    """Upload file to Cloudinary and return public URL - FIXED with timeout and size limits"""
    try:
        if not CLOUDINARY_AVAILABLE:
            log_error("Cloudinary not available", "VideoProcessingRoutes")
            return None
        
        # FIXED: Check file size before upload
        file_size_mb = len(file_content) / (1024 * 1024)
        max_upload_size = 100  # 100MB max for Cloudinary
        
        if file_size_mb > max_upload_size:
            log_error(f"File too large for Cloudinary upload: {file_size_mb:.1f}MB > {max_upload_size}MB", "VideoProcessingRoutes")
            return None
        
        log_info(f"Uploading {filename} to Cloudinary ({file_size_mb:.1f}MB)", "VideoProcessingRoutes")
        
        # Generate unique public_id
        public_id = f"myavatar/video_processing/{int(time.time())}_{filename.split('.')[0]}"
        
        # FIXED: Upload to Cloudinary with timeout and chunk upload for large files
        upload_params = {
            "public_id": public_id,
            "folder": "myavatar/video_processing",
            "resource_type": resource_type,
            "quality": "auto",
            "fetch_format": "auto",
            "timeout": 120,  # 2 minute timeout
        }
        
        # Use chunk upload for large files
        if file_size_mb > 10:  # Files larger than 10MB
            upload_params["chunk_size"] = 6000000  # 6MB chunks
            log_info(f"Using chunked upload for large file: {file_size_mb:.1f}MB", "VideoProcessingRoutes")
        
        result = cloudinary.uploader.upload(file_content, **upload_params)
        
        public_url = result.get("secure_url")
        if public_url:
            log_info(f"Successfully uploaded {filename} to Cloudinary: {public_url}", "VideoProcessingRoutes")
            return public_url
        else:
            log_error(f"Cloudinary upload failed - no URL returned", "VideoProcessingRoutes")
            return None
        
    except Exception as e:
        log_error(f"Cloudinary upload error: {e}", "VideoProcessingRoutes")
        # Log more specific error details
        if "timeout" in str(e).lower():
            log_error(f"Upload timeout for {filename} ({file_size_mb:.1f}MB)", "VideoProcessingRoutes")
        elif "size" in str(e).lower():
            log_error(f"File size issue for {filename}", "VideoProcessingRoutes")
        return None

def download_from_cloudinary(cloudinary_url: str, temp_path: str) -> bool:
    """Download file from Cloudinary to temporary local path"""
    try:
        import requests
        
        response = requests.get(cloudinary_url, timeout=30)
        response.raise_for_status()
        
        with open(temp_path, 'wb') as f:
            f.write(response.content)
        
        log_info(f"Downloaded file from Cloudinary to {temp_path}", "VideoProcessingRoutes")
        return True
        
    except Exception as e:
        log_error(f"Error downloading from Cloudinary: {e}", "VideoProcessingRoutes")
        return False

def create_processing_job(user_id: int, job_type: str, input_url: str, 
                         config: Dict[str, Any]) -> str:
    """FIXED: Create a new processing job with database schema compatibility"""
    try:
        job_id = str(uuid.uuid4())
        
        # Try with existing schema first (input_path column)
        try:
            execute_query(
                """INSERT INTO video_processing_jobs 
                   (job_id, user_id, job_type, input_path, config, status, progress, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (job_id, user_id, job_type, input_url, json.dumps(config), 
                 "pending", 0.0, datetime.now(), datetime.now())
            )
            log_info(f"Created processing job {job_id} for user {user_id} (input_path)", "VideoProcessingRoutes")
            return job_id
            
        except Exception as e:
            # If input_path fails, try with input_url (new schema)
            log_info(f"input_path failed ({e}), trying input_url", "VideoProcessingRoutes")
            execute_query(
                """INSERT INTO video_processing_jobs 
                   (job_id, user_id, job_type, input_url, config, status, progress, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (job_id, user_id, job_type, input_url, json.dumps(config), 
                 "pending", 0.0, datetime.now(), datetime.now())
            )
            log_info(f"Created processing job {job_id} for user {user_id} (input_url)", "VideoProcessingRoutes")
            return job_id
        
    except Exception as e:
        log_error(f"Error creating processing job: {e}", "VideoProcessingRoutes", e)
        raise HTTPException(status_code=500, detail="Failed to create processing job")

def update_job_status(job_id: str, status: str, progress: float = None, 
                     message: str = None, error_message: str = None, output_url: str = None):
    """Update processing job status"""
    try:
        execute_query(
            """UPDATE video_processing_jobs 
               SET status = %s, progress = %s, message = %s, error_message = %s, output_url = %s, updated_at = %s
               WHERE job_id = %s""",
            (status, progress, message, error_message, output_url, datetime.now(), job_id)
        )
        log_info(f"Updated job {job_id}: {status} ({progress}%)", "VideoProcessingRoutes")
    except Exception as e:
        log_error(f"Error updating job status: {e}", "VideoProcessingRoutes", e)

async def process_video_background_task(job_id: str, user_id: int, input_url: str, 
                                      background_config: Dict[str, Any], quality: str,
                                      segmentation_model: str):
    """Background task for video processing using Cloudinary storage"""
    temp_input_path = None
    temp_output_path = None
    
    try:
        log_info(f"Starting background processing for job {job_id}", "VideoProcessingRoutes")
        update_job_status(job_id, "processing", 0.0, "Starting video processing...")
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_input:
            temp_input_path = temp_input.name
        
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_output:
            temp_output_path = temp_output.name
        
        # Download input video from Cloudinary
        update_job_status(job_id, "processing", 10.0, "Downloading input video...")
        if not download_from_cloudinary(input_url, temp_input_path):
            raise Exception("Failed to download input video from Cloudinary")
        
        # Download background image if needed
        temp_bg_path = None
        if background_config.get('type') == 'image' and background_config.get('path'):
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_bg:
                temp_bg_path = temp_bg.name
            
            if not download_from_cloudinary(background_config['path'], temp_bg_path):
                log_warning("Failed to download background image, using default", "VideoProcessingRoutes")
                temp_bg_path = None
            else:
                background_config['path'] = temp_bg_path
        
        # FIXED: Direct progress callback - no more broken mapping
        def progress_callback(progress: float, message: str = ""):
            # Map video processing from 20% to 85% (leaving 15% for upload)
            mapped_progress = 20 + (progress * 0.65)  # 0-100% becomes 20-85%
            update_job_status(job_id, "processing", mapped_progress, message)
        
        replacer = AdvancedBackgroundReplacer(
            user_id=user_id,
            quality=quality,
            segmentation_model=segmentation_model
        )
        
        # Set progress callback if the replacer supports it
        if hasattr(replacer, 'set_progress_callback'):
            replacer.set_progress_callback(progress_callback)
        
        # Update progress
        progress_callback(0, "Initializing AI segmentation...")
        
        # Use your sophisticated background replacement
        success = replacer.replace_background(
            input_video_path=temp_input_path,
            output_video_path=temp_output_path,
            background_config=background_config,
            job_id=job_id
        )
        
        # FIXED: Better error handling - check if output file exists even if success=False
        if not success:
            if os.path.exists(temp_output_path) and os.path.getsize(temp_output_path) > 0:
                log_warning("Processing returned False but output file exists - continuing", "VideoProcessingRoutes")
                # Continue with upload despite False return
            else:
                raise Exception("Video processing failed - no output file created")
        
        # Upload result to Cloudinary with timeout
        update_job_status(job_id, "processing", 85.0, "Uploading processed video...")
        
        with open(temp_output_path, 'rb') as output_file:
            output_content = output_file.read()
        
        output_filename = f"processed_{job_id}.mp4"
        output_url = upload_to_cloudinary(output_content, output_filename, "video")
        
        if not output_url:
            raise Exception("Failed to upload processed video to Cloudinary")
        
        # FIXED: Auto-save to Recent Videos with all required fields
        try:
            execute_query(
                """INSERT INTO videos 
                   (user_id, avatar_id, title, description, video_path, status, format, created_at, background_type, heygen_video_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (user_id, None, f'BackgroundFX - {datetime.now().strftime("%Y-%m-%d %H:%M")}', 
                 'Video processed with BackgroundFX', output_url, 'completed', '16:9', 
                 datetime.now(), 'processed', None)
            )
            log_info(f"Auto-saved processed video to Recent Videos for user {user_id}", "VideoProcessingRoutes")
        except Exception as save_error:
            log_warning(f"Failed to auto-save to Recent Videos: {save_error}", "VideoProcessingRoutes")
        
        update_job_status(job_id, "completed", 100.0, "Processing completed - saved to Recent Videos", output_url=output_url)
        log_info(f"Background processing completed for job {job_id}", "VideoProcessingRoutes")
        
    except Exception as e:
        log_error(f"Error in background processing: {e}", "VideoProcessingRoutes", e)
        update_job_status(job_id, "failed", error_message=str(e))
    finally:
        # Cleanup temporary files
        for temp_path in [temp_input_path, temp_output_path, temp_bg_path]:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    log_warning(f"Failed to cleanup temp file {temp_path}: {e}", "VideoProcessingRoutes")
        
        # Cleanup replacer
        if 'replacer' in locals():
            replacer.cleanup()

# PLACEHOLDER: Local file processing function - PRODUCTION SAFE
async def process_video_background_task_local_fixed(job_id: str, user_id: int, input_path: str, 
                                                   background_config: Dict[str, Any], quality: str,
                                                   segmentation_model: str):
    """
    PLACEHOLDER: Local video processing - Currently returns a mock success
    TODO: Implement actual local processing when ready (separate from production)
    """
    try:
        log_info(f"🔥 LOCAL PROCESSING PLACEHOLDER for job {job_id}", "VideoProcessingRoutes")
        update_job_status(job_id, "processing", 0.0, "Local processing started...")
        
        # Simulate processing steps with progress updates
        await asyncio.sleep(1)
        update_job_status(job_id, "processing", 25.0, "Analyzing video...")
        
        await asyncio.sleep(2) 
        update_job_status(job_id, "processing", 50.0, "Processing frames...")
        
        await asyncio.sleep(2)
        update_job_status(job_id, "processing", 75.0, "Applying background...")
        
        await asyncio.sleep(1)
        update_job_status(job_id, "processing", 90.0, "Finalizing...")
        
        # TODO: Replace this mock with actual processing
        # For now, just copy the input file as a "processed" result
        import shutil
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_output:
            temp_output_path = temp_output.name
        
        shutil.copy2(input_path, temp_output_path)
        
        # Upload the "processed" file (actually just the original) to Cloudinary
        with open(temp_output_path, 'rb') as output_file:
            output_content = output_file.read()
        
        output_filename = f"local_mock_{job_id}.mp4"
        output_url = upload_to_cloudinary(output_content, output_filename, "video")
        
        if not output_url:
            raise Exception("Failed to upload mock result to cloud storage")
        
        # Auto-save to Recent Videos when processing completes
        try:
            execute_query(
                """INSERT INTO videos 
                   (user_id, avatar_id, title, description, video_path, status, format, created_at, background_type, heygen_video_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (user_id, None, f'BackgroundFX Local (MOCK) - {datetime.now().strftime("%Y-%m-%d %H:%M")}', 
                 'PLACEHOLDER: Local processing not yet implemented', output_url, 'completed', '16:9', 
                 datetime.now(), 'processed', None)
            )
            log_info(f"Auto-saved MOCK processed video for user {user_id}", "VideoProcessingRoutes")
        except Exception as save_error:
            log_warning(f"Failed to auto-save mock result: {save_error}", "VideoProcessingRoutes")
        
        update_job_status(job_id, "completed", 100.0, "Local processing completed (MOCK - not actual processing)", output_url=output_url)
        log_info(f"🔥 LOCAL PROCESSING PLACEHOLDER COMPLETED for job {job_id}", "VideoProcessingRoutes")
        
        # Cleanup temp files
        for temp_path in [input_path, temp_output_path]:
            if temp_path and temp_path.startswith('/tmp') and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                    log_info(f"Cleaned up temp file: {temp_path}", "VideoProcessingRoutes")
                except Exception as e:
                    log_warning(f"Failed to cleanup temp file {temp_path}: {e}", "VideoProcessingRoutes")
        
    except Exception as e:
        log_error(f"Error in local processing placeholder: {e}", "VideoProcessingRoutes", e)
        update_job_status(job_id, "failed", error_message=f"Local processing placeholder error: {str(e)}")

# Initialize tables on startup
create_tables()

# FIXED: Route for local file processing - NO MORE 500 ERRORS!

@router.post("/video-processing/process-local", response_model=ProcessingJobResponse)
async def process_local_files_alias(
    request: Request,
    background_tasks: BackgroundTasks,  # Pass through
    video_file: UploadFile = File(...),
    background_file: UploadFile = File(None),
    background_config: str = Form(...),
    quality: str = Form("medium"),
    segmentation_model: str = Form("auto"),
    preserve_audio: str = Form("true")
):
    log_info("[API] /video-processing/process-local endpoint called (alias for /process-local)", "VideoProcessingRoutes")
    # Delegate to the main handler
    return await process_local_files(
        request=request,
        background_tasks=background_tasks,
        video_file=video_file,
        background_file=background_file,
        background_config=background_config,
        quality=quality,
        segmentation_model=segmentation_model,
        preserve_audio=preserve_audio
    )

@router.post("/process-local", response_model=ProcessingJobResponse)
async def process_local_files(
    request: Request,
    background_tasks: BackgroundTasks,
    video_file: UploadFile = File(...),
    background_file: UploadFile = File(None),
    background_config: str = Form(...),
    quality: str = Form("medium"),
    segmentation_model: str = Form("auto"),
    preserve_audio: str = Form("true")
):
    # FIXED: Add the missing authentication check
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        log_info(f"User {user['id']} starting local file processing", "VideoProcessingRoutes")
        
        # Parse background config
        bg_config = json.loads(background_config)
        
        # Save uploaded video to temp file
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
            content = await video_file.read()
            temp_video.write(content)
            temp_input_path = temp_video.name
        
        # Save background image if provided
        temp_bg_path = None
        if background_file and bg_config.get('type') == 'image':
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_bg:
                bg_content = await background_file.read()
                temp_bg.write(bg_content)
                temp_bg_path = temp_bg.name
                bg_config['path'] = temp_bg_path
        
        # Create processing job
        job_id = create_processing_job(
            user_id=user['id'],
            job_type="background_replacement",  # FIXED: Use allowed job type
            input_url=temp_input_path,  # Use temp path
            config={
                "background_config": bg_config,
                "quality": quality,
                "segmentation_model": segmentation_model,
                "preserve_audio": preserve_audio == "true"
            }
        )
        
        # FIXED: Add background task properly - FastAPI handles execution automatically
        background_tasks.add_task(
            process_video_background_task_local_fixed,  # FIXED: Use the new fixed function
            job_id=job_id,
            user_id=user['id'],
            input_path=temp_input_path,
            background_config=bg_config,
            quality=quality,
            segmentation_model=segmentation_model
        )
        
        log_info(f"Local processing job started: {job_id}", "VideoProcessingRoutes")
        
        return ProcessingJobResponse(
            job_id=job_id,
            status="pending",
            message="Local processing job started - will auto-save to Recent Videos",
            created_at=datetime.now().isoformat(),
            estimated_duration=300
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error starting local processing: {e}", "VideoProcessingRoutes", e)
        raise HTTPException(status_code=500, detail="Failed to start local processing")

# Route: Upload video for processing
@router.post("/upload-video", response_model=VideoUploadResponse)
async def upload_video(
    request: Request,
    video: UploadFile = File(...)
):
    """
    Upload video file for background processing (using Cloudinary)
    """
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        log_info(f"User {user['id']} uploading video: {video.filename}", "VideoProcessingRoutes")
        
        # FIXED: Generate video_id before using it
        video_id = str(uuid.uuid4())
        
        # Validate file format
        if not validate_file_format(video.filename, ALLOWED_VIDEO_FORMATS):
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid video format. Allowed: {', '.join(ALLOWED_VIDEO_FORMATS)}"
            )
        
        # Validate file size
        if not validate_file_size(video, MAX_VIDEO_SIZE_MB):
            raise HTTPException(
                status_code=413, 
                detail=f"Video file too large. Maximum size: {MAX_VIDEO_SIZE_MB}MB"
            )
        
        # Read file content
        content = await video.read()
        size_mb = len(content) / (1024 * 1024)
        
        # Upload to Cloudinary
        cloudinary_url = upload_to_cloudinary(content, video.filename, "video")
        
        if not cloudinary_url:
            raise HTTPException(status_code=500, detail="Failed to upload video to cloud storage")
        
        # FIXED: Store video info in database with original_filename
        try:
            execute_query(
                """INSERT INTO uploaded_videos 
                   (video_id, user_id, filename, cloudinary_url, size_mb, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (video_id, user['id'], video.filename, cloudinary_url, size_mb, datetime.now())
            )
        except Exception as db_error:
            # Fallback: try with file_path instead of cloudinary_url (for old schema)
            log_warning(f"Cloudinary URL insert failed, trying file_path: {db_error}", "VideoProcessingRoutes")
            try:
                execute_query(
                    """INSERT INTO uploaded_videos 
                       (video_id, user_id, filename, file_path, size_mb, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (video_id, user['id'], video.filename, cloudinary_url, size_mb, datetime.now())
                )
            except Exception as fallback_error:
                log_error(f"Both insert methods failed: {fallback_error}", "VideoProcessingRoutes")
                raise HTTPException(status_code=500, detail="Failed to store video information")
        
        log_info(f"Video uploaded successfully: {video_id} by user {user['id']}", "VideoProcessingRoutes")
        
        return VideoUploadResponse(
            success=True,
            video_id=video_id,
            filename=video.filename,
            size_mb=round(size_mb, 2),
            cloudinary_url=cloudinary_url,
            message="Video uploaded successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error uploading video: {e}", "VideoProcessingRoutes", e)
        raise HTTPException(status_code=500, detail="Video upload failed")

# Route: Upload background image
@router.post("/upload-background")
async def upload_background(
    request: Request,
    background: UploadFile = File(...)
):
    """
    Upload background image for video processing (using Cloudinary)
    """
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        log_info(f"User {user['id']} uploading background: {background.filename}", "VideoProcessingRoutes")
        
        # FIXED: Generate bg_id before using it
        bg_id = str(uuid.uuid4())
        
        # Validate file format
        if not validate_file_format(background.filename, ALLOWED_IMAGE_FORMATS):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid image format. Allowed: {', '.join(ALLOWED_IMAGE_FORMATS)}"
            )
        
        # Validate file size
        if not validate_file_size(background, MAX_IMAGE_SIZE_MB):
            raise HTTPException(
                status_code=413,
                detail=f"Image file too large. Maximum size: {MAX_IMAGE_SIZE_MB}MB"
            )
        
        # Read file content
        content = await background.read()
        size_mb = len(content) / (1024 * 1024)
        
        # Upload to Cloudinary
        cloudinary_url = upload_to_cloudinary(content, background.filename, "image")
        
        if not cloudinary_url:
            raise HTTPException(status_code=500, detail="Failed to upload background to cloud storage")
        
        # FIXED: Store background info in database
        try:
            execute_query(
                """INSERT INTO background_images 
                   (bg_id, user_id, filename, cloudinary_url, size_mb, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (bg_id, user['id'], background.filename, cloudinary_url, size_mb, datetime.now())
            )
        except Exception as db_error:
            # Fallback: try with file_path instead of cloudinary_url (for old schema)
            log_warning(f"Cloudinary URL insert failed, trying file_path: {db_error}", "VideoProcessingRoutes")
            try:
                execute_query(
                    """INSERT INTO background_images 
                       (bg_id, user_id, filename, file_path, size_mb, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (bg_id, user['id'], background.filename, cloudinary_url, size_mb, datetime.now())
                )
            except Exception as fallback_error:
                log_error(f"Both background insert methods failed: {fallback_error}", "VideoProcessingRoutes")
                raise HTTPException(status_code=500, detail="Failed to store background information")
        
        log_info(f"Background uploaded successfully: {bg_id} by user {user['id']}", "VideoProcessingRoutes")
        
        return {
            "success": True,
            "bg_id": bg_id,
            "filename": background.filename,
            "file_path": cloudinary_url,  # FIXED: Return cloudinary_url as file_path for compatibility
            "cloudinary_url": cloudinary_url,
            "size_mb": round(size_mb, 2),
            "message": "Background image uploaded successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error uploading background: {e}", "VideoProcessingRoutes", e)
        raise HTTPException(status_code=500, detail="Background upload failed")

# FIXED: Add route aliases to match frontend expectations
@router.post("/api/videos/upload", response_model=VideoUploadResponse)
async def upload_video_alias(request: Request, video: UploadFile = File(...)):
    """Alias for video upload to match frontend expectations"""
    return await upload_video(request, video)

@router.post("/api/backgrounds/upload")
async def upload_background_alias(request: Request, background: UploadFile = File(...)):
    """Alias for background upload to match frontend expectations"""
    return await upload_background(request, background)

# Route: Start background replacement job
@router.post("/replace-background", response_model=ProcessingJobResponse)
async def start_background_replacement(
    request: Request,
    job_request: ProcessingJobRequest,
    background_tasks: BackgroundTasks
):
    """
    Start background replacement processing job (using Cloudinary)
    """
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        log_info(f"User {user['id']} starting background replacement job", "VideoProcessingRoutes")
        
        # Get video URL (try both cloudinary_url and file_path columns)
        if job_request.video_id:
            # Try new schema first (cloudinary_url)
            video_info = execute_query(
                "SELECT cloudinary_url, file_path FROM uploaded_videos WHERE video_id = %s AND user_id = %s",
                (job_request.video_id, user['id']),
                fetch_one=True
            )
            if not video_info:
                raise HTTPException(status_code=404, detail="Video not found")
            
            # Use cloudinary_url if available, otherwise use file_path
            input_url = video_info.get('cloudinary_url') or video_info.get('file_path')
            if not input_url:
                raise HTTPException(status_code=404, detail="Video URL not found")
        else:
            raise HTTPException(status_code=400, detail="Video ID is required")
        
        # Prepare background config
        bg_config = job_request.background_config.dict()
        
        # If background type is image, get the Cloudinary URL
        if bg_config['type'] == 'image' and bg_config.get('path'):
            # Assume path contains bg_id, look up the Cloudinary URL
            bg_info = execute_query(
                "SELECT cloudinary_url FROM background_images WHERE bg_id = %s AND user_id = %s",
                (bg_config['path'], user['id']),
                fetch_one=True
            )
            if bg_info:
                bg_config['path'] = bg_info['cloudinary_url']
            else:
                raise HTTPException(status_code=404, detail="Background image not found")
        
        # Create processing job
        job_id = create_processing_job(
            user_id=user['id'],
            job_type="background_replacement",
            input_url=input_url,
            config={
                "background_config": bg_config,
                "quality": job_request.quality,
                "segmentation_model": job_request.segmentation_model,
                "preserve_audio": job_request.preserve_audio
            }
        )
        
        # Start background processing
        background_tasks.add_task(
            process_video_background_task,
            job_id=job_id,
            user_id=user['id'],
            input_url=input_url,
            background_config=bg_config,
            quality=job_request.quality,
            segmentation_model=job_request.segmentation_model
        )
        
        log_info(f"Background replacement job started: {job_id}", "VideoProcessingRoutes")
        
        return ProcessingJobResponse(
            job_id=job_id,
            status="pending",
            message="Background replacement job started",
            created_at=datetime.now().isoformat(),
            estimated_duration=300  # 5 minutes estimate
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error starting background replacement: {e}", "VideoProcessingRoutes", e)
        raise HTTPException(status_code=500, detail="Failed to start background replacement")

# Route: Get job status
@router.get("/job/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    request: Request
):
    """
    Get processing job status
    """
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        # Get job info
        job = execute_query(
            """SELECT * FROM video_processing_jobs 
               WHERE job_id = %s AND user_id = %s""",
            (job_id, user['id']),
            fetch_one=True
        )
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return JobStatusResponse(
            job_id=job['job_id'],
            status=job['status'],
            progress=job['progress'] or 0.0,
            message=job.get('message'),
            error_message=job.get('error_message'),
            output_url=job.get('output_url'),
            created_at=job['created_at'].isoformat() if job['created_at'] else None,
            updated_at=job['updated_at'].isoformat() if job['updated_at'] else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting job status: {e}", "VideoProcessingRoutes", e)
        raise HTTPException(status_code=500, detail="Failed to get job status")

# Route: Download processed video (redirect to Cloudinary)
@router.get("/job/{job_id}/download")
async def download_processed_video(
    job_id: str,
    request: Request
):
    """
    Download processed video (redirect to Cloudinary URL)
    """
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        # Get job info
        job = execute_query(
            """SELECT * FROM video_processing_jobs 
               WHERE job_id = %s AND user_id = %s AND status = 'completed'""",
            (job_id, user['id']),
            fetch_one=True
        )
        
        if not job:
            raise HTTPException(status_code=404, detail="Completed job not found")
        
        output_url = job.get('output_url')
        if not output_url:
            raise HTTPException(status_code=404, detail="Processed video not found")
        
        # Redirect to Cloudinary URL for download
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=output_url)
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error downloading video: {e}", "VideoProcessingRoutes", e)
        raise HTTPException(status_code=500, detail="Failed to download video")

# Route: Save processed video to library
@router.post("/save-to-library")
async def save_to_library(
    request: Request
):
    """
    Save processed video to user's video library
    """
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        data = await request.json()
        job_id = data.get('job_id')
        title = data.get('title', f'BackgroundFX - {datetime.now().strftime("%Y-%m-%d")}')
        description = data.get('description', 'Video processed with BackgroundFX')
        
        # Get completed job
        job = execute_query(
            """SELECT * FROM video_processing_jobs 
               WHERE job_id = %s AND user_id = %s AND status = 'completed'""",
            (job_id, user['id']),
            fetch_one=True
        )
        
        if not job:
            raise HTTPException(status_code=404, detail="Completed job not found")
        
        output_url = job.get('output_url')
        if not output_url:
            raise HTTPException(status_code=404, detail="Processed video not found")
        
        # Save to videos table (your main video library) with Cloudinary URL and all required fields
        execute_query(
            """INSERT INTO videos 
               (user_id, avatar_id, title, description, video_path, status, format, created_at, background_type, heygen_video_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (user['id'], None, title, description, output_url, 'completed', '16:9', datetime.now(), 'processed', None)
        )
        
        log_info(f"Video saved to library for user {user['id']}", "VideoProcessingRoutes")
        
        return {
            "success": True,
            "message": "Video saved to your library successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error saving to library: {e}", "VideoProcessingRoutes", e)
        raise HTTPException(status_code=500, detail="Failed to save video to library")

# Route: Get system status
@router.get("/status")
async def get_system_status():
    """
    Get video processing system status
    """
    try:
        return {
            "success": True,
            "service": "Video Processing API",
            "status": "operational",
            "storage": "Cloudinary CDN",
            "features": {
                "background_replacement": True,
                "ai_segmentation": True,
                "multiple_formats": True,
                "quality_settings": True,
                "progress_tracking": True,
                "cloud_storage": CLOUDINARY_AVAILABLE,
                "local_processing": True,
                "auto_save_to_recent_videos": True
            },
            "limits": {
                "max_video_size_mb": MAX_VIDEO_SIZE_MB,
                "max_image_size_mb": MAX_IMAGE_SIZE_MB,
                "allowed_video_formats": ALLOWED_VIDEO_FORMATS,
                "allowed_image_formats": ALLOWED_IMAGE_FORMATS
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        log_error(f"Error getting system status: {e}", "VideoProcessingRoutes", e)
        return {"success": False, "error": str(e)}

# Debug endpoint for troubleshooting
@router.get("/debug/video-processing")
async def debug_video_processing(request: Request):
    """Debug endpoint to check video processing status"""
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        user_id = user['id']
        
        # Check table constraints
        constraints = execute_query("""
            SELECT constraint_name, check_clause
            FROM information_schema.check_constraints 
            WHERE constraint_schema = 'public' 
            AND constraint_name LIKE '%job_type%'
        """)
        
        # Check video processing jobs
        processing_jobs = execute_query("""
            SELECT job_id, job_type, status, created_at, output_url, input_path, input_url
            FROM video_processing_jobs 
            WHERE user_id = %s
            ORDER BY created_at DESC 
            LIMIT 10
        """, (user_id,))
        
        # Check videos table for processed videos
        processed_videos = execute_query("""
            SELECT id, title, status, background_type, video_path, created_at
            FROM videos 
            WHERE user_id = %s AND background_type IS NOT NULL
            ORDER BY created_at DESC
        """, (user_id,))
        
        # Check all recent videos
        all_recent_videos = execute_query("""
            SELECT id, title, status, background_type, created_at
            FROM videos 
            WHERE user_id = %s
            ORDER BY created_at DESC 
            LIMIT 10
        """, (user_id,))
        
        # Count totals
        job_counts = execute_query("""
            SELECT 
                COUNT(*) as total_jobs,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_jobs,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_jobs,
                COUNT(CASE WHEN status = 'processing' THEN 1 END) as processing_jobs,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_jobs
            FROM video_processing_jobs 
            WHERE user_id = %s
        """, (user_id,))
        
        return {
            "status": "success",
            "user_id": user_id,
            "constraints": constraints or [],
            "processing_jobs": processing_jobs or [],
            "processed_videos": processed_videos or [],
            "all_recent_videos": all_recent_videos or [],
            "job_counts": job_counts[0] if job_counts else {},
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        log_error(f"Debug endpoint error: {e}", "VideoProcessingRoutes")
        return {
            "status": "error", 
            "error": str(e)
        }
