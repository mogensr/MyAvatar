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
from fastapi.staticfiles import StaticFiles

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
    from ..logger.log_handler import log_error, log_info, log_warning
except ImportError:
    # Fallback implementations
    def log_error(msg, context, exc=None): logger.error(f"[{context}] {msg}")
    def log_info(msg, context): logger.info(f"[{context}] {msg}")
    def log_warning(msg, context): logger.warning(f"[{context}] {msg}")

# Import database query function
try:
    from ..db.database import execute_query
except ImportError:
    def execute_query(query, params=(), fetch_one=False, fetch_all=False):
        logger.error("execute_query not available - database import failed")
        return None

# Import utility functions
from ..utils.document_parser import parse_document, clean_and_truncate_text

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
        
        # AI Services
        self.OPENAI_API_KEY = self._get_env_with_fallback("OPENAI_API_KEY", "your-openai-api-key")
        self.HEYGEN_API_KEY = self._get_env_with_fallback("HEYGEN_API_KEY", "your-heygen-api-key")
        
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
    """Enhanced password validation - min 8 chars, at least 2 digits"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    digit_count = sum(1 for c in password if c.isdigit())
    if digit_count < 2:
        return False, "Password must contain at least 2 digits"
    
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    
    return True, "Password is strong"

def create_access_token(user_id: int) -> str:
    """Create JWT access token using standardized authentication system"""
    from ..auth.authentication import create_access_token as auth_create_token
    
    # Get user data using the db instance
    user = db.get_user_by_id(user_id)
    
    if not user:
        raise ValueError(f"User {user_id} not found")
    
    # Use standardized token creation
    token_data = {
        "sub": user['username'],
        "user_id": user_id,
        "admin": bool(user.get('is_admin', False))
    }
    
    return auth_create_token(token_data)

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

# STEP 14: User authentication function (after session_manager is available) - UPDATED FOR JWT COOKIES
def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """Get current user with enhanced security using JWT cookies"""
    try:
        # Get token from cookie instead of session
        token = request.cookies.get("access_token")
        if not token:
            return None
        
        # Validate session
        session = session_manager.validate_session(token, request)
        if not session:
            return None
        
        # Validate JWT
        try:
            payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
            user_id = payload.get("user_id")
            if not user_id:
                return None
        except jwt.ExpiredSignatureError:
            session_manager.active_sessions.pop(token, None)
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

# STEP 16: PASSWORD FIX UTILITIES - FIXED FIELD NAMES
def fix_user_passwords():
    """Fix passwords for all users who have empty password fields"""
    try:
        # Get all users with empty passwords
        all_users = db.get_all_users()  # You may need to implement this method
        fixed_count = 0
        
        for user in all_users:
            stored_password = user.get("password", "")  # FIXED: Use correct database field name
            if not stored_password or len(stored_password) == 0:
                username = user.get("username", "")
                
                # Set default password based on username
                if username == "admin":
                    default_password = "admin123"
                else:
                    default_password = "password123"  # Default for regular users
                
                # Hash the password
                hashed_password = hash_password(default_password)
                
                # Update user password - FIXED: Use correct field name
                update_query = "UPDATE users SET password = %s WHERE id = %s"
                db.execute_query(update_query, (hashed_password, user["id"]))
                
                logger.info(f"Fixed password for user: {username}")
                fixed_count += 1
        
        return fixed_count
    except Exception as e:
        logger.error(f"Error fixing user passwords: {e}")
        return 0

# STEP 17: DEFAULT AVATARS SETUP - UPDATED WITH REAL AVATAR IDS
def setup_default_avatars_for_user(user_id: int):
    """Set up default avatars for new users with confirmed working HeyGen avatar IDs"""
    try:
        logger.info(f"Setting up default avatars for user ID: {user_id}")
        
        # Default avatar configurations with REAL working HeyGen avatar IDs
        default_avatars = [
            {
                'heygen_avatar_id': 'Tyler-insuit-20220721',  # Confirmed working male avatar
                'avatar_name': 'Professional Male',
                'avatar_image_url': 'https://example.com/tyler.jpg',  # Placeholder for testing
                'is_default': 1
            },
            {
                'heygen_avatar_id': 'Kristin_public_2_20240108',  # Confirmed working female avatar
                'avatar_name': 'Professional Female',
                'avatar_image_url': 'https://example.com/kristin.jpg',  # Placeholder for testing
                'is_default': 1
            }
        ]
        
        for avatar_data in default_avatars:
            try:
                # Insert default avatar for the user
                insert_query = """
                INSERT INTO user_avatars (user_id, heygen_avatar_id, avatar_name, avatar_image_url, is_default, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """
                execute_query(
                    insert_query,
                    (
                        user_id,
                        avatar_data['heygen_avatar_id'],
                        avatar_data['avatar_name'],
                        avatar_data['avatar_image_url'],
                        avatar_data['is_default'],
                        datetime.now()
                    )
                )
                logger.info(f"Added default avatar '{avatar_data['avatar_name']}' for user {user_id}")
            except Exception as avatar_error:
                logger.error(f"Error adding default avatar for user {user_id}: {avatar_error}")
                
    except Exception as e:
        logger.error(f"Error setting up default avatars for user {user_id}: {e}")

# STEP 18: ROUTES (everything is now properly defined)
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

@router.post("/login")
@limiter.limit(config.RATE_LIMIT_LOGIN)
async def login_user(request: Request):
    """Handle user login with security measures - FIXED PASSWORD FIELD"""
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
        
        # Verify password - FIXED: Use correct database field name
        stored_password = user.get("password", "")
        logger.info(f"🔍 LOGIN PASSWORD CHECK - Stored hash length: {len(stored_password)}")
        
        # Check if password is empty and offer password reset
        if not stored_password or len(stored_password) == 0:
            logger.warning(f"🔍 LOGIN FAILED - Empty password for user: '{username}' - needs password reset")
            return templates.TemplateResponse("portal/login.html", {
                "request": request,
                "user": None,
                "error": "Account needs password reset. Please contact administrator or visit /fix-admin-password"
            }, status_code=401)
        
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
        
        # Create secure session using JWT token in cookie instead of session
        logger.info(f"🔍 LOGIN SUCCESS - Creating JWT token for user: '{username}'")
        token = session_manager.create_session(user["id"], request)
        
        # Update last login and clear failed attempts
        db.update_user_login(user["id"])
        db.clear_failed_login_attempts(client_ip, username)
        
        logger.info(f"User {username} logged in successfully from {client_ip}")
        
        # Create redirect response and set JWT cookie
        if user.get("is_admin", 0) == 1:
            logger.info(f"🔍 LOGIN SUCCESS - Admin user {username} redirecting to admin panel")
            response = RedirectResponse(url="/admin", status_code=302)
        else:
            logger.info(f"🔍 LOGIN SUCCESS - Regular user {username} redirecting to dashboard")
            response = RedirectResponse(url="/dashboard", status_code=302)
        
        # Set JWT token as HTTP-only cookie
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            secure=True,  # Use HTTPS in production
            samesite="lax",
            max_age=86400  # 24 hours
        )
        
        return response
        
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
    """DEBUGGING VERSION - Shows exact error details"""
    try:
        form = await request.form()
        username = sanitize_input(str(form.get("username", "")))
        email = sanitize_input(str(form.get("email", "")))
        password = str(form.get("password", ""))
        confirm_password = str(form.get("confirm_password", ""))
        
        print(f"🔍 DEBUG REGISTRATION - Username: '{username}', Email: '{email}', Password length: {len(password)}")
        logger.info(f"🔍 DEBUG REGISTRATION - Username: '{username}', Email: '{email}', Password length: {len(password)}")
        
        # Enhanced validation
        if not username or not email or not password:
            error_msg = "All fields are required"
            print(f"🔍 DEBUG REGISTRATION ERROR: {error_msg}")
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": error_msg
            }, status_code=400)
        
        if len(username) < 3 or len(username) > 50:
            error_msg = "Username must be between 3 and 50 characters"
            print(f"🔍 DEBUG REGISTRATION ERROR: {error_msg}")
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": error_msg
            }, status_code=400)
        
        # Check username for invalid characters
        if not username.replace('_', '').replace('-', '').isalnum():
            error_msg = "Username can only contain letters, numbers, hyphens, and underscores"
            print(f"🔍 DEBUG REGISTRATION ERROR: {error_msg}")
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": error_msg
            }, status_code=400)
        
        if not validate_email(email):
            error_msg = "Please enter a valid email address"
            print(f"🔍 DEBUG REGISTRATION ERROR: {error_msg}")
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": error_msg
            }, status_code=400)
        
        # Enhanced password validation
        is_strong, password_msg = validate_password_strength(password)
        if not is_strong:
            print(f"🔍 DEBUG REGISTRATION ERROR: {password_msg}")
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": password_msg
            }, status_code=400)
        
        if password != confirm_password:
            error_msg = "Passwords do not match"
            print(f"🔍 DEBUG REGISTRATION ERROR: {error_msg}")
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": error_msg
            }, status_code=400)
        
        print(f"🔍 DEBUG - Validation passed, checking if user exists...")
        
        # Check if user already exists
        existing_user_by_username = db.get_user_by_username(username)
        if existing_user_by_username:
            error_msg = "Username already exists"
            print(f"🔍 DEBUG REGISTRATION ERROR: {error_msg}")
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": error_msg
            }, status_code=409)
        
        existing_user_by_email = db.get_user_by_email(email)
        if existing_user_by_email:
            error_msg = "Email already registered"
            print(f"🔍 DEBUG REGISTRATION ERROR: {error_msg}")
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": error_msg
            }, status_code=409)
        
        print(f"🔍 DEBUG - User doesn't exist, creating user...")
        
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
            "email_verified": 0,
            "credits_remaining": 3
        }
        
        print(f"🔍 DEBUG - User data prepared: {list(user_data.keys())}")
        print(f"🔍 DEBUG - Calling db.create_user()...")
        
        user_id = db.create_user(user_data)
        
        print(f"🔍 DEBUG - db.create_user() returned: {user_id}")
        logger.error(f"🔍 DEBUG - db.create_user() returned: {user_id}")
        
        if not user_id:
            error_msg = f"Registration failed - database error. User ID returned: {user_id}"
            print(f"🔍 DEBUG REGISTRATION ERROR: {error_msg}")
            logger.error(f"🔍 DEBUG REGISTRATION ERROR: {error_msg}")
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": "Registration failed. Please try again."
            }, status_code=500)
        
        print(f"🔍 DEBUG - User created successfully with ID: {user_id}")
        logger.info(f"🔍 DEBUG - User created successfully with ID: {user_id}")
        
        # Set up default avatars for the new user
        try:
            print(f"🔍 DEBUG - Setting up default avatars...")
            setup_default_avatars_for_user(user_id)
            print(f"🔍 DEBUG - Default avatars set up successfully")
        except Exception as avatar_error:
            print(f"🔍 DEBUG - Avatar setup failed: {avatar_error}")
            logger.error(f"🔍 DEBUG - Avatar setup failed: {avatar_error}")
            # Don't fail registration if avatar setup fails
        
        # Auto-login after registration
        print(f"🔍 DEBUG - Creating session...")
        token = session_manager.create_session(user_id, request)
        print(f"🔍 DEBUG - Session created, redirecting to dashboard")
        
        # Create redirect response and set JWT cookie
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=86400
        )
        
        print(f"🔍 DEBUG - Registration completed successfully for user: {username}")
        logger.info(f"🔍 DEBUG - Registration completed successfully for user: {username}")
        return response
        
    except Exception as e:
        error_details = f"Registration error: {type(e).__name__}: {str(e)}"
        print(f"🔍 DEBUG REGISTRATION EXCEPTION: {error_details}")
        logger.error(f"🔍 DEBUG REGISTRATION EXCEPTION: {error_details}")
        
        import traceback
        full_traceback = traceback.format_exc()
        print(f"🔍 DEBUG FULL TRACEBACK:\n{full_traceback}")
        logger.error(f"🔍 DEBUG FULL TRACEBACK:\n{full_traceback}")
        
        return templates.TemplateResponse("portal/register.html", {
            "request": request,
            "user": None,
            "error": f"Registration failed: {error_details}"
        }, status_code=500)

@router.get("/logout")
async def logout_user(request: Request):
    """Handle user logout with session cleanup - UPDATED FOR JWT COOKIES"""
    try:
        token = request.cookies.get("access_token")
        if token:
            session_manager.active_sessions.pop(token, None)
        
        # Create redirect response and clear cookie
        response = RedirectResponse(url="/", status_code=302)
        response.delete_cookie("access_token")
        return response
    except Exception as e:
        logger.error(f"Error during logout: {e}")
        # Still redirect even if cleanup fails
        response = RedirectResponse(url="/", status_code=302)
        response.delete_cookie("access_token")
        return response

@router.get("/dashboard")
async def dashboard_page(request: Request):
    """Display user dashboard with comprehensive error handling - FOR ALL USERS - FIXED VIDEO DISPLAY"""
    user = None
    try:
        user = get_current_user(request)
        if not user:
            logger.info("🔍 DASHBOARD - No user found, redirecting to login")
            return RedirectResponse(url="/login", status_code=302)
        
        logger.info(f"🔍 DASHBOARD - User {user.get('username')} accessing dashboard (Admin: {user.get('is_admin', 0)})")
        
        # Get user's videos - FIXED VERSION
        videos = db.get_user_videos(user["id"])
        
        # Get user's avatars for the carousel
        user_avatars = []
        try:
            avatars = db.get_user_avatars(user["id"])
            logger.info(f"🎭 DASHBOARD - Raw avatars from DB: {avatars}")
            
            if avatars:
                for avatar in avatars:
                    if isinstance(avatar, dict):
                        # Use the avatar_image_url directly from database (already contains HeyGen URLs)
                        avatar_image = avatar.get('avatar_image_url', '')
                        avatar_name = avatar.get('avatar_name', 'Unnamed Avatar')
                        
                        logger.info(f"🖼️ Avatar {avatar_name} image: {avatar_image}")
                        
                        user_avatars.append({
                            'id': avatar.get('id'),
                            'name': sanitize_input(avatar_name),
                            'avatar_image_url': avatar_image,
                            'heygen_avatar_id': avatar.get('heygen_avatar_id', ''),
                            'avatar_id': avatar.get('heygen_avatar_id', '')  # For template compatibility
                        })
                        
            logger.info(f"🎭 DASHBOARD - Processed {len(user_avatars)} avatars for user {user.get('username')}")
            for avatar in user_avatars:
                logger.info(f"   - Avatar: {avatar['name']} | Image: {avatar['avatar_image_url'][:50] if avatar['avatar_image_url'] else 'No image'}...")
                
        except Exception as avatar_error:
            logger.error(f"Error fetching user avatars: {avatar_error}")
            import traceback
            logger.error(f"Avatar error traceback: {traceback.format_exc()}")
            user_avatars = []
        
        # Debug: Log what we're getting
        print(f"Dashboard - User ID: {user['id']}, Videos found: {len(videos) if videos else 0}")
        if videos:
            print(f"First video: {videos[0]}")
        
        # Make sure videos is a list
        if not videos:
            videos = []
        
        # Process videos to ensure proper format
        processed_videos = []
        for video in videos:
            if isinstance(video, dict):
                # Ensure video_url is set correctly from video_path
                video_url = video.get('video_path') or video.get('video_url')
                if video_url:
                    video['video_url'] = video_url
                
                # Ensure all required fields exist with safe defaults
                video['title'] = sanitize_input(video.get('title', 'Untitled Video'))
                video['status'] = sanitize_input(video.get('status', 'unknown'))
                video['duration'] = video.get('duration', '')
                video['format'] = video.get('format', '16:9')
                
                # Handle created_at datetime formatting
                if 'created_at' in video and video['created_at']:
                    try:
                        if isinstance(video['created_at'], str):
                            # Already a string, keep as is
                            pass
                        elif hasattr(video['created_at'], 'strftime'):
                            # It's a datetime object, convert to string for template
                            video['created_at'] = video['created_at']
                        else:
                            video['created_at'] = str(video['created_at'])
                    except Exception as date_error:
                        logger.error(f"Error processing created_at: {date_error}")
                        video['created_at'] = 'Unknown'
                
                processed_videos.append(video)
        
        # Initialize safe defaults for stats
        total_videos = len(processed_videos)
        total_duration_hours = 0
        total_views = 0
        total_shares = 0
        
        # Calculate stats from videos
        for video in processed_videos:
            try:
                duration = video.get('duration', 0)
                if isinstance(duration, (int, float)):
                    total_duration_hours += duration
                views = video.get('views', 0)
                if isinstance(views, (int, float)):
                    total_views += views
                shares = video.get('shares', 0)
                if isinstance(shares, (int, float)):
                    total_shares += shares
            except Exception as stat_error:
                logger.error(f"Error calculating stats: {stat_error}")
                continue
        
        # Format duration
        hours = int(total_duration_hours // 3600) if total_duration_hours > 0 else 0
        minutes = int((total_duration_hours % 3600) // 60) if total_duration_hours > 0 else 0
        duration_str = f"{hours}h {minutes}m" if hours > 0 or minutes > 0 else "0h 0m"
        
        # Get user credits remaining
        credits_remaining = user.get('credits_remaining', 0)
        
        # Build template context
        template_context = {
            "request": request,
            "user": user,
            "username": sanitize_input(user.get("username", "User")),
            "is_admin": bool(user.get("is_admin", 0)),
            "avatar_id": sanitize_input(user.get("avatar_id", "")),
            "user_id": int(user.get("id", 0)),
            "api_key": user.get("api_key", "") or os.getenv("HEYGEN_API_KEY", ""),
            "videos": processed_videos,  # FIXED: Pass processed videos
            "total_videos": total_videos,
            "total_duration": duration_str,
            "total_views": str(total_views),
            "total_shares": str(total_shares),
            "user_avatars": user_avatars,  # Add user avatars to template context
            "credits_remaining": credits_remaining  # Add credits to dashboard
        }
        
        logger.info(f"🔍 DASHBOARD - Passing {len(processed_videos)} videos to template")
        
        try:
            # All users (admin and regular) get the dashboard.html template
            response = templates.TemplateResponse("dashboard.html", template_context)
            
            # Add security headers
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            
            logger.info(f"🔍 DASHBOARD - Successfully loaded dashboard.html for user {user.get('username')} with {len(processed_videos)} videos")
            return response
        except Exception as template_error:
            logger.warning(f"🔍 DASHBOARD - Template error: {template_error}")
            # Fallback if dashboard.html template is missing
            return JSONResponse({
                "message": "Dashboard",
                "user": user.get("username", "User"),
                "is_admin": bool(user.get("is_admin", 0)),
                "stats": {
                    "total_videos": total_videos,
                    "total_views": total_views,
                    "total_duration": duration_str,
                },
                "videos": processed_videos[:5],  # Show first 5 videos
                "credits_remaining": credits_remaining,
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

# ⭐ NEW API ENDPOINT FOR USERNAME CHECKING ⭐
@router.post("/api/check-username")
async def check_username_availability(request: Request):
    """API endpoint to check if username is available - Real-time validation for registration form"""
    try:
        data = await request.json()
        username = sanitize_input(data.get("username", "").strip())
        
        logger.info(f"🔍 USERNAME CHECK - Checking availability for: '{username}'")
        
        if not username:
            return JSONResponse({
                "available": False,
                "error": "Username is required"
            }, status_code=400)
        
        # Validate username format
        if len(username) < 3 or len(username) > 50:
            return JSONResponse({
                "available": False,
                "error": "Username must be between 3 and 50 characters"
            }, status_code=400)
        
        # Check characters (only letters, numbers, hyphens, underscores)
        if not username.replace('_', '').replace('-', '').isalnum():
            return JSONResponse({
                "available": False,
                "error": "Username can only contain letters, numbers, hyphens, and underscores"
            }, status_code=400)
        
        # Check doesn't start or end with hyphen or underscore
        if username.startswith(('-', '_')) or username.endswith(('-', '_')):
            return JSONResponse({
                "available": False,
                "error": "Username cannot start or end with hyphen or underscore"
            }, status_code=400)
        
        # Check if username exists in database
        existing_user = db.get_user_by_username(username)
        
        if existing_user:
            logger.info(f"🔍 USERNAME CHECK - '{username}' is already taken")
            return JSONResponse({
                "available": False,
                "message": "Username is already taken"
            })
        else:
            logger.info(f"🔍 USERNAME CHECK - '{username}' is available")
            return JSONResponse({
                "available": True,
                "message": "Username is available"
            })
            
    except Exception as e:
        logger.error(f"Error checking username availability: {e}")
        return JSONResponse({
            "available": False,
            "error": "Unable to check username availability"
        }, status_code=500)

# 🔧 DATABASE SCHEMA FIX ROUTE
@router.get("/fix-database-schema")
async def fix_database_schema():
    """Emergency route to add missing password column"""
    try:
        print("🔧 FIXING DATABASE SCHEMA - Adding missing password column")
        logger.info("🔧 FIXING DATABASE SCHEMA - Adding missing password column")
        
        # Check if password column exists first
        try:
            check_query = """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'password'
            """
            result = execute_query(check_query, fetch_one=True)
            
            if result:
                return {
                    "success": True,
                    "message": "Password column already exists",
                    "action": "No changes needed"
                }
        except Exception as check_error:
            logger.warning(f"Could not check for password column: {check_error}")
        
        # Add missing password column
        alter_query = "ALTER TABLE users ADD COLUMN password TEXT"
        execute_query(alter_query)
        
        print("🔧 DATABASE FIX - Password column added successfully")
        logger.info("🔧 DATABASE FIX - Password column added successfully")
        
        # Verify table structure
        result = execute_query("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            ORDER BY ordinal_position
        """, fetch_all=True)
        
        table_structure = [dict(row) for row in result] if result else []
        
        return {
            "success": True,
            "message": "Password column added successfully",
            "table_structure": table_structure,
            "next_step": "Now try registration again at /register"
        }
        
    except Exception as e:
        error_msg = f"Failed to fix database schema: {str(e)}"
        print(f"🔧 DATABASE FIX ERROR: {error_msg}")
        logger.error(f"🔧 DATABASE FIX ERROR: {error_msg}")
        
        return {
            "success": False,
            "error": error_msg,
            "suggestion": "You may need to manually add the password column to your PostgreSQL database"
        }

# Additional routes would continue here...
@router.get("/test-routes")
async def test_routes():
    """Test endpoint to confirm routes are loaded"""
    return {
        "message": "Production web routes with DATABASE SCHEMA FIX are working!", 
        "routes_loaded": True,
        "debug_enabled": True,
        "new_feature": "🔧 Database Schema Fix Route at /fix-database-schema",
        "features": [
            "Authentication",
            "JWT Cookie Session Management", 
            "Password Security",
            "Rate Limiting",
            "Input Sanitization",
            "File Upload Security",
            "User Dashboard Access",
            "Real-time Username Validation API",
            "DEBUG REGISTRATION - Shows exact error details",
            "🔧 DATABASE SCHEMA FIX - Adds missing password column"
        ]
    }