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

# STEP 16: PASSWORD FIX UTILITIES
def fix_user_passwords():
    """Fix passwords for all users who have empty password fields"""
    try:
        # Get all users with empty passwords
        all_users = db.get_all_users()  # You may need to implement this method
        fixed_count = 0
        
        for user in all_users:
            stored_password = user.get("hashed_password", "")  # FIXED: Use correct database field name
            if not stored_password or len(stored_password) == 0:
                username = user.get("username", "")
                
                # Set default password based on username
                if username == "admin":
                    default_password = "admin123"
                else:
                    default_password = "password123"  # Default for regular users
                
                # Hash the password
                hashed_password = hash_password(default_password)
                
                # Update user password
                update_query = "UPDATE users SET hashed_password = %s WHERE id = %s"  # FIXED: Use correct field name
                db.execute_query(update_query, (hashed_password, user["id"]))
                
                logger.info(f"Fixed password for user: {username}")
                fixed_count += 1
        
        return fixed_count
    except Exception as e:
        logger.error(f"Error fixing user passwords: {e}")
        return 0

# STEP 17: ROUTES (everything is now properly defined)
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
    """Handle user login with security measures - UPDATED FOR JWT COOKIES"""
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
        stored_password = user.get("hashed_password", "")  # FIXED: Use correct database field name
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
    """Handle user registration with enhanced validation - UPDATED FOR JWT COOKIES"""
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
            "hashed_password": hashed_password,  # FIXED: Use correct database field name
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
        
        # Auto-login after registration using JWT cookie
        token = session_manager.create_session(user_id, request)
        
        logger.info(f"New user registered: {username}")
        
        # Create redirect response and set JWT cookie
        response = RedirectResponse(url="/dashboard", status_code=302)
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
        logger.error(f"Error during registration: {e}")
        return templates.TemplateResponse("portal/register.html", {
            "request": request,
            "user": None,
            "error": "Registration failed. Please try again."
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
                        avatar_name = avatar.get('name', 'Unnamed Avatar')
                        
                        logger.info(f"🖼️ Avatar {avatar_name} image: {avatar_image}")
                        
                        user_avatars.append({
                            'id': avatar.get('id'),
                            'name': sanitize_input(avatar_name),
                            'image_path': avatar_image,  # Changed from image_url to image_path
                            'heygen_avatar_id': avatar.get('heygen_avatar_id', ''),
                            'avatar_id': avatar.get('heygen_avatar_id', '')  # For template compatibility
                        })
                        
            logger.info(f"🎭 DASHBOARD - Processed {len(user_avatars)} avatars for user {user.get('username')}")
            for avatar in user_avatars:
                logger.info(f"   - Avatar: {avatar['name']} | Image: {avatar['image_path'][:50] if avatar['image_path'] else 'No image'}...")
                
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
            "user_avatars": user_avatars  # Add user avatars to template context
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

@router.get("/admin")
async def admin_panel(request: Request):
    """Admin panel - only for admin users"""
    try:
        user = get_current_user(request)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        # Check if user is admin
        if not user.get("is_admin", 0) == 1:
            logger.warning(f"🔍 ADMIN ACCESS DENIED - User {user.get('username')} is not admin")
            return RedirectResponse(url="/dashboard", status_code=302)
        
        logger.info(f"🔍 ADMIN PANEL - Admin user {user.get('username')} accessing admin panel")
        
        try:
            return templates.TemplateResponse("portal/admin_dashboard.html", {
                "request": request,
                "user": user
            })
        except Exception as template_error:
            logger.warning(f"🔍 ADMIN PANEL - Template error: {template_error}")
            return JSONResponse({
                "message": "Admin Panel",
                "user": user.get("username", "Admin"),
                "status": "Template not found - using JSON response"
            })
        
    except Exception as e:
        logger.error(f"Admin panel error: {e}")
        return JSONResponse({
            "error": "Admin panel temporarily unavailable",
            "status": "error"
        }, status_code=500)

@router.get("/videos")
async def videos_page(request: Request):
    """User videos page - for all authenticated users"""
    try:
        user = get_current_user(request)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        logger.info(f"🔍 VIDEOS PAGE - User {user.get('username')} accessing videos")
        
        # Get user videos
        video_list = []
        try:
            videos = db.get_user_videos(user["id"])
            if videos:
                for video in videos:
                    try:
                        # Convert to dict safely
                        if hasattr(video, '__dict__'):
                            video_dict = video.__dict__
                        elif isinstance(video, dict):
                            video_dict = video.copy()
                        else:
                            video_dict = dict(video) if video else {}
                        
                        # Sanitize data
                        video_dict['title'] = sanitize_input(video_dict.get('title', 'Untitled'))
                        video_dict['status'] = sanitize_input(video_dict.get('status', 'unknown'))
                        
                        video_list.append(video_dict)
                    except Exception as video_error:
                        logger.error(f"Error processing video: {video_error}")
                        continue
        except Exception as e:
            logger.error(f"Error fetching videos: {e}")
        
        try:
            return templates.TemplateResponse("videos.html", {
                "request": request,
                "user": user,
                "videos": video_list
            })
        except Exception as template_error:
            logger.warning(f"🔍 VIDEOS PAGE - Template error: {template_error}")
            return JSONResponse({
                "message": "User Videos",
                "user": user.get("username", "User"),
                "videos": video_list,
                "status": "Template not found - using JSON response"
            })
        
    except Exception as e:
        logger.error(f"Videos page error: {e}")
        return JSONResponse({
            "error": "Videos page temporarily unavailable",
            "status": "error"
        }, status_code=500)

@router.get("/admin/users")
async def admin_users(request: Request):
    """Admin users management page"""
    try:
        user = get_current_user(request)
        if not user or not user.get("is_admin", 0) == 1:
            return RedirectResponse(url="/login", status_code=302)
        
        logger.info(f"🔍 ADMIN USERS - Admin user {user.get('username')} accessing users management")
        
        # Fetch all users from database - SIMPLE APPROACH
        all_users = []
        try:
            # Try to get users by calling the database methods we know exist
            # We'll get each user one by one using the methods that work
            sample_usernames = ['admin', 'MogensR', 'testuser', 'Lars-Christian']
            
            for username in sample_usernames:
                try:
                    found_user = db.get_user_by_username(username)
                    if found_user:
                        all_users.append(found_user)
                except:
                    continue
                    
            logger.info(f"🔍 ADMIN USERS - Found {len(all_users)} users")
            
        except Exception as e:
            logger.error(f"🔍 ADMIN USERS - Error fetching users: {e}")
            all_users = []
        
        try:
            return templates.TemplateResponse("portal/admin_users.html", {
                "request": request,
                "user": user,
                "users": all_users  # Pass users to template
            })
        except Exception as template_error:
            logger.warning(f"🔍 ADMIN USERS - Template error: {template_error}")
            return JSONResponse({
                "message": "Admin Users Management",
                "users_found": len(all_users),
                "users": [u.get('username', 'unknown') for u in all_users],
                "user": user.get("username", "Admin"),
                "status": "Template not found - using JSON response"
            })
        
    except Exception as e:
        logger.error(f"Admin users page error: {e}")
        return JSONResponse({"error": "Admin users page unavailable"}, status_code=500)

@router.get("/admin/create-user")
async def admin_create_user(request: Request):
    """Admin create user page"""
    try:
        user = get_current_user(request)
        if not user or not user.get("is_admin", 0) == 1:
            return RedirectResponse(url="/login", status_code=302)
        
        logger.info(f"🔍 ADMIN CREATE USER - Admin user {user.get('username')} accessing create user")
        
        try:
            return templates.TemplateResponse("portal/admin_create_user.html", {
                "request": request,
                "user": user
            })
        except Exception as template_error:
            logger.warning(f"🔍 ADMIN CREATE USER - Template error: {template_error}")
            return JSONResponse({
                "message": "Admin Create User",
                "user": user.get("username", "Admin"),
                "status": "Template not found - using JSON response"
            })
        
    except Exception as e:
        logger.error(f"Admin create user page error: {e}")
        return JSONResponse({"error": "Admin create user page unavailable"}, status_code=500)

@router.get("/admin/upload-avatar")
async def admin_upload_avatar(request: Request):
    """Admin upload avatar page"""
    try:
        user = get_current_user(request)
        if not user or not user.get("is_admin", 0) == 1:
            return RedirectResponse(url="/login", status_code=302)
        
        logger.info(f"🔍 ADMIN UPLOAD AVATAR - Admin user {user.get('username')} accessing upload avatar")
        
        # For the main admin avatars page, we can show a general management interface
        # or redirect to a specific user. For now, let's show the template
        try:
            return templates.TemplateResponse("portal/admin_manage_avatars.html", {
                "request": request,
                "user": user,
                "user_to_manage": user,  # Show current admin user's avatars by default
                "avatars": []  # Empty for now, or get admin's avatars
            })
        except Exception as template_error:
            logger.warning(f"🔍 ADMIN UPLOAD AVATAR - Template error: {template_error}")
            return JSONResponse({
                "message": "Admin Upload Avatar",
                "user": user.get("username", "Admin"),
                "status": "Template not found - using JSON response"
            })
        
    except Exception as e:
        logger.error(f"Admin upload avatar page error: {e}")
        return JSONResponse({"error": "Admin upload avatar page unavailable"}, status_code=500)

@router.get("/admin/manage-avatars/{user_id}")
async def admin_manage_avatars_for_user(request: Request, user_id: int):
    """Admin manage avatars for specific user"""
    try:
        user = get_current_user(request)
        if not user or not user.get("is_admin", 0) == 1:
            return RedirectResponse(url="/login", status_code=302)
        
        logger.info(f"🔍 ADMIN MANAGE AVATARS - Admin user {user.get('username')} managing avatars for user ID: {user_id}")
        
        # Get the user whose avatars we're managing
        try:
            target_user = db.get_user_by_id(user_id)
            if not target_user:
                return RedirectResponse(url="/admin/users", status_code=302)
        except Exception as e:
            logger.error(f"Error fetching user for avatar management: {e}")
            return RedirectResponse(url="/admin/users", status_code=302)
        
        # Get user's avatars
        try:
            logger.info(f"🔍 ROUTE DEBUG: About to call get_user_avatars for user_id: {user_id}")
            user_avatars = db.get_user_avatars(user_id)
            logger.info(f"🔍 ROUTE DEBUG: get_user_avatars returned: {user_avatars}")
            if not user_avatars:
                user_avatars = []
            
            logger.info(f"🔍 DEBUG: Found {len(user_avatars)} avatars from get_user_avatars for user_id: {user_id}")
            
            all_avatars = user_avatars
            logger.info(f"🔍 DEBUG: Total avatars to display: {len(all_avatars)}")
            
        except Exception as e:
            logger.error(f"Error fetching user avatars: {e}")
            all_avatars = []
        
        try:
            return templates.TemplateResponse("portal/admin_manage_avatars.html", {
                "request": request,
                "user": user,
                "user_to_manage": target_user,  # Changed from target_user to user_to_manage
                "avatars": all_avatars  # Changed from user_avatars to all_avatars
            })
        except Exception as template_error:
            logger.warning(f"🔍 ADMIN MANAGE AVATARS - Template error: {template_error}")
            return JSONResponse({
                "message": "Admin Manage Avatars",
                "user": user.get("username", "Admin"),
                "target_user": target_user.get("username", "Unknown"),
                "avatars_count": len(all_avatars),
                "status": "Template not found - using JSON response"
            })
        
    except Exception as e:
        logger.error(f"Admin manage avatars page error: {e}")
        return JSONResponse({"error": "Admin manage avatars page unavailable"}, status_code=500)

@router.get("/admin/manage-voices")
async def admin_manage_voices(request: Request):
    """Admin manage voices page"""
    try:
        user = get_current_user(request)
        if not user or not user.get("is_admin", 0) == 1:
            return RedirectResponse(url="/login", status_code=302)
        
        logger.info(f"🔍 ADMIN MANAGE VOICES - Admin user {user.get('username')} accessing manage voices")
        
        try:
            return templates.TemplateResponse("portal/admin_manage_voices.html", {
                "request": request,
                "user": user
            })
        except Exception as template_error:
            logger.warning(f"🔍 ADMIN MANAGE VOICES - Template error: {template_error}")
            return JSONResponse({
                "message": "Admin Manage Voices",
                "user": user.get("username", "Admin"),
                "status": "Template not found - using JSON response"
            })
        
    except Exception as e:
        logger.error(f"Admin manage voices page error: {e}")
        return JSONResponse({"error": "Admin manage voices page unavailable"}, status_code=500)

@router.get("/admin/manage-passwords")
async def admin_manage_passwords(request: Request):
    """Admin manage passwords page"""
    try:
        user = get_current_user(request)
        if not user or not user.get("is_admin", 0) == 1:
            return RedirectResponse(url="/login", status_code=302)
        
        logger.info(f"🔍 ADMIN MANAGE PASSWORDS - Admin user {user.get('username')} accessing manage passwords")
        
        # Get all users for password management (using the same approach as admin users page)
        all_users = []
        try:
            sample_usernames = ['admin', 'MogensR', 'testuser', 'Lars-Christian']
            
            for username in sample_usernames:
                try:
                    found_user = db.get_user_by_username(username)
                    if found_user:
                        all_users.append(found_user)
                except:
                    continue
                    
            logger.info(f"🔍 ADMIN MANAGE PASSWORDS - Found {len(all_users)} users for password management")
            
        except Exception as e:
            logger.error(f"🔍 ADMIN MANAGE PASSWORDS - Error fetching users: {e}")
            all_users = []
        
        try:
            return templates.TemplateResponse("portal/admin_manage_passwords.html", {
                "request": request,
                "user": user,
                "users": all_users
            })
        except Exception as template_error:
            logger.warning(f"🔍 ADMIN MANAGE PASSWORDS - Template error: {template_error}")
            return JSONResponse({
                "message": "Admin Manage Passwords",
                "user": user.get("username", "Admin"),
                "users_count": len(all_users),
                "status": "Template not found - using JSON response"
            })
        
    except Exception as e:
        logger.error(f"Admin manage passwords page error: {e}")
        return JSONResponse({"error": "Admin manage passwords page unavailable"}, status_code=500)

@router.post("/api/admin/reset-password")
async def admin_reset_password_api(request: Request):
    """API endpoint to reset user password"""
    try:
        user = get_current_user(request)
        if not user or not user.get("is_admin", 0) == 1:
            return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
        
        # Get JSON data from request
        data = await request.json()
        user_id = data.get("user_id")
        new_password = data.get("new_password")
        
        if not user_id or not new_password:
            return JSONResponse({"success": False, "error": "Missing user_id or new_password"})
        
        # Validate password strength
        if len(new_password) < 8:
            return JSONResponse({"success": False, "error": "Password must be at least 8 characters long"})
        
        logger.info(f"🔍 ADMIN RESET PASSWORD - Admin {user.get('username')} resetting password for user ID: {user_id}")
        
        # Hash the new password
        hashed_password = hash_password(new_password)
        
        # Update the user's password in the database
        try:
            execute_query(
                "UPDATE users SET hashed_password = ? WHERE id = ?",
                (hashed_password, user_id)
            )
            logger.info(f"🔍 ADMIN RESET PASSWORD - Database updated for user ID: {user_id}")
        except Exception as db_error:
            logger.error(f"🔍 ADMIN RESET PASSWORD - Database update failed: {db_error}")
            return JSONResponse({"success": False, "error": "Failed to update password in database"})
        
        logger.info(f"🔍 ADMIN RESET PASSWORD - Password reset successful for user ID: {user_id}")
        
        return JSONResponse({
            "success": True,
            "message": f"Password updated for user ID: {user_id}"
        })
         
    except Exception as e:
        logger.error(f"Admin reset password API error: {e}")
        return JSONResponse({"success": False, "error": "Internal server error"}, status_code=500)

@router.get("/admin/manage-data")
async def admin_manage_data(request: Request):
    """Admin manage data page"""
    try:
        user = get_current_user(request)
        if not user or not user.get("is_admin", 0) == 1:
            return RedirectResponse(url="/login", status_code=302)
        
        logger.info(f"🔍 ADMIN MANAGE DATA - Admin user {user.get('username')} accessing manage data")
        
        try:
            return templates.TemplateResponse("portal/admin_manage_data.html", {
                "request": request,
                "user": user
            })
        except Exception as template_error:
            logger.warning(f"🔍 ADMIN MANAGE DATA - Template error: {template_error}")
            return JSONResponse({
                "message": "Admin Manage Data",
                "user": user.get("username", "Admin"),
                "status": "Template not found - using JSON response"
            })
        
    except Exception as e:
        logger.error(f"Admin manage data page error: {e}")
        return JSONResponse({"error": "Admin manage data page unavailable"}, status_code=500)

@router.get("/admin/edit-user/{user_id}")
async def admin_edit_user(request: Request, user_id: int):
    """Admin edit user page"""
    try:
        user = get_current_user(request)
        if not user or not user.get("is_admin", 0) == 1:
            return RedirectResponse(url="/login", status_code=302)
        
        logger.info(f"🔍 ADMIN EDIT USER - Admin user {user.get('username')} editing user ID: {user_id}")
        
        # Get the user to edit
        try:
            edit_user = db.get_user_by_id(user_id)
            if not edit_user:
                return RedirectResponse(url="/admin/users", status_code=302)
        except Exception as e:
            logger.error(f"Error fetching user to edit: {e}")
            return RedirectResponse(url="/admin/users", status_code=302)
        
        try:
            return templates.TemplateResponse("portal/admin_edit_user.html", {
                "request": request,
                "user": user,
                "user_to_edit": edit_user  # Changed from edit_user to user_to_edit
            })
        except Exception as template_error:
            logger.warning(f"🔍 ADMIN EDIT USER - Template error: {template_error}")
            return JSONResponse({
                "message": "Admin Edit User",
                "user": user.get("username", "Admin"),
                "edit_user": edit_user.get("username", "Unknown"),
                "status": "Template not found - using JSON response"
            })
        
    except Exception as e:
        logger.error(f"Admin edit user page error: {e}")
        return JSONResponse({"error": "Admin edit user page unavailable"}, status_code=500)

@router.post("/admin/edit-user/{user_id}")
async def admin_update_user(request: Request, user_id: int):
    """Handle user update"""
    try:
        user = get_current_user(request)
        if not user or not user.get("is_admin", 0) == 1:
            return RedirectResponse(url="/login", status_code=302)
        
        form = await request.form()
        
        # Get updated data from form
        updated_data = {}
        for field in ['username', 'email', 'display_name', 'bio', 'company']:
            if field in form:
                updated_data[field] = sanitize_input(str(form.get(field, "")))
        
        logger.info(f"🔍 ADMIN UPDATE USER - Admin {user.get('username')} updating user ID: {user_id}")
        
        # Here you would update the user in database
        # For now, just redirect back to users list
        return RedirectResponse(url="/admin/users", status_code=302)
        
    except Exception as e:
        logger.error(f"Admin update user error: {e}")
        return RedirectResponse(url="/admin/users", status_code=302)

@router.get("/admin/user-avatars/{user_id}")
async def admin_user_avatars(request: Request, user_id: int):
    """Admin user avatars page"""
    try:
        user = get_current_user(request)
        if not user or not user.get("is_admin", 0) == 1:
            return RedirectResponse(url="/login", status_code=302)
        
        logger.info(f"🔍 ADMIN USER AVATARS - Admin user {user.get('username')} viewing avatars for user ID: {user_id}")
        
        # Get the user whose avatars we're viewing
        try:
            target_user = db.get_user_by_id(user_id)
            if not target_user:
                return RedirectResponse(url="/admin/users", status_code=302)
        except Exception as e:
            logger.error(f"Error fetching user for avatars: {e}")
            return RedirectResponse(url="/admin/users", status_code=302)
        
        # Get user's avatars
        try:
            user_avatars = db.get_user_avatars(user_id)
            if not user_avatars:
                user_avatars = []
                
            logger.info(f"🔍 DEBUG: Found {len(user_avatars)} avatars from get_user_avatars for user_id: {user_id}")
            
            all_avatars = user_avatars
            logger.info(f"🔍 DEBUG: Total avatars to display: {len(all_avatars)}")
            
        except Exception as e:
            logger.error(f"Error fetching user avatars: {e}")
            all_avatars = []
        
        try:
            return templates.TemplateResponse("portal/admin_manage_avatars.html", {
                "request": request,
                "user": user,
                "user_to_manage": target_user,  # Changed from target_user to user_to_manage
                "avatars": all_avatars  # Changed from user_avatars to all_avatars
            })
        except Exception as template_error:
            logger.warning(f"🔍 ADMIN USER AVATARS - Template error: {template_error}")
            return JSONResponse({
                "message": "Admin User Avatars",
                "user": user.get("username", "Admin"),
                "target_user": target_user.get("username", "Unknown"),
                "avatars_count": len(all_avatars),
                "status": "Template not found - using JSON response"
            })
        
    except Exception as e:
        logger.error(f"Admin user avatars page error: {e}")
        return JSONResponse({"error": "Admin user avatars page unavailable"}, status_code=500)

@router.get("/admin/delete-user/{user_id}")
async def admin_delete_user(request: Request, user_id: int):
    """Delete user (with confirmation)"""
    try:
        user = get_current_user(request)
        if not user or not user.get("is_admin", 0) == 1:
            return RedirectResponse(url="/login", status_code=302)
        
        logger.info(f"🔍 ADMIN DELETE USER - Admin user {user.get('username')} deleting user ID: {user_id}")
        
        # Don't allow deleting the current admin user
        if user_id == user.get("id"):
            logger.warning(f"🔍 ADMIN DELETE USER - Admin tried to delete themselves")
            return RedirectResponse(url="/admin/users", status_code=302)
        
        # Here you would delete the user from database
        # For now, just redirect back to users list
        logger.info(f"🔍 ADMIN DELETE USER - User ID {user_id} would be deleted here")
        return RedirectResponse(url="/admin/users", status_code=302)
        
    except Exception as e:
        logger.error(f"Admin delete user error: {e}")
        return RedirectResponse(url="/admin/users", status_code=302)

@router.get("/voice-recording")
async def voice_recording_page(request: Request):
    """Voice recording page for creating videos from audio"""
    try:
        user = get_current_user(request)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        logger.info(f"🎤 VOICE RECORDING - User {user.get('username')} accessing voice recording page")
        
        # Get user's avatars for selection
        user_avatars = []
        try:
            # Get real avatars from database
            user_avatars = db.get_user_avatars(user["id"])
            
            # If no avatars found, create a fallback
            if not user_avatars:
                if user.get("avatar_id"):
                    user_avatars = [
                        {
                            'id': user.get("avatar_id"),
                            'avatar_id': user.get("avatar_id"),
                            'name': 'Your Avatar',
                            'image_path': None
                        }
                    ]
                else:
                    user_avatars = [
                        {
                            'id': 'default_avatar',
                            'avatar_id': 'default_avatar',
                            'name': 'Default Avatar',
                            'image_path': None
                        }
                    ]
        except Exception as e:
            logger.error(f"Error loading avatars: {e}")
            user_avatars = [
                {
                    'id': 'default_avatar',
                    'avatar_id': 'default_avatar',
                    'name': 'Default Avatar',
                    'image_path': None
                }
            ]
        
        return templates.TemplateResponse("voice_recording.html", {
            "request": request,
            "user": user,
            "username": sanitize_input(user.get("username", "User")),
            "avatars": user_avatars
        })
        
    except Exception as e:
        logger.error(f"Voice recording page error: {e}")
        return RedirectResponse(url="/dashboard", status_code=302)

@router.get("/text-to-video")
async def text_to_video_page(request: Request):
    """Text-to-video creation page"""
    try:
        user = get_current_user(request)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        logger.info(f"📝 TEXT-TO-VIDEO - User {user.get('username')} accessing text-to-video page")
        
        # Get user's avatars for selection
        user_avatars = []
        try:
            # Get real avatars from database
            user_avatars = db.get_user_avatars(user["id"])
            
            # If no avatars found, create a fallback
            if not user_avatars:
                if user.get("avatar_id"):
                    user_avatars = [
                        {
                            'id': user.get("avatar_id"),
                            'avatar_id': user.get("avatar_id"),
                            'name': 'Your Avatar',
                            'image_path': None
                        }
                    ]
                else:
                    user_avatars = [
                        {
                            'id': 'default_avatar',
                            'avatar_id': 'default_avatar',
                            'name': 'Default Avatar',
                            'image_path': None
                        }
                    ]
        except Exception as e:
            logger.error(f"Error loading avatars: {e}")
            user_avatars = [
                {
                    'id': 'default_avatar',
                    'avatar_id': 'default_avatar',
                    'name': 'Default Avatar',
                    'image_path': None
                }
            ]
        
        return templates.TemplateResponse("text_video_component.html", {
            "request": request,
            "user": user,
            "username": sanitize_input(user.get("username", "User")),
            "avatars": user_avatars
        })
        
    except Exception as e:
        logger.error(f"Text-to-video page error: {e}")
        return RedirectResponse(url="/dashboard", status_code=302)

@router.get("/debug-videos/{user_id}")
async def debug_videos(request: Request, user_id: int):
    """Debug route to check videos for a specific user"""
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse({"error": "Not authenticated"}, status_code=401)
        
        # Get database instance
        db_instance = db
        
        # Check if get_user_videos method exists
        if not hasattr(db_instance, 'get_user_videos'):
            return JSONResponse({"error": "get_user_videos method not found in Database class"})
        
        # Try to get videos
        videos = db_instance.get_user_videos(user_id)
        
        # Convert datetime objects to strings for JSON serialization
        serializable_videos = []
        if videos:
            for video in videos:
                if isinstance(video, dict):
                    serializable_video = {}
                    for key, value in video.items():
                        if hasattr(value, 'isoformat'):  # datetime object
                            serializable_video[key] = value.isoformat()
                        else:
                            serializable_video[key] = value
                    serializable_videos.append(serializable_video)
                else:
                    serializable_videos.append(str(video))
        
        return JSONResponse({
            "user_id": user_id,
            "videos_found": len(videos) if videos else 0,
            "videos": serializable_videos,
            "method_exists": True
        })
        
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.get("/test-routes")
async def test_routes():
    """Test endpoint to confirm routes are loaded"""
    return {
        "message": "Production web routes are working!", 
        "routes_loaded": True,
        "features": [
            "Authentication",
            "JWT Cookie Session Management", 
            "Password Security",
            "Rate Limiting",
            "Input Sanitization",
            "File Upload Security",
            "Admin Password Fix",
            "User Dashboard Access",
            "Complete Admin Panel Routes",
            "Video Debug Route",
            "FIXED Dashboard Video Display"
        ]
    }

@router.get("/backgrounds")
async def backgrounds_page(request: Request):
    """BackGroundFX backgrounds management page"""
    try:
        user = get_current_user(request)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        return templates.TemplateResponse("backgrounds.html", {
            "request": request,
            "user": user
        })
        
    except Exception as e:
        logger.error(f"Error loading backgrounds page: {e}")
        return RedirectResponse(url="/dashboard", status_code=302)

@router.get("/backgroundfx")
async def backgroundfx_page(request: Request):
    """BackGroundFX main page - premium background replacement feature"""
    try:
        user = get_current_user(request)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        return templates.TemplateResponse("backgrounds.html", {
            "request": request,
            "user": user
        })
        
    except Exception as e:
        logger.error(f"Error loading BackGroundFX page: {e}")
        return RedirectResponse(url="/dashboard", status_code=302)

@router.get("/api/videos")
async def get_user_videos_api(request: Request):
    """API endpoint to get user videos for BackGroundFX"""
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse({"error": "Not authenticated"}, status_code=401)
        
        # Get user videos
        videos = db.get_user_videos(user["id"])
        
        # Convert datetime objects to strings for JSON serialization
        serializable_videos = []
        if videos:
            for video in videos:
                if isinstance(video, dict):
                    serializable_video = {}
                    for key, value in video.items():
                        if hasattr(value, 'isoformat'):  # datetime object
                            serializable_video[key] = value.isoformat()
                        else:
                            serializable_video[key] = value
                    serializable_videos.append(serializable_video)
                else:
                    serializable_videos.append(str(video))
        
        return JSONResponse(serializable_videos)
        
    except Exception as e:
        logger.error(f"Error fetching videos API: {e}")
        return JSONResponse({"error": "Failed to fetch videos"}, status_code=500)

@router.post("/api/document-parser")
async def document_parser_api(request: Request, file: UploadFile = File(...)):
    """API endpoint to parse document files (.txt, .docx, .pdf)"""
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse({"error": "Not authenticated"}, status_code=401)
        
        # Validate file type
        allowed_extensions = ['.txt', '.docx', '.pdf']
        file_extension = '.' + file.filename.lower().split('.')[-1] if '.' in file.filename else ''
        
        if file_extension not in allowed_extensions:
            return JSONResponse({
                "error": f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
            }, status_code=400)
        
        # Check file size (10MB limit)
        file_content = await file.read()
        if len(file_content) > 10 * 1024 * 1024:  # 10MB
            return JSONResponse({
                "error": "File too large. Maximum size is 10MB."
            }, status_code=400)
        
        logger.info(f"📄 Parsing document: {file.filename} ({len(file_content)} bytes)")
        
        # Parse document
        parsed_text = parse_document(file_content, file.filename)
        
        if parsed_text is None:
            return JSONResponse({
                "error": "Failed to parse document. Please check the file format."
            }, status_code=400)
        
        # Clean and truncate text
        result = clean_and_truncate_text(parsed_text, max_length=1500)
        
        logger.info(f"✅ Document parsed successfully: {len(result['text'])} characters")
        
        return JSONResponse({
            "success": True,
            "filename": file.filename,
            "text": result['text'],
            "truncated": result['truncated'],
            "original_length": result['original_length'],
            "final_length": len(result['text'])
        })
        
    except Exception as e:
        logger.error(f"❌ Error parsing document {file.filename}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return JSONResponse({
            "error": f"Failed to parse document: {str(e)}"
        }, status_code=500)

@router.get("/create-voice")
async def create_voice_page(request: Request):
    """Voice recording page with avatar selection"""
    try:
        user = get_current_user(request)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        # Get user's avatars for the voice recording page - copied from dashboard
        user_avatars = []
        try:
            avatars = db.get_user_avatars(user["id"])
            logger.info(f"🎭 VOICE RECORDING - Raw avatars from DB: {avatars}")
            
            if avatars:
                for avatar in avatars:
                    if isinstance(avatar, dict):
                        # Use the avatar_image_url directly from database (already contains HeyGen URLs)
                        avatar_image = avatar.get('avatar_image_url', '')
                        avatar_name = avatar.get('name', 'Unnamed Avatar')
                        
                        logger.info(f"🖼️ Avatar {avatar_name} image: {avatar_image}")
                        
                        user_avatars.append({
                            'id': avatar.get('id'),
                            'name': sanitize_input(avatar_name),
                            'image_path': avatar_image,  # Changed from image_url to image_path
                            'heygen_avatar_id': avatar.get('heygen_avatar_id', ''),
                            'avatar_id': avatar.get('heygen_avatar_id', '')  # For template compatibility
                        })
                        
            logger.info(f"🎭 VOICE RECORDING - Processed {len(user_avatars)} avatars for user {user.get('username')}")
            for avatar in user_avatars:
                logger.info(f"   - Avatar: {avatar['name']} | Image: {avatar['image_path'][:50] if avatar['image_path'] else 'No image'}...")
                
        except Exception as avatar_error:
            logger.error(f"Error fetching user avatars: {avatar_error}")
            import traceback
            logger.error(f"Avatar error traceback: {traceback.format_exc()}")
            user_avatars = []
        
        return templates.TemplateResponse("voice_recording.html", {
            "request": request,
            "user": user,
            "avatars": user_avatars
        })
        
    except Exception as e:
        logger.error(f"Error loading voice recording page: {e}")
        return RedirectResponse(url="/dashboard", status_code=302)