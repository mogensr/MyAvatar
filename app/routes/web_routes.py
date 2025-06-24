import os
import uuid
import shutil
import logging
import time
import magic
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import APIRouter, Request, Form, HTTPException, Depends, UploadFile, File, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.gzip import GZipMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

import bcrypt
import jwt
import bleach
from database import Database
from utils import log_error, log_info, validate_email, generate_api_key

# Production Configuration Class
class Config:
    def __init__(self):
        # Security
        self.JWT_SECRET = self._get_required_env("JWT_SECRET")
        self.JWT_ALGORITHM = "HS256"
        self.JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
        self.BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "12"))
        
        # File Upload
        self.MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "10485760"))  # 10MB
        self.ALLOWED_EXTENSIONS = set(os.getenv("ALLOWED_EXTENSIONS", "jpg,jpeg,png,gif,webp").split(","))
        self.UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "static/uploads"))
        
        # Rate Limiting
        self.RATE_LIMIT_LOGIN = os.getenv("RATE_LIMIT_LOGIN", "5/minute")
        self.RATE_LIMIT_REGISTER = os.getenv("RATE_LIMIT_REGISTER", "3/minute")
        self.RATE_LIMIT_API = os.getenv("RATE_LIMIT_API", "100/minute")
        
        # Database
        self.DATABASE_URL = self._get_required_env("DATABASE_URL")
        self.DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
        self.DB_TIMEOUT = int(os.getenv("DB_TIMEOUT", "30"))
        
        # Session
        self.SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT", "3600"))  # 1 hour
        self.MAX_SESSIONS_PER_USER = int(os.getenv("MAX_SESSIONS_PER_USER", "5"))
        
        # Security Headers
        self.TRUSTED_HOSTS = os.getenv("TRUSTED_HOSTS", "localhost,127.0.0.1").split(",")
        self.CORS_ORIGINS = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else []
        
        # Validate configuration
        self._validate_config()
    
    def _get_required_env(self, key: str) -> str:
        value = os.getenv(key)
        if not value or value in ["your-secret-key-change-this", "change-this"]:
            raise ValueError(f"Required environment variable {key} is missing or using default value")
        return value
    
    def _validate_config(self):
        # Ensure upload directory exists
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        
        # Validate JWT secret strength
        if len(self.JWT_SECRET) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters long")

# Initialize configuration
config = Config()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Initialize router and templates
router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Configure Jinja2 for security
templates.env.autoescape = True

# Initialize database with connection pooling
db = Database(
    url=config.DATABASE_URL,
    pool_size=config.DB_POOL_SIZE,
    timeout=config.DB_TIMEOUT
)

# Security utilities
security = HTTPBearer(auto_error=False)

def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent XSS"""
    if not text:
        return ""
    return bleach.clean(text.strip(), tags=[], attributes={}, strip=True)

def validate_file_content(file_path: str, expected_type: str) -> bool:
    """Validate file content matches expected type"""
    try:
        file_type = magic.from_file(file_path, mime=True)
        return file_type.startswith(expected_type)
    except Exception as e:
        logger.error(f"File validation error: {e}")
        return False

def create_secure_filename(filename: str) -> str:
    """Create secure filename"""
    if not filename:
        return f"{uuid.uuid4()}.jpg"
    
    # Extract extension
    name, ext = os.path.splitext(filename)
    ext = ext.lower()
    
    # Validate extension
    if ext.lstrip('.') not in config.ALLOWED_EXTENSIONS:
        ext = '.jpg'
    
    # Create secure name
    secure_name = f"{uuid.uuid4()}{ext}"
    return secure_name

# Session and Authentication with enhanced security
class SessionManager:
    def __init__(self):
        self.active_sessions = {}  # In production, use Redis
    
    def create_session(self, user_id: int, request: Request) -> str:
        """Create secure session with limits"""
        # Check concurrent sessions
        user_sessions = [s for s in self.active_sessions.values() if s.get('user_id') == user_id]
        if len(user_sessions) >= config.MAX_SESSIONS_PER_USER:
            # Remove oldest session
            oldest = min(user_sessions, key=lambda x: x['created_at'])
            del self.active_sessions[oldest['token']]
        
        # Create new session
        token = create_access_token(user_id)
        session_data = {
            'user_id': user_id,
            'created_at': time.time(),
            'ip_address': get_remote_address(request),
            'user_agent': request.headers.get('user-agent', ''),
            'token': token
        }
        
        self.active_sessions[token] = session_data
        return token
    
    def validate_session(self, token: str, request: Request) -> Optional[Dict]:
        """Validate session with security checks"""
        if not token or token not in self.active_sessions:
            return None
        
        session = self.active_sessions[token]
        
        # Check timeout
        if time.time() - session['created_at'] > config.SESSION_TIMEOUT:
            del self.active_sessions[token]
            return None
        
        # Check IP consistency (optional, can be disabled for mobile users)
        current_ip = get_remote_address(request)
        if session['ip_address'] != current_ip:
            logger.warning(f"IP mismatch for session: {session['ip_address']} vs {current_ip}")
            # Could optionally invalidate session here
        
        return session

session_manager = SessionManager()

def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """Get current user with enhanced security"""
    try:
        token = request.session.get("access_token")
        if not token:
            return None
        
        # Validate session
        session = session_manager.validate_session(token, request)
        if not session:
            request.session.clear()
            return None
        
        # Validate JWT
        try:
            payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
            user_id = payload.get("user_id")
            if not user_id:
                return None
        except jwt.ExpiredSignatureError:
            session_manager.active_sessions.pop(token, None)
            request.session.clear()
            return None
        except jwt.InvalidTokenError:
            return None
        
        # Get user from database with retry logic
        for attempt in range(3):
            try:
                user = db.get_user_by_id(user_id)
                if user:
                    return user
                break
            except Exception as e:
                if attempt == 2:
                    logger.error(f"Failed to get user after 3 attempts: {e}")
                time.sleep(0.1 * (attempt + 1))
        
        return None
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        return None

def create_access_token(user_id: int) -> str:
    """Create JWT access token with enhanced security"""
    expire = datetime.utcnow() + timedelta(hours=config.JWT_EXPIRATION_HOURS)
    payload = {
        "user_id": user_id,
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": str(uuid.uuid4())  # JWT ID for token tracking
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)

def hash_password(password: str) -> str:
    """Hash password with configurable rounds"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=config.BCRYPT_ROUNDS)).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False

def validate_password_strength(password: str) -> tuple[bool, str]:
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    
    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        return False, "Password must contain at least one special character"
    
    return True, "Password is strong"

# Enhanced error handling
class APIError(Exception):
    def __init__(self, message: str, status_code: int = 500, error_code: str = "INTERNAL_ERROR"):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code

def handle_api_error(error: Exception, context: str = "") -> JSONResponse:
    """Handle API errors securely"""
    if isinstance(error, APIError):
        logger.error(f"API Error in {context}: {error.message}")
        return JSONResponse(
            status_code=error.status_code,
            content={
                "success": False,
                "error_code": error.error_code,
                "message": error.message
            }
        )
    else:
        logger.error(f"Unexpected error in {context}: {str(error)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error_code": "INTERNAL_ERROR",
                "message": "An internal error occurred"
            }
        )

# Main Routes with Security
@router.get("/")
async def home_page(request: Request):
    """Home page with security headers"""
    try:
        user = get_current_user(request)
        if user:
            return RedirectResponse(url="/dashboard", status_code=302)
            
        response = templates.TemplateResponse("index.html", {
            "request": request,
            "user": None
        })
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response
    except Exception as e:
        logger.error(f"Error loading home page: {e}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "user": None,
            "error_message": "Service temporarily unavailable"
        })

# Authentication Routes with Rate Limiting
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
        logger.error(f"Error loading login page: {e}")
        return templates.TemplateResponse("login.html", {
            "request": request,
            "user": None
        })

@router.post("/login")
@limiter.limit(config.RATE_LIMIT_LOGIN)
async def login_user(request: Request):
    """Handle user login with security measures"""
    try:
        form = await request.form()
        username = sanitize_input(str(form.get("username", "")))
        password = str(form.get("password", ""))
        
        if not username or not password:
            return templates.TemplateResponse("login.html", {
                "request": request,
                "user": None,
                "error": "Username and password are required"
            }, status_code=400)
        
        # Rate limiting check (additional to decorator)
        client_ip = get_remote_address(request)
        failed_attempts = db.get_failed_login_attempts(client_ip, username)
        
        if failed_attempts >= 5:
            logger.warning(f"Too many failed login attempts from {client_ip} for {username}")
            return templates.TemplateResponse("login.html", {
                "request": request,
                "user": None,
                "error": "Too many failed attempts. Please try again later."
            }, status_code=429)
        
        # Get user from database
        user = db.get_user_by_username(username)
        if not user:
            db.record_failed_login(client_ip, username)
            return templates.TemplateResponse("login.html", {
                "request": request,
                "user": None,
                "error": "Invalid username or password"
            }, status_code=401)
        
        # Verify password
        if not verify_password(password, user.get("password", "")):
            db.record_failed_login(client_ip, username)
            return templates.TemplateResponse("login.html", {
                "request": request,
                "user": None,
                "error": "Invalid username or password"
            }, status_code=401)
        
        # Check if account is locked
        if user.get("is_locked", False):
            return templates.TemplateResponse("login.html", {
                "request": request,
                "user": None,
                "error": "Account is temporarily locked. Please contact support."
            }, status_code=403)
        
        # Create secure session
        token = session_manager.create_session(user["id"], request)
        request.session["access_token"] = token
        
        # Update last login and clear failed attempts
        db.update_user_login(user["id"])
        db.clear_failed_login_attempts(client_ip, username)
        
        logger.info(f"User {username} logged in successfully from {client_ip}")
        return RedirectResponse(url="/dashboard", status_code=302)
        
    except Exception as e:
        logger.error(f"Error during login: {e}")
        return templates.TemplateResponse("login.html", {
            "request": request,
            "user": None,
            "error": "Login failed. Please try again."
        }, status_code=500)

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
        logger.error(f"Error loading register page: {e}")
        return templates.TemplateResponse("register.html", {
            "request": request,
            "user": None
        })

@router.post("/register")
@limiter.limit(config.RATE_LIMIT_REGISTER)
async def register_user(request: Request):
    """Handle user registration with enhanced validation"""
    try:
        form = await request.form()
        username = sanitize_input(str(form.get("username", "")))
        email = sanitize_input(str(form.get("email", "")))
        password = str(form.get("password", ""))
        confirm_password = str(form.get("confirm_password", ""))
        
        # Enhanced validation
        if not username or not email or not password:
            return templates.TemplateResponse("register.html", {
                "request": request,
                "user": None,
                "error": "All fields are required"
            }, status_code=400)
        
        if len(username) < 3 or len(username) > 50:
            return templates.TemplateResponse("register.html", {
                "request": request,
                "user": None,
                "error": "Username must be between 3 and 50 characters"
            }, status_code=400)
        
        # Check username for invalid characters
        if not username.replace('_', '').replace('-', '').isalnum():
            return templates.TemplateResponse("register.html", {
                "request": request,
                "user": None,
                "error": "Username can only contain letters, numbers, hyphens, and underscores"
            }, status_code=400)
        
        if not validate_email(email):
            return templates.TemplateResponse("register.html", {
                "request": request,
                "user": None,
                "error": "Please enter a valid email address"
            }, status_code=400)
        
        # Enhanced password validation
        is_strong, password_msg = validate_password_strength(password)
        if not is_strong:
            return templates.TemplateResponse("register.html", {
                "request": request,
                "user": None,
                "error": password_msg
            }, status_code=400)
        
        if password != confirm_password:
            return templates.TemplateResponse("register.html", {
                "request": request,
                "user": None,
                "error": "Passwords do not match"
            }, status_code=400)
        
        # Check if user already exists
        if db.get_user_by_username(username):
            return templates.TemplateResponse("register.html", {
                "request": request,
                "user": None,
                "error": "Username already exists"
            }, status_code=409)
        
        if db.get_user_by_email(email):
            return templates.TemplateResponse("register.html", {
                "request": request,
                "user": None,
                "error": "Email already registered"
            }, status_code=409)
        
        # Create user with enhanced security
        hashed_password = hash_password(password)
        api_key = generate_api_key()
        
        user_data = {
            "username": username,
            "email": email,
            "password": hashed_password,
            "api_key": api_key,
            "is_admin": 0,
            "is_locked": 0,
            "avatar_id": "",
            "created_at": datetime.now().isoformat(),
            "email_verified": 0  # For future email verification
        }
        
        user_id = db.create_user(user_data)
        if not user_id:
            return templates.TemplateResponse("register.html", {
                "request": request,
                "user": None,
                "error": "Registration failed. Please try again."
            }, status_code=500)
        
        # Auto-login after registration
        token = session_manager.create_session(user_id, request)
        request.session["access_token"] = token
        
        logger.info(f"New user registered: {username}")
        return RedirectResponse(url="/dashboard", status_code=302)
        
    except Exception as e:
        logger.error(f"Error during registration: {e}")
        return templates.TemplateResponse("register.html", {
            "request": request,
            "user": None,
            "error": "Registration failed. Please try again."
        }, status_code=500)

@router.get("/logout")
async def logout_user(request: Request):
    """Handle user logout with session cleanup"""
    try:
        token = request.session.get("access_token")
        if token:
            session_manager.active_sessions.pop(token, None)
        request.session.clear()
        return RedirectResponse(url="/", status_code=302)
    except Exception as e:
        logger.error(f"Error during logout: {e}")
        # Still redirect even if cleanup fails
        return RedirectResponse(url="/", status_code=302)

# Production-Ready Dashboard Route
@router.get("/dashboard")
async def dashboard_page(request: Request):
    """Display user dashboard with comprehensive error handling"""
    user = None
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
        
        # Safely get user videos with retry logic
        for attempt in range(3):
            try:
                videos = db.get_user_videos(user["id"])
                if videos:
                    video_list = []
                    for video in videos:
                        try:
                            # Safely convert video to dict if needed
                            if hasattr(video, '__dict__'):
                                video_dict = video.__dict__
                            elif isinstance(video, dict):
                                video_dict = video.copy()
                            else:
                                video_dict = dict(video) if video else {}
                            
                            # Sanitize and clean datetime fields
                            if 'created_at' in video_dict and video_dict['created_at']:
                                try:
                                    if isinstance(video_dict['created_at'], str):
                                        video_dict['created_at'] = datetime.fromisoformat(video_dict['created_at'].replace('Z', '+00:00'))
                                    video_dict['created_at_formatted'] = video_dict['created_at'].strftime('%Y-%m-%d %H:%M')
                                except Exception:
                                    video_dict['created_at_formatted'] = 'Unknown'
                            else:
                                video_dict['created_at_formatted'] = 'Unknown'
                            
                            # Ensure required fields exist and sanitize
                            video_dict['title'] = sanitize_input(video_dict.get('title', 'Untitled'))
                            video_dict['status'] = sanitize_input(video_dict.get('status', 'unknown'))
                            video_dict['duration'] = max(0, int(video_dict.get('duration', 0)))
                            video_dict['views'] = max(0, int(video_dict.get('views', 0)))
                            video_dict['shares'] = max(0, int(video_dict.get('shares', 0)))
                            
                            video_list.append(video_dict)
                        except Exception as video_error:
                            logger.error(f"Error processing video record: {video_error}")
                            continue
                    
                    total_videos = len(video_list)
                    total_duration_hours = sum(v.get('duration', 0) for v in video_list) // 3600
                    total_views = sum(v.get('views', 0) for v in video_list)
                    total_shares = sum(v.get('shares', 0) for v in video_list)
                
                break  # Success, exit retry loop
                
            except Exception as video_error:
                if attempt == 2:  # Last attempt
                    logger.error(f"Failed to fetch user videos after 3 attempts: {video_error}")
                else:
                    time.sleep(0.1 * (attempt + 1))  # Brief delay before retry
        
        # Safely get user avatars with retry logic
        for attempt in range(3):
            try:
                avatars = db.get_user_avatars(user["id"])
                if avatars:
                    avatar_list = []
                    for avatar in avatars:
                        try:
                            # Safely convert avatar to dict
                            if hasattr(avatar, '__dict__'):
                                avatar_dict = avatar.__dict__
                            elif isinstance(avatar, dict):
                                avatar_dict = avatar.copy()
                            else:
                                avatar_dict = dict(avatar) if avatar else {}
                            
                            # Ensure required fields and sanitize
                            avatar_dict['name'] = sanitize_input(avatar_dict.get('name', 'Unnamed Avatar'))
                            avatar_dict['avatar_id'] = sanitize_input(avatar_dict.get('avatar_id', ''))
                            avatar_dict['image_url'] = avatar_dict.get('image_url', '/static/images/default-avatar.png')
                            
                            avatar_list.append(avatar_dict)
                        except Exception as avatar_error:
                            logger.error(f"Error processing avatar record: {avatar_error}")
                            continue
                
                break  # Success, exit retry loop
                
            except Exception as avatar_error:
                if attempt == 2:  # Last attempt
                    logger.error(f"Failed to fetch user avatars after 3 attempts: {avatar_error}")
                else:
                    time.sleep(0.1 * (attempt + 1))  # Brief delay before retry
        
        # Build secure template context
        template_context = {
            "request": request,
            "user": user,
            "username": sanitize_input(user.get("username", "User")),
            "is_admin": bool(user.get("is_admin", 0)),
            "avatar_id": sanitize_input(user.get("avatar_id", "")),
            "user_id": int(user.get("id", 0)),
            "api_key": user.get("api_key", "") or os.getenv("HEYGEN_API_KEY", ""),
            "videos": video_list,
            "avatars": avatar_list,
            "total_videos": total_videos,
            "total_duration": f"{total_duration_hours}h" if total_duration_hours > 0 else "0h",
            "total_views": total_views,
            "total_shares": total_shares,
        }
        
        response = templates.TemplateResponse("dashboard.html", template_context)
        
        # Add security headers
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        
        return response
        
    except Exception as e:
        logger.error(f"Dashboard error for user {user.get('username', 'unknown') if user else 'unknown'}: {e}")
        
        # Return dashboard with safe defaults instead of error page
        safe_user = user if user else {
            "username": "User", 
            "is_admin": 0, 
            "avatar_id": "", 
            "id": 0, 
            "api_key": ""
        }
        
        safe_context = {
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
        }
        
        return templates.TemplateResponse("dashboard.html", safe_context)

# File Upload with Enhanced Security
@router.post("/upload/avatar")
@limiter.limit("10/minute")
async def upload_avatar_image(request: Request, file: UploadFile = File(...)):
    """Handle avatar image uploads with comprehensive security"""
    try:
        user = get_current_user(request)
        if not user:
            raise APIError("Authentication required", 401, "AUTH_REQUIRED")
        
        # Validate file
        if not file.filename:
            raise APIError("No file provided", 400, "NO_FILE")
        
        # Check file size
        file_content = await file.read()
        if len(file_content) > config.MAX_FILE_SIZE:
            raise APIError(f"File too large. Maximum size is {config.MAX_FILE_SIZE // 1024 // 1024}MB", 413, "FILE_TOO_LARGE")
        
        # Reset file position
        await file.seek(0)
        
        # Validate MIME type
        if not file.content_type or not file.content_type.startswith("image/"):
            raise APIError("Only image files are allowed", 400, "INVALID_FILE_TYPE")
        
        # Create secure filename
        secure_filename = create_secure_filename(file.filename)
        file_path = config.UPLOAD_DIR / "avatars" / secure_filename
        
        # Ensure directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Validate file content
        if not validate_file_content(str(file_path), "image"):
            file_path.unlink()  # Remove invalid file
            raise APIError("File content validation failed", 400, "INVALID_FILE_CONTENT")
        
        file_url = f"/static/uploads/avatars/{secure_filename}"
        logger.info(f"Avatar uploaded successfully by user {user['id']}: {file_url}")
        
        return JSONResponse({
            "success": True, 
            "file_url": file_url,
            "filename": secure_filename
        })
        
    except APIError:
        raise
    except Exception as e:
        logger.error(f"Error uploading avatar image: {e}")
        raise APIError("Upload failed", 500, "UPLOAD_ERROR")

# Production Health Checks
@router.get("/health")
async def health_check():
    """Comprehensive health check with database connectivity"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "checks": {}
    }
    
    # Database health check
    try:
        start_time = time.time()
        db.get_total_users()
        db_response_time = time.time() - start_time
        
        health_status["checks"]["database"] = {
            "status": "healthy",
            "response_time_ms": round(db_response_time * 1000, 2)
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "error": "Connection failed"
        }
        health_status["status"] = "degraded"
    
    # File system health check
    try:
        test_file = config.UPLOAD_DIR / "health_check.tmp"
        test_file.write_text("health check")
        test_file.unlink()
        
        health_status["checks"]["filesystem"] = {"status": "healthy"}
    except Exception as e:
        logger.error(f"Filesystem health check failed: {e}")
        health_status["checks"]["filesystem"] = {
            "status": "unhealthy",
            "error": "Write failed"
        }
        health_status["status"] = "degraded"
    
    # Memory check
    import psutil
    memory = psutil.virtual_memory()
    health_status["checks"]["memory"] = {
        "status": "healthy" if memory.percent < 90 else "warning",
        "usage_percent": memory.percent
    }
    
    return health_status

@router.get("/simple-health")
async def simple_health_check():
    """Ultra-simple health check for load balancers"""
    return {"status": "ok"}

@router.get("/metrics")
async def metrics_endpoint(request: Request):
    """Basic metrics endpoint"""
    user = get_current_user(request)
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        metrics = {
            "active_sessions": len(session_manager.active_sessions),
            "total_users": db.get_total_users() or 0,
            "total_videos": db.get_total_videos() or 0,
            "disk_usage": shutil.disk_usage(config.UPLOAD_DIR),
            "timestamp": datetime.now().isoformat()
        }
        return metrics
    except Exception as e:
        logger.error(f"Error generating metrics: {e}")
        raise HTTPException(status_code=500, detail="Metrics unavailable")

# Error handlers for rate limiting
@router.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    response = JSONResponse(
        status_code=429,
        content={
            "success": False,
            "error_code": "RATE_LIMIT_EXCEEDED",
            "message": f"Rate limit exceeded: {exc.detail}"
        }
    )
    response = limiter._get_retry_after(request, response)
    return response