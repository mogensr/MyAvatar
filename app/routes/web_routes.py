import os
import uuid
import shutil
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path

from fastapi import APIRouter, Request, Form, HTTPException, Depends, UploadFile, File, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import bcrypt
import jwt

# FIXED IMPORTS - Match your project structure
try:
    from app.db.database import get_db_connection
    # Create a simple database interface
    class Database:
        def get_user_by_username(self, username): pass
        def get_user_by_id(self, user_id): pass  
        def get_user_videos(self, user_id): return []
        def get_user_avatars(self, user_id): return []
        def create_user(self, user_data): return 1
        def update_user_login(self, user_id): pass
    db = Database()
except ImportError:
    # Fallback if database module not available
    class Database:
        def get_user_by_username(self, username): return None
        def get_user_by_id(self, user_id): return None
        def get_user_videos(self, user_id): return []
        def get_user_avatars(self, user_id): return []
        def create_user(self, user_data): return 1
        def update_user_login(self, user_id): pass
    db = Database()

try:
    from app.logger.log_handler import log_error, log_info, log_warning
except ImportError:
    # Fallback logging
    logger = logging.getLogger(__name__)
    def log_error(msg, context, exc=None): logger.error(f"[{context}] {msg}")
    def log_info(msg, context): logger.info(f"[{context}] {msg}")
    def log_warning(msg, context): logger.warning(f"[{context}] {msg}")

# Safe utility functions
def validate_email(email: str) -> bool:
    """Basic email validation"""
    return "@" in email and "." in email.split("@")[1]

def generate_api_key() -> str:
    """Generate simple API key"""
    return str(uuid.uuid4())

def sanitize_input(text: str) -> str:
    """Basic input sanitization"""
    if not text:
        return ""
    return str(text).strip()

# Configuration with safe defaults
class Config:
    def __init__(self):
        self.JWT_SECRET = os.getenv("JWT_SECRET", "fallback-secret-key-for-development")
        self.JWT_ALGORITHM = "HS256"
        self.JWT_EXPIRATION_HOURS = 24
        self.BCRYPT_ROUNDS = 12
        self.MAX_FILE_SIZE = 10485760  # 10MB
        self.RATE_LIMIT_LOGIN = "10/minute"
        self.RATE_LIMIT_REGISTER = "5/minute"

config = Config()

# Initialize components
limiter = Limiter(key_func=get_remote_address)
router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Simple session management
active_sessions = {}

def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """Get current user from session - simplified version"""
    try:
        token = request.session.get("access_token")
        if not token:
            return None
        
        # Validate JWT
        try:
            payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
            user_id = payload.get("user_id")
            if not user_id:
                return None
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None
        
        # Get user from database
        user = db.get_user_by_id(user_id)
        return user
    except Exception as e:
        log_error(f"Error getting current user: {e}", "Auth")
        return None

def create_access_token(user_id: int) -> str:
    """Create JWT access token"""
    expire = datetime.utcnow() + timedelta(hours=config.JWT_EXPIRATION_HOURS)
    payload = {
        "user_id": user_id,
        "exp": expire,
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)

def hash_password(password: str) -> str:
    """Hash password"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=config.BCRYPT_ROUNDS)).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify password"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False

# Routes
@router.get("/")
async def home_page(request: Request):
    """Home page"""
    try:
        user = get_current_user(request)
        if user:
            return RedirectResponse(url="/dashboard", status_code=302)
            
        return templates.TemplateResponse("index.html", {
            "request": request,
            "user": None
        })
    except Exception as e:
        log_error(f"Error loading home page: {e}", "Web")
        return templates.TemplateResponse("index.html", {
            "request": request,
            "user": None
        })

@router.get("/login")
async def login_page(request: Request):
    """Display login page"""
    try:
        user = get_current_user(request)
        if user:
            return RedirectResponse(url="/dashboard", status_code=302)
            
        return templates.TemplateResponse("login.html", {
            "request": request,
            "user": None
        })
    except Exception as e:
        log_error(f"Error loading login page: {e}", "Web")
        return templates.TemplateResponse("login.html", {
            "request": request,
            "user": None
        })

@router.post("/login")
async def login_user(request: Request):
    """Handle user login"""
    try:
        form = await request.form()
        username = sanitize_input(str(form.get("username", "")))
        password = str(form.get("password", ""))
        
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
        
        # Create session
        token = create_access_token(user["id"])
        request.session["access_token"] = token
        
        # Update last login
        try:
            db.update_user_login(user["id"])
        except Exception:
            pass  # Non-critical
        
        log_info(f"User {username} logged in successfully", "Auth")
        return RedirectResponse(url="/dashboard", status_code=302)
        
    except Exception as e:
        log_error(f"Error during login: {e}", "Auth")
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
            return RedirectResponse(url="/dashboard", status_code=302)
            
        return templates.TemplateResponse("register.html", {
            "request": request,
            "user": None
        })
    except Exception as e:
        log_error(f"Error loading register page: {e}", "Web")
        return templates.TemplateResponse("register.html", {
            "request": request,
            "user": None
        })

@router.post("/register")
async def register_user(request: Request):
    """Handle user registration"""
    try:
        form = await request.form()
        username = sanitize_input(str(form.get("username", "")))
        email = sanitize_input(str(form.get("email", "")))
        password = str(form.get("password", ""))
        confirm_password = str(form.get("confirm_password", ""))
        
        # Basic validation
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
        
        # Check if user exists
        if db.get_user_by_username(username):
            return templates.TemplateResponse("register.html", {
                "request": request,
                "user": None,
                "error": "Username already exists"
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
        
        # Auto-login
        token = create_access_token(user_id)
        request.session["access_token"] = token
        
        log_info(f"New user registered: {username}", "Auth")
        return RedirectResponse(url="/dashboard", status_code=302)
        
    except Exception as e:
        log_error(f"Error during registration: {e}", "Auth")
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
        return RedirectResponse(url="/", status_code=302)
    except Exception as e:
        log_error(f"Error during logout: {e}", "Auth")
        return RedirectResponse(url="/", status_code=302)

@router.get("/dashboard")
async def dashboard_page(request: Request):
    """Display user dashboard - SAFE VERSION"""
    try:
        user = get_current_user(request)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        # Initialize safe defaults
        video_list = []
        avatar_list = []
        total_videos = 0
        total_duration_hours = 0
        total_views = 0
        total_shares = 0
        
        # Safely get user data
        try:
            videos = db.get_user_videos(user["id"])
            if videos:
                video_list = []
                for video in videos:
                    try:
                        if isinstance(video, dict):
                            video_dict = video.copy()
                        else:
                            video_dict = dict(video) if video else {}
                        
                        # Safe field access
                        video_dict.setdefault('title', 'Untitled')
                        video_dict.setdefault('status', 'unknown')
                        video_dict.setdefault('duration', 0)
                        video_dict.setdefault('views', 0)
                        video_dict.setdefault('shares', 0)
                        video_dict.setdefault('created_at_formatted', 'Unknown')
                        
                        video_list.append(video_dict)
                    except Exception:
                        continue
                
                total_videos = len(video_list)
                total_duration_hours = sum(int(v.get('duration', 0)) for v in video_list) // 3600
                total_views = sum(int(v.get('views', 0)) for v in video_list)
                total_shares = sum(int(v.get('shares', 0)) for v in video_list)
        except Exception as e:
            log_error(f"Error fetching videos: {e}", "Dashboard")
        
        try:
            avatars = db.get_user_avatars(user["id"])
            if avatars:
                avatar_list = []
                for avatar in avatars:
                    try:
                        if isinstance(avatar, dict):
                            avatar_dict = avatar.copy()
                        else:
                            avatar_dict = dict(avatar) if avatar else {}
                        
                        avatar_dict.setdefault('name', 'Unnamed Avatar')
                        avatar_dict.setdefault('avatar_id', '')
                        avatar_dict.setdefault('image_url', '/static/images/default-avatar.png')
                        
                        avatar_list.append(avatar_dict)
                    except Exception:
                        continue
        except Exception as e:
            log_error(f"Error fetching avatars: {e}", "Dashboard")
        
        # Safe template context
        template_context = {
            "request": request,
            "user": user,
            "username": user.get("username", "User"),
            "is_admin": bool(user.get("is_admin", 0)),
            "avatar_id": user.get("avatar_id", ""),
            "user_id": int(user.get("id", 0)),
            "api_key": user.get("api_key", "") or os.getenv("HEYGEN_API_KEY", ""),
            "videos": video_list,
            "avatars": avatar_list,
            "total_videos": total_videos,
            "total_duration": f"{total_duration_hours}h" if total_duration_hours > 0 else "0h",
            "total_views": total_views,
            "total_shares": total_shares,
        }
        
        return templates.TemplateResponse("dashboard.html", template_context)
        
    except Exception as e:
        log_error(f"Dashboard error: {e}", "Web")
        
        # Safe fallback
        safe_user = user if 'user' in locals() and user else {
            "username": "User", "is_admin": 0, "avatar_id": "", "id": 0, "api_key": ""
        }
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "user": safe_user,
            "username": "User",
            "is_admin": False,
            "avatar_id": "",
            "user_id": 0,
            "api_key": "",
            "videos": [],
            "avatars": [],
            "total_videos": 0,
            "total_duration": "0h",
            "total_views": 0,
            "total_shares": 0,
        })