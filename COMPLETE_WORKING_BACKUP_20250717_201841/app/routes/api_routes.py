"""
API routes for MyAvatar
"""
import os
import zipfile
import xml.etree.ElementTree as ET
from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException, Request, Form, UploadFile, File, Path
from fastapi.responses import JSONResponse, RedirectResponse
from datetime import datetime, timedelta
from typing import Optional
import uuid
from ..api.heygen import (create_video_from_audio_file, create_video_from_text,
                          get_available_avatars, get_available_voices, 
                          create_video_with_template, create_video_with_background,
                          get_video_details, test_heygen_connection)
from ..db.database import execute_query
from ..auth.authentication import get_current_user, is_admin
from ..storage.file_storage import upload_avatar_to_cloudinary, upload_audio_to_cloudinary
from ..logger.log_handler import log_info, log_error, log_warning
from ..utils.avatar_utils import ensure_avatar_persistence
from ..utils.heygen_image_utils import ensure_avatar_has_heygen_image

# Create router
router = APIRouter(tags=["api"])

# TEST MODE - Set to True to bypass HeyGen API for testing
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

@router.post("/document-parser")
async def parse_document(request: Request, file: UploadFile = File(...)):
    """
    Parse uploaded document and extract text content
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
        
        # Check file size (10MB limit)
        if file.size and file.size > 10 * 1024 * 1024:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "File too large. Maximum size is 10MB."}
            )
        
        # Check file type
        allowed_extensions = ['.txt', '.docx', '.pdf']
        file_extension = '.' + file.filename.lower().split('.')[-1]
        
        if file_extension not in allowed_extensions:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"}
            )
        
        # Read file content
        content = await file.read()
        
        # Extract text based on file type
        text = ""
        if file_extension == '.txt':
            # Plain text file
            text = content.decode('utf-8', errors='ignore')
        elif file_extension == '.docx':
            # Word document - basic text extraction
            try:
                with zipfile.ZipFile(BytesIO(content), 'r') as zip_file:
                    # Extract text from document.xml
                    xml_content = zip_file.read('word/document.xml')
                    root = ET.fromstring(xml_content)
                    
                    # Extract text from all text nodes
                    text_elements = []
                    for elem in root.iter():
                        if elem.tag.endswith('}t'):  # Text elements
                            if elem.text:
                                text_elements.append(elem.text)
                    
                    text = ' '.join(text_elements)
            except Exception as e:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "error": f"Could not parse Word document: {str(e)}"}
                )
        elif file_extension == '.pdf':
            # PDF - basic text extraction
            try:
                import PyPDF2
                
                pdf_reader = PyPDF2.PdfReader(BytesIO(content))
                text_parts = []
                
                for page in pdf_reader.pages:
                    text_parts.append(page.extract_text())
                
                text = ' '.join(text_parts)
            except Exception as e:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "error": f"Could not parse PDF: {str(e)}. Try saving as plain text."}
                )
        
        # Clean and process text
        original_length = len(text)
        
        # Basic cleaning
        text = text.strip()
        text = ' '.join(text.split())  # Normalize whitespace
        
        # Remove common document artifacts
        text = text.replace('\n', ' ')
        text = text.replace('\r', ' ')
        text = text.replace('\t', ' ')
        
        # Truncate to 1500 characters (text-to-video limit)
        truncated = False
        if len(text) > 1500:
            text = text[:1500]
            truncated = True
        
        final_length = len(text)
        
        if not text:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "No text content found in file"}
            )
        
        log_info(f"Document parsed successfully: {file.filename} ({original_length} -> {final_length} chars)", "DocumentParser")
        
        return JSONResponse(content={
            "success": True,
            "text": text,
            "filename": file.filename,
            "original_length": original_length,
            "final_length": final_length,
            "truncated": truncated,
            "file_type": file_extension
        })
        
    except Exception as e:
        log_error(f"Document parser error: {str(e)}", "DocumentParser", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Failed to process document"}
        )

@router.get("/debug/check-videos")
async def debug_check_videos(request: Request):
    """
    Debug endpoint to check specific video statuses
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
        
        videos = execute_query(
            """
            SELECT id, heygen_video_id, status, video_path, title, created_at
            FROM videos 
            WHERE heygen_video_id IN (%s, %s)
            ORDER BY created_at DESC
            """,
            ('dfb8d77e53664300ab0d7106cf395e4d', '125e966b2c44461eb9b8e985bc064472'),
            fetch_all=True
        )
        
        # Convert datetime objects to strings for JSON serialization
        video_list = []
        for video in videos:
            video_dict = dict(video)
            for key, value in video_dict.items():
                if hasattr(value, 'isoformat'):  # datetime object
                    video_dict[key] = value.isoformat()
            video_list.append(video_dict)
        
        return JSONResponse(content={"success": True, "videos": video_list})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

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
                "SELECT * FROM videos WHERE user_id = %s ORDER BY created_at DESC",
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
        
        # Get video from database - handle both numeric IDs and HeyGen video IDs
        if video_id.isdigit():
            # Numeric ID - check both id and heygen_video_id fields
            video = execute_query(
                "SELECT * FROM videos WHERE id = %s OR heygen_video_id = %s",
                (int(video_id), video_id),
                fetch_one=True
            )
        else:
            # Non-numeric ID (HeyGen video ID) - only check heygen_video_id field
            video = execute_query(
                "SELECT * FROM videos WHERE heygen_video_id = %s",
                (video_id,),
                fetch_one=True
            )
        
        if not video:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Video not found"}
            )
            
        log_info(f"Found video in database: ID={video.get('id')}, HeyGen_ID={video.get('heygen_video_id')}, Status={video.get('status')}, Has_URL={bool(video.get('video_path'))}", "API")
            
    # Check if user has access to this video
        if not user["is_admin"] and video["user_id"] != int(user["id"]):
            return JSONResponse(
                status_code=403,
                content={"success": False, "error": "Access denied"}
            )

        # Check if video has a URL
        video_path = video.get("video_path")
        if not video_path:
            # Try to get the latest video details from HeyGen
            api_key = os.getenv("HEYGEN_API_KEY") or user.get("api_key")
            if api_key and video.get("heygen_video_id"):
                log_info(f"Fetching video URL from HeyGen for video {video['heygen_video_id']}", "API")
                result = get_video_details(api_key, video["heygen_video_id"])
                
                if result["success"] and result.get("details"):
                    details = result["details"]
                    log_info(f"HeyGen response details: {details}", "API")
                    
                    # Try different possible fields for video URL
                    video_path = (details.get("video_url") or 
                               details.get("video_url_caption") or 
                               details.get("url") or 
                               details.get("download_url"))
                    
                    # Check if video is completed
                    video_status = details.get("status", "unknown")
                    log_info(f"Video {video['heygen_video_id']} status: {video_status}", "API")
                    
                    if video_path:
                        # Update the database with the video URL
                        execute_query(
                            "UPDATE videos SET video_path = %s, status = %s WHERE id = %s",
                            (video_path, video_status, video["id"])
                        )
                        log_info(f"Updated video {video['id']} with URL and status {video_status}", "API")
                    elif video_status in ["processing", "pending", "waiting"]:
                        return JSONResponse(
                            status_code=200,
                            content={
                                "success": True, 
                                "message": f"Video is still {video_status}. Please wait...",
                                "status": video_status,
                                "processing": True
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
        
        if not video_path:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False, 
                    "error": "Video URL not available. Video may still be processing or failed to generate."
                }
            )
        
        log_info(f"User {user['username']} downloading video {video_id}", "API")
        
        # Redirect to the video URL for download
        return RedirectResponse(url=video_path, status_code=302)
        
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
        
        # Get video from database - handle both numeric IDs and HeyGen video IDs
        if video_id.isdigit():
            # Numeric ID - check both id and heygen_video_id fields
            video = execute_query(
                "SELECT * FROM videos WHERE id = %s OR heygen_video_id = %s",
                (int(video_id), video_id),
                fetch_one=True
            )
        else:
            # Non-numeric ID (HeyGen video ID) - only check heygen_video_id field
            video = execute_query(
                "SELECT * FROM videos WHERE heygen_video_id = %s",
                (video_id,),
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
            "has_video_path": bool(video.get("video_path")),
            "video_path_preview": video.get("video_path", "")[:100] + "..." if video.get("video_path") else None,
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
            
        # First try to get from local database - handle both numeric IDs and HeyGen video IDs
        if video_id.isdigit():
            # Numeric ID - check both id and heygen_video_id fields
            video = execute_query(
                "SELECT * FROM videos WHERE id = %s OR heygen_video_id = %s",
                (int(video_id), video_id),
                fetch_one=True
            )
        else:
            # Non-numeric ID (HeyGen video ID) - only check heygen_video_id field
            video = execute_query(
                "SELECT * FROM videos WHERE heygen_video_id = %s",
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
                video_path = result["details"].get("video_path", None)
                
                if status != video["status"] or (video_path and not video["video_path"]):
                    execute_query(
                        "UPDATE videos SET status = %s, video_path = %s WHERE heygen_video_id = %s",
                        (status, video_path, video_id)
                    )
                    
                return JSONResponse(content={
                    "success": True,
                    "video": {
                        **dict(video),
                        "status": status,
                        "video_path": video_path or video["video_path"]
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
    avatar_id: str = Form(None),
    voice_id: str = Form(None),  # Changed to None default to allow system to find the right voice ID
    title: str = Form(None),
    description: str = Form(None)
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
        if not avatar_id:
            avatar_id = user.get("avatar_id")
            if not avatar_id:
                # Get default avatar for user
                avatar = execute_query(
                    "SELECT avatar_id FROM user_avatars WHERE user_id = %s AND is_default = 1",
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
        
        # Always try to find user's preferred voice ID
        if not voice_id:
            # Try to get voice ID from users table heygen_voice_id column
            try:
                if user.get("heygen_voice_id"):
                    voice_id = user["heygen_voice_id"]
                    log_info(f"Using user's heygen_voice_id: {voice_id}", "API")
            except Exception as e:
                log_warning(f"Error retrieving user heygen_voice_id: {str(e)}", "API")
        
        # If still no voice_id, use a valid HeyGen voice ID as fallback
        if not voice_id:
            voice_id = "0f04c50500bf417396ba2e846d7bd3d7"  # Valid HeyGen voice ID
            log_warning(f"Using fallback HeyGen voice_id: {voice_id}", "API")
                
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
        
        execute_query(
            """
            INSERT INTO videos (user_id, avatar_id, heygen_video_id, status, format, title, audio_path, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, str(avatar_id), str(heygen_video_id), "processing", str(format), str(title), "", str(description) if description else "")
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
    title: str = Form(None),
    description: str = Form(None)
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
                "SELECT avatar_id FROM user_avatars WHERE user_id = %s AND is_default = 1",
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
        
        # Always try to find user's preferred voice ID
        voice_id = None
        try:
            if user.get("heygen_voice_id"):
                voice_id = user["heygen_voice_id"]
                log_info(f"Using user's heygen_voice_id: {voice_id}", "API")
        except Exception as e:
            log_warning(f"Error retrieving user heygen_voice_id: {str(e)}", "API")
        
        # If still no voice_id, use a valid HeyGen voice ID as fallback
        if not voice_id:
            voice_id = "0f04c50500bf417396ba2e846d7bd3d7"  # Valid HeyGen voice ID
            log_warning(f"Using fallback HeyGen voice_id: {voice_id}", "API")
        
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
            INSERT INTO videos (user_id, avatar_id, audio_path, heygen_video_id, status, format, title, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, str(avatar_id), audio_url, str(heygen_video_id), "processing", str(format), str(title), str(description))
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
                "UPDATE user_avatars SET is_default = 0 WHERE user_id = %s",
                (int(user["id"]),)
            )
            
        # Add avatar to database
        execute_query(
            """
            INSERT INTO user_avatars (user_id, avatar_id, avatar_name, avatar_image_url, is_default)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (int(user["id"]), avatar_id, avatar_name, avatar_image_url, is_default)
        )
        
        # If default, also update user record
        if is_default:
            execute_query(
                "UPDATE users SET avatar_id = %s WHERE id = %s",
                (avatar_id, int(user["id"]))
            )
            
        log_info(f"Avatar added for user {user['username']}: {avatar_id}", "API")
        
        return JSONResponse(content={
            "success": True,
            "avatar_id": avatar_id,
            "avatar_image_url": avatar_image_url,
            "message": "HeyGen avatar added successfully"
        })
    except Exception as e:
        log_error("Error adding HeyGen avatar", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.post("/avatars/heygen")
async def add_heygen_avatar(
    request: Request,
    avatar_id: str = Form(...),
    avatar_name: str = Form(None),
    is_default: bool = Form(False)
):
    """
    Add a HeyGen avatar by ID only (no file upload required)
    Enhanced with proper avatar validation using HeyGen API
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
        
        # Check if avatar already exists for this user
        existing = execute_query(
            "SELECT id FROM user_avatars WHERE user_id = %s AND heygen_avatar_id = %s",
            (int(user["id"]), avatar_id)
        )
        
        if existing:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Avatar already exists for this user"}
            )
        
        # Clean up avatar ID (remove any whitespace)
        avatar_id = avatar_id.strip()
        
        # Get HeyGen API key
        heygen_api_key = os.getenv("HEYGEN_API_KEY")
        avatar_type = "unknown"
        
        if not heygen_api_key:
            log_warning("HeyGen API key not found - adding avatar without validation", "API")
            # Fallback: Add avatar without validation
            if not avatar_name:
                avatar_name = f"HeyGen Avatar {avatar_id[:8]}"
            avatar_image_url = f"https://files2.heygen.ai/avatar/v3/{avatar_id}/{avatar_id}.jpg"
        else:
            # Try to validate avatar with HeyGen API
            log_info(f"Validating HeyGen avatar ID: {avatar_id}", "API")
            
            try:
                from ..api.heygen import get_avatar_from_any_endpoint
                avatar_result = get_avatar_from_any_endpoint(heygen_api_key, avatar_id)
                
                if avatar_result and avatar_result.get("error"):
                    # Handle old talking photo error - still allow adding
                    log_warning(f"HeyGen validation warning for {avatar_id}: {avatar_result.get('error')}", "API")
                    avatar_type = "legacy"
                    if not avatar_name:
                        avatar_name = f"Legacy Avatar {avatar_id[:8]}"
                    avatar_image_url = f"https://files2.heygen.ai/avatar/v3/{avatar_id}/{avatar_id}.jpg"
                elif avatar_result:
                    # Extract avatar details from HeyGen response
                    avatar_data = avatar_result.get("data", {})
                    avatar_type = avatar_result.get("type", "unknown")
                    
                    # Generate avatar name if not provided
                    if not avatar_name:
                        # Try to get name from HeyGen data
                        heygen_name = avatar_data.get("name") or avatar_data.get("avatar_name")
                        if heygen_name:
                            avatar_name = heygen_name
                        else:
                            avatar_name = f"Avatar {avatar_id}"
                    
                    # Get avatar image URL from HeyGen data or construct it
                    avatar_image_url = None
                    
                    # Try to get image URL from HeyGen response
                    if avatar_data.get("preview_image_url"):
                        avatar_image_url = avatar_data["preview_image_url"]
                    elif avatar_data.get("image_url"):
                        avatar_image_url = avatar_data["image_url"]
                    elif avatar_data.get("preview_image"):
                        avatar_image_url = avatar_data["preview_image"]
                    else:
                        # Fallback: construct URL based on avatar type
                        avatar_image_url = f"https://files2.heygen.ai/avatar/v3/{avatar_id}/{avatar_id}.jpg"
                    
                    log_info(f"HeyGen avatar validated successfully (type: {avatar_type})", "API")
                else:
                    # Validation failed but we'll add it anyway with a warning
                    log_warning(f"Could not validate HeyGen avatar {avatar_id} - adding with fallback data", "API")
                    avatar_type = "unvalidated"
                    if not avatar_name:
                        avatar_name = f"Unvalidated Avatar {avatar_id[:8]}"
                    avatar_image_url = f"https://files2.heygen.ai/avatar/v3/{avatar_id}/{avatar_id}.jpg"
                    
            except Exception as validation_error:
                log_error(f"HeyGen validation error for {avatar_id}: {validation_error}", "API")
                # Fallback: Add avatar without validation
                avatar_type = "fallback"
                if not avatar_name:
                    avatar_name = f"HeyGen Avatar {avatar_id[:8]}"
                avatar_image_url = f"https://files2.heygen.ai/avatar/v3/{avatar_id}/{avatar_id}.jpg"
        
        # If setting as default, clear other defaults
        if is_default:
            execute_query(
                "UPDATE user_avatars SET is_default = 0 WHERE user_id = %s",
                (int(user["id"]),)
            )
            
        # Add avatar to database
        execute_query(
            """
            INSERT INTO user_avatars (user_id, heygen_avatar_id, avatar_name, avatar_image_url, is_default, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            """,
            (int(user["id"]), avatar_id, avatar_name, avatar_image_url, is_default)
        )
        
        # If default, also update user record
        if is_default:
            execute_query(
                "UPDATE users SET avatar_id = %s WHERE id = %s",
                (avatar_id, int(user["id"]))
            )
            
        log_info(f"HeyGen avatar added for user {user['username']}: {avatar_id} (type: {avatar_type})", "API")
        
        return JSONResponse(content={
            "success": True,
            "avatar_id": avatar_id,
            "avatar_name": avatar_name,
            "avatar_image_url": avatar_image_url,
            "avatar_type": avatar_type,
            "message": "HeyGen avatar added successfully"
        })
    except Exception as e:
        log_error("Error adding HeyGen avatar", "API", e)
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
            "SELECT * FROM user_avatars WHERE user_id = %s",
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
        
        # Get video from database - handle both numeric IDs and HeyGen video IDs
        if video_id.isdigit():
            # Numeric ID - check both id and heygen_video_id fields
            video = execute_query(
                "SELECT * FROM videos WHERE id = %s OR heygen_video_id = %s",
                (int(video_id), video_id),
                fetch_one=True
            )
        else:
            # Non-numeric ID (HeyGen video ID) - only check heygen_video_id field
            video = execute_query(
                "SELECT * FROM videos WHERE heygen_video_id = %s",
                (video_id,),
                fetch_one=True
            )
        
        if not video:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Video not found"}
            )
            
        log_info(f"Found video in database: ID={video.get('id')}, HeyGen_ID={video.get('heygen_video_id')}, Status={video.get('status')}, Has_URL={bool(video.get('video_path'))}", "API")
            
        # Check if user has access to this video
        if not user["is_admin"] and video["user_id"] != int(user["id"]):
            return JSONResponse(
                status_code=403,
                content={"success": False, "error": "Access denied"}
            )
        
        # Check if video has a URL
        video_path = video.get("video_path")
        if not video_path:
            # Try to get the latest video details from HeyGen
            api_key = os.getenv("HEYGEN_API_KEY") or user.get("api_key")
            if api_key and video.get("heygen_video_id"):
                log_info(f"Fetching video URL from HeyGen for video {video['heygen_video_id']}", "API")
                result = get_video_details(api_key, video["heygen_video_id"])
                
                if result["success"] and result.get("details"):
                    details = result["details"]
                    log_info(f"HeyGen response details: {details}", "API")
                    
                    # Try different possible fields for video URL
                    video_path = (details.get("video_url") or 
                               details.get("video_url_caption") or 
                               details.get("url") or 
                               details.get("download_url"))
                    
                    # Check if video is completed
                    video_status = details.get("status", "unknown")
                    log_info(f"Video {video['heygen_video_id']} status: {video_status}", "API")
                    
                    if video_path:
                        # Update the database with the video URL
                        execute_query(
                            "UPDATE videos SET video_path = %s, status = %s WHERE id = %s",
                            (video_path, video_status, video["id"])
                        )
                        log_info(f"Updated video {video['id']} with URL and status {video_status}", "API")
                    elif video_status in ["processing", "pending", "waiting"]:
                        return JSONResponse(
                            status_code=200,
                            content={
                                "success": True, 
                                "message": f"Video is still {video_status}. Please wait...",
                                "status": video_status,
                                "processing": True
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
        
        if not video_path:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False, 
                    "error": "Video URL not available. Video may still be processing or failed to generate."
                }
            )
        
        log_info(f"User {user['username']} checking video status {video_id}", "API")
        
        # Return status information as JSON instead of redirecting
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status": "completed",
                "video_path": video_path,
                "message": "Video is ready for download"
            }
        )
        
    except Exception as e:
        log_error(f"Error downloading video {video_id}", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/debug-video-status/{video_id}")
async def debug_video_status(request: Request, video_id: str):
    """
    Debug endpoint to test video status checking
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
            "SELECT * FROM videos WHERE heygen_video_id = %s",
            (video_id,),
            fetch_one=True
        )
        
        if not video:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Video not found"}
            )
        
        # Test HeyGen API call
        api_key = os.getenv("HEYGEN_API_KEY")
        if not api_key:
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "No API key available"}
            )
        
        # Call HeyGen API
        result = get_video_details(api_key, video_id)
        
        # Convert video record to JSON-serializable format
        video_dict = dict(video)
        for key, value in video_dict.items():
            if hasattr(value, 'isoformat'):  # datetime object
                video_dict[key] = value.isoformat()
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "video_db": video_dict,
                "heygen_result": result
            }
        )
        
    except Exception as e:
        log_error(f"Debug video status error: {str(e)}", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.post("/heygen/webhook")
async def heygen_webhook(request: Request):
    """
    Webhook endpoint to receive HeyGen video completion notifications
    """
    try:
        # Get the webhook payload
        payload = await request.json()
        log_info(f"Received HeyGen webhook: {payload}", "API")
        
        # Extract event information from HeyGen webhook format
        event_type = payload.get("event_type")
        event_data = payload.get("event_data", {})
        
        if not event_type or not event_data:
            log_error("HeyGen webhook missing event_type or event_data", "API")
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Invalid webhook format"}
            )
        
        # Extract video information from event_data
        video_id = event_data.get("video_id")
        video_path = event_data.get("url")
        callback_id = event_data.get("callback_id")
        
        if not video_id:
            log_error("HeyGen webhook missing video_id in event_data", "API")
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Missing video_id"}
            )
        
        log_info(f"HeyGen webhook for video {video_id}: event_type={event_type}, has_url={bool(video_path)}", "API")
        
        # Find the video in our database using HeyGen video ID
        video = execute_query(
            "SELECT * FROM videos WHERE heygen_video_id = %s",
            (video_id,),
            fetch_one=True
        )
        
        if not video:
            log_warning(f"HeyGen webhook for unknown video {video_id}", "API")
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Video not found"}
            )
        
        # Update video based on event type
        if event_type == "avatar_video.success" and video_path:
            execute_query(
                "UPDATE videos SET video_path = %s, status = %s WHERE id = %s",
                (video_path, "completed", video["id"])
            )
            log_info(f"Updated video {video['id']} via webhook: status=completed, url={video_path}", "API")
        elif event_type == "avatar_video.fail":
            error_msg = event_data.get("msg", "Video generation failed")
            execute_query(
                "UPDATE videos SET status = %s, error_message = %s WHERE id = %s",
                ("failed", error_msg, video["id"])
            )
            log_info(f"Updated video {video['id']} via webhook: status=failed, error={error_msg}", "API")
        else:
            log_warning(f"Unknown event type {event_type} for video {video_id}", "API")
        
        return JSONResponse(
            content={"success": True, "message": "Webhook processed successfully"}
        )
        
    except Exception as e:
        log_error(f"Error processing HeyGen webhook", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/test/heygen-status")
async def test_heygen_status(request: Request):
    """
    Test HeyGen API connection and status
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
            
        api_key = os.getenv("HEYGEN_API_KEY")
        if not api_key:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "No HeyGen API key configured"}
            )
            
        # Test basic connection
        from ..api.heygen import test_heygen_connection, get_available_voices
        
        connection_test = test_heygen_connection(api_key)
        voices_result = get_available_voices(api_key)
        
        return JSONResponse(content={
            "success": True,
            "connection_test": connection_test,
            "voices_available": voices_result.get("success", False),
            "voices_count": len(voices_result.get("voices", [])) if voices_result.get("success") else 0,
            "api_key_present": bool(api_key),
            "api_key_length": len(api_key) if api_key else 0
        })
        
    except Exception as e:
        log_error("Error testing HeyGen API status", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.post("/avatars/update-images")
async def update_avatar_images(request: Request):
    """
    Update all user avatars with fresh HeyGen images
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
            
        # Get user's avatars
        user_avatars = execute_query(
            "SELECT avatar_id, avatar_image_url FROM user_avatars WHERE user_id = %s",
            (int(user["id"]),),
            fetch_all=True
        )
        
        if not user_avatars:
            return JSONResponse(content={
                "success": True,
                "message": "No avatars to update",
                "updated_count": 0
            })
        
        api_key = os.getenv("HEYGEN_API_KEY") or user.get("api_key")
        updated_count = 0
        
        # Update each avatar with fresh HeyGen image
        for avatar in user_avatars:
            avatar_data = dict(avatar)
            avatar_id = avatar_data['avatar_id']
            current_image = avatar_data['avatar_image_url']
            
            # Get the best HeyGen image
            new_image_url = ensure_avatar_has_heygen_image(avatar_id, current_image, api_key)
            
            # Update if we got a different/better image
            if new_image_url and new_image_url != current_image:
                execute_query(
                    "UPDATE user_avatars SET avatar_image_url = %s WHERE user_id = %s AND avatar_id = %s",
                    (new_image_url, int(user["id"]), avatar_id)
                )
                updated_count += 1
                log_info(f"Updated avatar image for {avatar_id}: {new_image_url}", "API")
        
        return JSONResponse(content={
            "success": True,
            "message": f"Updated {updated_count} avatar images",
            "updated_count": updated_count
        })
        
    except Exception as e:
        log_error("Error updating avatar images", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )
