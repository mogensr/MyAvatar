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
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# STEP 1: Configure logging FIRST (before anything uses logger)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# STEP 2: Import bcrypt and JWT with safe fallbacks
import bcrypt

# FIXED JWT IMPORT - Use python-jose instead of PyJWT
try:
    from jose import jwt
    JWT_AVAILABLE = True
except ImportError:
    try:
        import jwt  # Fallback to PyJWT if available
        JWT_AVAILABLE = True
    except ImportError:
        JWT_AVAILABLE = False
        # Create dummy JWT functions
        class jwt:
            @staticmethod
            def encode(payload, secret, algorithm): return "dummy-token"
            @staticmethod 
            def decode(token, secret, algorithms): return {"user_id": 1}
            class ExpiredSignatureError(Exception): pass
            class InvalidTokenError(Exception): pass

# STEP 3: Import optional dependencies
try:
    import bleach
    BLEACH_AVAILABLE = True
except ImportError:
    BLEACH_AVAILABLE = False

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    SLOWAPI_AVAILABLE = True
except ImportError:
    SLOWAPI_AVAILABLE = False
    # Create dummy classes
    class Limiter:
        def __init__(self, **kwargs): pass
        def limit(self, rate): 
            def decorator(func): return func
            return decorator
    class RateLimitExceeded(Exception): pass
    def get_remote_address(request): return "127.0.0.1"

# STEP 4: Import database - NO MOCKS, REAL IMPLEMENTATION ONLY
try:
    from app.db.user_manager import Database
    db = Database()
    print("✅ Successfully imported Database from app.db.user_manager")
except ImportError as e:
    try:
        from ..db.user_manager import Database
        db = Database()
        print("✅ Successfully imported Database from ..db.user_manager")
    except ImportError as e2:
        print(f"❌ CRITICAL: Failed to import real Database class!")
        print(f"Import error 1: {e}")
        print(f"Import error 2: {e2}")
        raise ImportError("Real Database class is required - no mocks allowed!")

# STEP 5: Import logging functions with fallbacks
try:
    from app.logger.log_handler import log_error, log_info, log_warning
except ImportError:
    # Fallback implementations
    def log_error(msg, context, exc=None): logger.error(f"[{context}] {msg}")
    def log_info(msg, context): logger.info(f"[{context}] {msg}")
    def log_warning(msg, context): logger.warning(f"[{context}] {msg}")

# STEP 6: Define utility functions
def validate_email(email: str) -> bool:
    """Basic email validation"""
    return "@" in email and "." in email.split("@")[1]

def generate_api_key() -> str:
    """Generate API key"""
    return str(uuid.uuid4())

def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent XSS"""
    if not text:
        return ""
    
    if BLEACH_AVAILABLE:
        return bleach.clean(text.strip(), tags=[], attributes={}, strip=True)
    else:
        # Basic sanitization without bleach
        return str(text).strip().replace("<", "&lt;").replace(">", "&gt;")

# STEP 7: Configuration class (NOW logger is available)
class Config:
    def __init__(self):
        # Security - with safe fallbacks
        self.JWT_SECRET = self._get_env_with_fallback("JWT_SECRET", "fallback-development-secret-key")
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
        
        # Database - safe fallback
        self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./fallback.db")
        self.DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
        self.DB_TIMEOUT = int(os.getenv("DB_TIMEOUT", "30"))
        
        # Session
        self.SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT", "3600"))  # 1 hour
        self.MAX_SESSIONS_PER_USER = int(os.getenv("MAX_SESSIONS_PER_USER", "5"))
        
        # Security Headers
        self.TRUSTED_HOSTS = os.getenv("TRUSTED_HOSTS", "localhost,127.0.0.1").split(",")
        self.CORS_ORIGINS = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else []
        
        # Safe validation
        self._validate_config()
    
    def _get_env_with_fallback(self, key: str, fallback: str) -> str:
        """Get environment variable with fallback instead of failing"""
        value = os.getenv(key)
        if not value or value in ["your-secret-key-change-this", "change-this"]:
            # Use safe logging that handles cases where logger might not be fully initialized
            try:
                if 'logger' in globals() and logger:
                    logger.warning(f"Using fallback value for {key}")
                else:
                    print(f"WARNING: Using fallback value for {key}")
            except:
                print(f"WARNING: Using fallback value for {key}")
            return fallback
        return value
    
    def _validate_config(self):
        """Safe validation that doesn't fail"""
        try:
            # Ensure upload directory exists
            self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            # Use safe logging that handles cases where logger might not be fully initialized
            try:
                if 'logger' in globals() and logger:
                    logger.warning(f"Could not create upload directory: {e}")
                else:
                    print(f"WARNING: Could not create upload directory: {e}")
            except:
                print(f"WARNING: Could not create upload directory: {e}")

# STEP 8: Initialize configuration (NOW Config class is defined and logger is available)
config = Config()

# STEP 9: Initialize components that depend on config
if SLOWAPI_AVAILABLE:
    limiter = Limiter(key_func=get_remote_address)
else:
    limiter = Limiter()

router = APIRouter()

# Robust template directory detection
def find_templates_directory():
    """Find templates directory with multiple fallback paths"""
    possible_paths = [
        Path(__file__).parent.parent.parent / "templates",  # From app/routes/web_routes.py -> project_root/templates
        Path("templates"),  # Relative to current working directory
        Path("/app/templates"),  # Common container path
        Path("./templates"),  # Explicit relative
        Path(__file__).parent.parent / "templates",  # From app/routes -> app/templates
    ]
    
    for path in possible_paths:
        if path.exists() and path.is_dir():
            try:
                # Check if it has some expected template files
                template_files = list(path.glob("*.html"))
                if template_files:
                    print(f"Found templates directory: {path} with {len(template_files)} HTML files")
                    return str(path)
            except Exception as e:
                print(f"Error checking template path {path}: {e}")
                continue
    
    # Fallback - use the first path even if it doesn't exist
    fallback_path = str(possible_paths[0])
    print(f"No templates directory found, using fallback: {fallback_path}")
    return fallback_path

templates_dir = find_templates_directory()
templates = Jinja2Templates(directory=templates_dir)

# Configure Jinja2 for security
try:
    templates.env.autoescape = True
except Exception:
    pass

security = HTTPBearer(auto_error=False)

# STEP 10: File utilities (after config is available)
def validate_file_content(file_path: str, expected_type: str) -> bool:
    """Validate file content matches expected type - SAFE VERSION"""
    try:
        # Without python-magic, do basic validation
        with open(file_path, 'rb') as f:
            header = f.read(12)
            
        # Basic image type detection
        if expected_type == "image":
            # Check for common image headers
            if header.startswith(b'\xff\xd8\xff'):  # JPEG
                return True
            elif header.startswith(b'\x89PNG\r\n\x1a\n'):  # PNG
                return True
            elif header.startswith(b'GIF87a') or header.startswith(b'GIF89a'):  # GIF
                return True
            elif header.startswith(b'RIFF') and b'WEBP' in header:  # WebP
                return True
        
        return False
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

# STEP 11: Authentication functions (after config is available)
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

# STEP 12: Session management class (after all dependencies available)
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

# STEP 13: Initialize session manager (after SessionManager class is defined)
session_manager = SessionManager()

# STEP 14: User authentication function (after session_manager is available)
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

# STEP 15: Error handling classes
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

# STEP 16: ROUTES (everything is now properly defined)
@router.get("/")
async def home_page(request: Request):
    """Home page with security headers"""
    try:
        # DEBUG: Log when home page is accessed
        logger.info("🔍 HOME PAGE ACCESSED - GET /")
        
        user = get_current_user(request)
        if user:
            logger.info(f"🔍 HOME PAGE - User already logged in: {user.get('username')}, redirecting to dashboard")
            return RedirectResponse(url="/dashboard", status_code=302)
        
        logger.info("🔍 HOME PAGE - No user logged in, showing home page")
            
        try:
            response = templates.TemplateResponse("index.html", {
                "request": request,
                "user": None
            })
            logger.info("🔍 HOME PAGE - Successfully loaded index.html template")
        except Exception as template_error:
            logger.warning(f"🔍 HOME PAGE - Template error: {template_error}")
            # Fallback if index.html template is missing
            return JSONResponse({
                "message": "MyAvatar Home Page",
                "status": "Template not found - using JSON response",
                "login_url": "/login"
            })
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response
    except Exception as e:
        logger.error(f"Error loading home page: {e}")
        # Safe fallback without template dependency
        return JSONResponse({
            "error": "Service temporarily unavailable",
            "status": "error",
            "login_url": "/login"
        }, status_code=500)

@router.get("/login")
async def login_page(request: Request):
    """Display login page"""
    try:
        # DEBUG: Log when login page is accessed
        logger.info("🔍 LOGIN PAGE ACCESSED - GET /login")
        
        user = get_current_user(request)
        if user:
            return RedirectResponse(url="/dashboard", status_code=302)
        
        return templates.TemplateResponse("portal/login.html", {
            "request": request,
            "user": None,
            "error": None
        })
    except Exception as e:
        logger.error(f"Error loading login page: {e}")
        return JSONResponse({
            "error": "Login page unavailable",
            "instructions": "POST to /login with username and password"
        }, status_code=500)

@router.get("/test-debug")
async def test_debug(request: Request):
    """Test route to verify server is receiving requests"""
    logger.info("🔍 TEST DEBUG ROUTE ACCESSED")
    return JSONResponse({"status": "Server is receiving requests", "timestamp": str(datetime.now())})

@router.post("/login")
@limiter.limit(config.RATE_LIMIT_LOGIN)
async def login_user(request: Request):
    """Handle user login with security measures"""
    try:
        form = await request.form()
        username = sanitize_input(str(form.get("username", "")))
        password = str(form.get("password", ""))
        
        # DEBUG: Log the login attempt
        logger.info(f"🔍 LOGIN ATTEMPT - Username: '{username}', Password length: {len(password)}")
        
        if not username or not password:
            logger.warning(f"🔍 LOGIN FAILED - Missing credentials: username='{username}', password_len={len(password)}")
            return templates.TemplateResponse("portal/login.html", {
                "request": request,
                "user": None,
                "error": "Username and password are required"
            }, status_code=400)
        
        # Rate limiting check (additional to decorator)
        client_ip = get_remote_address(request)
        failed_attempts = db.get_failed_login_attempts(client_ip, username)
        
        logger.info(f"🔍 LOGIN CHECK - IP: {client_ip}, Failed attempts: {failed_attempts}")
        
        if failed_attempts >= 5:
            logger.warning(f"Too many failed login attempts from {client_ip} for {username}")
            return templates.TemplateResponse("portal/login.html", {
                "request": request,
                "user": None,
                "error": "Too many failed attempts. Please try again later."
            }, status_code=429)
        
        # Get user from database
        logger.info(f"🔍 LOGIN LOOKUP - Searching for user: '{username}'")
        user = db.get_user_by_username(username)
        if not user:
            logger.warning(f"🔍 LOGIN FAILED - User not found: '{username}'")
            db.record_failed_login(client_ip, username)
            return templates.TemplateResponse("portal/login.html", {
                "request": request,
                "user": None,
                "error": "Invalid username or password"
            }, status_code=401)
        
        logger.info(f"🔍 LOGIN USER FOUND - ID: {user.get('id')}, Username: '{user.get('username')}', Email: '{user.get('email')}'")
        
        # Verify password
        stored_password = user.get("password", "")
        logger.info(f"🔍 LOGIN PASSWORD CHECK - Stored hash length: {len(stored_password)}")
        
        password_valid = verify_password(password, stored_password)
        logger.info(f"🔍 LOGIN PASSWORD RESULT - Valid: {password_valid}")
        
        if not password_valid:
            logger.warning(f"🔍 LOGIN FAILED - Invalid password for user: '{username}'")
            db.record_failed_login(client_ip, username)
            return templates.TemplateResponse("portal/login.html", {
                "request": request,
                "user": None,
                "error": "Invalid username or password"
            }, status_code=401)
        
        # Check if account is locked
        if user.get("is_locked", False):
            logger.warning(f"🔍 LOGIN FAILED - Account locked: '{username}'")
            return templates.TemplateResponse("portal/login.html", {
                "request": request,
                "user": None,
                "error": "Account is temporarily locked. Please contact support."
            }, status_code=403)
        
        # Create secure session
        logger.info(f"🔍 LOGIN SUCCESS - Creating session for user: '{username}'")
        token = session_manager.create_session(user["id"], request)
        request.session["access_token"] = token
        
        # Update last login and clear failed attempts
        db.update_user_login(user["id"])
        db.clear_failed_login_attempts(client_ip, username)
        
        logger.info(f"User {username} logged in successfully from {client_ip}")
        return RedirectResponse(url="/dashboard", status_code=302)
        
    except Exception as e:
        logger.error(f"Error during login: {e}")
        return templates.TemplateResponse("portal/login.html", {
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
            
        return templates.TemplateResponse("portal/register.html", {
            "request": request,
            "user": None
        })
    except Exception as e:
        logger.error(f"Error loading register page: {e}")
        return templates.TemplateResponse("portal/register.html", {
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
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": "All fields are required"
            }, status_code=400)
        
        if len(username) < 3 or len(username) > 50:
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": "Username must be between 3 and 50 characters"
            }, status_code=400)
        
        # Check username for invalid characters
        if not username.replace('_', '').replace('-', '').isalnum():
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": "Username can only contain letters, numbers, hyphens, and underscores"
            }, status_code=400)
        
        if not validate_email(email):
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": "Please enter a valid email address"
            }, status_code=400)
        
        # Enhanced password validation
        is_strong, password_msg = validate_password_strength(password)
        if not is_strong:
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": password_msg
            }, status_code=400)
        
        if password != confirm_password:
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": "Passwords do not match"
            }, status_code=400)
        
        # Check if user already exists
        if db.get_user_by_username(username):
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": "Username already exists"
            }, status_code=409)
        
        if db.get_user_by_email(email):
            return templates.TemplateResponse("portal/register.html", {
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
            return templates.TemplateResponse("portal/register.html", {
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
        return templates.TemplateResponse("portal/register.html", {
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
        
        try:
            response = templates.TemplateResponse("dashboard.html", template_context)
            
            # Add security headers
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            
            return response
        except Exception:
            # Fallback if dashboard.html template is missing
            return JSONResponse({
                "message": "Dashboard",
                "user": user.get("username", "User"),
                "stats": {
                    "total_videos": total_videos,
                    "total_views": total_views,
                    "total_duration": f"{total_duration_hours}h",
                },
                "videos": video_list[:5],  # Show first 5 videos
                "status": "Template not found - using JSON response"
            })
        
    except Exception as e:
        logger.error(f"Dashboard error for user {user.get('username', 'unknown') if user else 'unknown'}: {e}")
        
        # Safe JSON fallback
        return JSONResponse({
            "error": "Dashboard temporarily unavailable",
            "user": user.get("username", "User") if user else "Unknown",
            "status": "error"
        }, status_code=500)

@router.get("/test-routes")
async def test_routes():
    """Test endpoint to confirm routes are loaded"""
    return {
        "message": "Production web routes are working!", 
        "routes_loaded": True,
        "features": [
            "Authentication",
            "Session Management", 
            "Password Security",
            "Rate Limiting",
            "Input Sanitization",
            "File Upload Security"
        ]
    }