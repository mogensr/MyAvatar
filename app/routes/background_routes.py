# DEPLOY TEST - 2025-07-21 4:15 PM


"""
API routes for background replacement functionality in MyAvatar videos
FIXED: Removed duplicate save to Recent Videos - now handled by video_processing_routes.py
"""
import os
import logging
from fastapi import APIRouter, Request, File, Form, UploadFile, HTTPException
from fastapi.responses import JSONResponse, FileResponse
import sqlite3
from typing import Optional, List
import asyncio
import time
import uuid
from pathlib import Path

from app.auth.authentication import get_current_user
from app.db.database import execute_query
# Using BackgroundFX microservice instead of local background replacement
from app.services.backgroundfx_client_v2 import BackgroundFXClient
from app.video_enhancer.video_processor import VideoProcessor

# Cloudinary imports
try:
    import cloudinary
    import cloudinary.uploader
    CLOUDINARY_AVAILABLE = True
except ImportError:
    CLOUDINARY_AVAILABLE = False

# Configure router
router = APIRouter()

# Configure logging
logger = logging.getLogger(__name__)

# Define paths
BACKGROUNDS_DIR = os.path.join("static", "backgrounds")
VIDEOS_DIR = os.path.join("static", "videos")
TEMP_DIR = os.path.join("temp", "background_processing")

# Ensure directories exist
os.makedirs(BACKGROUNDS_DIR, exist_ok=True)
os.makedirs(VIDEOS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

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
    logger.info("Cloudinary configured for video processing")
else:
    logger.warning("Cloudinary not configured - videos will be stored locally")

def upload_video_to_cloudinary(video_path: str, video_id: int) -> Optional[str]:
    """Upload processed video to Cloudinary and return public URL"""
    try:
        if not CLOUDINARY_AVAILABLE:
            logger.error("Cloudinary not available")
            return None
        
        logger.info(f"Uploading video {video_id} to Cloudinary...")
        
        # Read video file
        with open(video_path, 'rb') as video_file:
            video_content = video_file.read()
        
        # Generate unique public_id
        public_id = f"myavatar/processed_videos/bg_{video_id}_{int(time.time())}"
        
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            video_content,
            resource_type="video",
            public_id=public_id,
            folder="myavatar/processed_videos",
            quality="auto",
            format="mp4"
        )
        
        cloudinary_url = result.get("secure_url")
        if cloudinary_url:
            logger.info(f"Successfully uploaded video {video_id} to Cloudinary: {cloudinary_url}")
            return cloudinary_url
        else:
            logger.error(f"Cloudinary upload failed - no URL returned for video {video_id}")
            return None
        
    except Exception as e:
        logger.error(f"Cloudinary upload error for video {video_id}: {e}")
        return None


@router.get("/backgrounds")
async def list_backgrounds(request: Request):
    """
    Get list of available background images
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse(content={"success": False, "error": "Authentication required"}, status_code=401)
    
    try:
        # Get all backgrounds
        backgrounds = execute_query(
            "SELECT id, name, description, category, thumbnail_path, is_default FROM backgrounds ORDER BY name",
            (),
            fetch_all=True
        )
        
        # Convert to list of dicts
        background_list = []
        for bg in backgrounds:
            if isinstance(bg, dict):
                background_list.append(bg)
            else:
                # Handle SQLite Row objects
                bg_dict = {}
                for key in bg.keys():
                    bg_dict[key] = bg[key]
                background_list.append(bg_dict)
        
        # Add URLs for thumbnails
        for bg in background_list:
            if bg.get("thumbnail_path"):
                bg["thumbnail_url"] = f"/static/backgrounds/{os.path.basename(bg['thumbnail_path'])}"
        
        return JSONResponse(content={"success": True, "backgrounds": background_list})
        
    except Exception as e:
        logger.error(f"Error listing backgrounds: {e}")
        return JSONResponse(
            content={"success": False, "error": "Failed to retrieve backgrounds"},
            status_code=500
        )


@router.post("/backgrounds/upload")
async def upload_background(
    request: Request,
    background_file: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form(""),
    category: str = Form("Custom")
):
    """
    Upload a new background image
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse(content={"success": False, "error": "Authentication required"}, status_code=401)
    
    # Allow all authenticated users to upload backgrounds
    # Add user ID to category for personal backgrounds
    if category == "Custom":
        category = f"User {user['id']}"
    
    try:
        # Validate file type
        if not background_file.content_type.startswith("image/"):
            return JSONResponse(
                content={"success": False, "error": "Only image files are allowed"},
                status_code=400
            )
        
        # Generate unique filename
        file_ext = os.path.splitext(background_file.filename)[1]
        unique_filename = f"bg_{int(time.time())}_{uuid.uuid4().hex[:8]}{file_ext}"
        file_path = os.path.join(BACKGROUNDS_DIR, unique_filename)
        
        # Save file
        with open(file_path, "wb") as f:
            contents = await background_file.read()
            f.write(contents)
        
        # Generate thumbnail (simpler version for now)
        thumbnail_filename = f"thumb_{unique_filename}"
        thumbnail_path = os.path.join(BACKGROUNDS_DIR, thumbnail_filename)
        
        # This is simple copy for now, ideally would resize the image
        with open(thumbnail_path, "wb") as f:
            f.write(contents)
        
        # Add to database
        background_id = execute_query(
            """
            INSERT INTO backgrounds (name, description, category, file_path, thumbnail_path, is_default)
            VALUES (%s, %s, %s, %s, %s, 0)
            RETURNING id
            """,
            (name, description, category, file_path, thumbnail_path),
            fetch_one=True
        )
        
        return JSONResponse(content={
            "success": True,
            "background_id": background_id["id"] if isinstance(background_id, dict) else background_id[0],
            "message": "Background uploaded successfully"
        })
        
    except Exception as e:
        logger.error(f"Error uploading background: {e}")
        return JSONResponse(
            content={"success": False, "error": f"Failed to upload background: {str(e)}"},
            status_code=500
        )


@router.post("/videos/{video_id}/replace-background")
async def replace_video_background(
    request: Request,
    video_id: int,
    background_id: int = Form(...),
    quality: str = Form("medium")
):
    """
    Replace the background in a video
    
    Args:
        video_id: ID of the video to process
        background_id: ID of the background to use
        quality: Processing quality ('low', 'medium', 'high')
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse(content={"success": False, "error": "Authentication required"}, status_code=401)
    
    # Validate params
    if quality not in ["low", "medium", "high"]:
        quality = "medium"
    
    try:
        # Check if video exists and belongs to user
        video = execute_query(
            "SELECT * FROM videos WHERE id = %s AND user_id = %s",
            (video_id, user["id"]),
            fetch_one=True
        )
        
        if not video:
            return JSONResponse(
                content={"success": False, "error": "Video not found or access denied"},
                status_code=404
            )
        
        # Check if background exists
        background = execute_query(
            "SELECT * FROM backgrounds WHERE id = %s",
            (background_id,),
            fetch_one=True
        )
        
        if not background:
            return JSONResponse(
                content={"success": False, "error": "Background not found"},
                status_code=404
            )
        
        # Get video and background files
        video_file = video.get("video_path") or video.get("file_path") or f"{VIDEOS_DIR}/video_{video_id}.mp4"
        bg_file = background.get("file_path")
        
        # Handle Cloudinary URLs - if video_path is a URL, we need to download it first
        if video_file.startswith("http"):
            logger.info(f"Video is stored on Cloudinary, downloading for processing: {video_file}")
            import requests
            import tempfile
            
            try:
                response = requests.get(video_file, timeout=30)
                response.raise_for_status()
                
                # Create temporary file for processing
                with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
                    temp_video.write(response.content)
                    video_file = temp_video.name
                    logger.info(f"Downloaded video to temporary file: {video_file}")
                    
            except Exception as e:
                logger.error(f"Failed to download video from Cloudinary: {e}")
                return JSONResponse(
                    content={"success": False, "error": "Failed to download video for processing"},
                    status_code=500
                )
        
        if not os.path.exists(video_file):
            return JSONResponse(
                content={"success": False, "error": "Video file not found"},
                status_code=404
            )
            
        if not os.path.exists(bg_file):
            return JSONResponse(
                content={"success": False, "error": "Background file not found"},
                status_code=404
            )
        
        # Create unique output path
        output_filename = f"bg_{video_id}_{background_id}_{int(time.time())}.mp4"
        output_path = os.path.join(TEMP_DIR, output_filename)
        
        # Start background task for processing
        task = asyncio.create_task(
            process_video_background(video_id, video_file, bg_file, output_path, quality, user["id"], background_id)
        )
        
        # Update video record with pending background change
        execute_query(
            "UPDATE videos SET status = 'processing' WHERE id = %s",
            (video_id,)
        )
        
        return JSONResponse(content={
            "success": True,
            "message": "Background replacement started",
            "video_id": video_id
        })
        
    except Exception as e:
        logger.error(f"Error starting background replacement: {e}")
        return JSONResponse(
            content={"success": False, "error": f"Failed to start background replacement: {str(e)}"},
            status_code=500
        )


async def process_video_background(
    video_id: int, 
    video_path: str, 
    background_path: str, 
    output_path: str, 
    quality: str,
    user_id: int,
    background_id: int
):
    """
    Process video with background replacement as async task
    FIXED: NO MORE DUPLICATE SAVE - let video_processing_routes.py handle saving
    """
    temp_files_to_cleanup = []
    
    try:
        logger.info(f"Starting background replacement for video {video_id}")
        
        # Add paths to cleanup list
        temp_files_to_cleanup.append(video_path)
        temp_files_to_cleanup.append(output_path)
        
        # Initialize components
        video_processor = VideoProcessor({"temp_dir": TEMP_DIR})
        
        # Initialize BackgroundFX client
        background_client = BackgroundFXClient()
        
        # Check if service is available
        try:
            connection_status = background_client.check_connection()
            if connection_status.get('status') != 'ok':
                logger.error(f"BackgroundFX service is not healthy: {connection_status}")
                execute_query(
                    "UPDATE videos SET status = 'error', error_message = 'Background service unavailable' WHERE id = %s",
                    (video_id,)
                )
                return
        except Exception as e:
            logger.error(f"BackgroundFX connection check failed: {e}")
            execute_query(
                "UPDATE videos SET status = 'error', error_message = 'Background service connection failed' WHERE id = %s",
                (video_id,)
            )
            return
        
        # Load video
        capture, width, height, fps, frame_count = video_processor.load_video(video_path)
        
        # Process frames
        processed_frames = []
        frame_idx = 0
        
        while capture.isOpened():
            ret, frame = capture.read()
            if not ret:
                break
            
            # Replace background in this frame using the client
            try:
                processed_frame, _ = background_client.replace_background(
                    image=frame,
                    background_image=background_path,
                    quality=quality
                )
                processed_frames.append(processed_frame)
            except Exception as e:
                logger.error(f"Error processing frame {frame_idx}: {e}")
                # Use original frame if processing fails
                processed_frames.append(frame)
            
            # Log progress
            frame_idx += 1
            if frame_idx % 30 == 0 or frame_idx == frame_count:
                logger.info(f"Video {video_id}: Processed {frame_idx}/{frame_count} frames")
        
        # Release resources
        capture.release()
        
        # Save the processed video with audio from the original
        output_file = video_processor.save_video(
            processed_frames, output_path, width, height, fps, input_video_path=video_path
        )
        
        logger.info(f"Video processing completed: {output_path}")
        
        # FIXED: Upload processed video to Cloudinary
        cloudinary_url = upload_video_to_cloudinary(output_path, video_id)
        
        if cloudinary_url:
            logger.info(f"🎬 Video uploaded to Cloudinary successfully: {cloudinary_url}")
            
            # REMOVED: No longer saving to Recent Videos here!
            # This is now handled by video_processing_routes.py to avoid duplicates
            logger.info(f"✅ Background processing completed - video_processing_routes.py will handle saving")
            
            # Update original video status only
            execute_query(
                """UPDATE videos 
                   SET video_path = %s, status = 'completed', background_type = 'processed'
                   WHERE id = %s""",
                (cloudinary_url, video_id)
            )
            logger.info(f"✅ Updated original video record with Cloudinary URL")
            
        else:
            logger.error(f"❌ Failed to upload to Cloudinary")
            execute_query(
                """UPDATE videos 
                   SET status = 'error', error_message = 'Failed to upload processed video'
                   WHERE id = %s""",
                (video_id,)
            )
        
        logger.info(f"Background replacement completed for video {video_id}")
        
    except Exception as e:
        logger.error(f"Error processing video background: {e}")
        # Update status to error
        execute_query(
            "UPDATE videos SET status = 'error', error_message = %s WHERE id = %s",
            (str(e), video_id)
        )
    finally:
        # Cleanup temporary files
        for temp_file in temp_files_to_cleanup:
            if temp_file and os.path.exists(temp_file) and temp_file.startswith('/tmp'):
                try:
                    os.remove(temp_file)
                    logger.info(f"Cleaned up temporary file: {temp_file}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup {temp_file}: {cleanup_error}")


# Import needed in function above but need to avoid circular imports
import cv2
