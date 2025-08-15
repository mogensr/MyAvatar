"""
Updated video routes with proper download functionality + missing template routes
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pathlib import Path
from ..services.video_service import VideoService
from ..auth.authentication import get_current_user
from ..logger.log_handler import log_info, log_error
from ..db.database import execute_query
import requests
import os

# Define templates
templates_path = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_path))

router = APIRouter(tags=["videos"])

# =============================================================================
# MISSING TEMPLATE ROUTES - ADD THESE TO FIX /voice-recording and /text-to-video
# =============================================================================

@router.get("/voice-recording")
async def voice_recording_page(request: Request):
    """Serve the voice recording page"""
    try:
        user = get_current_user(request)
        if not user:
            return RedirectResponse(url="/login", status_code=303)
        
        # Get available avatars for the user
        avatars = execute_query(
            "SELECT * FROM user_avatars WHERE user_id = ? ORDER BY avatar_name",
            (int(user["id"]),),
            fetch_all=True
        )
        
        return templates.TemplateResponse(
            "voice_recording.html",
            {
                "request": request,
                "user": user,
                "username": user.get("username", "User"),
                "avatars": avatars
            }
        )
    except Exception as e:
        log_error(f"Error serving voice recording page: {str(e)}", "VideoRoutes")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/text-to-video")
async def text_to_video_page(request: Request):
    """Serve the text-to-video page"""
    try:
        user = get_current_user(request)
        if not user:
            return RedirectResponse(url="/login", status_code=303)
        
        # Get available avatars for the user
        avatars = execute_query(
            "SELECT * FROM user_avatars WHERE user_id = ? ORDER BY avatar_name",
            (int(user["id"]),),
            fetch_all=True
        )
        
        return templates.TemplateResponse(
            "text_video_component.html",
            {
                "request": request,
                "user": user,
                "username": user.get("username", "User"),
                "avatars": avatars
            }
        )
    except Exception as e:
        log_error(f"Error serving text-to-video page: {str(e)}", "VideoRoutes")
        raise HTTPException(status_code=500, detail="Internal server error")

# =============================================================================
# EXISTING VIDEO ROUTES (keep these as they are)
# =============================================================================

@router.get("/videos/{video_id}/download")
async def download_video(request: Request, video_id: str):
    """
    Download video with proper headers for direct download
    """
    try:
        user = get_current_user(request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        video_service = VideoService()
        
        # Get video from database
        video = video_service.get_video_by_id(video_id, int(user["id"]))
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Get fresh video URL (handles expiry automatically)
        fresh_url = video_service.get_fresh_video_url(video, user)
        if not fresh_url:
            raise HTTPException(status_code=404, detail="Video URL not available")
        
        log_info(f"User {user['username']} downloading video {video_id}", "VideoDownload")
        
        # Check if request wants direct download (from download button)
        user_agent = request.headers.get("user-agent", "")
        is_download_request = "download" in request.url.query.lower() or request.headers.get("sec-fetch-dest") == "document"
        
        if is_download_request:
            # For download button: stream the video content with download headers
            try:
                # Get video content
                response = requests.get(fresh_url, stream=True, timeout=30)
                response.raise_for_status()
                
                # Determine filename
                video_title = video.get("title", "video").replace(" ", "_")
                filename = f"{video_title}.mp4"
                
                # Return video content with download headers
                headers = {
                    "Content-Disposition": f"attachment; filename=\"{filename}\"",
                    "Content-Type": "video/mp4",
                    "Content-Length": response.headers.get("content-length", "")
                }
                
                return Response(
                    content=response.content,
                    headers=headers,
                    media_type="video/mp4"
                )
                
            except Exception as e:
                log_error(f"Error streaming video for download: {str(e)}", "VideoDownload")
                # Fallback to redirect if streaming fails
                return RedirectResponse(url=fresh_url, status_code=302)
        else:
            # For play button: redirect to video URL
            return RedirectResponse(url=fresh_url, status_code=302)
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error in video download endpoint: {str(e)}", "VideoDownload")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/videos/{video_id}")
async def get_video_details(request: Request, video_id: str):
    """
    Get video details without downloading
    """
    try:
        user = get_current_user(request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        video_service = VideoService()
        video = video_service.get_video_by_id(video_id, int(user["id"]))
        
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        return {"success": True, "video": dict(video)}
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting video details: {str(e)}", "VideoAPI")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/videos")
async def get_user_videos(request: Request):
    """
    Get all videos for current user
    """
    try:
        user = get_current_user(request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        from ..db.database import execute_query
        
        # Get user's videos
        videos = execute_query(
            "SELECT * FROM videos WHERE user_id = %s ORDER BY created_at DESC",
            (int(user["id"]),),
            fetch_all=True
        )
        
        # Convert to JSON-serializable format
        video_list = []
        for video in videos:
            video_dict = dict(video)
            for key, value in video_dict.items():
                if hasattr(value, 'isoformat'):
                    video_dict[key] = value.isoformat()
            video_list.append(video_dict)
        
        return {"success": True, "videos": video_list}
        
    except Exception as e:
        log_error(f"Error getting user videos: {str(e)}", "VideoAPI")
        raise HTTPException(status_code=500, detail="Internal server error")
