# app/routes/backgroundfx_automation.py - AUTOMATED SAVE-TO-LIBRARY INTEGRATION
import logging
import os
import uuid
import aiohttp
import aiofiles
from pathlib import Path
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
import tempfile
import shutil

# Configure logging
logger = logging.getLogger("BackgroundFX-Automation")

# Initialize router
router = APIRouter()

# File storage configuration
UPLOAD_DIR = Path("user_uploads")
VIDEO_DIR = UPLOAD_DIR / "videos"
IMAGE_DIR = UPLOAD_DIR / "images"

# Ensure directories exist
for directory in [UPLOAD_DIR, VIDEO_DIR, IMAGE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Dependency to get current user
async def get_current_user(request: Request):
    """Get current user from session"""
    try:
        # Try cookie-based auth first
        token = request.cookies.get("access_token")
        if token:
            try:
                from app.services.auth_service import auth_service
                payload = auth_service.validate_token(token)
                if payload:
                    user_id = payload.get("user_id")
                    if user_id:
                        from app.db.user_manager import Database
                        db = Database()
                        user = db.get_user_by_id(user_id)
                        if user:
                            return user
            except ImportError:
                pass
        
        # Fallback to session
        if hasattr(request, 'session') and request.session:
            user_data = request.session.get("user", {})
            if isinstance(user_data, dict) and user_data.get("id"):
                return user_data
                
    except Exception as e:
        logger.warning(f"Error getting current user: {e}")
    
    return None

async def save_file_to_library(user_id: int, file_url: str, filename: str, file_type: str) -> Optional[int]:
    """Download and save file to user's library"""
    try:
        # Generate unique filename
        file_ext = Path(filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        
        # Determine save path
        if file_type == "video":
            save_path = VIDEO_DIR / str(user_id) / unique_filename
        else:
            save_path = IMAGE_DIR / str(user_id) / unique_filename
        
        # Create user directory
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Download file
        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as response:
                if response.status == 200:
                    async with aiofiles.open(save_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)
                else:
                    logger.error(f"Failed to download file: {response.status}")
                    return None
        
        # Get file size
        file_size = save_path.stat().st_size
        
        # Save metadata to database
        from app.db.database import execute_query
        
        query = """
        INSERT INTO user_files (user_id, filename, file_type, file_path, file_size, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """
        
        result = execute_query(
            query, 
            (user_id, filename, file_type, str(save_path), file_size, datetime.now()),
            fetch_one=True
        )
        
        if result:
            logger.info(f"✅ File saved to library: {filename} (ID: {result['id']})")
            return result['id']
        else:
            logger.error(f"❌ Failed to save file metadata: {filename}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error saving file to library: {e}")
        return None

@router.post("/api/backgroundfx/auto-save-background")
async def auto_save_background_image(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
):
    """Auto-save background image when uploaded to HF Space"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    user_id = current_user.get("id") if isinstance(current_user, dict) else getattr(current_user, "id", None)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid user")
    
    try:
        # Get request data
        data = await request.json()
        image_url = data.get("image_url")
        filename = data.get("filename", f"background_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
        
        if not image_url:
            raise HTTPException(status_code=400, detail="Image URL required")
        
        # Save to library in background
        background_tasks.add_task(
            save_file_to_library,
            user_id,
            image_url,
            filename,
            "image"
        )
        
        logger.info(f"🖼️ Auto-saving background image for user {user_id}: {filename}")
        
        return JSONResponse({
            "success": True,
            "message": "Background image will be saved to My Images",
            "filename": filename
        })
        
    except Exception as e:
        logger.error(f"❌ Error auto-saving background: {e}")
        raise HTTPException(status_code=500, detail=f"Auto-save failed: {str(e)}")

@router.post("/api/backgroundfx/auto-save-processed-video")
async def auto_save_processed_video(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
):
    """Auto-save processed video when HF Space processing completes"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    user_id = current_user.get("id") if isinstance(current_user, dict) else getattr(current_user, "id", None)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid user")
    
    try:
        # Get request data
        data = await request.json()
        video_url = data.get("video_url")
        filename = data.get("filename", f"processed_video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
        
        if not video_url:
            raise HTTPException(status_code=400, detail="Video URL required")
        
        # Save to library in background
        background_tasks.add_task(
            save_file_to_library,
            user_id,
            video_url,
            filename,
            "video"
        )
        
        logger.info(f"🎬 Auto-saving processed video for user {user_id}: {filename}")
        
        return JSONResponse({
            "success": True,
            "message": "Processed video will be saved to My Videos",
            "filename": filename
        })
        
    except Exception as e:
        logger.error(f"❌ Error auto-saving processed video: {e}")
        raise HTTPException(status_code=500, detail=f"Auto-save failed: {str(e)}")

@router.get("/api/backgroundfx/automation-status")
async def automation_status(current_user = Depends(get_current_user)):
    """Check automation system status"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    return JSONResponse({
        "automation_enabled": True,
        "features": {
            "auto_save_backgrounds": True,
            "auto_save_processed_videos": True,
            "seamless_workflow": True
        },
        "storage_info": {
            "video_dir": str(VIDEO_DIR),
            "image_dir": str(IMAGE_DIR),
            "user_specific": True
        },
        "message": "Automation system ready - files will be auto-saved to your library"
    })

# Startup logging
logger.info("🤖 BackgroundFX automation system initialized")
logger.info("✅ Auto-save to library enabled")
logger.info("🎬 Seamless workflow ready")
