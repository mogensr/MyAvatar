# app/routes/backgroundfx_webhook.py - Auto-Save BackgroundFX Videos Like HeyGen
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import logging
from datetime import datetime
import uuid
import aiohttp
import aiofiles
from pathlib import Path
import tempfile
import os

# Configure logging
logger = logging.getLogger("BackgroundFX-Webhook")

# Initialize router
router = APIRouter()

# Database connection
from app.db.database import execute_query

@router.post("/api/backgroundfx/process-complete")
async def backgroundfx_process_complete(request: Request):
    """
    Webhook-style endpoint for BackgroundFX processing completion
    Mirrors HeyGen webhook pattern for automatic video saving
    """
    try:
        # Get the completion payload
        payload = await request.json()
        logger.info(f"📥 BackgroundFX completion webhook: {payload}")
        
        # Extract completion information
        job_id = payload.get("job_id")
        video_url = payload.get("video_url")
        user_id = payload.get("user_id")
        original_video_name = payload.get("original_video_name", "processed_video")
        background_image_url = payload.get("background_image_url")
        
        if not job_id or not video_url or not user_id:
            logger.error("❌ Missing required fields in completion payload")
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Missing required fields"}
            )
        
        logger.info(f"🎬 Processing completion for job {job_id}, user {user_id}")
        
        # Generate filename for processed video
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        processed_filename = f"backgroundfx_{timestamp}_{original_video_name}"
        if not processed_filename.endswith('.mp4'):
            processed_filename += '.mp4'
        
        # Download and save processed video to user's library
        video_file_id = await download_and_save_video(
            video_url, 
            processed_filename, 
            user_id
        )
        
        # Also save background image if provided
        background_file_id = None
        if background_image_url:
            background_filename = f"background_{timestamp}.jpg"
            background_file_id = await download_and_save_image(
                background_image_url,
                background_filename,
                user_id
            )
        
        # Record the processing job completion
        execute_query(
            """
            INSERT INTO backgroundfx_jobs (
                job_id, user_id, status, processed_video_id, background_image_id, 
                original_video_name, processed_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (job_id) DO UPDATE SET
                status = EXCLUDED.status,
                processed_video_id = EXCLUDED.processed_video_id,
                background_image_id = EXCLUDED.background_image_id,
                processed_at = EXCLUDED.processed_at
            """,
            (job_id, user_id, "completed", video_file_id, background_file_id, 
             original_video_name, datetime.now())
        )
        
        logger.info(f"✅ BackgroundFX auto-save complete - Video: {video_file_id}, Background: {background_file_id}")
        
        return JSONResponse(
            content={
                "success": True, 
                "message": "Video automatically saved to My Videos",
                "video_file_id": video_file_id,
                "background_file_id": background_file_id
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error processing BackgroundFX completion: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

async def download_and_save_video(video_url: str, filename: str, user_id: int) -> int:
    """Download video from URL and save to user's video library"""
    try:
        # Create user video directory
        video_dir = Path("user_uploads/videos") / str(user_id)
        video_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        unique_filename = f"{uuid.uuid4()}_{filename}"
        file_path = video_dir / unique_filename
        
        # Download video
        async with aiohttp.ClientSession() as session:
            async with session.get(video_url) as response:
                if response.status == 200:
                    async with aiofiles.open(file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)
                else:
                    raise Exception(f"Failed to download video: HTTP {response.status}")
        
        # Get file size
        file_size = file_path.stat().st_size
        
        # Save to database (same pattern as HeyGen videos)
        result = execute_query(
            """
            INSERT INTO videos (user_id, title, video_path, status, file_size, created_at, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (user_id, filename, str(file_path), "completed", file_size, datetime.now(), "backgroundfx"),
            fetch_one=True
        )
        
        if result:
            logger.info(f"✅ Video saved to videos table: {filename} (ID: {result['id']})")
            return result['id']
        else:
            raise Exception("Failed to save video metadata to database")
            
    except Exception as e:
        logger.error(f"❌ Error downloading/saving video: {e}")
        raise

async def download_and_save_image(image_url: str, filename: str, user_id: int) -> int:
    """Download image from URL and save to user's image library"""
    try:
        # Create user image directory
        image_dir = Path("user_uploads/images") / str(user_id)
        image_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        unique_filename = f"{uuid.uuid4()}_{filename}"
        file_path = image_dir / unique_filename
        
        # Download image
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status == 200:
                    async with aiofiles.open(file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)
                else:
                    raise Exception(f"Failed to download image: HTTP {response.status}")
        
        # Get file size
        file_size = file_path.stat().st_size
        
        # Save to user_files table (for images)
        result = execute_query(
            """
            INSERT INTO user_files (user_id, filename, file_type, file_path, file_size, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (user_id, filename, "image", str(file_path), file_size, datetime.now()),
            fetch_one=True
        )
        
        if result:
            logger.info(f"✅ Image saved to user_files table: {filename} (ID: {result['id']})")
            return result['id']
        else:
            raise Exception("Failed to save image metadata to database")
            
    except Exception as e:
        logger.error(f"❌ Error downloading/saving image: {e}")
        raise

@router.post("/api/backgroundfx/trigger-auto-save")
async def trigger_auto_save(request: Request):
    """
    Manual trigger for auto-save when HF Space processing completes
    This can be called from frontend JavaScript when processing is detected as complete
    """
    try:
        payload = await request.json()
        user_id = payload.get("user_id")
        
        if not user_id:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "User ID required"}
            )
        
        # Try to detect completed processing in HF Space
        # This is a fallback method when direct webhook isn't available
        
        # For now, return success and let frontend handle the detection
        return JSONResponse(
            content={
                "success": True,
                "message": "Auto-save monitoring enabled",
                "instructions": "Frontend will monitor for completion and trigger save"
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error in trigger auto-save: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# Database schema for tracking BackgroundFX jobs (to be added to migration)
BACKGROUNDFX_JOBS_SCHEMA = """
CREATE TABLE IF NOT EXISTS backgroundfx_jobs (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(255) UNIQUE NOT NULL,
    user_id INTEGER NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'processing',
    processed_video_id INTEGER,
    background_image_id INTEGER,
    original_video_name VARCHAR(255),
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (processed_video_id) REFERENCES videos(id),
    FOREIGN KEY (background_image_id) REFERENCES user_files(id)
);
"""

logger.info("🤖 BackgroundFX webhook system initialized - Auto-save ready!")
