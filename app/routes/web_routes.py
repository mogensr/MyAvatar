# WEB ROUTES FOR MYAVATAR - CLEANED VERSION (NO DUPLICATES, FIXED SYNTAX)

import os
import uuid
import requests
import re
import tempfile
import base64
import time
import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, Depends, HTTPException, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta
from typing import Optional
from ..db.database import execute_query
from ..auth.authentication import (
    get_current_user, authenticate_user, authenticate_user_by_email,
    create_access_token, get_password_hash, is_admin
)
from ..logger.log_handler import log_info, log_error, log_warning
from app.api.heygen import create_video_from_text
import json
import os
from app.auth.authentication import SECRET_KEY, ALGORITHM

# UTILITIES
def secure_filename(filename):
    filename = filename.replace('/', '').replace('\\', '')
    filename = re.sub(r'[^a-zA-Z0-9._-]', '', filename)
    filename = re.sub(r'\.+', '.', filename)
    filename = filename.strip('. ')
    if not filename or len(filename) > 100:
        return f"file_{uuid.uuid4().hex[:8]}.jpg"
    return filename

# ROUTER SETUP
router = APIRouter(prefix="", tags=["web"])
templates = Jinja2Templates(directory="templates")

# ROOT ROUTE - REDIRECT TO DASHBOARD
@router.get("/", response_class=RedirectResponse, status_code=302)
async def root():
    return "/dashboard"

# LOGOUT ROUTE
@router.get("/logout")
async def logout(request: Request):
    log_info("User logout requested")
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")
    return response

# ============================================================================  
# DIAGNOSTIC ROUTE - ONLY FOR TROUBLESHOOTING
# ============================================================================  

@router.get("/auth-diagnostics", response_class=JSONResponse)
async def auth_diagnostics(request: Request):
    """Diagnostic route to troubleshoot authentication (secure - doesn't expose secrets)"""
    # Only allow access in development mode
    is_production = os.environ.get("PRODUCTION", "false").lower() == "true"
    if is_production:
        return JSONResponse({"error": "Diagnostics disabled in production"}, status_code=403)
        
    try:
        # Get database info
        db_type = "PostgreSQL" if os.environ.get("DATABASE_URL") else "SQLite"
        
        # Check if JWT secret is properly set
        jwt_status = "Environment variable set" if os.environ.get("JWT_SECRET_KEY") else "Using default random value"
        
        # Check templates directory
        templates_path = os.path.join(os.getcwd(), "templates")
        templates_exists = os.path.exists(templates_path)
        template_files = os.listdir(templates_path) if templates_exists else []
        login_template_exists = os.path.exists(os.path.join(templates_path, "portal/login.html"))
        
        # Collect diagnostic information without exposing secrets
        diagnostics = {
            "database": {
                "type": db_type,
                "connection": "Configured" if db_type == "PostgreSQL" else "Using SQLite fallback"
            },
            "jwt": {
                "status": jwt_status,
                "algorithm": ALGORITHM
            },
            "templates": {
                "directory_exists": templates_exists,
                "num_templates": len(template_files) if templates_exists else 0,
                "login_template_exists": login_template_exists
            },
            "env": {
                "deployment_environment": os.environ.get("DEPLOYMENT_ENVIRONMENT", "not set"),
                "production": is_production
            }
        }
        
        log_info("Auth diagnostics requested", "Diagnostics")
        return JSONResponse(diagnostics)
    except Exception as e:
        log_error(f"Error in diagnostics: {str(e)}", "Diagnostics", e)
        return JSONResponse({"error": "Diagnostic error", "message": str(e)}, status_code=500)

# ============================================================================  
# LOGIN ROUTES  
# ============================================================================  

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page"""
    return templates.TemplateResponse("portal/login.html", {"request": request})

@router.post("/login")
async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    """Process login"""
    try:
        user = authenticate_user(username, password)
        if not user:
            return templates.TemplateResponse(
                "portal/login.html",
                {
                    "request": request,
                    "error": "Invalid username or password"
                }
            )
        
        access_token = create_access_token(data={"sub": user["username"]})
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(key="access_token", value=access_token, httponly=True)
        
        log_info(f"User {username} logged in successfully", "Web")
        return response
        
    except Exception as e:
        log_error(f"Login error: {str(e)}", "Web", e)
        return templates.TemplateResponse(
            "portal/login.html",
            {
                "request": request,
                "error": "Login error"
            }
        )
# ============================================================================  
# REGISTRATION ROUTES  
# ============================================================================  

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Registration page"""
    return templates.TemplateResponse("portal/register.html", {"request": request})

@router.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    """Process registration"""
    try:
        log_info(f"Registration attempt: username={username}, email={email}", "Web")

        existing_user = execute_query(
            "SELECT * FROM users WHERE username = ? OR email = ?",
            (username, email),
            fetch_one=True
        )

        if existing_user:
            log_error(f"Registration failed - user exists: username={username}, email={email}", "Web")
            return templates.TemplateResponse(
                "portal/register.html",
                {
                    "request": request,
                    "error": "Username or email already exists"
                }
            )

        hashed_password = get_password_hash(password)
        execute_query(
            "INSERT INTO users (username, email, hashed_password, created_at) VALUES (?, ?, ?, ?)",
            (username, email, hashed_password, datetime.now().isoformat())
        )

        log_info(f"User {username} registered successfully", "Web")

        return templates.TemplateResponse(
            "portal/login.html",
            {
                "request": request,
                "success": "Registration successful. Please log in."
            }
        )

    except Exception as e:
        log_error("Registration error", "Web", e)
        return templates.TemplateResponse(
            "portal/register.html",
            {
                "request": request,
                "error": "Registration error"
            }
        )
# ============================================================================
# DASHBOARD ROUTE - WITH REAL STATISTICS
# ============================================================================

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """
    User dashboard - With real statistics instead of mock data
    """
    user = get_current_user(request)
    if not user:
        log_info("Unauthenticated dashboard access attempt", "Web")
        return RedirectResponse(url="/login", status_code=303)

    log_info(f"Dashboard access by user {user.get('username')}", "Web")

    try:
        videos = execute_query(
            "SELECT * FROM videos WHERE user_id = ? ORDER BY created_at DESC",
            (user["id"],),
            fetch_all=True
        )

        avatars = execute_query(
            "SELECT * FROM avatars WHERE user_id = ?",
            (user["id"],),
            fetch_all=True
        )

        log_info(f"Dashboard data loaded: {len(videos) if videos else 0} videos, {len(avatars) if avatars else 0} avatars", "Web")

        video_list = []
        total_duration = 0
        total_views = 0
        total_shares = 0

        for v in videos:
            try:
                video_dict = dict(v) if isinstance(v, dict) else {key: v[key] for key in v.keys()}
                safe_video = {
                    'id': video_dict.get('id'),
                    'title': video_dict.get('title', 'Untitled'),
                    'status': video_dict.get('status', 'unknown'),
                    'created_at': video_dict.get('created_at').strftime('%m/%d/%Y') if video_dict.get('created_at') else 'Unknown',
                    'video_path': video_dict.get('video_path'),
                    'thumbnail_url': video_dict.get('thumbnail_url'),
                    'duration': video_dict.get('duration'),
                    'heygen_video_id': video_dict.get('heygen_video_id'),
                    'video_format': '16:9'
                }
                video_list.append(safe_video)
                if video_dict.get('duration'):
                    total_duration += float(video_dict['duration'])
            except Exception as e:
                log_error(f"Error processing video {v}: {e}", "Web")
                continue

        avatar_list = [dict(a) if isinstance(a, dict) else {key: a[key] for key in a.keys()} for a in avatars]

        total_videos = len(video_list)
        total_duration_hours = round(total_duration / 3600, 1) if total_duration > 0 else 0

        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "user": user,
                "username": user.get("username", ""),
                "is_admin": user.get("is_admin", 0),
                "avatar_id": user.get("avatar_id", ""),
                "user_id": user.get("id", 0),
                "api_key": user.get("api_key", "") or os.getenv("HEYGEN_API_KEY", ""),
                "videos": video_list,
                "avatars": avatar_list,
                "total_videos": total_videos,
                "total_duration": f"{total_duration_hours}h" if total_duration_hours > 0 else "0h",
                "total_views": total_views,
                "total_shares": total_shares,
            }
        )
    except Exception as e:
        log_error(f"Dashboard error for user {user.get('username')}", "Web", e)
        return templates.TemplateResponse(
            "portal/login.html",
            {
                "request": request,
                "error": "Dashboard error"
            }
        )
# ============================================================================
# VIDEO CREATION PAGES - VOICE RECORDING & TEXT-TO-VIDEO
# ============================================================================

@router.get("/voice-recording", response_class=HTMLResponse)
async def voice_recording_page(request: Request):
    """
    Voice recording page for creating videos from audio
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    log_info(f"Voice recording page accessed by user {user.get('username')}", "Web")

    avatars = execute_query(
        "SELECT * FROM avatars WHERE user_id = ?",
        (user["id"],),
        fetch_all=True
    )

    avatar_list = [dict(a) if isinstance(a, dict) else {key: a[key] for key in a.keys()} for a in avatars]

    return templates.TemplateResponse(
        "voice_recording.html",
        {
            "request": request,
            "user": user,
            "username": user.get("username", ""),
            "is_admin": user.get("is_admin", 0),
            "avatars": avatar_list
        }
    )


@router.get("/text-to-video", response_class=HTMLResponse)
async def text_to_video_page(request: Request):
    """
    Text to video creation page
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    log_info(f"Text-to-video page accessed by user {user.get('username')}", "Web")

    avatars = execute_query(
        "SELECT * FROM avatars WHERE user_id = ?",
        (user["id"],),
        fetch_all=True
    )

    avatar_list = [dict(a) if isinstance(a, dict) else {key: a[key] for key in a.keys()} for a in avatars]

    return templates.TemplateResponse(
        "text_video_component.html",
        {
            "request": request,
            "user": user,
            "username": user.get("username", ""),
            "is_admin": user.get("is_admin", 0),
            "avatars": avatar_list
        }
    )

# ============================================================================
# HEYGEN WEBHOOK ROUTE
# ============================================================================

@router.post("/api/heygen/webhook")
async def heygen_webhook(request: Request):
    """Handle HeyGen video completion webhook - All Events"""
    try:
        log_info("HeyGen webhook received", "Webhook")
        data = await request.json()
        log_info(f"HeyGen webhook data: {data}", "Webhook")

        video_id = data.get("video_id") or data.get("data", {}).get("video_id")
        status = data.get("status") or data.get("event", "").replace("video.", "")
        video_url = data.get("video_url") or data.get("data", {}).get("video_url")
        event = data.get("event", "unknown")

        if not video_id:
            log_error("No video_id in webhook data", "Webhook")
            return JSONResponse(status_code=400, content={"error": "Missing video_id"})

        log_info(f"Processing webhook - Event: {event}, Video: {video_id}, Status: {status}", "Webhook")

        if event in ["video.completed", "completed"] or status == "completed":
            if video_url:
                execute_query(
                    "UPDATE videos SET status = ?, video_path = ? WHERE heygen_video_id = ?",
                    ("completed", video_url, video_id)
                )
                log_info(f"Video completed and DB updated: {video_id}", "Webhook")
            else:
                log_error(f"Video completed but no URL provided: {video_id}", "Webhook")

        elif event in ["video.failed", "failed"] or status in ["failed", "error"]:
            execute_query(
                "UPDATE videos SET status = ? WHERE heygen_video_id = ?",
                ("failed", video_id)
            )
            log_error(f"Video failed: {video_id}", "Webhook")

        elif event in ["video.processing", "processing"] or status == "processing":
            execute_query(
                "UPDATE videos SET status = ? WHERE heygen_video_id = ?",
                ("processing", video_id)
            )
            log_info(f"Video processing status updated: {video_id}", "Webhook")

        else:
            if status:
                execute_query(
                    "UPDATE videos SET status = ? WHERE heygen_video_id = ?",
                    (status, video_id)
                )
            log_info(f"Unknown event/status: {event}/{status} for video: {video_id}", "Webhook")

        return JSONResponse(content={"status": "success", "message": f"Webhook processed: {event}"})

    except Exception as e:
        log_error(f"HeyGen webhook error: {e}", "Webhook", e)
        return JSONResponse(status_code=500, content={"error": "Webhook processing failed"})
# ============================================================================
# VIDEO CREATION FROM AUDIO - CLOUDINARY + HEYGEN
# ============================================================================

@router.post("/api/create-video")
async def create_video_from_audio(
    request: Request,
    audio: UploadFile = File(...),
    title: str = Form(...),
    avatar_id: str = Form(...),
    description: str = Form(None)
):
    user = get_current_user(request)
    if not user:
        log_error("Unauthorized video creation attempt", "API")
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    log_info(f"Video creation request by user {user['username']}: title='{title}', avatar_id={avatar_id}", "API")
    temp_audio_path = None
    try:
        heygen_api_key = os.getenv("HEYGEN_API_KEY")
        if not heygen_api_key:
            log_error("HeyGen API key not configured", "API")
            return JSONResponse(status_code=500, content={"error": "HeyGen API key not configured"})

        avatar = execute_query(
            "SELECT * FROM avatars WHERE id = ? AND user_id = ?",
            (avatar_id, user["id"]),
            fetch_one=True
        )
        if not avatar:
            log_error(f"Avatar not found: {avatar_id}", "API")
            return JSONResponse(status_code=400, content={"error": "Avatar not found"})

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
            audio_content = await audio.read()
            temp_audio.write(audio_content)
            temp_audio_path = temp_audio.name

        upload_result = cloudinary.uploader.upload(
            temp_audio_path,
            resource_type="video",
            format="m4a",
            flags="audio_codec:aac",
            audio_codec="aac",
            public_id=f"myavatar_audio_{user['id']}_{int(time.time())}"
        )
        cloudinary_url = upload_result.get('secure_url')
        if temp_audio_path:
            os.unlink(temp_audio_path)

        heygen_avatar_id = avatar.get("heygen_avatar_id")
        if not heygen_avatar_id:
            return JSONResponse(status_code=400, content={"error": "Avatar has no HeyGen ID"})

        payload = {
            "video_inputs": [
                {
                    "character": {"type": "avatar", "avatar_id": heygen_avatar_id, "avatar_style": "normal"},
                    "voice": {"type": "audio", "audio_url": cloudinary_url},
                    "background": {"type": "color", "value": "#ffffff"}
                }
            ],
            "dimension": {"width": 1920, "height": 1080},
            "aspect_ratio": "16:9",
            "test": False
        }

        headers = {"X-Api-Key": heygen_api_key, "Content-Type": "application/json"}
        response = requests.post("https://api.heygen.com/v2/video/generate", json=payload, headers=headers)
        if response.status_code != 200:
            return JSONResponse(status_code=400, content={"error": "HeyGen API error"})

        result = response.json()
        video_id = result.get("data", {}).get("video_id")
        if not video_id:
            return JSONResponse(status_code=500, content={"error": "No video ID returned from HeyGen"})

        execute_query(
            """
            INSERT INTO videos (user_id, title, avatar_id, audio_path, heygen_video_id, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user["id"], title, avatar_id, cloudinary_url, video_id, "processing", datetime.now().isoformat())
        )

        return JSONResponse(content={
            "success": True,
            "video_id": video_id,
            "message": "Video creation started successfully"
        })

    except Exception as e:
        log_error(f"Error creating video: {e}", "API", e)
        if temp_audio_path:
            try:
                os.unlink(temp_audio_path)
            except:
                pass
        return JSONResponse(status_code=500, content={"error": "Internal server error"})
# ============================================================================
# VIDEO CREATION FROM AUDIO (Cloudinary + HeyGen Integration)
# ============================================================================

@router.post("/api/create-video")
async def create_video_from_audio(
    request: Request,
    audio: UploadFile = File(...),
    title: str = Form(...),
    avatar_id: str = Form(...),
    description: str = Form(None)
):
    user = get_current_user(request)
    if not user:
        log_error("Unauthorized video creation attempt", "API")
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    log_info(f"Video creation request by {user['username']}: title='{title}', avatar_id={avatar_id}", "API")

    temp_audio_path = None
    try:
        heygen_api_key = os.getenv("HEYGEN_API_KEY")
        if not heygen_api_key:
            return JSONResponse(status_code=500, content={"error": "HeyGen API key not configured"})

        avatar = execute_query(
            "SELECT * FROM avatars WHERE id = ? AND user_id = ?",
            (avatar_id, user["id"]),
            fetch_one=True
        )
        if not avatar:
            return JSONResponse(status_code=400, content={"error": "Avatar not found"})

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
            content = await audio.read()
            temp_audio.write(content)
            temp_audio_path = temp_audio.name

        upload_result = cloudinary.uploader.upload(
            temp_audio_path,
            resource_type="video",
            format="m4a",
            flags="audio_codec:aac",
            audio_codec="aac",
            public_id=f"myavatar_audio_{user['id']}_{int(time.time())}"
        )
        cloudinary_url = upload_result.get('secure_url')

        if temp_audio_path:
            os.unlink(temp_audio_path)
            temp_audio_path = None

        heygen_avatar_id = avatar.get("heygen_avatar_id")
        if not heygen_avatar_id:
            return JSONResponse(status_code=400, content={"error": "Avatar has no HeyGen ID"})

        payload = {
            "video_inputs": [
                {
                    "character": {
                        "type": "avatar",
                        "avatar_id": heygen_avatar_id,
                        "avatar_style": "normal"
                    },
                    "voice": {
                        "type": "audio",
                        "audio_url": cloudinary_url
                    },
                    "background": {
                        "type": "color",
                        "value": "#ffffff"
                    }
                }
            ],
            "dimension": {"width": 1920, "height": 1080},
            "aspect_ratio": "16:9",
            "test": False
        }

        headers = {"X-Api-Key": heygen_api_key, "Content-Type": "application/json"}
        response = requests.post("https://api.heygen.com/v2/video/generate", json=payload, headers=headers, timeout=30)

        if response.status_code == 200:
            res_data = response.json()
            video_id = res_data.get("data", {}).get("video_id")
            if video_id:
                try:
                    execute_query(
                        """
                        INSERT INTO videos (user_id, title, avatar_id, audio_path, heygen_video_id, status, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (user["id"], title, avatar_id, cloudinary_url, video_id, "processing", datetime.now().isoformat())
                    )
                except:
                    pass
                return JSONResponse(content={"success": True, "video_id": video_id, "message": "Video creation started successfully"})
        else:
            return JSONResponse(status_code=400, content={"error": "HeyGen API error"})

    except Exception as e:
        log_error(f"Create video error: {e}", "API", e)
        if temp_audio_path:
            try:
                os.unlink(temp_audio_path)
            except:
                pass
        return JSONResponse(status_code=500, content={"error": "Internal server error"})
# ============================================================================
# TEXT-TO-VIDEO CREATION ROUTE (HeyGen Voice Integration)
# ============================================================================

@router.post("/api/create-text-video")
async def create_video_from_text_input(
    request: Request,
    title: str = Form(...),
    avatar_id: str = Form(...),
    text: str = Form(...),
    description: str = Form(None),
    format: str = Form("16:9")
):
    log_info(f"[Video] Text-to-video request - Title: '{title}', Avatar: '{avatar_id}'", "Video")

    user = get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    try:
        user_data = execute_query(
            "SELECT heygen_voice_id FROM users WHERE id = ?",
            (user["id"],),
            fetch_one=True
        )
        heygen_voice_id = user_data.get("heygen_voice_id") if user_data else None

        if not heygen_voice_id:
            return JSONResponse(status_code=400, content={"error": "No voice assigned. Please contact admin."})

        heygen_api_key = os.getenv("HEYGEN_API_KEY")
        if not heygen_api_key:
            return JSONResponse(status_code=500, content={"error": "HeyGen API key not configured"})

        avatar = execute_query(
            "SELECT * FROM avatars WHERE id = ? AND user_id = ?",
            (avatar_id, user["id"]),
            fetch_one=True
        )
        if not avatar:
            return JSONResponse(status_code=400, content={"error": "Avatar not found"})

        heygen_avatar_id = avatar.get("heygen_avatar_id")
        if not heygen_avatar_id:
            return JSONResponse(status_code=400, content={"error": "Avatar has no HeyGen ID"})

        heygen_result = create_video_from_text(
            api_key=heygen_api_key,
            avatar_id=heygen_avatar_id,
            text=text,
            video_format=format,
            voice_id=heygen_voice_id
        )

        if heygen_result.get("success"):
            video_id = heygen_result.get("video_id")
            try:
                execute_query(
                    """
                    INSERT INTO videos (user_id, title, avatar_id, audio_path, heygen_video_id, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user["id"], title, avatar_id, f"voice_{heygen_voice_id}", video_id, "processing", datetime.now().isoformat())
                )
            except:
                pass

            return JSONResponse(content={
                "success": True,
                "video_id": video_id,
                "message": "Video creation started with your personalized voice"
            })

        else:
            return JSONResponse(status_code=400, content={"error": heygen_result.get("error", "Unknown HeyGen error")})

    except Exception as e:
        log_error(f"[Video] Error creating text-to-video: {e}", "Video", e)
        return JSONResponse(status_code=500, content={"error": "Internal server error"})
# ============================================================================
# CHECK VIDEO STATUS ROUTE
# ============================================================================

@router.get("/api/video-status/{video_id}")
async def check_video_status(request: Request, video_id: str):
    """Check video processing status from HeyGen"""
    user = get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    log_info(f"Video status check by user {user['username']} for video_id: {video_id}", "API")

    try:
        video = execute_query(
            "SELECT * FROM videos WHERE heygen_video_id = ? AND user_id = ?",
            (video_id, user["id"]),
            fetch_one=True
        )

        if not video:
            return JSONResponse(status_code=404, content={"error": "Video not found"})

        heygen_api_key = os.getenv("HEYGEN_API_KEY")
        if not heygen_api_key:
            return JSONResponse(status_code=500, content={"error": "HeyGen API key not configured"})

        headers = {"X-Api-Key": heygen_api_key}
        status_url = f"https://api.heygen.com/v1/video_status.get?video_id={video_id}"

        response = requests.get(status_url, headers=headers)

        if response.status_code == 200:
            status_data = response.json()

            if status_data.get("code") == 100:
                data = status_data.get("data", {})
                status = data.get("status")
                video_url = data.get("video_url")

                if status == "completed" and video_url:
                    execute_query(
                        "UPDATE videos SET status = ?, video_path = ? WHERE heygen_video_id = ?",
                        ("completed", video_url, video_id)
                    )
                elif status == "failed":
                    execute_query(
                        "UPDATE videos SET status = ? WHERE heygen_video_id = ?",
                        ("failed", video_id)
                    )

                return JSONResponse(content={
                    "status": status,
                    "video_url": video_url,
                    "progress": data.get("progress", 0)
                })

        return JSONResponse(status_code=400, content={"error": "Failed to get video status"})

    except Exception as e:
        log_error(f"Error checking video status: {e}", "API", e)
        return JSONResponse(status_code=500, content={"error": "Internal server error"})
# ============================================================================
# ADMIN USERS PAGE
# ============================================================================

@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users(request: Request):
    """Admin users page"""
    user = get_current_user(request)
    if not user or not is_admin(request):
        log_error(f"Unauthorized admin access attempt by {user.get('username') if user else 'anonymous'}", "Admin")
        return RedirectResponse(url="/login", status_code=303)

    log_info(f"Admin users page accessed by {user['username']}", "Admin")

    users = execute_query(
        "SELECT * FROM users ORDER BY created_at DESC",
        fetch_all=True
    )

    return templates.TemplateResponse(
        "portal/admin_users.html",
        {
            "request": request,
            "users": users
        }
    )
# ============================================================================
# ADMIN DASHBOARD PAGE
# ============================================================================

@router.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Admin dashboard"""
    user = get_current_user(request)
    if not user or not is_admin(request):
        return RedirectResponse(url="/login", status_code=303)

    log_info(f"Admin dashboard accessed by {user['username']}", "Admin")

    user_count = execute_query(
        "SELECT COUNT(*) as count FROM users",
        fetch_one=True
    )

    video_count = execute_query(
        "SELECT COUNT(*) as count FROM videos",
        fetch_one=True
    )

    avatar_count = execute_query(
        "SELECT COUNT(*) as count FROM avatars",
        fetch_one=True
    )

    return templates.TemplateResponse(
        "portal/admin_dashboard.html",
        {
            "request": request,
            "user_count": user_count["count"] if user_count else 0,
            "video_count": video_count["count"] if video_count else 0,
            "avatar_count": avatar_count["count"] if avatar_count else 0
        }
    )
# ============================================================================
# ADMIN CREATE USER (GET + POST)
# ============================================================================

@router.get("/admin/create-user", response_class=HTMLResponse)
async def admin_create_user_page(request: Request):
    """Admin create user page"""
    user = get_current_user(request)
    if not user or not is_admin(request):
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse("portal/admin_create_user.html", {"request": request})


@router.post("/admin/create-user")
async def admin_create_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    is_admin_user: bool = Form(False),
    api_key: str = Form(None)
):
    """Admin create user"""
    user = get_current_user(request)
    if not user or not is_admin(request):
        return RedirectResponse(url="/login", status_code=303)

    try:
        log_info(f"Admin {user['username']} creating user: {username}", "Admin")

        existing_user = execute_query(
            "SELECT * FROM users WHERE username = ? OR email = ?",
            (username, email),
            fetch_one=True
        )

        if existing_user:
            return templates.TemplateResponse(
                "portal/admin_create_user.html",
                {
                    "request": request,
                    "error": "Username or email already exists"
                }
            )

        hashed_password = get_password_hash(password)
        execute_query(
            "INSERT INTO users (username, email, hashed_password, created_at, is_admin, api_key) VALUES (?, ?, ?, ?, ?, ?)",
            (username, email, hashed_password, datetime.now().isoformat(), is_admin_user, api_key)
        )

        log_info(f"Admin {user['username']} created user {username} successfully", "Admin")
        return RedirectResponse(url="/admin/users", status_code=303)

    except Exception as e:
        log_error("Admin create user error", "Admin", e)
        return templates.TemplateResponse(
            "portal/admin_create_user.html",
            {
                "request": request,
                "error": "Error creating user"
            }
        )
# ============================================================================
# ADMIN EDIT USER (GET + POST)
# ============================================================================

@router.get("/admin/edit-user/{user_id}", response_class=HTMLResponse)
async def admin_edit_user_page(request: Request, user_id: int):
    """Admin edit user page"""
    user = get_current_user(request)
    if not user or not is_admin(request):
        return RedirectResponse(url="/login", status_code=303)

    try:
        user_to_edit = execute_query(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
            fetch_one=True
        )

        if not user_to_edit:
            return RedirectResponse(url="/admin/users?error=user_not_found", status_code=303)

        return templates.TemplateResponse("portal/admin_edit_user.html", {
            "request": request,
            "user": user,
            "user_to_edit": user_to_edit,
            "title": f"Edit User: {user_to_edit['username']}"
        })
    except Exception as e:
        log_error(f"Error in admin_edit_user_page: {e}", "Admin", e)
        return RedirectResponse(url="/admin/users?error=system_error", status_code=303)


@router.post("/admin/edit-user/{user_id}")
async def admin_edit_user_submit(request: Request, user_id: int):
    """Handle admin edit user form submission"""
    user = get_current_user(request)
    if not user or not is_admin(request):
        return RedirectResponse(url="/login", status_code=303)

    try:
        form = await request.form()
        username = form.get("username", "").strip()
        email = form.get("email", "").strip()
        is_premium = 1 if form.get("is_premium") == "on" else 0
        is_admin_user = 1 if form.get("is_admin") == "on" else 0

        execute_query(
            """
            UPDATE users 
            SET username = ?, email = ?, is_premium = ?, is_admin = ?
            WHERE id = ?
            """,
            (username, email, is_premium, is_admin_user, user_id)
        )

        log_info(f"Admin {user['username']} updated user {username} successfully", "Admin")
        return RedirectResponse(url=f"/admin/users?success=user_updated", status_code=303)

    except Exception as e:
        log_error(f"Error updating user: {e}", "Admin", e)
        return RedirectResponse(url=f"/admin/edit-user/{user_id}?error=update_failed", status_code=303)

# ============================================================================
# ADMIN MANAGE AVATARS PAGE
# ============================================================================

@router.get("/admin/manage-avatars/{user_id}", response_class=HTMLResponse)
async def admin_manage_avatars_page(request: Request, user_id: int):
    """Admin manage user avatars page"""
    user = get_current_user(request)
    if not user or not is_admin(request):
        return RedirectResponse(url="/login", status_code=303)

    try:
        user_to_manage = execute_query(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
            fetch_one=True
        )

        if not user_to_manage:
            return RedirectResponse(url="/admin/users?error=user_not_found", status_code=303)

        raw_avatars = execute_query(
            "SELECT * FROM avatars WHERE user_id = ?",
            (user_id,),
            fetch_all=True
        )

        avatars = []
        for avatar in raw_avatars:
            avatar_dict = dict(avatar) if isinstance(avatar, dict) else {key: avatar[key] for key in avatar.keys()}
            processed_avatar = {
                'id': avatar_dict.get('id'),
                'user_id': avatar_dict.get('user_id'),
                'avatar_name': avatar_dict.get('name', 'Unnamed'),
                'avatar_url': avatar_dict.get('image_path'),
                'heygen_avatar_id': avatar_dict.get('heygen_avatar_id'),
                'created_at': avatar_dict.get('created_at')
            }
            if processed_avatar['heygen_avatar_id'] and not processed_avatar['avatar_name']:
                processed_avatar['avatar_name'] = f"HeyGen Avatar {processed_avatar['heygen_avatar_id'][:8]}..."
            avatars.append(processed_avatar)

        return templates.TemplateResponse("portal/admin_manage_avatars.html", {
            "request": request,
            "user": user,
            "user_to_manage": user_to_manage,
            "avatars": avatars,
            "title": f"Manage Avatars: {user_to_manage['username']}"
        })

    except Exception as e:
        log_error(f"Error in admin_manage_avatars_page: {e}", "Admin", e)
        return RedirectResponse(url="/admin/users?error=system_error", status_code=303)
# ============================================================================
# ADMIN DELETE AVATAR
# ============================================================================

@router.post("/admin/delete-avatar/{avatar_id}")
async def admin_delete_avatar(request: Request, avatar_id: int):
    """Admin delete avatar"""
    user = get_current_user(request)
    if not user or not is_admin(request):
        return RedirectResponse(url="/login", status_code=303)

    try:
        avatar = execute_query(
            "SELECT user_id FROM avatars WHERE id = ?",
            (avatar_id,),
            fetch_one=True
        )

        if avatar:
            user_id = avatar["user_id"]
            execute_query(
                "DELETE FROM avatars WHERE id = ?",
                (avatar_id,)
            )
            log_info(f"Admin {user['username']} deleted avatar {avatar_id} successfully", "Admin")
            return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?success=avatar_deleted", status_code=303)
        else:
            return RedirectResponse(url="/admin/users?error=avatar_not_found", status_code=303)

    except Exception as e:
        log_error(f"Error deleting avatar {avatar_id}: {e}", "Admin", e)
        return RedirectResponse(url="/admin/users?error=delete_failed", status_code=303)

# ============================================================================
# ADMIN UPLOAD IMAGE FOR USER (AVATAR)
# ============================================================================

@router.post("/admin/upload-image/{user_id}")
async def admin_upload_image(request: Request, user_id: int):
    """Admin upload image for user"""
    user = get_current_user(request)
    if not user or not is_admin(request):
        return RedirectResponse(url="/login", status_code=303)

    try:
        log_info(f"Admin {user['username']} uploading image for user {user_id}", "Admin")

        form = await request.form()
        image_file = form.get("image_file")

        if not image_file or not image_file.filename:
            return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?error=no_file", status_code=303)

        allowed_types = ['.png', '.jpg', '.jpeg', '.gif']
        file_ext = os.path.splitext(image_file.filename)[1].lower()
        if file_ext not in allowed_types:
            return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?error=invalid_file", status_code=303)

        upload_dir = "static/uploads/avatars"
        os.makedirs(upload_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        secure_name = secure_filename(image_file.filename)
        unique_filename = f"user_{user_id}_{timestamp}{file_ext}"
        file_path = os.path.join(upload_dir, unique_filename)

        with open(file_path, "wb") as buffer:
            content = await image_file.read()
            buffer.write(content)

        image_url = f"/static/uploads/avatars/{unique_filename}"
        execute_query(
            "INSERT INTO avatars (user_id, name, image_path) VALUES (?, ?, ?)",
            (user_id, unique_filename, image_url)
        )

        log_info(f"Admin {user['username']} uploaded image for user {user_id}: {unique_filename}", "Admin")
        return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?success=image_uploaded", status_code=303)

    except Exception as e:
        log_error(f"Error uploading image: {e}", "Admin", e)
        return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?error=upload_failed", status_code=303)
# ============================================================================
# ADMIN FETCH HEYGEN AVATAR
# ============================================================================

@router.post("/admin/fetch-heygen-avatar/{user_id}")
async def admin_fetch_heygen_avatar(request: Request, user_id: int):
    """Admin fetch avatar from HeyGen"""
    user = get_current_user(request)
    if not user or not is_admin(request):
        return RedirectResponse(url="/login", status_code=303)

    try:
        form = await request.form()
        heygen_avatar_id = form.get("heygen_avatar_id", "").strip()

        if not heygen_avatar_id:
            return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?error=no_avatar_id", status_code=303)

        heygen_api_key = os.getenv("HEYGEN_API_KEY")
        if not heygen_api_key:
            return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?error=api_key_missing", status_code=303)

        headers = {
            'X-Api-Key': heygen_api_key,
            'Content-Type': 'application/json'
        }

        heygen_url = f"https://api.heygen.com/v1/avatar/{heygen_avatar_id}"

        try:
            response = requests.get(heygen_url, headers=headers, timeout=30)
            if response.status_code == 200:
                avatar_data = response.json()
                if avatar_data.get('code') == 100:
                    avatar_info = avatar_data.get('data', {})
                    avatar_name = avatar_info.get('avatar_name', heygen_avatar_id)
                    avatar_preview_url = avatar_info.get('preview_image_url', '')

                    execute_query(
                        "INSERT INTO avatars (user_id, name, image_path, heygen_avatar_id) VALUES (?, ?, ?, ?)",
                        (user_id, avatar_name, avatar_preview_url, heygen_avatar_id)
                    )

                    return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?success=avatar_fetched", status_code=303)
                else:
                    return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?error=heygen_api_error", status_code=303)

            elif response.status_code == 401:
                return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?error=invalid_api_key", status_code=303)
            elif response.status_code == 404:
                return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?error=avatar_not_found", status_code=303)
            else:
                return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?error=heygen_failed", status_code=303)

        except requests.exceptions.Timeout:
            return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?error=timeout", status_code=303)
        except requests.exceptions.RequestException as e:
            log_error(f"HeyGen API request error: {e}", "Admin")
            return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?error=connection_failed", status_code=303)

    except Exception as e:
        log_error(f"Fetch HeyGen avatar error: {e}", "Admin", e)
        return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?error=system_error", status_code=303)
