# app/routes/backgroundfx_save.py - Simple Save-to-Library Endpoint
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import logging
from datetime import datetime
import uuid
import requests
from pathlib import Path
import os

# Configure logging
logger = logging.getLogger("BackgroundFX-Save")

# Initialize router
router = APIRouter()

# Database connection
from app.db.database import execute_query

# Dependency to get current user
async def get_current_user(request: Request):
    """Get current user from session - simplified version to prevent 500 errors"""
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
                        # Return a simple user object
                        return {"id": user_id, "authenticated": True}
            except (ImportError, Exception) as e:
                logger.warning(f"Auth service error: {e}")
        
        # Fallback: try to get user from session
        session_user_id = request.session.get("user_id") if hasattr(request, 'session') else None
        if session_user_id:
            return {"id": session_user_id, "authenticated": True}
        
        # Final fallback: check for any user indicator in cookies
        user_cookie = request.cookies.get("user_id")
        if user_cookie:
            return {"id": user_cookie, "authenticated": True}
            
        return None
        
    except Exception as e:
        logger.error(f"❌ Authentication error: {e}")
        return None

@router.post("/api/backgroundfx/save-video")
async def save_processed_video_to_library(request: Request):
    """
    Enhanced endpoint to save processed video to user's My Videos
    Supports both URL and base64 data:
    - URL payload: {"video_url": "https://...", "filename": "optional_name.mp4"}
    - Base64 payload: {"video_data": "base64_string", "filename": "optional_name.mp4"}
    """
    # Get current user
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid user")
    
    try:
        # Get request data
        data = await request.json()
        video_url = data.get("video_url")
        video_data = data.get("video_data")  # Base64 encoded video
        filename = data.get("filename")
        
        if not video_url and not video_data:
            raise HTTPException(status_code=400, detail="Either video_url or video_data is required")
        
        logger.info(f"🎬 Saving processed video for user {user_id}: {video_url or 'base64_data'}")
        
        # Generate filename if not provided
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"backgroundfx_processed_{timestamp}.mp4"
        
        # Ensure .mp4 extension
        if not filename.lower().endswith('.mp4'):
            filename += '.mp4'
        
        # Create user video directory
        video_dir = Path("user_uploads/videos") / str(user_id)
        video_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename to avoid conflicts
        unique_filename = f"{uuid.uuid4()}_{filename}"
        file_path = video_dir / unique_filename
        
        # Handle video data (URL or base64)
        if video_data:
            # Handle base64 encoded video data (from HF Space)
            logger.info(f"💾 Saving base64 video data ({len(video_data)} chars)")
            import base64
            try:
                # Decode base64 data
                video_bytes = base64.b64decode(video_data)
                
                # Write directly to file
                with open(file_path, 'wb') as f:
                    f.write(video_bytes)
                    
                logger.info(f"✅ Base64 video saved: {len(video_bytes):,} bytes")
                
            except Exception as decode_error:
                logger.error(f"❌ Base64 decode error: {decode_error}")
                raise HTTPException(status_code=400, detail=f"Invalid base64 video data: {decode_error}")
                
        elif video_url:
            # Handle video URL (download from URL)
            logger.info(f"📥 Downloading video from: {video_url}")
            response = requests.get(video_url, stream=True, timeout=60)
            response.raise_for_status()
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        
        # Get file size
        file_size = file_path.stat().st_size
        logger.info(f"✅ Downloaded {file_size:,} bytes")
        
        # Save to database (same table as HeyGen videos)
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
            video_id = result['id']
            logger.info(f"✅ Saved to My Videos with ID: {video_id}")
            
            return JSONResponse({
                "success": True,
                "message": "Video saved to My Videos!",
                "video_id": video_id,
                "filename": filename,
                "file_size": file_size
            })
        else:
            raise Exception("Failed to save video metadata to database")
            
    except requests.RequestException as e:
        logger.error(f"❌ Download error: {e}")
        # Clean up partial file
        if 'file_path' in locals() and file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=400, detail=f"Failed to download video: {str(e)}")
        
    except Exception as e:
        logger.error(f"❌ Save error: {e}")
        # Clean up partial file
        if 'file_path' in locals() and file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Failed to save video: {str(e)}")

@router.get("/api/backgroundfx/save-status")
async def get_save_status(request: Request):
    """Check if save functionality is available"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    return JSONResponse({
        "save_available": True,
        "message": "Ready to save processed videos to My Videos",
        "endpoint": "/api/backgroundfx/save-video"
    })

# Startup logging
logger.info("💾 BackgroundFX save-to-library endpoint ready")
