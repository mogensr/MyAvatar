"""
Updated video routes with proper download functionality + FIXED AUTHENTICATION + VIDEO CREATION ENDPOINTS + HF SPACES INTEGRATION + CLOUDINARY URL SUPPORT + DASHBOARD API ENDPOINTS
"""
from fastapi import APIRouter, HTTPException, Request, File, UploadFile, Form
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from ..services.video_service import VideoService
from ..logger.log_handler import log_info, log_error, log_warning
from ..db.database import execute_query
import requests
import os
import json
from datetime import datetime

# JWT imports for authentication (same as working dashboard)
try:
    from jose import jwt
except ImportError:
    import jwt

# Define templates
templates_path = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_path))

router = APIRouter(tags=["videos"])

# Configuration - same as working web_routes
class Config:
    JWT_SECRET = os.getenv("JWT_SECRET", "fallback-development-secret-key")
    JWT_ALGORITHM = "HS256"

config = Config()

# FIXED AUTHENTICATION FUNCTION - PostgreSQL compatible
def get_current_user_fixed(request: Request):
    """Get current user with proper JWT validation - PostgreSQL compatible"""
    try:
        token = request.cookies.get("access_token")
        if not token:
            return None
        
        # Validate JWT token with expiry check
        try:
            payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
        
        user_id = payload.get("user_id")
        if not user_id:
            return None
        
        # Get fresh user data from database using your existing execute_query
        user = execute_query(
            "SELECT * FROM users WHERE id = %s",
            (user_id,),
            fetch_one=True
        )
        
        if not user:
            return None
        
        # Security checks (removed is_locked check as we removed it from main.py)
        return user
        
    except Exception as e:
        log_error(f"Error getting current user: {e}", "VideoRoutes")
        return None

def verify_token_from_header(auth_header: str):
    """Verify JWT token from Authorization header for API calls"""
    try:
        if not auth_header or not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header.replace('Bearer ', '')
        
        try:
            payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
        
        user_id = payload.get("user_id")
        if not user_id:
            return None
        
        # Get user from database (removed is_locked check)
        user = execute_query(
            "SELECT * FROM users WHERE id = %s",
            (user_id,),
            fetch_one=True
        )
        
        return user
        
    except Exception as e:
        log_error(f"Error verifying token from header: {e}", "VideoAPI")
        return None

# =============================================================================
# DASHBOARD API ENDPOINTS - NEW! (FIXES 404 ERRORS)
# =============================================================================

@router.get("/videos/{video_id}")
async def get_video_for_dashboard(request: Request, video_id: int):
    """Get individual video data for dashboard Play/Download buttons"""
    try:
        user = get_current_user_fixed(request)
        if not user:
            return Response(
                content=json.dumps({"success": False, "error": "Not authenticated"}),
                status_code=401,
                headers={"Content-Type": "application/json"}
            )
        
        # Get video from database
        video = execute_query(
            "SELECT * FROM videos WHERE id = %s AND user_id = %s",
            (video_id, int(user["id"])),
            fetch_one=True
        )
        
        if not video:
            return Response(
                content=json.dumps({"success": False, "error": "Video not found"}),
                status_code=404,
                headers={"Content-Type": "application/json"}
            )
        
        # Convert datetime to string if needed
        video_data = dict(video)
        for key, value in video_data.items():
            if hasattr(value, 'isoformat'):
                video_data[key] = value.isoformat()
        
        # ✅ CRITICAL: Return video_path (which contains the Cloudinary URL)
        response_data = {
            "success": True,
            "video": {
                "id": video_data.get("id"),
                "title": video_data.get("title"),
                "video_path": video_data.get("video_path"),  # ← This is the Cloudinary URL the buttons need!
                "status": video_data.get("status", "completed"),
                "created_at": video_data.get("created_at"),
                "duration": video_data.get("duration"),
                "format": video_data.get("format", "16:9")
            }
        }
        
        log_info(f"✅ Dashboard fetched video {video_id}: {video_data.get('title')} - URL: {video_data.get('video_path')}", "VideoAPI")
        
        return Response(
            content=json.dumps(response_data),
            status_code=200,
            headers={"Content-Type": "application/json"}
        )
        
    except Exception as e:
        log_error(f"❌ Error fetching video {video_id}: {str(e)}", "VideoAPI")
        return Response(
            content=json.dumps({"success": False, "error": str(e)}),
            status_code=500,
            headers={"Content-Type": "application/json"}
        )

@router.get("/api/user-videos")  
async def get_user_videos_for_dashboard(request: Request):
    """Get user's video list for dashboard auto-refresh"""
    try:
        user = get_current_user_fixed(request)
        if not user:
            return Response(
                content=json.dumps({"success": False, "error": "Not authenticated"}),
                status_code=401,
                headers={"Content-Type": "application/json"}
            )
        
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
            
            video_list.append({
                "id": video_dict.get("id"),
                "title": video_dict.get("title"),
                "video_path": video_dict.get("video_path"),  # ← Cloudinary URL
                "status": video_dict.get("status", "completed"),
                "created_at": video_dict.get("created_at"),
                "duration": video_dict.get("duration"),
                "format": video_dict.get("format", "16:9")
            })
        
        log_info(f"✅ Dashboard fetched {len(video_list)} user videos", "VideoAPI")
        
        return Response(
            content=json.dumps({
                "success": True,
                "videos": video_list,
                "total": len(video_list)
            }),
            status_code=200,
            headers={"Content-Type": "application/json"}
        )
        
    except Exception as e:
        log_error(f"❌ Error fetching user videos: {str(e)}", "VideoAPI")
        return Response(
            content=json.dumps({"success": False, "error": str(e)}),
            status_code=500,
            headers={"Content-Type": "application/json"}
        )

# =============================================================================
# HF SPACES INTEGRATION - SAVE VIDEO METADATA API (EXISTING)
# =============================================================================

@router.post("/api/save-video-metadata")
@router.options("/api/save-video-metadata")
async def save_video_metadata(request: Request):
    """
    Save video metadata from external sources (like HF Spaces)
    Video file is already uploaded to Cloudinary - we just save metadata
    Enhanced version with better error handling and flexible auth
    """
    
    # Handle CORS preflight request
    if request.method == "OPTIONS":
        return Response(
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            }
        )
    
    try:
        log_info("📥 Received save-video-metadata request from HF Spaces", "VideoAPI")
        
        # Get JSON data from request
        try:
            data = await request.json()
        except Exception as e:
            log_error(f"Failed to parse JSON: {e}", "VideoAPI")
            return Response(
                content=json.dumps({
                    "success": False,
                    "error": "Invalid JSON format"
                }),
                status_code=400,
                headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"}
            )
        
        log_info(f"📊 Request data: {data}", "VideoAPI")
        
        # Flexible authentication - try multiple methods
        user = None
        user_id = 1  # Default fallback user for testing
        
        # Method 1: Try Authorization header
        auth_header = request.headers.get('Authorization', '')
        if auth_header:
            user = verify_token_from_header(auth_header)
            if user:
                user_id = int(user['id'])
                log_info(f"✅ Authenticated user via header: {user.get('username')}", "VideoAPI")
        
        # Method 2: Try user_id in data (for testing)
        elif data.get('user_id'):
            try:
                test_user_id = int(data['user_id'])
                user = execute_query(
                    "SELECT * FROM users WHERE id = %s",
                    (test_user_id,),
                    fetch_one=True
                )
                if user:
                    user_id = test_user_id
                    log_info(f"✅ Found user via data: {user.get('username')}", "VideoAPI")
            except:
                pass
        
        # Method 3: Use default user (fallback for testing)
        if not user:
            user = execute_query(
                "SELECT * FROM users WHERE id = %s",
                (user_id,),
                fetch_one=True
            )
            log_info(f"⚠️ Using fallback user: {user_id}", "VideoAPI")
        
        # Validate required fields
        if not data.get('video_url'):
            return Response(
                content=json.dumps({
                    "success": False,
                    "error": "video_url is required"
                }),
                status_code=400,
                headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"}
            )
        
        # Prepare video data for database
        video_title = data.get('title', 'BackgroundFX Video')[:255]  # Limit title length
        
        video_data = {
            "user_id": user_id,
            "title": video_title,
            "status": "completed",
            "video_url": data['video_url'],  # Cloudinary URL
            "thumbnail_url": data.get('thumbnail_url', data['video_url'].replace('.mp4', '.jpg')),
            "duration": str(data.get('duration', 8)),  # Convert to string for PostgreSQL
            "format": data.get('format', '16:9'),
            "source": data.get('source', 'BackgroundFX')
        }
        
        log_info(f"💾 Saving video data: {video_data}", "VideoAPI")
        
        # Insert into videos table with proper error handling - FIXED SCHEMA
        try:
            video_result = execute_query(
                """
                INSERT INTO videos (user_id, title, status, video_path, audio_path, avatar_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                RETURNING id
                """,
                (
                    video_data["user_id"],
                    video_data["title"],
                    video_data["status"],
                    video_data["video_url"],  # Store Cloudinary URL in video_path
                    video_data["video_url"],  # Same URL for audio_path
                    1  # Default avatar_id
                ),
                fetch_one=True
            )
            
            if video_result and video_result.get('id'):
                video_id = video_result['id']
                log_info(f"✅ Video metadata saved successfully: Video ID {video_id} for user {user_id}", "VideoAPI")
                
                response_data = {
                    "success": True,
                    "video_id": video_id,
                    "message": "Video saved to My Videos successfully!",
                    "video_url": data['video_url'],
                    "user_id": user_id
                }
                
                return Response(
                    content=json.dumps(response_data),
                    status_code=201,
                    headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"}
                )
            else:
                raise Exception("Database insert returned no ID")
                
        except Exception as db_error:
            log_error(f"❌ Database error: {str(db_error)}", "VideoAPI")
            
            # Return graceful error but don't fail completely
            response_data = {
                "success": False,
                "error": f"Database error: {str(db_error)}",
                "message": "Failed to save to database, but video is available on cloud",
                "video_url": data['video_url']
            }
            
            return Response(
                content=json.dumps(response_data),
                status_code=500,
                headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"}
            )
        
    except Exception as e:
        log_error(f"❌ Unexpected error in save-video-metadata: {str(e)}", "VideoAPI")
        
        error_response = {
            "success": False,
            "error": str(e),
            "message": "Internal server error"
        }
        
        return Response(
            content=json.dumps(error_response),
            status_code=500,
            headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"}
        )

@router.get("/api/test-connection")
async def test_connection(request: Request):
    """Test endpoint to verify API connectivity from HF Spaces"""
    try:
        response_data = {
            "status": "ok",
            "message": "MyAvatar API is running and accessible",
            "timestamp": datetime.now().isoformat(),
            "endpoints": {
                "save_video_metadata": "/api/save-video-metadata",
                "test_connection": "/api/test-connection",
                "get_video": "/videos/{video_id}",
                "get_user_videos": "/api/user-videos"
            },
            "cors_enabled": True,
            "authentication": {
                "methods": ["jwt_header", "user_id_fallback"],
                "required": False  # For testing
            }
        }
        
        return Response(
            content=json.dumps(response_data),
            status_code=200,
            headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"}
        )
        
    except Exception as e:
        log_error(f"Error in test connection: {e}", "VideoAPI")
        return Response(
            content=json.dumps({
                "status": "error",
                "error": str(e)
            }),
            status_code=500,
            headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"}
        )

# =============================================================================
# PAGE ROUTES - FIXED AUTHENTICATION
# =============================================================================

@router.get("/voice-recording")
async def voice_recording_page(request: Request):
    """Serve the voice recording page - FIXED AUTHENTICATION"""
    try:
        user = get_current_user_fixed(request)
        if not user:
            return RedirectResponse(url="/login", status_code=303)
        
        log_info(f"User {user.get('username')} accessing voice recording page", "VideoRoutes")
        
        # Get available avatars for the user - same query as dashboard
        avatars = execute_query(
            "SELECT * FROM user_avatars WHERE user_id = %s ORDER BY avatar_name",
            (int(user["id"]),),
            fetch_all=True
        )
        
        # Process avatars to ensure proper format
        processed_avatars = []
        if avatars:
            for avatar in avatars:
                if isinstance(avatar, dict):
                    processed_avatars.append({
                        'id': avatar.get('id'),
                        'avatar_name': avatar.get('avatar_name', 'Unnamed Avatar'),
                        'avatar_image_url': avatar.get('avatar_image_url', ''),
                        'heygen_avatar_id': avatar.get('heygen_avatar_id', ''),
                        'avatar_id': avatar.get('heygen_avatar_id', ''),  # Alias for compatibility
                        'is_default': avatar.get('is_default', 0)
                    })
        
        return templates.TemplateResponse(
            "voice_recording.html",
            {
                "request": request,
                "user": user,
                "username": user.get("username", "User"),
                "user_id": int(user.get("id", 0)),
                "avatars": processed_avatars,
                "avatar_count": len(processed_avatars)
            }
        )
    except Exception as e:
        log_error(f"Error serving voice recording page: {str(e)}", "VideoRoutes")
        return RedirectResponse(url="/login", status_code=303)

# TEXT-TO-VIDEO ROUTE REMOVED - Now handled in main.py to avoid conflicts

# =============================================================================
# VIDEO CREATION API ENDPOINTS - EXISTING FUNCTIONALITY
# =============================================================================

@router.post("/api/create-video")
async def create_video_from_text(request: Request):
    """Create video from text - FIXED AUTHENTICATION"""
    try:
        user = get_current_user_fixed(request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Get form data
        form_data = await request.form()
        text = form_data.get("text", "").strip()
        avatar_id = form_data.get("avatar_id", "").strip()
        title = form_data.get("title", "").strip()
        language = form_data.get("language", "en-US").strip()  # Get selected language
        voice_id = form_data.get("voice_id", "1bd001e7e50f421d891986aad5158bc8")  # Default voice
        
        # Get voice emotion parameters for more natural intonation
        emotion = form_data.get("emotion", "Friendly").strip()
        
        # Get voice speed parameter (default: 1.0)
        try:
            speed = float(form_data.get("speed", "1.0"))
            # Ensure speed is within valid range
            speed = max(0.5, min(speed, 2.0))
        except ValueError:
            speed = 1.0
            
        # Get voice pitch parameter (default: 1.0)
        try:
            pitch = float(form_data.get("pitch", "1.0"))
            # Ensure pitch is within valid range
            pitch = max(0.5, min(pitch, 1.5))
        except ValueError:
            pitch = 1.0
            
        log_info(f"Voice parameters - Emotion: {emotion}, Speed: {speed}, Pitch: {pitch}", "VideoCreation")
        
        if not text:
            raise HTTPException(status_code=400, detail="Text is required")
        
        if not avatar_id:
            raise HTTPException(status_code=400, detail="Avatar is required")
        
        if not title:
            title = f"Video {text[:30]}..."
        
        log_info(f"User {user.get('username')} creating video: {title}", "VideoCreation")
        
        # Create video using your video service
        video_service = VideoService()
        result = await video_service.create_text_video(
            user_id=int(user["id"]),
            text=text,
            avatar_id=avatar_id,
            title=title,
            voice_id=voice_id,
            language=language,
            emotion=emotion,
            speed=speed,
            pitch=pitch
        )
        
        if result.get("success"):
            return {
                "success": True,
                "message": "Video creation started successfully",
                "video_id": result.get("video_id"),
                "heygen_video_id": result.get("heygen_video_id"),
                "status": "processing"
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Video creation failed"))
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error creating video from text: {str(e)}", "VideoCreation")
        raise HTTPException(status_code=500, detail=f"Error creating video: {str(e)}")

@router.post("/api/create-voice-video")
async def create_voice_video(request: Request):
    """Create video from voice recording - RESTORED WORKING ENDPOINT"""
    try:
        user = get_current_user_fixed(request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Get form data
        form_data = await request.form()
        avatar_id = form_data.get("avatar_id", "").strip()
        title = form_data.get("title", "").strip()
        audio_file = form_data.get("audio")
        video_format = form_data.get("format", "mp4")
        
        if not avatar_id:
            return JSONResponse({
                "success": False,
                "error": "Avatar is required"
            }, status_code=400)
        
        if not audio_file:
            return JSONResponse({
                "success": False,
                "error": "Audio recording is required"
            }, status_code=400)
        
        if not title:
            title = f"Voice Video - {user.get('username')}"
        
        # Create video using VideoService
        video_service = VideoService()
        result = await video_service.create_voice_video(
            user_id=user["id"],
            avatar_id=avatar_id,
            audio_file=audio_file,
            title=title,
            format=video_format
        )
        
        if result.get("success"):
            return JSONResponse({
                "success": True,
                "video_id": result.get("video_id"),
                "title": title,
                "status": result.get("status", "processing"),
                "message": "Voice video created successfully"
            })
        else:
            return JSONResponse({
                "success": False,
                "error": result.get("error", "Failed to create voice video")
            }, status_code=500)
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error creating voice video: {str(e)}", "VoiceVideoCreation")
        return JSONResponse({
            "success": False,
            "error": f"Error creating voice video: {str(e)}"
        }, status_code=500)

@router.post("/api/submit-video")
async def submit_video_creation(request: Request):
    """Alternative endpoint for video submission - handles both text and voice"""
    try:
        user = get_current_user_fixed(request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Try to get JSON data first, then form data
        try:
            data = await request.json()
            is_json = True
        except:
            data = await request.form()
            is_json = False
        
        # Extract common fields
        avatar_id = data.get("avatar_id", "").strip() if is_json else data.get("avatar_id", "").strip()
        title = data.get("title", "").strip() if is_json else data.get("title", "").strip()
        video_type = data.get("type", "text") if is_json else data.get("type", "text")
        
        if not avatar_id:
            raise HTTPException(status_code=400, detail="Avatar is required")
        
        if not title:
            title = f"My Video - {user.get('username')}"
        
        video_service = VideoService()
        
        if video_type == "voice" or "audio" in data:
            # Voice video creation
            audio_file = data.get("audio") if not is_json else None
            if not audio_file:
                raise HTTPException(status_code=400, detail="Audio file is required for voice videos")
            
            result = await video_service.create_voice_video(
                user_id=int(user["id"]),
                audio_file=audio_file,
                avatar_id=avatar_id,
                title=title
            )
        else:
            # Text video creation
            text = data.get("text", "").strip() if is_json else data.get("text", "").strip()
            voice_id = data.get("voice_id", "1bd001e7e50f421d891986aad5158bc8")
            
            if not text:
                raise HTTPException(status_code=400, detail="Text is required for text videos")
            
            result = await video_service.create_text_video(
                user_id=int(user["id"]),
                text=text,
                avatar_id=avatar_id,
                title=title,
                voice_id=voice_id
            )
        
        if result.get("success"):
            return {
                "success": True,
                "message": f"{video_type.title()} video creation started successfully",
                "video_id": result.get("video_id"),
                "heygen_video_id": result.get("heygen_video_id"),
                "status": "processing"
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Video creation failed"))
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error submitting video: {str(e)}", "VideoCreation")
        raise HTTPException(status_code=500, detail=f"Error creating video: {str(e)}")

@router.get("/api/video-status/{video_id}")
async def check_video_status(request: Request, video_id: str):
    """Check video processing status - FIXED AUTHENTICATION"""
    try:
        user = get_current_user_fixed(request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        video_service = VideoService()
        status = await video_service.check_video_status(video_id, int(user["id"]))
        
        return {
            "success": True,
            "status": status.get("status", "unknown"),
            "video_url": status.get("video_url"),
            "thumbnail_url": status.get("thumbnail_url"),
            "duration": status.get("duration"),
            "progress": status.get("progress", 0)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error checking video status: {str(e)}", "VideoStatus")
        raise HTTPException(status_code=500, detail="Error checking video status")

# =============================================================================
# FIXED AVATAR MANAGEMENT FOR VIDEO CREATION
# =============================================================================

def get_user_avatars_standardized(user_id: int):
    """Get user avatars with standardized field names and proper error handling"""
    try:
        # CORRECTED QUERY - uses proper column names from your database
        avatars = execute_query(
            """
            SELECT id, user_id, name, avatar_image_url, heygen_avatar_id, 
                   created_at, updated_at, is_default, status
            FROM user_avatars 
            WHERE user_id = %s 
              AND (status IS NULL OR status != 'deleted')
              AND (avatar_image_url IS NOT NULL AND avatar_image_url != '')
              AND avatar_image_url NOT ILIKE '%placeholder%'
              AND avatar_image_url NOT ILIKE '%temp%'
            ORDER BY is_default DESC, created_at DESC
            """,
            (user_id,),
            fetch_all=True
        )
        
        # Process avatars with CONSISTENT field names
        processed_avatars = []
        if avatars:
            for avatar in avatars:
                avatar_dict = dict(avatar) if hasattr(avatar, '_asdict') else avatar
                
                processed_avatars.append({
                    'id': avatar_dict.get('id'),
                    'name': avatar_dict.get('name', 'Unnamed Avatar'),  # ← CORRECTED: 'name' not 'avatar_name'
                    'avatar_image_url': avatar_dict.get('avatar_image_url', ''),
                    'heygen_avatar_id': avatar_dict.get('heygen_avatar_id', ''),
                    'is_default': bool(avatar_dict.get('is_default', False)),
                    'status': avatar_dict.get('status', 'active')
                })
        
        log_info(f"✅ Retrieved {len(processed_avatars)} avatars for user {user_id}", "VideoRoutes")
        return processed_avatars
        
    except Exception as e:
        log_error(f"❌ Error getting user avatars: {e}", "VideoRoutes")
        return []

@router.get("/api/user-avatars")
async def get_user_avatars(request: Request):
    """Get user's avatars for video creation - FIXED with proper database schema"""
    try:
        user = get_current_user_fixed(request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Use the standardized avatar function
        processed_avatars = get_user_avatars_standardized(int(user["id"]))
        
        log_info(f"API returned {len(processed_avatars)} avatars for user {user['id']}", "VideoAPI")
        
        return {
            "success": True,
            "avatars": processed_avatars,
            "count": len(processed_avatars),
            "user_id": int(user["id"]),
            "debug_info": {
                "avatar_fields": list(processed_avatars[0].keys()) if processed_avatars else [],
                "query_method": "standardized_with_proper_schema"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"❌ Error in get_user_avatars API: {str(e)}", "VideoAPI")
        raise HTTPException(status_code=500, detail="Error getting avatars")

# =============================================================================
# UPDATED VIDEO ROUTES WITH CLOUDINARY URL SUPPORT
# =============================================================================

@router.get("/videos/{video_id}/download")
async def download_video(request: Request, video_id: str):
    """
    Download video with proper headers for direct download
    UPDATED: Now handles Cloudinary URLs from BackgroundFX
    """
    try:
        user = get_current_user_fixed(request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Get video from database directly (bypass VideoService for Cloudinary URLs)
        video = execute_query(
            "SELECT * FROM videos WHERE id = %s AND user_id = %s",
            (video_id, int(user["id"])),
            fetch_one=True
        )
        
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        log_info(f"User {user['username']} downloading video {video_id}", "VideoDownload")
        
        # Check if this is a Cloudinary URL (BackgroundFX video)
        video_path = video.get("video_path", "")
        
        if video_path and video_path.startswith("https://res.cloudinary.com/"):
            # This is a Cloudinary URL - handle directly with video optimization
            fresh_url = video_path
            
            # Add video optimization parameters for better browser compatibility
            if "?" not in fresh_url:
                fresh_url += "?f_auto,q_auto,c_limit,w_1920,h_1080"
            
            log_info(f"Cloudinary video detected: {fresh_url}", "VideoDownload")
        else:
            # This is a traditional video - use VideoService
            video_service = VideoService()
            fresh_url = video_service.get_fresh_video_url(video, user)
            if not fresh_url:
                raise HTTPException(status_code=404, detail="Video URL not available")
        
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

@router.get("/videos/{video_id}/play")
async def play_video(request: Request, video_id: str):
    """
    Play video - handles both local files and Cloudinary URLs
    NEW ENDPOINT for better video playback handling
    """
    try:
        user = get_current_user_fixed(request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Get video from database directly
        video = execute_query(
            "SELECT * FROM videos WHERE id = %s AND user_id = %s",
            (video_id, int(user["id"])),
            fetch_one=True
        )
        
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        log_info(f"User {user['username']} playing video {video_id}", "VideoPlay")
        
        # Check if this is a Cloudinary URL (BackgroundFX video)
        video_path = video.get("video_path", "")
        
        if video_path and video_path.startswith("https://res.cloudinary.com/"):
            # This is a Cloudinary URL - redirect directly with video optimization
            fresh_url = video_path
            
            # Add video optimization parameters for better browser compatibility
            if "?" not in fresh_url:
                fresh_url += "?f_auto,q_auto,c_limit,w_1920,h_1080"
            
            log_info(f"Cloudinary video playback: {fresh_url}", "VideoPlay")
        else:
            # This is a traditional video - use VideoService
            video_service = VideoService()
            fresh_url = video_service.get_fresh_video_url(video, user)
            if not fresh_url:
                raise HTTPException(status_code=404, detail="Video URL not available")
        
        # Redirect to the video URL for playback
        return RedirectResponse(url=fresh_url, status_code=302)
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error in video play endpoint: {str(e)}", "VideoPlay")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/videos/{video_id}")
async def get_video_details(request: Request, video_id: str):
    """
    Get video details without downloading
    """
    try:
        user = get_current_user_fixed(request)
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

@router.get("/api/videos")
async def get_user_videos_api(request: Request):
    """Get all videos for current user - API endpoint"""
    try:
        user = get_current_user_fixed(request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
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

@router.get("/voice-to-video")
async def voice_recording_page_fixed(request: Request):
    """Voice recording page - WORKING VERSION with proper avatar loading"""
    try:
        user = get_current_user_fixed(request)
        if not user:
            return RedirectResponse(url="/login", status_code=303)
        
        user_id = int(user["id"])
        username = user.get("username", "User")
        
        print(f"🎭 ENHANCED ROUTE: User {username} (ID: {user_id}) accessing voice-to-video")
        
        # WORKING AVATAR QUERY - Based on your diagnostic data
        try:
            # Your avatar uses 'name' column, not 'avatar_name'
            avatars = execute_query(
                """
                SELECT id, name, avatar_image_url, heygen_avatar_id, is_default, created_at
                FROM user_avatars 
                WHERE user_id = %s 
                ORDER BY created_at DESC
                """,
                (user_id,),
                fetch_all=True
            )
            
            print(f"🔍 Raw query result: {len(avatars) if avatars else 0} avatars found")
            
        except Exception as query_error:
            print(f"❌ Avatar query failed: {query_error}")
            avatars = []
        
        # Process avatars
        processed_avatars = []
        if avatars:
            for i, avatar in enumerate(avatars):
                try:
                    avatar_dict = dict(avatar)
                    
                    processed_avatar = {
                        'id': avatar_dict.get('id'),
                        'name': avatar_dict.get('name', f'Avatar {i+1}'),
                        'avatar_image_url': avatar_dict.get('avatar_image_url', '/static/images/default-avatar.jpg'),
                        'heygen_avatar_id': avatar_dict.get('heygen_avatar_id', ''),
                        'is_default': bool(avatar_dict.get('is_default', False))
                    }
                    
                    processed_avatars.append(processed_avatar)
                    print(f"✅ Processed avatar {i+1}: {processed_avatar['name']} - {processed_avatar['avatar_image_url']}")
                    
                except Exception as process_error:
                    print(f"❌ Failed to process avatar {i}: {process_error}")
                    continue
        
        # Add fallback if needed
        if not processed_avatars:
            print("⚠️ No avatars found, creating fallback")
            processed_avatars = [{
                'id': 'fallback',
                'name': 'Default Avatar',
                'avatar_image_url': '/static/images/default-avatar.jpg',
                'heygen_avatar_id': 'default',
                'is_default': True
            }]
        
        print(f"🎯 FINAL: Sending {len(processed_avatars)} avatars to template")
        
        # Template context
        context = {
            "request": request,
            "user": user,
            "username": username,
            "user_id": user_id,
            "avatars": processed_avatars,
            "avatar_count": len(processed_avatars),
            "debug_info": {
                "backend_status": "enhanced_diagnostics_working",
                "raw_avatar_count": len(avatars) if avatars else 0,
                "processed_avatar_count": len(processed_avatars),
                "user_id": user_id,
                "avatar_loading_log": [
                    f"Found {len(avatars) if avatars else 0} raw avatars",
                    f"Processed {len(processed_avatars)} avatars",
                    "Using name column (not avatar_name)",
                    "Enhanced route is working"
                ]
            }
        }
        
        return templates.TemplateResponse("voice_recording.html", context)
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR in enhanced voice-to-video route: {str(e)}")
        import traceback
        traceback.print_exc()
        return RedirectResponse(url="/dashboard", status_code=303)

@router.get("/api/user-avatars")
async def get_user_avatars_api(request: Request):
    """Get user's avatars for video creation - WORKING VERSION"""
    try:
        user = get_current_user_fixed(request)
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        user_id = int(user["id"])
        log_info(f"API request for user avatars: user {user_id}", "VideoAPI")
        
        # Get avatars using EXACT same query as admin panel (WORKING VERSION)
        avatars = []
        try:
            # Use exact admin panel query that works
            avatars_query = """
            SELECT id, avatar_name, avatar_image_url, avatar_id, heygen_avatar_id, is_default, created_at 
            FROM user_avatars 
            WHERE user_id = %s 
            ORDER BY created_at DESC
            """
            avatars = execute_query(avatars_query, (user_id,), fetch_all=True)
            log_info(f"Found {len(avatars) if avatars else 0} raw avatars using admin query", "VideoAPI")
            
        except Exception as e:
            log_error(f"Avatar query failed: {e}", "VideoAPI")
            return {"success": False, "error": f"Database query failed: {str(e)}"}
        
        # Process avatars
        processed_avatars = []
        if avatars:
            for i, avatar in enumerate(avatars):
                try:
                    # Handle different data formats
                    if hasattr(avatar, '_asdict'):
                        avatar_dict = avatar._asdict()
                    else:
                        avatar_dict = dict(avatar)
                    
                    # Use EXACT same field mapping as admin panel
                    processed_avatar = {
                        'id': avatar_dict.get('id'),
                        'name': avatar_dict.get('avatar_name', f'Avatar {i+1}'),  # admin uses 'avatar_name'
                        'avatar_image_url': avatar_dict.get('avatar_image_url', '/static/images/default-avatar.jpg'),
                        'heygen_avatar_id': avatar_dict.get('heygen_avatar_id', ''),  # This is the critical HeyGen ID
                        'avatar_id': avatar_dict.get('avatar_id', ''),  # Additional ID field from admin
                        'is_default': bool(avatar_dict.get('is_default', False)),
                        'created_at': avatar_dict.get('created_at', ''),
                        'status': 'active'  # Always active for video creation
                    }
                    
                    if processed_avatar['id'] and processed_avatar['name']:
                        processed_avatars.append(processed_avatar)
                        
                except Exception as process_error:
                    log_warning(f"Failed to process avatar {i}: {process_error}", "VideoAPI")
                    continue
        
        log_info(f"API returning {len(processed_avatars)} processed avatars", "VideoAPI")
        
        return {
            "success": True,
            "avatars": processed_avatars,
            "count": len(processed_avatars),
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Unexpected error in user-avatars API: {str(e)}", "VideoAPI")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/api/test-video-routes")
async def test_video_routes():
    """Test if video routes are loaded"""
    return {
        "status": "working",
        "message": "Video routes are properly loaded",
        "available_endpoints": [
            "/api/user-avatars",
            "/api/test-video-routes",
            "/voice-to-video"
        ]
    }

@router.get("/api/debug/voice-page-data/{user_id}")
async def debug_voice_page_data(request: Request, user_id: int):
    """Debug endpoint to check what data the voice page should receive"""
    try:
        user = get_current_user_fixed(request)
        if not user or int(user['id']) != user_id:
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        # Test exact same query as voice page
        avatars = execute_query(
            """
            SELECT id, user_id, name, avatar_image_url, heygen_avatar_id, 
                   created_at, is_default, status
            FROM user_avatars 
            WHERE user_id = %s 
              AND (status IS NULL OR status != 'deleted')
              AND (avatar_image_url IS NOT NULL AND avatar_image_url != '')
              AND avatar_image_url NOT ILIKE '%%placeholder%%'
            ORDER BY is_default DESC, created_at DESC
            """,
            (user_id,),
            fetch_all=True
        )
        
        # Process same as voice page
        processed_avatars = []
        if avatars:
            for avatar in avatars:
                avatar_dict = dict(avatar)
                processed_avatars.append({
                    'id': avatar_dict.get('id'),
                    'name': avatar_dict.get('name', 'Unnamed Avatar'),
                    'avatar_image_url': avatar_dict.get('avatar_image_url', ''),
                    'heygen_avatar_id': avatar_dict.get('heygen_avatar_id', ''),
                    'is_default': bool(avatar_dict.get('is_default', False))
                })
        
        return {
            "success": True,
            "user_id": user_id,
            "raw_avatar_count": len(avatars) if avatars else 0,
            "processed_avatar_count": len(processed_avatars),
            "avatars": processed_avatars,
            "raw_avatars": [dict(av) for av in avatars] if avatars else [],
            "query_executed": True,
            "user_authenticated": True
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# =============================================================================
# VOICE PROCESSING HELPERS
# =============================================================================

@router.get("/api/voices")
async def get_available_voices(request: Request):
    """Get available HeyGen voices for video creation"""
    try:
        user = get_current_user_fixed(request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Return a list of available voices
        # You can expand this with actual HeyGen voice API calls
        voices = [
            {
                "voice_id": "1bd001e7e50f421d891986aad5158bc8",
                "name": "Default Female Voice",
                "language": "en-US",
                "gender": "female"
            },
            {
                "voice_id": "2bd001e7e50f421d891986aad5158bc9",
                "name": "Default Male Voice", 
                "language": "en-US",
                "gender": "male"
            }
        ]
        
        return {
            "success": True,
            "voices": voices,
            "count": len(voices)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting voices: {str(e)}", "VideoAPI")
        raise HTTPException(status_code=500, detail="Error getting voices")

# =============================================================================
# VIDEO CREATION STATUS AND UTILITIES
# =============================================================================

@router.get("/api/creation-status")
async def get_video_creation_status(request: Request):
    """Get overall video creation system status"""
    try:
        user = get_current_user_fixed(request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Check user's video count and limits
        video_count = execute_query(
            "SELECT COUNT(*) as count FROM videos WHERE user_id = %s",
            (int(user["id"]),),
            fetch_one=True
        )
        
        current_videos = video_count['count'] if video_count else 0
        
        return {
            "success": True,
            "system_status": "operational",
            "user_videos": current_videos,
            "features": {
                "text_to_video": True,
                "voice_to_video": True,
                "avatar_selection": True,
                "video_download": True,
                "status_tracking": True,
                "hf_spaces_integration": True,
                "cloudinary_support": True,  # NEW
                "dashboard_api": True  # NEW
            },
            "limits": {
                "max_text_length": 10000,
                "max_audio_duration": 300,  # 5 minutes
                "supported_audio_formats": ["mp3", "wav", "m4a"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting creation status: {str(e)}", "VideoAPI")
        raise HTTPException(status_code=500, detail="Error getting status")

# =============================================================================
# DEBUG AND IMPROVED VIDEO CREATION ENDPOINTS
# =============================================================================

@router.get("/api/debug/avatar-system/{user_id}")
async def debug_avatar_system(request: Request, user_id: int):
    """Debug endpoint to check entire avatar system"""
    try:
        user = get_current_user_fixed(request)
        if not user or int(user['id']) != user_id:
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        # Test database connection
        db_test = execute_query("SELECT 1 as test", fetch_one=True)
        
        # Get raw avatar data
        raw_avatars = execute_query(
            "SELECT * FROM user_avatars WHERE user_id = %s",
            (user_id,),
            fetch_all=True
        )
        
        # Get processed avatar data
        processed_avatars = get_user_avatars_standardized(user_id)
        
        # Check table schema
        schema_query = execute_query(
            """
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'user_avatars'
            ORDER BY ordinal_position
            """,
            fetch_all=True
        )
        
        return {
            "success": True,
            "user_id": user_id,
            "database_connection": bool(db_test),
            "table_schema": [dict(col) for col in schema_query] if schema_query else [],
            "raw_avatar_count": len(raw_avatars) if raw_avatars else 0,
            "raw_avatars": [dict(av) for av in raw_avatars] if raw_avatars else [],
            "processed_avatar_count": len(processed_avatars),
            "processed_avatars": processed_avatars,
            "authentication_working": True,
            "endpoints_available": [
                "/api/user-avatars",
                "/api/create-video", 
                "/api/create-voice-video",
                "/voice-to-video"
            ]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "user_id": user_id
        }

# =============================================================================
# ALL VIDEOS PAGE ENDPOINT
# =============================================================================

@router.get("/videos")
async def videos_page(request: Request):
    """All Videos page - renders videos.html template"""
    try:
        # Get current user
        user = get_current_user_fixed(request)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        log_info(f"🎬 VIDEOS PAGE - User {user.get('username')} accessing videos page", "VideosPage")
        
        # Get user videos from database
        videos = execute_query(
            "SELECT * FROM videos WHERE user_id = %s ORDER BY created_at DESC",
            (int(user["id"]),),
            fetch_all=True
        )
        
        # Process videos for template
        processed_videos = []
        if videos:
            for video in videos:
                video_dict = dict(video)
                processed_videos.append({
                    'id': video_dict.get('id'),
                    'title': video_dict.get('title', 'Untitled Video'),
                    'status': video_dict.get('status', 'unknown'),
                    'created_at': video_dict.get('created_at'),
                    'video_path': video_dict.get('video_path'),
                    'audio_path': video_dict.get('audio_path'),
                    'thumbnail_url': video_dict.get('thumbnail_url'),
                    'duration': video_dict.get('duration'),
                    'description': video_dict.get('description'),
                    'format': video_dict.get('format', '16:9')
                })
        
        # Template context
        context = {
            "request": request,
            "user": user,
            "username": user.get("username", "User"),
            "is_admin": user.get("is_admin", False),
            "user_id": user["id"],
            "videos": processed_videos,
            "total_videos": len(processed_videos),
            "user_avatars": [],
            "avatar_count": 0,
            "credits_remaining": user.get("credits_remaining", 0),
            "max_credits": user.get("max_credits", 100),
            "max_videos_per_user": 7,
            "user_video_count": len(processed_videos),
            "vacation_mode": False,
            "video_limit_reached": False
        }
        
        log_info(f"🎬 VIDEOS PAGE: Rendering videos.html with {len(processed_videos)} videos", "VideosPage")
        return templates.TemplateResponse("videos.html", context)
        
    except Exception as e:
        log_error(f"❌ Error in videos page: {e}", "VideosPage")
        return RedirectResponse(url="/dashboard", status_code=302)

# =============================================================================
# IMPROVED VIDEO CREATION WITH PROPER AVATAR VALIDATION
# =============================================================================

@router.post("/api/create-video")
async def create_video_from_text_improved(request: Request):
    """Create video from text - FIXED with proper avatar validation"""
    try:
        user = get_current_user_fixed(request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Get form data
        form_data = await request.form()
        text = form_data.get("text", "").strip()
        avatar_id = form_data.get("avatar_id", "").strip()
        heygen_avatar_id = form_data.get("heygen_avatar_id", "").strip()
        title = form_data.get("title", "").strip()
        voice_id = form_data.get("voice_id", "1bd001e7e50f421d891986aad5158bc8")
        
        log_info(f"Video creation request - Text: {text[:50]}..., Avatar ID: {avatar_id}, HeyGen ID: {heygen_avatar_id}", "VideoCreation")
        
        if not text:
            raise HTTPException(status_code=400, detail="Text is required")
        
        if not avatar_id and not heygen_avatar_id:
            raise HTTPException(status_code=400, detail="Avatar selection is required")
        
        # Validate avatar belongs to user
        user_avatars = get_user_avatars_standardized(int(user["id"]))
        selected_avatar = None
        
        for avatar in user_avatars:
            if str(avatar['id']) == str(avatar_id) or str(avatar['heygen_avatar_id']) == str(heygen_avatar_id):
                selected_avatar = avatar
                break
        
        if not selected_avatar:
            log_error(f"Avatar validation failed - ID: {avatar_id}, HeyGen: {heygen_avatar_id}", "VideoCreation")
            raise HTTPException(status_code=400, detail="Invalid avatar selection")
        
        if not title:
            title = f"Text Video - {text[:30]}..."
        
        log_info(f"✅ User {user.get('username')} creating text video with avatar: {selected_avatar['name']}", "VideoCreation")
        
        # Use the HeyGen avatar ID for video creation
        final_avatar_id = selected_avatar['heygen_avatar_id'] or selected_avatar['id']
        
        # Create video using your video service
        video_service = VideoService()
        result = await video_service.create_text_video(
            user_id=int(user["id"]),
            text=text,
            avatar_id=final_avatar_id,
            title=title,
            voice_id=voice_id
        )
        
        if result.get("success"):
            log_info(f"✅ Text video creation started successfully for user {user['id']}", "VideoCreation")
            return {
                "success": True,
                "message": "Video creation started successfully",
                "video_id": result.get("video_id"),
                "heygen_video_id": result.get("heygen_video_id"),
                "status": "processing",
                "avatar_name": selected_avatar['name'],
                "estimated_duration": "2-5 minutes"
            }
        else:
            log_error(f"❌ Video creation failed: {result.get('error')}", "VideoCreation")
            raise HTTPException(status_code=500, detail=result.get("error", "Video creation failed"))
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"❌ Error creating video from text: {str(e)}", "VideoCreation")
        raise HTTPException(status_code=500, detail=f"Error creating video: {str(e)}")

@router.post("/api/create-voice-video")
async def create_video_from_voice_improved(request: Request):
    """Create video from voice recording - FIXED with proper avatar validation"""
    try:
        user = get_current_user_fixed(request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Get form data
        form_data = await request.form()
        audio_file = form_data.get("audio")
        avatar_id = form_data.get("avatar_id", "").strip()
        heygen_avatar_id = form_data.get("heygen_avatar_id", "").strip()
        title = form_data.get("title", "").strip()
        
        log_info(f"Voice video creation request - Avatar ID: {avatar_id}, HeyGen ID: {heygen_avatar_id}", "VideoCreation")
        
        if not audio_file:
            raise HTTPException(status_code=400, detail="Audio file is required")
        
        if not avatar_id and not heygen_avatar_id:
            raise HTTPException(status_code=400, detail="Avatar selection is required")
        
        # Validate avatar belongs to user
        user_avatars = get_user_avatars_standardized(int(user["id"]))
        selected_avatar = None
        
        for avatar in user_avatars:
            if str(avatar['id']) == str(avatar_id) or str(avatar['heygen_avatar_id']) == str(heygen_avatar_id):
                selected_avatar = avatar
                break
        
        if not selected_avatar:
            log_error(f"Avatar validation failed - ID: {avatar_id}, HeyGen: {heygen_avatar_id}", "VideoCreation")
            raise HTTPException(status_code=400, detail="Invalid avatar selection")
        
        if not title:
            title = f"Voice Video - {user.get('username')}"
        
        log_info(f"✅ User {user.get('username')} creating voice video with avatar: {selected_avatar['name']}", "VideoCreation")
        
        # Use the HeyGen avatar ID for video creation
        final_avatar_id = selected_avatar['heygen_avatar_id'] or selected_avatar['id']
        
        # Create video using your video service
        video_service = VideoService()
        result = await video_service.create_voice_video(
            user_id=int(user["id"]),
            audio_file=audio_file,
            avatar_id=final_avatar_id,
            title=title
        )
        
        if result.get("success"):
            log_info(f"✅ Voice video creation started successfully for user {user['id']}", "VideoCreation")
            return {
                "success": True,
                "message": "Voice video creation started successfully",
                "video_id": result.get("video_id"),
                "heygen_video_id": result.get("heygen_video_id"),
                "status": "processing",
                "avatar_name": selected_avatar['name'],
                "estimated_duration": "3-7 minutes"
            }
        else:
            log_error(f"❌ Voice video creation failed: {result.get('error')}", "VideoCreation")
            raise HTTPException(status_code=500, detail=result.get("error", "Voice video creation failed"))
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"❌ Error creating voice video: {str(e)}", "VideoCreation")
        raise HTTPException(status_code=500, detail=f"Error creating video: {str(e)}")