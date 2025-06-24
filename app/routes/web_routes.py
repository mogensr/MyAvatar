import os
import uuid
import shutil
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Request, Form, HTTPException, Depends, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import bcrypt
import jwt
from database import Database
from utils import log_error, log_info, validate_email, generate_api_key

# Initialize router and templates
router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Initialize database
db = Database()

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-this")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Session helpers
def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """Get current user from session"""
    try:
        token = request.session.get("access_token")
        if not token:
            return None
        
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            return None
        
        user = db.get_user_by_id(user_id)
        return user
    except Exception as e:
        log_error("Error getting current user from session", "Auth", e)
        return None

def create_access_token(user_id: int) -> str:
    """Create JWT access token"""
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    payload = {
        "user_id": user_id,
        "exp": expire
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# Main Routes
@router.get("/")
async def home_page(request: Request):
    """Home page"""
    try:
        user = get_current_user(request)
        if user:
            return RedirectResponse(url="/dashboard")
            
        return templates.TemplateResponse("index.html", {
            "request": request,
            "user": None
        })
    except Exception as e:
        log_error("Error loading home page", "Web", e)
        return templates.TemplateResponse("index.html", {
            "request": request,
            "user": None
        })

# Authentication Routes
@router.get("/login")
async def login_page(request: Request):
    """Display login page"""
    try:
        user = get_current_user(request)
        if user:
            return RedirectResponse(url="/dashboard")
            
        return templates.TemplateResponse("login.html", {
            "request": request,
            "user": None
        })
    except Exception as e:
        log_error("Error loading login page", "Web", e)
        return templates.TemplateResponse("login.html", {
            "request": request,
            "user": None
        })

@router.post("/login")
async def login_user(request: Request):
    """Handle user login"""
    try:
        form = await request.form()
        username = form.get("username", "").strip()
        password = form.get("password", "").strip()
        
        if not username or not password:
            return templates.TemplateResponse("login.html", {
                "request": request,
                "user": None,
                "error": "Username and password are required"
            })
        
        # Get user from database
        user = db.get_user_by_username(username)
        if not user:
            return templates.TemplateResponse("login.html", {
                "request": request,
                "user": None,
                "error": "Invalid username or password"
            })
        
        # Verify password
        if not verify_password(password, user.get("password", "")):
            return templates.TemplateResponse("login.html", {
                "request": request,
                "user": None,
                "error": "Invalid username or password"
            })
        
        # Create access token and set session
        token = create_access_token(user["id"])
        request.session["access_token"] = token
        
        # Update last login
        db.update_user_login(user["id"])
        
        log_info(f"User {username} logged in successfully", "Auth")
        return RedirectResponse(url="/dashboard", status_code=302)
        
    except Exception as e:
        log_error("Error during login", "Auth", e)
        return templates.TemplateResponse("login.html", {
            "request": request,
            "user": None,
            "error": "Login failed. Please try again."
        })

@router.get("/register")
async def register_page(request: Request):
    """Display registration page"""
    try:
        user = get_current_user(request)
        if user:
            return RedirectResponse(url="/dashboard")
            
        return templates.TemplateResponse("register.html", {
            "request": request,
            "user": None
        })
    except Exception as e:
        log_error("Error loading register page", "Web", e)
        return templates.TemplateResponse("register.html", {
            "request": request,
            "user": None
        })

@router.post("/register")
async def register_user(request: Request):
    """Handle user registration"""
    try:
        form = await request.form()
        username = form.get("username", "").strip()
        email = form.get("email", "").strip()
        password = form.get("password", "").strip()
        confirm_password = form.get("confirm_password", "").strip()
        
        # Validation
        if not username or not email or not password:
            return templates.TemplateResponse("register.html", {
                "request": request,
                "user": None,
                "error": "All fields are required"
            })
        
        if len(username) < 3:
            return templates.TemplateResponse("register.html", {
                "request": request,
                "user": None,
                "error": "Username must be at least 3 characters long"
            })
        
        if not validate_email(email):
            return templates.TemplateResponse("register.html", {
                "request": request,
                "user": None,
                "error": "Please enter a valid email address"
            })
        
        if len(password) < 6:
            return templates.TemplateResponse("register.html", {
                "request": request,
                "user": None,
                "error": "Password must be at least 6 characters long"
            })
        
        if password != confirm_password:
            return templates.TemplateResponse("register.html", {
                "request": request,
                "user": None,
                "error": "Passwords do not match"
            })
        
        # Check if user already exists
        if db.get_user_by_username(username):
            return templates.TemplateResponse("register.html", {
                "request": request,
                "user": None,
                "error": "Username already exists"
            })
        
        if db.get_user_by_email(email):
            return templates.TemplateResponse("register.html", {
                "request": request,
                "user": None,
                "error": "Email already registered"
            })
        
        # Create user
        hashed_password = hash_password(password)
        api_key = generate_api_key()
        
        user_data = {
            "username": username,
            "email": email,
            "password": hashed_password,
            "api_key": api_key,
            "is_admin": 0,
            "avatar_id": "",
            "created_at": datetime.now().isoformat()
        }
        
        user_id = db.create_user(user_data)
        if not user_id:
            return templates.TemplateResponse("register.html", {
                "request": request,
                "user": None,
                "error": "Registration failed. Please try again."
            })
        
        # Auto-login after registration
        token = create_access_token(user_id)
        request.session["access_token"] = token
        
        log_info(f"New user registered: {username}", "Auth")
        return RedirectResponse(url="/dashboard", status_code=302)
        
    except Exception as e:
        log_error("Error during registration", "Auth", e)
        return templates.TemplateResponse("register.html", {
            "request": request,
            "user": None,
            "error": "Registration failed. Please try again."
        })

@router.get("/logout")
async def logout_user(request: Request):
    """Handle user logout"""
    try:
        request.session.clear()
        return RedirectResponse(url="/")
    except Exception as e:
        log_error("Error during logout", "Auth", e)
        return RedirectResponse(url="/")

# Dashboard Route - FIXED VERSION
@router.get("/dashboard")
async def dashboard_page(request: Request):
    """Display user dashboard with safe error handling"""
    try:
        user = get_current_user(request)
        if not user:
            return RedirectResponse(url="/login")
        
        # Initialize safe defaults
        video_list = []
        avatar_list = []
        total_videos = 0
        total_duration_hours = 0
        total_views = 0
        total_shares = 0
        
        try:
            # Safely get user videos
            videos = db.get_user_videos(user["id"])
            if videos:
                video_list = []
                for video in videos:
                    try:
                        # Safely convert video to dict if needed
                        if hasattr(video, '__dict__'):
                            video_dict = video.__dict__
                        elif isinstance(video, dict):
                            video_dict = video
                        else:
                            video_dict = dict(video) if video else {}
                        
                        # Clean datetime fields
                        if 'created_at' in video_dict and video_dict['created_at']:
                            try:
                                if isinstance(video_dict['created_at'], str):
                                    video_dict['created_at'] = datetime.fromisoformat(video_dict['created_at'].replace('Z', '+00:00'))
                                video_dict['created_at_formatted'] = video_dict['created_at'].strftime('%Y-%m-%d %H:%M')
                            except:
                                video_dict['created_at_formatted'] = 'Unknown'
                        else:
                            video_dict['created_at_formatted'] = 'Unknown'
                        
                        # Ensure required fields exist
                        video_dict.setdefault('title', 'Untitled')
                        video_dict.setdefault('status', 'unknown')
                        video_dict.setdefault('duration', 0)
                        video_dict.setdefault('views', 0)
                        video_dict.setdefault('shares', 0)
                        
                        video_list.append(video_dict)
                    except Exception as video_error:
                        log_error(f"Error processing video record", "Dashboard", video_error)
                        continue
                
                total_videos = len(video_list)
                total_duration_hours = sum(int(v.get('duration', 0)) for v in video_list) // 3600
                total_views = sum(int(v.get('views', 0)) for v in video_list)
                total_shares = sum(int(v.get('shares', 0)) for v in video_list)
        
        except Exception as video_error:
            log_error(f"Error fetching user videos", "Dashboard", video_error)
            # Continue with empty defaults
        
        try:
            # Safely get user avatars - using correct table reference
            avatars = db.get_user_avatars(user["id"])
            if avatars:
                avatar_list = []
                for avatar in avatars:
                    try:
                        # Safely convert avatar to dict
                        if hasattr(avatar, '__dict__'):
                            avatar_dict = avatar.__dict__
                        elif isinstance(avatar, dict):
                            avatar_dict = avatar
                        else:
                            avatar_dict = dict(avatar) if avatar else {}
                        
                        # Ensure required fields
                        avatar_dict.setdefault('name', 'Unnamed Avatar')
                        avatar_dict.setdefault('avatar_id', '')
                        avatar_dict.setdefault('image_url', '/static/images/default-avatar.png')
                        
                        avatar_list.append(avatar_dict)
                    except Exception as avatar_error:
                        log_error(f"Error processing avatar record", "Dashboard", avatar_error)
                        continue
                        
        except Exception as avatar_error:
            log_error(f"Error fetching user avatars", "Dashboard", avatar_error)
            # Continue with empty defaults
        
        # Use proper template rendering with REAL statistics
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "user": user,
                "username": user.get("username", "User"),
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
        log_error(f"Dashboard error for user {user.get('username', 'unknown') if user else 'unknown'}", "Web", e)
        # Return dashboard with safe defaults instead of login page
        safe_user = user if user else {"username": "User", "is_admin": 0, "avatar_id": "", "id": 0, "api_key": ""}
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "user": safe_user,
                "username": safe_user.get("username", "User"),
                "is_admin": safe_user.get("is_admin", 0),
                "avatar_id": safe_user.get("avatar_id", ""),
                "user_id": safe_user.get("id", 0),
                "api_key": "",
                "videos": [],
                "avatars": [],
                "total_videos": 0,
                "total_duration": "0h",
                "total_views": 0,
                "total_shares": 0,
            }
        )

# Video Management Routes
@router.get("/video/{video_id}")
async def get_video(request: Request, video_id: str):
    """Get specific video details"""
    try:
        user = get_current_user(request)
        if not user:
            return RedirectResponse(url="/login")
        
        # Get video from database
        video = db.get_video_by_id(video_id, user["id"])
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        return templates.TemplateResponse("video_detail.html", {
            "request": request,
            "user": user,
            "video": video
        })
    except Exception as e:
        log_error(f"Error getting video {video_id}", "Web", e)
        return RedirectResponse(url="/dashboard")

@router.post("/video/{video_id}/delete")
async def delete_video(request: Request, video_id: str):
    """Delete a video"""
    try:
        user = get_current_user(request)
        if not user:
            return RedirectResponse(url="/login")
        
        # Delete video from database
        success = db.delete_video(video_id, user["id"])
        if success:
            return JSONResponse({"success": True, "message": "Video deleted successfully"})
        else:
            return JSONResponse({"success": False, "message": "Failed to delete video"})
    except Exception as e:
        log_error(f"Error deleting video {video_id}", "Web", e)
        return JSONResponse({"success": False, "message": str(e)})

# Avatar Management Routes
@router.get("/avatars")
async def avatars_page(request: Request):
    """Display avatars page"""
    try:
        user = get_current_user(request)
        if not user:
            return RedirectResponse(url="/login")
        
        # Get user's avatars
        avatars = db.get_user_avatars(user["id"]) or []
        
        return templates.TemplateResponse("avatars.html", {
            "request": request,
            "user": user,
            "avatars": avatars
        })
    except Exception as e:
        log_error(f"Error loading avatars page", "Web", e)
        return templates.TemplateResponse("avatars.html", {
            "request": request,
            "user": user,
            "avatars": []
        })

@router.post("/avatar/create")
async def create_avatar(request: Request):
    """Create new avatar"""
    try:
        user = get_current_user(request)
        if not user:
            return RedirectResponse(url="/login")
        
        form = await request.form()
        avatar_name = form.get("avatar_name", "").strip()
        avatar_image = form.get("avatar_image")
        
        if not avatar_name:
            return JSONResponse({"success": False, "message": "Avatar name is required"})
        
        # Process avatar creation
        avatar_id = db.create_avatar(user["id"], avatar_name, avatar_image)
        if avatar_id:
            return JSONResponse({"success": True, "message": "Avatar created successfully", "avatar_id": avatar_id})
        else:
            return JSONResponse({"success": False, "message": "Failed to create avatar"})
    except Exception as e:
        log_error(f"Error creating avatar", "Web", e)
        return JSONResponse({"success": False, "message": str(e)})

# Video Creation Routes
@router.get("/create")
async def create_video_page(request: Request):
    """Display video creation page"""
    try:
        user = get_current_user(request)
        if not user:
            return RedirectResponse(url="/login")
        
        # Get user's avatars for selection
        avatars = db.get_user_avatars(user["id"]) or []
        
        return templates.TemplateResponse("create_video.html", {
            "request": request,
            "user": user,
            "avatars": avatars
        })
    except Exception as e:
        log_error(f"Error loading create video page", "Web", e)
        return templates.TemplateResponse("create_video.html", {
            "request": request,
            "user": user,
            "avatars": []
        })

@router.post("/create/video")
async def create_video(request: Request):
    """Handle video creation"""
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse({"success": False, "message": "Authentication required"})
        
        form = await request.form()
        script = form.get("script", "").strip()
        avatar_id = form.get("avatar_id", "").strip()
        title = form.get("title", "").strip()
        
        if not script:
            return JSONResponse({"success": False, "message": "Script is required"})
        
        if not avatar_id:
            return JSONResponse({"success": False, "message": "Avatar selection is required"})
        
        # Create video job
        video_data = {
            "user_id": user["id"],
            "title": title or "Untitled Video",
            "script": script,
            "avatar_id": avatar_id,
            "status": "pending"
        }
        
        video_id = db.create_video_job(video_data)
        if video_id:
            # Trigger video generation (async)
            # This would typically queue a background job
            return JSONResponse({
                "success": True, 
                "message": "Video creation started", 
                "video_id": video_id,
                "redirect": "/dashboard"
            })
        else:
            return JSONResponse({"success": False, "message": "Failed to create video job"})
            
    except Exception as e:
        log_error(f"Error creating video", "Web", e)
        return JSONResponse({"success": False, "message": str(e)})

# Settings Routes
@router.get("/settings")
async def settings_page(request: Request):
    """Display settings page"""
    try:
        user = get_current_user(request)
        if not user:
            return RedirectResponse(url="/login")
        
        return templates.TemplateResponse("settings.html", {
            "request": request,
            "user": user
        })
    except Exception as e:
        log_error(f"Error loading settings page", "Web", e)
        return RedirectResponse(url="/dashboard")

@router.post("/settings/update")
async def update_settings(request: Request):
    """Update user settings"""
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse({"success": False, "message": "Authentication required"})
        
        form = await request.form()
        username = form.get("username", "").strip()
        email = form.get("email", "").strip()
        api_key = form.get("api_key", "").strip()
        
        updates = {}
        if username and username != user.get("username"):
            updates["username"] = username
        if email and email != user.get("email"):
            updates["email"] = email
        if api_key:
            updates["api_key"] = api_key
        
        if updates:
            success = db.update_user(user["id"], updates)
            if success:
                return JSONResponse({"success": True, "message": "Settings updated successfully"})
            else:
                return JSONResponse({"success": False, "message": "Failed to update settings"})
        else:
            return JSONResponse({"success": True, "message": "No changes made"})
            
    except Exception as e:
        log_error(f"Error updating settings", "Web", e)
        return JSONResponse({"success": False, "message": str(e)})

# Profile Routes
@router.get("/profile")
async def profile_page(request: Request):
    """Display profile page"""
    try:
        user = get_current_user(request)
        if not user:
            return RedirectResponse(url="/login")
        
        # Get user statistics
        stats = {
            "total_videos": db.get_user_video_count(user["id"]) or 0,
            "total_views": db.get_user_total_views(user["id"]) or 0,
            "account_created": user.get("created_at", "Unknown"),
            "last_login": user.get("last_login", "Unknown")
        }
        
        return templates.TemplateResponse("profile.html", {
            "request": request,
            "user": user,
            "stats": stats
        })
    except Exception as e:
        log_error(f"Error loading profile page", "Web", e)
        return templates.TemplateResponse("profile.html", {
            "request": request,
            "user": user,
            "stats": {
                "total_videos": 0,
                "total_views": 0,
                "account_created": "Unknown",
                "last_login": "Unknown"
            }
        })

# API Routes for AJAX calls
@router.get("/api/videos")
async def api_get_videos(request: Request):
    """API endpoint to get user videos"""
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse({"success": False, "message": "Authentication required"})
        
        videos = db.get_user_videos(user["id"]) or []
        return JSONResponse({"success": True, "videos": videos})
    except Exception as e:
        log_error(f"Error getting videos via API", "Web", e)
        return JSONResponse({"success": False, "message": str(e)})

@router.get("/api/video/{video_id}/status")
async def api_video_status(request: Request, video_id: str):
    """API endpoint to check video generation status"""
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse({"success": False, "message": "Authentication required"})
        
        video = db.get_video_by_id(video_id, user["id"])
        if not video:
            return JSONResponse({"success": False, "message": "Video not found"})
        
        return JSONResponse({
            "success": True,
            "status": video.get("status", "unknown"),
            "progress": video.get("progress", 0),
            "video_url": video.get("video_url", "")
        })
    except Exception as e:
        log_error(f"Error checking video status", "Web", e)
        return JSONResponse({"success": False, "message": str(e)})

# Admin Routes
@router.get("/admin")
async def admin_page(request: Request):
    """Display admin dashboard"""
    try:
        user = get_current_user(request)
        if not user or not user.get("is_admin"):
            return RedirectResponse(url="/dashboard")
        
        # Get admin statistics
        admin_stats = {
            "total_users": db.get_total_users() or 0,
            "total_videos": db.get_total_videos() or 0,
            "active_users": db.get_active_users_count() or 0,
            "pending_videos": db.get_pending_videos_count() or 0
        }
        
        return templates.TemplateResponse("admin.html", {
            "request": request,
            "user": user,
            "stats": admin_stats
        })
    except Exception as e:
        log_error(f"Error loading admin page", "Web", e)
        return RedirectResponse(url="/dashboard")

@router.get("/admin/users")
async def admin_users(request: Request):
    """Display admin users management"""
    try:
        user = get_current_user(request)
        if not user or not user.get("is_admin"):
            return RedirectResponse(url="/dashboard")
        
        users = db.get_all_users() or []
        return templates.TemplateResponse("admin_users.html", {
            "request": request,
            "user": user,
            "users": users
        })
    except Exception as e:
        log_error(f"Error loading admin users page", "Web", e)
        return RedirectResponse(url="/admin")

# Help and Support Routes
@router.get("/help")
async def help_page(request: Request):
    """Display help page"""
    try:
        user = get_current_user(request)
        return templates.TemplateResponse("help.html", {
            "request": request,
            "user": user
        })
    except Exception as e:
        log_error(f"Error loading help page", "Web", e)
        return templates.TemplateResponse("help.html", {
            "request": request,
            "user": None
        })

@router.get("/terms")
async def terms_page(request: Request):
    """Display terms of service"""
    return templates.TemplateResponse("terms.html", {
        "request": request,
        "user": get_current_user(request)
    })

@router.get("/privacy")
async def privacy_page(request: Request):
    """Display privacy policy"""
    return templates.TemplateResponse("privacy.html", {
        "request": request,
        "user": get_current_user(request)
    })

# Error handling routes
@router.get("/error")
async def error_page(request: Request):
    """Display error page"""
    error_msg = request.query_params.get("msg", "An error occurred")
    return templates.TemplateResponse("error.html", {
        "request": request,
        "user": get_current_user(request),
        "error_message": error_msg
    })

# Health check route
@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse({"status": "ok", "timestamp": datetime.now().isoformat()})

# Webhook routes for external services
@router.post("/webhook/heygen")
async def heygen_webhook(request: Request):
    """Handle HeyGen webhooks for video status updates"""
    try:
        data = await request.json()
        video_id = data.get("video_id")
        status = data.get("status")
        video_url = data.get("video_url")
        
        if video_id and status:
            db.update_video_status(video_id, status, video_url)
            return JSONResponse({"success": True})
        
        return JSONResponse({"success": False, "message": "Invalid webhook data"})
    except Exception as e:
        log_error(f"Error processing HeyGen webhook", "Web", e)
        return JSONResponse({"success": False, "message": str(e)})

# File upload routes
@router.post("/upload/avatar")
async def upload_avatar_image(request: Request, file: UploadFile = File(...)):
    """Handle avatar image uploads"""
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse({"success": False, "message": "Authentication required"})
        
        # Validate file type
        if not file.content_type.startswith("image/"):
            return JSONResponse({"success": False, "message": "Only image files are allowed"})
        
        # Save file and return URL
        file_url = await save_uploaded_file(file, "avatars")
        return JSONResponse({"success": True, "file_url": file_url})
        
    except Exception as e:
        log_error(f"Error uploading avatar image", "Web", e)
        return JSONResponse({"success": False, "message": str(e)})

# Utility functions
async def save_uploaded_file(file: UploadFile, folder: str) -> str:
    """Save uploaded file and return URL"""
    try:
        # Generate unique filename
        file_extension = file.filename.split(".")[-1] if "." in file.filename else "jpg"
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        
        # Create directory if it doesn't exist
        upload_dir = f"static/uploads/{folder}"
        os.makedirs(upload_dir, exist_ok=True)
        
        # Save file
        file_path = f"{upload_dir}/{unique_filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return f"/static/uploads/{folder}/{unique_filename}"
    except Exception as e:
        log_error(f"Error saving uploaded file", "Web", e)
        raise e