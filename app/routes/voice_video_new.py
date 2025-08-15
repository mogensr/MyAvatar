"""
Clean Voice-to-Video API - Built from scratch
No legacy code, no placeholders, just working functionality
"""
from fastapi import APIRouter, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
import tempfile
import os
from ..core.auth import get_current_user_fixed
from ..core.database import execute_query
from ..services.video_service import VideoService
from ..utils.logging_utils import log_error, log_info

router = APIRouter()

@router.post("/api/voice-video/create")
async def create_voice_video_clean(
    request: Request,
    audio: UploadFile = File(...),
    avatar_id: str = Form(...),
    title: str = Form(default=""),
    format: str = Form(default="16:9")
):
    """
    Clean voice-to-video creation endpoint
    Built from scratch with no legacy issues
    """
    try:
        # Authentication
        user = get_current_user_fixed(request)
        if not user:
            return JSONResponse({
                "success": False,
                "error": "Authentication required"
            }, status_code=401)
        
        user_id = user["id"]
        log_info(f"Voice video creation started for user {user_id}")
        
        # Validation
        if not avatar_id:
            return JSONResponse({
                "success": False,
                "error": "Avatar selection required"
            }, status_code=400)
        
        if not audio:
            return JSONResponse({
                "success": False,
                "error": "Audio recording required"
            }, status_code=400)
        
        # Set default title
        if not title.strip():
            title = f"Voice Video - {user.get('username', 'User')}"
        
        # Validate audio file
        if audio.size > 50 * 1024 * 1024:  # 50MB limit
            return JSONResponse({
                "success": False,
                "error": "Audio file too large (max 50MB)"
            }, status_code=400)
        
        # Save audio temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
            content = await audio.read()
            temp_file.write(content)
            temp_audio_path = temp_file.name
        
        try:
            # Create video using VideoService
            video_service = VideoService()
            result = await video_service.create_voice_video(
                user_id=user_id,
                avatar_id=avatar_id,
                audio_file_path=temp_audio_path,
                title=title,
                format=format
            )
            
            if result.get("success"):
                log_info(f"Voice video created successfully: {result.get('video_id')}")
                return JSONResponse({
                    "success": True,
                    "video_id": result.get("video_id"),
                    "title": title,
                    "status": result.get("status", "processing"),
                    "message": "Voice video created successfully! Check My Videos for progress."
                })
            else:
                error_msg = result.get("error", "Unknown error occurred")
                log_error(f"Voice video creation failed: {error_msg}")
                return JSONResponse({
                    "success": False,
                    "error": error_msg
                }, status_code=500)
                
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_audio_path)
            except:
                pass
        
    except Exception as e:
        log_error(f"Voice video creation error: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": f"Server error: {str(e)}"
        }, status_code=500)

@router.get("/api/voice-video/status/{video_id}")
async def get_voice_video_status(video_id: int, request: Request):
    """Get status of voice video creation"""
    try:
        user = get_current_user_fixed(request)
        if not user:
            return JSONResponse({"error": "Authentication required"}, status_code=401)
        
        # Get video status from database
        video = execute_query(
            "SELECT id, title, status, video_path, error_message FROM videos WHERE id = %s AND user_id = %s",
            (video_id, user["id"]),
            fetch_one=True
        )
        
        if not video:
            return JSONResponse({"error": "Video not found"}, status_code=404)
        
        return JSONResponse({
            "video_id": video["id"],
            "title": video["title"],
            "status": video["status"],
            "video_url": video.get("video_path"),
            "error": video.get("error_message")
        })
        
    except Exception as e:
        log_error(f"Error getting video status: {str(e)}")
        return JSONResponse({"error": "Server error"}, status_code=500)
