"""
API routes for background replacement functionality in MyAvatar videos
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
        video_file = video.get("file_path") or f"{VIDEOS_DIR}/video_{video_id}.mp4"
        bg_file = background.get("file_path")
        
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
        output_path = os.path.join(VIDEOS_DIR, output_filename)
        
        # Start background task for processing
        # This would be better with a proper task queue, but for simplicity we'll use asyncio
        task = asyncio.create_task(
            process_video_background(video_id, video_file, bg_file, output_path, quality)
        )
        
        # Update video record with pending background change
        execute_query(
            "UPDATE videos SET background_id = %s, status = 'processing_background' WHERE id = %s",
            (background_id, video_id)
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
    quality: str
):
    """
    Process video with background replacement as async task
    """
    try:
        logger.info(f"Starting background replacement for video {video_id}")
        
        # Initialize components
        video_processor = VideoProcessor({"temp_dir": TEMP_DIR})
        
        # Initialize BackgroundFX client instead of local replacer
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
            if frame_idx % 10 == 0 or frame_idx == frame_count:
                logger.info(f"Video {video_id}: Processed {frame_idx}/{frame_count} frames")
        
        # Release resources
        capture.release()
        
        # Save the processed video with audio from the original
        output_file = video_processor.save_video(
            processed_frames, output_path, width, height, fps, input_video_path=video_path
        )
        
        # Update database
        execute_query(
            """
            UPDATE videos 
            SET file_path = %s, background_id = %s, status = 'completed' 
            WHERE id = %s
            """,
            (output_path, background_id, video_id)
        )
        
        logger.info(f"Background replacement complete for video {video_id}")
        
    except Exception as e:
        logger.error(f"Error processing video background: {e}")
        # Update status to error
        execute_query(
            "UPDATE videos SET status = 'error' WHERE id = %s",
            (video_id,)
        )


# Import needed in function above but need to avoid circular imports
import cv2