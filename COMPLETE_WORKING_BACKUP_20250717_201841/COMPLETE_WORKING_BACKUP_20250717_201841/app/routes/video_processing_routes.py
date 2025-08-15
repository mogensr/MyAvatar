"""
Video Processing Routes for MyAvatar
FastAPI endpoints for advanced background replacement functionality
"""
import os
import uuid
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
import json

from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

# MyAvatar imports
try:
    from app.db.database import execute_query
    from app.logger.log_handler import log_info, log_error, log_warning
    from app.services.auth_service import auth_service
    from app.db.user_manager import Database
    from app.config.settings import config
    from app.video_enhancer.advanced_background_replacer import (
        AdvancedBackgroundReplacer,
        replace_video_background
    )
except ImportError as e:
    raise ImportError(f"Required MyAvatar modules not found: {e}")

router = APIRouter()
security = HTTPBearer(auto_error=False)
db = Database()

# Constants
MAX_VIDEO_SIZE_MB = getattr(config, 'MAX_VIDEO_SIZE_MB', 500)
MAX_IMAGE_SIZE_MB = getattr(config, 'MAX_IMAGE_SIZE_MB', 50)
ALLOWED_VIDEO_FORMATS = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
ALLOWED_IMAGE_FORMATS = ['.jpg', '.jpeg', '.png', '.bmp', '.webp']
UPLOAD_DIR = getattr(config, 'UPLOAD_DIR', 'uploads')
OUTPUT_DIR = getattr(config, 'OUTPUT_DIR', 'output')

# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

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
    output_path: Optional[str] = None
    created_at: str
    updated_at: str
    estimated_completion: Optional[str] = None

class VideoUploadResponse(BaseModel):
    success: bool
    video_id: str
    filename: str
    size_mb: float
    duration: Optional[float] = None
    message: str

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[Dict]:
    """Get current user from JWT token"""
    try:
        if not credentials:
            return None
        
        payload = auth_service.validate_token(credentials.credentials)
        if not payload:
            return None
            
        user_id = payload.get("user_id")
        if not user_id:
            return None
            
        return db.get_user_by_id(user_id)
        
    except Exception as e:
        log_error(f"Error validating user: {e}", "VideoProcessingRoutes")
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

def create_processing_job(user_id: int, job_type: str, input_path: str, 
                         config: Dict[str, Any]) -> str:
    """Create a new processing job in database"""
    try:
        job_id = str(uuid.uuid4())
        
        execute_query(
            """INSERT INTO video_processing_jobs 
               (job_id, user_id, job_type, input_path, config, status, progress, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (job_id, user_id, job_type, input_path, json.dumps(config), 
             "pending", 0.0, datetime.now(), datetime.now())
        )
        
        log_info(f"Created processing job {job_id} for user {user_id}", "VideoProcessingRoutes")
        return job_id
        
    except Exception as e:
        log_error(f"Error creating processing job: {e}", "VideoProcessingRoutes", e)
        raise HTTPException(status_code=500, detail="Failed to create processing job")

def update_job_status(job_id: str, status: str, progress: float = None, 
                     error_message: str = None, output_path: str = None):
    """Update processing job status"""
    try:
        execute_query(
            """UPDATE video_processing_jobs 
               SET status = %s, progress = %s, error_message = %s, output_path = %s, updated_at = %s
               WHERE job_id = %s""",
            (status, progress, error_message, output_path, datetime.now(), job_id)
        )
    except Exception as e:
        log_error(f"Error updating job status: {e}", "VideoProcessingRoutes", e)

async def process_video_background_task(job_id: str, user_id: int, input_path: str, 
                                      background_config: Dict[str, Any], quality: str,
                                      segmentation_model: str):
    """Background task for video processing"""
    try:
        log_info(f"Starting background processing for job {job_id}", "VideoProcessingRoutes")
        update_job_status(job_id, "processing", 0.0)
        
        # Generate output path
        output_filename = f"processed_{job_id}.mp4"
        output_path = os.path.join(OUTPUT_DIR, f"user_{user_id}", output_filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Create background replacer with progress callback
        def progress_callback(progress: float, message: str = ""):
            update_job_status(job_id, "processing", progress)
        
        replacer = AdvancedBackgroundReplacer(
            user_id=user_id,
            quality=quality,
            segmentation_model=segmentation_model
        )
        replacer.set_progress_callback(progress_callback)
        
        # Process video
        success = replacer.replace_background(
            input_video_path=input_path,
            output_video_path=output_path,
            background_config=background_config,
            job_id=job_id
        )
        
        if success:
            update_job_status(job_id, "completed", 1.0, output_path=output_path)
            log_info(f"Background processing completed for job {job_id}", "VideoProcessingRoutes")
        else:
            update_job_status(job_id, "failed", error_message="Video processing failed")
            log_error(f"Background processing failed for job {job_id}", "VideoProcessingRoutes")
            
    except Exception as e:
        log_error(f"Error in background processing: {e}", "VideoProcessingRoutes", e)
        update_job_status(job_id, "failed", error_message=str(e))
    finally:
        # Cleanup
        if 'replacer' in locals():
            replacer.cleanup()

# Route: Upload video for processing
@router.post("/upload-video", response_model=VideoUploadResponse)
async def upload_video(
    request: Request,
    video: UploadFile = File(...),
    user: Dict = Depends(get_current_user)
):
    """
    Upload video file for background processing
    """
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
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
        
        # Generate unique filename
        video_id = str(uuid.uuid4())
        file_ext = Path(video.filename).suffix
        filename = f"video_{video_id}{file_ext}"
        
        # Create user upload directory
        user_upload_dir = os.path.join(UPLOAD_DIR, f"user_{user['id']}")
        os.makedirs(user_upload_dir, exist_ok=True)
        
        # Save uploaded file
        file_path = os.path.join(user_upload_dir, filename)
        with open(file_path, "wb") as buffer:
            content = await video.read()
            buffer.write(content)
        
        # Get file size
        size_mb = len(content) / (1024 * 1024)
        
        # Store video info in database
        execute_query(
            """INSERT INTO uploaded_videos 
               (video_id, user_id, filename, file_path, size_mb, created_at)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (video_id, user['id'], video.filename, file_path, size_mb, datetime.now())
        )
        
        log_info(f"Video uploaded: {video_id} by user {user['id']}", "VideoProcessingRoutes")
        
        return VideoUploadResponse(
            success=True,
            video_id=video_id,
            filename=video.filename,
            size_mb=round(size_mb, 2),
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
    background: UploadFile = File(...),
    user: Dict = Depends(get_current_user)
):
    """
    Upload background image for video processing
    """
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
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
        
        # Generate unique filename
        bg_id = str(uuid.uuid4())
        file_ext = Path(background.filename).suffix
        filename = f"background_{bg_id}{file_ext}"
        
        # Create user backgrounds directory
        user_bg_dir = os.path.join(UPLOAD_DIR, f"user_{user['id']}", "backgrounds")
        os.makedirs(user_bg_dir, exist_ok=True)
        
        # Save uploaded file
        file_path = os.path.join(user_bg_dir, filename)
        with open(file_path, "wb") as buffer:
            content = await background.read()
            buffer.write(content)
        
        size_mb = len(content) / (1024 * 1024)
        
        # Store background info in database
        execute_query(
            """INSERT INTO background_images 
               (bg_id, user_id, filename, file_path, size_mb, created_at)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (bg_id, user['id'], background.filename, file_path, size_mb, datetime.now())
        )
        
        log_info(f"Background uploaded: {bg_id} by user {user['id']}", "VideoProcessingRoutes")
        
        return {
            "success": True,
            "bg_id": bg_id,
            "filename": background.filename,
            "file_path": file_path,
            "size_mb": round(size_mb, 2),
            "message": "Background image uploaded successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error uploading background: {e}", "VideoProcessingRoutes", e)
        raise HTTPException(status_code=500, detail="Background upload failed")

# Route: Start background replacement job
@router.post("/replace-background", response_model=ProcessingJobResponse)
async def start_background_replacement(
    request: Request,
    job_request: ProcessingJobRequest,
    background_tasks: BackgroundTasks,
    user: Dict = Depends(get_current_user)
):
    """
    Start background replacement processing job
    """
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        # Get video path
        if job_request.video_id:
            # Use uploaded video
            video_info = execute_query(
                "SELECT file_path FROM uploaded_videos WHERE video_id = %s AND user_id = %s",
                (job_request.video_id, user['id']),
                fetch_one=True
            )
            if not video_info:
                raise HTTPException(status_code=404, detail="Video not found")
            input_path = video_info['file_path']
        else:
            raise HTTPException(status_code=400, detail="Video ID is required")
        
        # Validate video file exists
        if not os.path.exists(input_path):
            raise HTTPException(status_code=404, detail="Video file not found on server")
        
        # Prepare background config
        bg_config = job_request.background_config.dict()
        
        # If background type is image, validate the path
        if bg_config['type'] == 'image' and bg_config.get('path'):
            if not os.path.exists(bg_config['path']):
                raise HTTPException(status_code=404, detail="Background image not found")
        
        # Create processing job
        job_id = create_processing_job(
            user_id=user['id'],
            job_type="background_replacement",
            input_path=input_path,
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
            input_path=input_path,
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
    user: Dict = Depends(get_current_user)
):
    """
    Get processing job status
    """
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
            output_path=job.get('output_path'),
            created_at=job['created_at'].isoformat() if job['created_at'] else None,
            updated_at=job['updated_at'].isoformat() if job['updated_at'] else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting job status: {e}", "VideoProcessingRoutes", e)
        raise HTTPException(status_code=500, detail="Failed to get job status")

# Route: Download processed video
@router.get("/job/{job_id}/download")
async def download_processed_video(
    job_id: str,
    user: Dict = Depends(get_current_user)
):
    """
    Download processed video
    """
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
        
        output_path = job.get('output_path')
        if not output_path or not os.path.exists(output_path):
            raise HTTPException(status_code=404, detail="Processed video file not found")
        
        # Return file
        return FileResponse(
            path=output_path,
            media_type='video/mp4',
            filename=f"processed_video_{job_id}.mp4"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error downloading video: {e}", "VideoProcessingRoutes", e)
        raise HTTPException(status_code=500, detail="Failed to download video")

# Route: List user's processing jobs
@router.get("/jobs")
async def list_user_jobs(
    status: Optional[str] = None,
    limit: int = 20,
    user: Dict = Depends(get_current_user)
):
    """
    List user's processing jobs
    """
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        query = "SELECT * FROM video_processing_jobs WHERE user_id = %s"
        params = [user['id']]
        
        if status:
            query += " AND status = %s"
            params.append(status)
        
        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        
        jobs = execute_query(query, params, fetch_all=True)
        
        return {
            "success": True,
            "jobs": [dict(job) for job in jobs] if jobs else [],
            "count": len(jobs) if jobs else 0
        }
        
    except Exception as e:
        log_error(f"Error listing jobs: {e}", "VideoProcessingRoutes", e)
        raise HTTPException(status_code=500, detail="Failed to list jobs")

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
            "features": {
                "background_replacement": True,
                "ai_segmentation": True,
                "multiple_formats": True,
                "quality_settings": True,
                "progress_tracking": True
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
