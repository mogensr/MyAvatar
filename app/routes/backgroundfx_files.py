# app/routes/backgroundfx_files.py - USER FILE MANAGEMENT FOR BACKGROUNDFX
import logging
import os
import uuid
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Request, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.security import HTTPBearer
import aiofiles
import shutil
from PIL import Image
import cv2

# Configure logging
logger = logging.getLogger("BackgroundFX-Files")

# Initialize router
router = APIRouter()

# File storage configuration
UPLOAD_DIR = Path("user_uploads")
VIDEO_DIR = UPLOAD_DIR / "videos"
IMAGE_DIR = UPLOAD_DIR / "images"

# Create directories if they don't exist
for directory in [UPLOAD_DIR, VIDEO_DIR, IMAGE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Supported file formats
SUPPORTED_VIDEO_FORMATS = {'.mp4', '.avi', '.mov', '.webm', '.mkv'}
SUPPORTED_IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

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

def get_user_file_path(user_id: int, file_type: str, filename: str) -> Path:
    """Get user-specific file path"""
    base_dir = VIDEO_DIR if file_type == "video" else IMAGE_DIR
    user_dir = base_dir / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / filename

def validate_file_format(filename: str, file_type: str) -> bool:
    """Validate file format"""
    file_ext = Path(filename).suffix.lower()
    if file_type == "video":
        return file_ext in SUPPORTED_VIDEO_FORMATS
    elif file_type == "image":
        return file_ext in SUPPORTED_IMAGE_FORMATS
    return False

async def save_file_metadata(user_id: int, filename: str, file_type: str, file_path: str, file_size: int):
    """Save file metadata to database"""
    try:
        from app.db.database import execute_query
        
        query = """
        INSERT INTO user_files (user_id, filename, file_type, file_path, file_size, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """
        
        result = execute_query(
            query, 
            (user_id, filename, file_type, file_path, file_size, datetime.now()),
            fetch_one=True
        )
        
        return result['id'] if result else None
        
    except Exception as e:
        logger.error(f"Error saving file metadata: {e}")
        return None

@router.post("/api/backgroundfx/upload-video")
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    current_user = Depends(get_current_user)
):
    """Upload a video file for BackgroundFX"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    user_id = current_user.get("id") if isinstance(current_user, dict) else getattr(current_user, "id", None)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid user")
    
    try:
        # Validate file format
        if not validate_file_format(file.filename, "video"):
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported video format. Supported formats: {', '.join(SUPPORTED_VIDEO_FORMATS)}"
            )
        
        # Check file size
        if file.size and file.size > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File too large. Maximum size: 100MB")
        
        # Generate unique filename
        file_ext = Path(file.filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = get_user_file_path(user_id, "video", unique_filename)
        
        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Get video metadata
        try:
            cap = cv2.VideoCapture(str(file_path))
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = frame_count / fps if fps > 0 else 0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
        except Exception as e:
            logger.warning(f"Could not extract video metadata: {e}")
            duration, width, height = 0, 0, 0
        
        # Save metadata to database
        file_id = await save_file_metadata(
            user_id, 
            file.filename, 
            "video", 
            str(file_path), 
            len(content)
        )
        
        logger.info(f"✅ Video uploaded successfully for user {user_id}: {file.filename}")
        
        return JSONResponse({
            "success": True,
            "message": "Video uploaded successfully",
            "file_id": file_id,
            "filename": file.filename,
            "unique_filename": unique_filename,
            "file_size": len(content),
            "duration": duration,
            "resolution": f"{width}x{height}",
            "file_path": f"/api/backgroundfx/user-files/video/{unique_filename}"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error uploading video: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/api/backgroundfx/upload-image")
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    current_user = Depends(get_current_user)
):
    """Upload an image file for BackgroundFX backgrounds"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    user_id = current_user.get("id") if isinstance(current_user, dict) else getattr(current_user, "id", None)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid user")
    
    try:
        # Validate file format
        if not validate_file_format(file.filename, "image"):
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported image format. Supported formats: {', '.join(SUPPORTED_IMAGE_FORMATS)}"
            )
        
        # Check file size
        if file.size and file.size > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File too large. Maximum size: 100MB")
        
        # Generate unique filename
        file_ext = Path(file.filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = get_user_file_path(user_id, "image", unique_filename)
        
        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Get image metadata
        try:
            with Image.open(file_path) as img:
                width, height = img.size
                format_name = img.format
        except Exception as e:
            logger.warning(f"Could not extract image metadata: {e}")
            width, height, format_name = 0, 0, "Unknown"
        
        # Save metadata to database
        file_id = await save_file_metadata(
            user_id, 
            file.filename, 
            "image", 
            str(file_path), 
            len(content)
        )
        
        logger.info(f"✅ Image uploaded successfully for user {user_id}: {file.filename}")
        
        return JSONResponse({
            "success": True,
            "message": "Image uploaded successfully",
            "file_id": file_id,
            "filename": file.filename,
            "unique_filename": unique_filename,
            "file_size": len(content),
            "resolution": f"{width}x{height}",
            "format": format_name,
            "file_path": f"/api/backgroundfx/user-files/image/{unique_filename}"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error uploading image: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("/api/backgroundfx/my-videos")
async def get_my_videos(request: Request, current_user = Depends(get_current_user)):
    """Get user's uploaded videos"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    user_id = current_user.get("id") if isinstance(current_user, dict) else getattr(current_user, "id", None)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid user")
    
    try:
        from app.db.database import execute_query
        
        # Get user's videos from database (use existing videos table)
        query = """
        SELECT id, title as filename, created_at, video_path as file_path
        FROM videos 
        WHERE user_id = %s AND status = 'completed' AND video_path IS NOT NULL
        ORDER BY created_at DESC
        """
        
        videos = execute_query(query, (user_id,), fetch_all=True)
        
        video_list = []
        for video in videos:
            # Extract unique filename from path
            unique_filename = Path(video['file_path']).name
            video_list.append({
                "id": video['id'],
                "filename": video['filename'],
                "unique_filename": unique_filename,
                "file_size": video['file_size'],
                "created_at": video['created_at'].isoformat() if video['created_at'] else None,
                "file_path": f"/api/backgroundfx/user-files/video/{unique_filename}"
            })
        
        return JSONResponse({
            "success": True,
            "videos": video_list,
            "total": len(video_list)
        })
        
    except Exception as e:
        logger.error(f"❌ Error getting user videos: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get videos: {str(e)}")

@router.get("/api/backgroundfx/my-images")
async def get_my_images(request: Request, current_user = Depends(get_current_user)):
    """Get user's uploaded images"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    user_id = current_user.get("id") if isinstance(current_user, dict) else getattr(current_user, "id", None)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid user")
    
    try:
        from app.db.database import execute_query
        
        # Get user's images from database (temporary fix - return empty for now)
        # TODO: Implement proper image storage or use existing table
        query = """
        SELECT id, title as filename, created_at, thumbnail_url as file_path
        FROM videos 
        WHERE user_id = %s AND thumbnail_url IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 0
        """
        
        result = execute_query(query, (user_id,), fetch_all=True)
        images = [{"id": row[0], "filename": row[1], "file_size": "Unknown", "created_at": row[2].isoformat() if row[2] else None, "file_path": row[3]} for row in result]
        
        image_list = []
        for image in images:
            # Extract unique filename from path
            unique_filename = Path(image['file_path']).name
            image_list.append({
                "id": image['id'],
                "filename": image['filename'],
                "unique_filename": unique_filename,
                "file_size": image['file_size'],
                "created_at": image['created_at'].isoformat() if image['created_at'] else None,
                "file_path": f"/api/backgroundfx/user-files/image/{unique_filename}",
                "thumbnail_path": f"/api/backgroundfx/user-files/image/{unique_filename}?thumbnail=true"
            })
        
        return JSONResponse({
            "success": True,
            "images": image_list,
            "total": len(image_list)
        })
        
    except Exception as e:
        logger.error(f"❌ Error getting user images: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get images: {str(e)}")

@router.get("/api/backgroundfx/user-files/{file_type}/{filename}")
async def serve_user_file(
    request: Request,
    file_type: str,
    filename: str,
    thumbnail: bool = False,
    current_user = Depends(get_current_user)
):
    """Serve user-specific files with security"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    user_id = current_user.get("id") if isinstance(current_user, dict) else getattr(current_user, "id", None)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid user")
    
    if file_type not in ["video", "image"]:
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    try:
        # Get file path
        file_path = get_user_file_path(user_id, file_type, filename)
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        # For image thumbnails, create a smaller version
        if thumbnail and file_type == "image":
            thumbnail_path = file_path.parent / f"thumb_{filename}"
            
            if not thumbnail_path.exists():
                try:
                    with Image.open(file_path) as img:
                        img.thumbnail((200, 200), Image.Resampling.LANCZOS)
                        img.save(thumbnail_path, optimize=True, quality=85)
                except Exception as e:
                    logger.warning(f"Could not create thumbnail: {e}")
                    # Fall back to original file
                    thumbnail_path = file_path
            
            return FileResponse(thumbnail_path)
        
        return FileResponse(file_path)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error serving file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to serve file: {str(e)}")

@router.delete("/api/backgroundfx/delete-file/{file_id}")
async def delete_user_file(
    request: Request,
    file_id: int,
    current_user = Depends(get_current_user)
):
    """Delete a user's file"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    user_id = current_user.get("id") if isinstance(current_user, dict) else getattr(current_user, "id", None)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid user")
    
    try:
        from app.db.database import execute_query
        
        # Get file info and verify ownership
        query = """
        SELECT file_path, filename, file_type
        FROM user_files 
        WHERE id = %s AND user_id = %s
        """
        
        file_info = execute_query(query, (file_id, user_id), fetch_one=True)
        
        if not file_info:
            raise HTTPException(status_code=404, detail="File not found or access denied")
        
        # Delete physical file
        file_path = Path(file_info['file_path'])
        if file_path.exists():
            file_path.unlink()
            
            # Also delete thumbnail if it exists
            if file_info['file_type'] == 'image':
                thumbnail_path = file_path.parent / f"thumb_{file_path.name}"
                if thumbnail_path.exists():
                    thumbnail_path.unlink()
        
        # Delete database record
        delete_query = "DELETE FROM user_files WHERE id = %s AND user_id = %s"
        execute_query(delete_query, (file_id, user_id))
        
        logger.info(f"✅ File deleted successfully: {file_info['filename']}")
        
        return JSONResponse({
            "success": True,
            "message": f"File '{file_info['filename']}' deleted successfully"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")

# Startup logging
logger.info("🗂️ BackgroundFX file management router initialized")
logger.info(f"📁 Upload directory: {UPLOAD_DIR}")
logger.info("✅ BackgroundFX file management ready")
