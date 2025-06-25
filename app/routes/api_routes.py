"""
API routes for MyAvatar
"""
import os
from fastapi import APIRouter, Depends, HTTPException, Request, Form, UploadFile, File, Path
from fastapi.responses import JSONResponse, RedirectResponse
from datetime import datetime, timedelta
from typing import Optional
from ..api.heygen import (create_video_from_audio_file, create_video_from_text,
                          get_available_avatars, get_available_voices, 
                          create_video_with_template, create_video_with_background,
                          get_video_details)
from ..db.database import execute_query
from ..auth.authentication import get_current_user, is_admin
from ..storage.file_storage import upload_avatar_to_cloudinary, upload_audio_to_cloudinary
from ..logger.log_handler import log_info, log_error, log_warning
from ..utils.avatar_utils import ensure_avatar_persistence

# Create router
router = APIRouter(prefix="/api", tags=["api"])

@router.get("/videos")
async def get_videos(request: Request):
    """
    Get videos for current user
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
            
        # Admin can see all videos, normal users only see their own
        if user["is_admin"]:
            videos = execute_query(
                """
                SELECT v.*, u.username, u.email FROM videos v 
                LEFT JOIN users u ON v.user_id = u.id 
                ORDER BY v.created_at DESC
                """, 
                fetch_all=True
            )
        else:
            videos = execute_query(
                "SELECT * FROM videos WHERE user_id = ? ORDER BY created_at DESC",
                (int(user["id"]),),
                fetch_all=True
            )
            
        # Convert to list of dicts
        video_list = []
        for v in videos:
            if isinstance(v, dict):
                video_dict = {}
                for key, value in v.items():
                    if isinstance(value, datetime):
                        video_dict[key] = value.isoformat()
                    else:
                        video_dict[key] = value
                video_list.append(video_dict)
            else:
                # Handle SQLite Row objects
                video_dict = {}
                for key in v.keys():
                    value = v[key]
                    if isinstance(value, datetime):
                        video_dict[key] = value.isoformat()
                    else:
                        video_dict[key] = value
                video_list.append(video_dict)
                
        return JSONResponse(content={"success": True, "videos": video_list})
    except Exception as e:
        log_error("Error getting videos", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/videos/{video_id}/download")
async def download_video(request: Request, video_id: str):
    """
    Download video by redirecting to the video URL
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
        
        # Get video from database
        video = execute_query(
            "SELECT * FROM videos WHERE id = ? OR heygen_video_id = ?",
            (video_id, video_id),
            fetch_one=True
        )
        
        if not video:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Video not found"}
            )
            
        log_info(f"Found video in database: ID={video.get('id')}, HeyGen_ID={video.get('heygen_video_id')}, Status={video.get('status')}, Has_URL={bool(video.get('video_url'))}", "API")
            
        # Check if user has access to this video
        if not user["is_admin"] and video["user_id"] != int(user["id"]):
            return JSONResponse(
                status_code=403,
                content={"success": False, "error": "Access denied"}
            )

        # Check if video has a URL
        video_url = video.get("video_url")
        if not video_url:
            # Try to get the latest video details from HeyGen
            api_key = os.getenv("HEYGEN_API_KEY") or user.get("api_key")
            if api_key and video.get("heygen_video_id"):
                log_info(f"Fetching video URL from HeyGen for video {video['heygen_video_id']}", "API")
                result = get_video_details(api_key, video["heygen_video_id"])
                
                if result["success"] and result.get("details"):
                    details = result["details"]
                    log_info(f"HeyGen response details: {details}", "API")
                    
                    # Try different possible fields for video URL
                    video_url = (details.get("video_url") or 
                               details.get("video_url_caption") or 
                               details.get("url") or 
                               details.get("download_url"))
                    
                    # Check if video is completed
                    video_status = details.get("status", "unknown")
                    log_info(f"Video {video['heygen_video_id']} status: {video_status}", "API")
                    
                    if video_url:
                        # Update the database with the video URL
                        execute_query(
                            "UPDATE videos SET video_url = ?, status = ? WHERE id = ?",
                            (video_url, video_status, video["id"])
                        )
                        log_info(f"Updated video {video['id']} with URL and status {video_status}", "API")
                    elif video_status in ["processing", "pending", "waiting"]:
                        return JSONResponse(
                            status_code=202,
                            content={
                                "success": False, 
                                "error": f"Video is still {video_status}. Please try again in a few minutes.",
                                "status": video_status
                            }
                        )
                    elif video_status == "failed":
                        return JSONResponse(
                            status_code=400,
                            content={
                                "success": False, 
                                "error": "Video generation failed. Please try creating a new video.",
                                "status": video_status
                            }
                        )
                else:
                    log_error(f"Failed to get video details from HeyGen: {result.get('error', 'Unknown error')}", "API")
        
        if not video_url:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False, 
                    "error": "Video URL not available. Video may still be processing or failed to generate."
                }
            )
        
        log_info(f"User {user['username']} downloading video {video_id}", "API")
        
        # Redirect to the video URL for download
        return RedirectResponse(url=video_url, status_code=302)
        
    except Exception as e:
        log_error(f"Error downloading video {video_id}", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/videos/{video_id}/debug")
async def debug_video(request: Request, video_id: str):
    """
    Debug endpoint to check video details without downloading
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
        
        # Get video from database
        video = execute_query(
            "SELECT * FROM videos WHERE id = ? OR heygen_video_id = ?",
            (video_id, video_id),
            fetch_one=True
        )
        
        if not video:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Video not found"}
            )
            
        return JSONResponse(content={
            "success": True,
            "video_id": video.get("id"),
            "heygen_video_id": video.get("heygen_video_id"),
            "status": video.get("status"),
            "has_video_url": bool(video.get("video_url")),
            "video_url_preview": video.get("video_url", "")[:100] + "..." if video.get("video_url") else None,
            "user_id": video.get("user_id"),
            "current_user_id": user.get("id"),
            "is_admin": user.get("is_admin", False),
            "created_at": str(video.get("created_at")) if video.get("created_at") else None
        })
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/videos/{video_id}")
async def get_video(request: Request, video_id: str):
    """
    Get details for a specific video
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
            
        # First try to get from local database
        video = execute_query(
            "SELECT * FROM videos WHERE heygen_video_id = ?",
            (video_id,),
            fetch_one=True
        )
        
        if not video:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Video not found"}
            )
            
        # Check if user has access
        if not user["is_admin"] and video["user_id"] != int(user["id"]):
            return JSONResponse(
                status_code=403,
                content={"success": False, "error": "Access denied"}
            )
            
        # Get current status from HeyGen API
        api_key = os.getenv("HEYGEN_API_KEY") or user.get("api_key")
        if not api_key:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "No API key available"}
            )
            
        if video["status"] in ["pending", "processing"]:
            # Fetch latest status from HeyGen
            result = get_video_details(api_key, video_id)
            if result["success"]:
                # Update video status in database
                status = result["details"]["status"]
                video_url = result["details"].get("video_url", None)
                
                if status != video["status"] or (video_url and not video["video_url"]):
                    execute_query(
                        "UPDATE videos SET status = ?, video_url = ? WHERE heygen_video_id = ?",
                        (status, video_url, video_id)
                    )
                    
                return JSONResponse(content={
                    "success": True,
                    "video": {
                        **dict(video),
                        "status": status,
                        "video_url": video_url or video["video_url"]
                    }
                })
                
        # Return video details
        return JSONResponse(content={"success": True, "video": dict(video)})
    except Exception as e:
        log_error(f"Error getting video {video_id}", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.post("/videos/create-from-text")
async def create_video_from_text_endpoint(
    request: Request,
    text: str = Form(...),
    format: str = Form("16:9"),
    voice_id: str = Form(None),  # Changed to None default to allow system to find the right voice ID
    title: str = Form(None)
):
    """
    Create a video from text
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
            
        api_key = os.getenv("HEYGEN_API_KEY") or user.get("api_key")
        if not api_key:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "No API key available"}
            )
            
        # Get user's avatar ID
        avatar_id = user.get("avatar_id")
        if not avatar_id:
            # Get default avatar for user
            avatar = execute_query(
                "SELECT avatar_id FROM user_avatars WHERE user_id = ? AND is_default = 1",
                (int(user["id"]),),
                fetch_one=True
            )
            
            if avatar:
                avatar_id = avatar["avatar_id"]
            else:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "error": "No avatar available"}
                )
        
        # Check if this is a public avatar (not starting with "custom-")
        is_public_avatar = not avatar_id.startswith("custom-")
        
        # If public avatar and no voice_id provided, try to find user's preferred voice ID
        if is_public_avatar and not voice_id:
            # Try to get voice ID from user_settings
            try:
                user_voice = execute_query(
                    "SELECT setting_value FROM user_settings WHERE user_id = ? AND setting_name = 'voice_id'",
                    (int(user["id"]),),
                    fetch_one=True
                )
                
                if user_voice and user_voice["setting_value"]:
                    voice_id = user_voice["setting_value"]
                    log_info(f"Using user's preferred voice_id from settings: {voice_id}", "API")
            except Exception as e:
                log_warning(f"Error retrieving user voice setting: {str(e)}", "API")
        
        # For testuser with specific public avatars, hardcode the voice ID if not found elsewhere
        if is_public_avatar and not voice_id and user.get("username") == "testuser":
            voice_id = "0f04c50500bf417396ba2e846d7bd3d7"  # Use the voice ID you provided
            log_info(f"Using hardcoded voice_id for testuser with public avatar: {voice_id}", "API")
        
        # If still no voice_id for public avatar, use a default
        if is_public_avatar and not voice_id:
            voice_id = "en-US-JennyNeural"  # Default Microsoft neural voice
            log_warning(f"Using fallback voice_id for public avatar: {voice_id}", "API")
                
        # Create video with HeyGen API
        result = create_video_from_text(api_key, avatar_id, text, format, voice_id)
        
        if not result["success"]:
            return JSONResponse(
                status_code=500,
                content=result
            )
            
        # Save video to database
        heygen_video_id = result["video_id"]
        title = title or f"Video {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        # Ensure all values are properly typed for PostgreSQL
        user_id = int(user["id"]) if user["id"] else None
        voice_id_value = str(voice_id) if voice_id else None
        
        execute_query(
            """
            INSERT INTO videos (user_id, avatar_id, heygen_video_id, status, format, title, voice_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, str(avatar_id), str(heygen_video_id), "processing", str(format), str(title), voice_id_value)
        )
        
        log_info(f"Text-to-video created: {heygen_video_id}", "API")
        
        return JSONResponse(content={
            "success": True,
            "video_id": heygen_video_id,
            "message": "Video creation initiated"
        })
    except Exception as e:
        log_error("Error creating video from text", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.post("/videos/create-from-audio")
async def create_video_from_audio_endpoint(
    request: Request,
    audio: UploadFile = File(...),
    format: str = Form("16:9"),
    avatar_id: str = Form(None),
    title: str = Form(None)
):
    """
    Create a video from audio file - UPDATED to accept avatar_id from form
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
            
        api_key = os.getenv("HEYGEN_API_KEY") or user.get("api_key")
        if not api_key:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "No API key available"}
            )
            
        # Get avatar_id from form data or fall back to user's default avatar
        if not avatar_id:
            avatar_id = user.get("avatar_id")
            
        if not avatar_id:
            # Get default avatar for user
            avatar = execute_query(
                "SELECT avatar_id FROM user_avatars WHERE user_id = ? AND is_default = 1",
                (int(user["id"]),),
                fetch_one=True
            )
            
            if avatar:
                avatar_id = avatar["avatar_id"]
            else:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "error": "No avatar available. Please select an avatar."}
                )
                
        # Upload audio file
        audio_url = upload_audio_to_cloudinary(audio, user["id"])
        
        # Create video with HeyGen API
        result = create_video_from_audio_file(api_key, avatar_id, audio_url, format)
        
        if not result["success"]:
            return JSONResponse(
                status_code=500,
                content=result
            )
            
        # Save video to database
        heygen_video_id = result["video_id"]
        title = title or f"Audio Video {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        # Ensure all values are properly typed for PostgreSQL
        user_id = int(user["id"]) if user["id"] else None
        
        # FIXED: Added avatar_id and audio_path to the INSERT statement
        execute_query(
            """
            INSERT INTO videos (user_id, avatar_id, audio_path, heygen_video_id, status, format, title)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, str(avatar_id), audio_url, str(heygen_video_id), "processing", str(format), str(title))
        )
        
        log_info(f"Audio-to-video created: {heygen_video_id} with avatar: {avatar_id}", "API")
        
        return JSONResponse(content={
            "success": True,
            "video_id": heygen_video_id,
            "message": "Video creation initiated"
        })
    except Exception as e:
        log_error("Error creating video from audio", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.post("/avatars")
async def add_avatar(
    request: Request,
    avatar_id: str = Form(...),
    avatar_name: str = Form(...),
    avatar_image: UploadFile = File(...),
    is_default: bool = Form(False)
):
    """
    Add a new avatar for a user
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
            
        # Upload avatar image
        avatar_image_url = upload_avatar_to_cloudinary(avatar_image, user["id"])
        
        # If setting as default, clear other defaults
        if is_default:
            execute_query(
                "UPDATE user_avatars SET is_default = 0 WHERE user_id = ?",
                (int(user["id"]),)
            )
            
        # Add avatar to database
        execute_query(
            """
            INSERT INTO user_avatars (user_id, avatar_id, avatar_name, avatar_image_url, is_default)
            VALUES (?, ?, ?, ?, ?)
            """,
            (int(user["id"]), avatar_id, avatar_name, avatar_image_url, is_default)
        )
        
        # If default, also update user record
        if is_default:
            execute_query(
                "UPDATE users SET avatar_id = ? WHERE id = ?",
                (avatar_id, int(user["id"]))
            )
            
        log_info(f"Avatar added for user {user['username']}: {avatar_id}", "API")
        
        return JSONResponse(content={
            "success": True,
            "avatar_id": avatar_id,
            "avatar_image_url": avatar_image_url,
            "message": "Avatar added successfully"
        })
    except Exception as e:
        log_error("Error adding avatar", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/avatars")
async def get_avatars(request: Request):
    """
    Get avatars for current user
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
            
        # Get user's avatars
        avatars = execute_query(
            "SELECT * FROM user_avatars WHERE user_id = ?",
            (int(user["id"]),),
            fetch_all=True
        )
        
        # Convert to list of dicts
        avatar_list = []
        for a in avatars:
            if isinstance(a, dict):
                avatar_list.append(a)
            else:
                # Handle SQLite Row objects
                avatar_dict = {}
                for key in a.keys():
                    avatar_dict[key] = a[key]
                avatar_list.append(avatar_dict)
                
        return JSONResponse(content={"success": True, "avatars": avatar_list})
    except Exception as e:
        log_error("Error getting avatars", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/voices")
async def get_voices(request: Request, language: Optional[str] = None):
    """
    Get available voices from HeyGen
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
            
        api_key = os.getenv("HEYGEN_API_KEY") or user.get("api_key")
        if not api_key:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "No API key available"}
            )
            
        result = get_available_voices(api_key, language)
        return JSONResponse(content=result)
    except Exception as e:
        log_error("Error getting voices", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/heygen-avatars")
async def get_heygen_avatars(request: Request):
    """
    Get available avatars from HeyGen
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
            
        api_key = os.getenv("HEYGEN_API_KEY") or user.get("api_key")
        if not api_key:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "No API key available"}
            )
            
        result = get_available_avatars(api_key)
        return JSONResponse(content=result)
    except Exception as e:
        log_error("Error getting HeyGen avatars", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/video-status/{video_id}")
async def get_video_status(request: Request, video_id: str):
    """
    Check status of a video by ID
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
        
        # Get video from database
        video = execute_query(
            "SELECT * FROM videos WHERE id = ? OR heygen_video_id = ?",
            (video_id, video_id),
            fetch_one=True
        )
        
        if not video:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Video not found"}
            )
            
        log_info(f"Found video in database: ID={video.get('id')}, HeyGen_ID={video.get('heygen_video_id')}, Status={video.get('status')}, Has_URL={bool(video.get('video_url'))}", "API")
            
        # Check if user has access to this video
        if not user["is_admin"] and video["user_id"] != int(user["id"]):
            return JSONResponse(
                status_code=403,
                content={"success": False, "error": "Access denied"}
            )
        
        # Check if video has a URL
        video_url = video.get("video_url")
        if not video_url:
            # Try to get the latest video details from HeyGen
            api_key = os.getenv("HEYGEN_API_KEY") or user.get("api_key")
            if api_key and video.get("heygen_video_id"):
                log_info(f"Fetching video URL from HeyGen for video {video['heygen_video_id']}", "API")
                result = get_video_details(api_key, video["heygen_video_id"])
                
                if result["success"] and result.get("details"):
                    details = result["details"]
                    log_info(f"HeyGen response details: {details}", "API")
                    
                    # Try different possible fields for video URL
                    video_url = (details.get("video_url") or 
                               details.get("video_url_caption") or 
                               details.get("url") or 
                               details.get("download_url"))
                    
                    # Check if video is completed
                    video_status = details.get("status", "unknown")
                    log_info(f"Video {video['heygen_video_id']} status: {video_status}", "API")
                    
                    if video_url:
                        # Update the database with the video URL
                        execute_query(
                            "UPDATE videos SET video_url = ?, status = ? WHERE id = ?",
                            (video_url, video_status, video["id"])
                        )
                        log_info(f"Updated video {video['id']} with URL and status {video_status}", "API")
                    elif video_status in ["processing", "pending", "waiting"]:
                        return JSONResponse(
                            status_code=202,
                            content={
                                "success": False, 
                                "error": f"Video is still {video_status}. Please try again in a few minutes.",
                                "status": video_status
                            }
                        )
                    elif video_status == "failed":
                        return JSONResponse(
                            status_code=400,
                            content={
                                "success": False, 
                                "error": "Video generation failed. Please try creating a new video.",
                                "status": video_status
                            }
                        )git add app/routes/api_routes.py
git add templates/dashboard.html  
git commit -m "Move voice recording route from api_routes to web_routes"
git push
                else:
                    log_error(f"Failed to get video details from HeyGen: {result.get('error', 'Unknown error')}", "API")
        
        if not video_url:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False, 
                    "error": "Video URL not available. Video may still be processing or failed to generate."
                }
            )
        
        log_info(f"User {user['username']} downloading video {video_id}", "API")
        
        # Redirect to the video URL for download
        return RedirectResponse(url=video_url, status_code=302)
        
    except Exception as e:
        log_error(f"Error downloading video {video_id}", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )