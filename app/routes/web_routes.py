import os
import uuid
import shutil
import logging
import time
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path

from fastapi import APIRouter, Request, Form, HTTPException, Depends, UploadFile, File, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
import time

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
try:
    from ..utils.document_parser import parse_document, clean_and_truncate_text
except ImportError:
    def parse_document(file): return ""
    def clean_and_truncate_text(text): return text[:1000]

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

# STEP 7: VACATION-SAFE Configuration class with REAL API COST TRACKING
class Config:
    def __init__(self):
        # 🏖️ VACATION MODE PROTECTION - $100 BUDGET EACH (Railway + HeyGen)
        self.VACATION_MODE = True
        self.RAILWAY_BUDGET = 100.0  # $100 Railway budget
        self.HEYGEN_BUDGET = 100.0   # $100 HeyGen budget
        self.TOTAL_BUDGET = 200.0    # $200 total budget
        
        # Smart limits based on budget
        self.MAX_TOTAL_USERS = 300  # Higher limit since we have bigger budget
        self.MAX_VIDEOS_PER_USER = 7  # 7 videos per user  
        self.MAX_DAILY_REGISTRATIONS = 30  # 30 new users per day max
        self.MAX_CREDITS_PER_USER = 15  # 15 credits per user
        self.EMERGENCY_STOP = os.getenv("EMERGENCY_STOP", "false").lower() == "true"
        
        # Security - with safe fallbacks
        self.JWT_SECRET = self._get_env_with_fallback("JWT_SECRET", "fallback-development-secret-key")
        self.JWT_ALGORITHM = "HS256"
        self.JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
        self.BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "12"))
        
        # Emergency Reset System
        self.EMERGENCY_MASTER_KEY = self._get_env_with_fallback("EMERGENCY_MASTER_KEY", "blackbelt")
        self.EMERGENCY_KEY_HINT = self._get_env_with_fallback("EMERGENCY_KEY_HINT", "Your blackbelt level in Ju-Jitsu")
        
        # File Upload
        self.MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "5242880"))  # 5MB
        self.ALLOWED_EXTENSIONS = set(os.getenv("ALLOWED_EXTENSIONS", "jpg,jpeg,png,gif,webp").split(","))
        self.UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "static/uploads"))
        
        # Rate Limiting - VACATION MODE BALANCED
        self.RATE_LIMIT_LOGIN = os.getenv("RATE_LIMIT_LOGIN", "5/minute")
        self.RATE_LIMIT_REGISTER = os.getenv("RATE_LIMIT_REGISTER", "3/minute")
        self.RATE_LIMIT_API = os.getenv("RATE_LIMIT_API", "50/minute")
        self.RATE_LIMIT_VIDEO_CREATE = "3/hour"  # Video creation limit
        
        # Database
        self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./fallback.db")
        self.DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
        self.DB_TIMEOUT = int(os.getenv("DB_TIMEOUT", "30"))
        
        # Session
        self.SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT", "3600"))  # 1 hour
        self.MAX_SESSIONS_PER_USER = int(os.getenv("MAX_SESSIONS_PER_USER", "3"))
        
        # Security Headers
        self.TRUSTED_HOSTS = os.getenv("TRUSTED_HOSTS", "localhost,127.0.0.1").split(",")
        self.CORS_ORIGINS = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else []
        
        # AI Services
        self.OPENAI_API_KEY = self._get_env_with_fallback("OPENAI_API_KEY", "your-openai-api-key")
        self.HEYGEN_API_KEY = self._get_env_with_fallback("HEYGEN_API_KEY", "your-heygen-api-key")
        self.RAILWAY_API_KEY = self._get_env_with_fallback("RAILWAY_API_KEY", "your-railway-api-key")
        
        # Safe validation
        self._validate_config()
        
        # Log vacation mode status
        if self.VACATION_MODE:
            logger.info(f"🏖️ VACATION MODE ACTIVE - Budget: Railway $100 + HeyGen $100 = $200 total")
            logger.info(f"🏖️ Limits: {self.MAX_TOTAL_USERS} users, {self.MAX_VIDEOS_PER_USER} videos/user, {self.MAX_DAILY_REGISTRATIONS}/day")
            logger.info(f"🔑 Emergency Reset: Hint = '{self.EMERGENCY_KEY_HINT}'")
    
    def _get_env_with_fallback(self, key: str, fallback: str) -> str:
        """Get environment variable with fallback instead of failing"""
        value = os.getenv(key)
        if not value or value in ["your-secret-key-change-this", "change-this", "your-openai-api-key", "your-heygen-api-key", "your-railway-api-key"]:
            if key in ["RAILWAY_API_KEY", "HEYGEN_API_KEY"]:
                logger.warning(f"⚠️ {key} not found - cost tracking will use estimates")
            elif key in ["EMERGENCY_MASTER_KEY", "EMERGENCY_KEY_HINT"]:
                logger.warning(f"⚠️ {key} not found - using default emergency reset settings")
            else:
                logger.warning(f"Using fallback value for {key}")
            return fallback
        return value
    
    def _validate_config(self):
        """Safe validation that doesn't fail"""
        try:
            # Ensure upload directory exists
            self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create upload directory: {e}")

# STEP 8: Initialize configuration
config = Config()

# STEP 9: REAL API COST TRACKING FUNCTIONS
async def get_real_railway_costs():
    """Get actual Railway billing data using API"""
    try:
        railway_api_key = config.RAILWAY_API_KEY
        if not railway_api_key or railway_api_key == "your-railway-api-key":
            logger.warning("No valid Railway API key found")
            return None
        
        headers = {
            "Authorization": f"Bearer {railway_api_key}",
            "Content-Type": "application/json"
        }
        
        # Railway GraphQL API query for current month usage
        query = """
        query {
            me {
                currentUsage {
                    amount
                    measurement
                }
                estimatedUsage {
                    amount
                    measurement  
                }
            }
        }
        """
        
        response = requests.post(
            "https://backboard.railway.app/graphql",
            json={"query": query},
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and 'me' in data['data'] and data['data']['me']:
                me_data = data['data']['me']
                current_usage = me_data.get('currentUsage', {}).get('amount', 0)
                estimated_usage = me_data.get('estimatedUsage', {}).get('amount', 0)
                
                return {
                    "current_cost": current_usage / 100,  # Convert cents to dollars
                    "estimated_cost": estimated_usage / 100,
                    "currency": "USD",
                    "status": "success",
                    "budget_limit": config.RAILWAY_BUDGET
                }
        
        logger.error(f"Railway API error: {response.status_code} - {response.text}")
        return None
        
    except Exception as e:
        logger.error(f"Error fetching Railway costs: {e}")
        return None

async def get_heygen_usage_stats():
    """Get actual HeyGen API usage and costs"""
    try:
        heygen_api_key = config.HEYGEN_API_KEY
        if not heygen_api_key or heygen_api_key == "your-heygen-api-key":
            logger.warning("No valid HeyGen API key found")
            return None
        
        headers = {
            "X-API-Key": heygen_api_key,
            "Content-Type": "application/json"
        }
        
        # Get quota/usage info from HeyGen
        response = requests.get(
            "https://api.heygen.com/v1/user/quota",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 100:  # HeyGen success code
                quota_data = data.get('data', {})
                
                # Estimate costs based on usage (rough calculation)
                quota_used = quota_data.get('quota_used', 0)
                estimated_cost = quota_used * 0.08  # Rough estimate: $0.08 per credit
                
                return {
                    "quota_used": quota_used,
                    "quota_total": quota_data.get('quota_total', 0), 
                    "quota_remaining": quota_data.get('quota_remaining', 0),
                    "current_month_usage": quota_data.get('current_month_usage', 0),
                    "estimated_cost": estimated_cost,
                    "budget_limit": config.HEYGEN_BUDGET,
                    "status": "success"
                }
        
        logger.error(f"HeyGen API error: {response.status_code} - {response.text}")
        return None
        
    except Exception as e:
        logger.error(f"Error fetching HeyGen usage: {e}")
        return None

async def log_api_cost_event(service: str, endpoint: str, cost_estimate: float):
    """Log API calls for cost tracking"""
    try:
        execute_query(
            """INSERT INTO api_usage_log (service, endpoint, cost_estimate, created_at) 
               VALUES (%s, %s, %s, %s)""",
            (service, endpoint, cost_estimate, datetime.now())
        )
    except Exception as e:
        logger.error(f"Error logging API call: {e}")

# STEP 10: VACATION MODE PROTECTION FUNCTIONS
def check_emergency_stop():
    """Check if emergency stop is activated"""
    if config.EMERGENCY_STOP:
        return True, "🚧 MyAvatar is temporarily undergoing maintenance to improve our service. Please check back in a few hours!"
    return False, None

def check_user_limits():
    """Check if we've hit user registration limits"""
    try:
        # Check total users
        total_users_result = execute_query("SELECT COUNT(*) as count FROM users", fetch_one=True)
        total_users = total_users_result['count'] if total_users_result else 0
        
        if total_users >= config.MAX_TOTAL_USERS:
            return False, f"🎉 Incredible! MyAvatar has reached {config.MAX_TOTAL_USERS} beta users! We're scaling up our infrastructure to handle the amazing demand. Please check back next week for expanded capacity!"
        
        # Check daily registrations
        today = datetime.now().date()
        daily_users_result = execute_query(
            "SELECT COUNT(*) as count FROM users WHERE DATE(created_at) = %s", 
            (today,), 
            fetch_one=True
        )
        daily_users = daily_users_result['count'] if daily_users_result else 0
        
        if daily_users >= config.MAX_DAILY_REGISTRATIONS:
            return False, f"🔥 What an amazing day! We've had {config.MAX_DAILY_REGISTRATIONS} new users join MyAvatar today! To ensure the best experience for everyone, we've reached our daily capacity. Please try again tomorrow!"
        
        return True, None
        
    except Exception as e:
        logger.error(f"Error checking user limits: {e}")
        return False, "⚠️ Our systems are experiencing high demand right now. Please try again in a few minutes!"

def check_user_video_limits(user_id: int):
    """Check if user has hit video creation limits"""
    try:
        user_videos_result = execute_query(
            "SELECT COUNT(*) as count FROM videos WHERE user_id = %s", 
            (user_id,), 
            fetch_one=True
        )
        user_videos = user_videos_result['count'] if user_videos_result else 0
        
        if user_videos >= config.MAX_VIDEOS_PER_USER:
            return False, f"🎬 Wow! You've created {config.MAX_VIDEOS_PER_USER} amazing videos! You're really exploring MyAvatar's capabilities. To ensure fair access during our beta phase, that's our current limit per user. We're working hard to increase these limits as we scale!"
        
        return True, None
        
    except Exception as e:
        logger.error(f"Error checking user video limits: {e}")
        return False, "⚠️ Unable to check video limits right now. Please try again in a moment!"

async def check_budget_limits():
    """Check if we've exceeded budget limits"""
    try:
        railway_costs = await get_real_railway_costs()
        heygen_usage = await get_heygen_usage_stats()
        
        railway_percentage = 0
        heygen_percentage = 0
        
        if railway_costs:
            railway_percentage = (railway_costs['current_cost'] / config.RAILWAY_BUDGET) * 100
        
        if heygen_usage:
            heygen_percentage = (heygen_usage['estimated_cost'] / config.HEYGEN_BUDGET) * 100
        
        # Check Railway budget
        if railway_percentage >= 90:
            return False, f"🚨 We're experiencing such high demand that we've reached our infrastructure capacity! We're working on expanding and will be back soon with even better service!"
        
        # Check HeyGen budget  
        if heygen_percentage >= 90:
            return False, f"🎬 MyAvatar is so popular that we've used up our video generation capacity for this period! We're increasing our limits and will be back with more video creation power soon!"
        
        # Warning at 80%
        if railway_percentage >= 80 or heygen_percentage >= 80:
            logger.warning(f"🚨 BUDGET WARNING: Railway {railway_percentage:.1f}%, HeyGen {heygen_percentage:.1f}%")
        
        return True, None
        
    except Exception as e:
        logger.error(f"Error checking budget limits: {e}")
        return True, None

def get_system_stats():
    """Get current system usage stats"""
    try:
        stats = {}
        
        # Total users
        total_users_result = execute_query("SELECT COUNT(*) as count FROM users", fetch_one=True)
        stats['total_users'] = total_users_result['count'] if total_users_result else 0
        
        # Total videos
        total_videos_result = execute_query("SELECT COUNT(*) as count FROM videos", fetch_one=True)
        stats['total_videos'] = total_videos_result['count'] if total_videos_result else 0
        
        # Today's registrations
        today = datetime.now().date()
        daily_users_result = execute_query(
            "SELECT COUNT(*) as count FROM users WHERE DATE(created_at) = %s", 
            (today,), 
            fetch_one=True
        )
        stats['daily_registrations'] = daily_users_result['count'] if daily_users_result else 0
        
        # Usage percentages
        stats['users_percentage'] = round((stats['total_users'] / config.MAX_TOTAL_USERS) * 100, 1)
        stats['daily_percentage'] = round((stats['daily_registrations'] / config.MAX_DAILY_REGISTRATIONS) * 100, 1)
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        return {
            'total_users': 0,
            'total_videos': 0,
            'daily_registrations': 0,
            'users_percentage': 0,
            'daily_percentage': 0
        }

# STEP 11: Initialize components that depend on config
if SLOWAPI_AVAILABLE:
    limiter = Limiter(key_func=get_remote_address)
else:
    limiter = Limiter()

router = APIRouter()

# Robust template directory detection
def find_templates_directory():
    """Find templates directory - FIXED for your exact Windows path"""
    
    # Your exact project structure
    current_file = Path(__file__)
    print(f"🔍 Current file: {current_file}")
    print(f"🔍 Working directory: {os.getcwd()}")
    
    # Since we know your exact path, let's try the most likely locations
    possible_paths = [
        # Most likely: go up from wherever web_routes.py is to MyAvatar root
        current_file.parent.parent.parent / "templates",  # If web_routes.py is in app/routes/
        current_file.parent.parent / "templates",        # If web_routes.py is in app/
        current_file.parent / "templates",               # If web_routes.py is in root
        
        # Your exact absolute path as backup
        Path("C:/Users/mogen/Projects/python/CHATGPT/MyAvatar/templates"),
        
        # Working directory variations
        Path.cwd() / "templates",
        Path("./templates"),
        Path("templates"),
    ]
    
    for path in possible_paths:
        print(f"🔍 Checking: {path}")
        if path.exists() and path.is_dir():
            dashboard_file = path / "dashboard.html"
            if dashboard_file.exists():
                print(f"✅ Found dashboard.html at: {dashboard_file}")
                return str(path)
            else:
                print(f"📁 Directory exists but no dashboard.html: {path}")
    
    # Fallback to your known path
    fallback = "C:/Users/mogen/Projects/python/CHATGPT/MyAvatar/templates"
    print(f"❌ Using fallback path: {fallback}")
    return fallback

templates_dir = find_templates_directory()
templates = Jinja2Templates(directory=templates_dir)

try:
    templates.env.autoescape = True
except Exception:
    pass

security = HTTPBearer(auto_error=False)

# STEP 12: Authentication functions
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
    """Enhanced password validation"""
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
    """Create JWT access token"""
    try:
        from ..auth.authentication import create_access_token as auth_create_token
        
        user = db.get_user_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        token_data = {
            "sub": user['username'],
            "user_id": user_id,
            "admin": bool(user.get('is_admin', False))
        }
        
        return auth_create_token(token_data)
    except ImportError:
        # Fallback JWT creation
        payload = {
            "user_id": user_id,
            "exp": datetime.utcnow() + timedelta(hours=config.JWT_EXPIRATION_HOURS)
        }
        return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)

# STEP 13: Session management
class SessionManager:
    def __init__(self):
        self.active_sessions = {}
    
    def create_session(self, user_id: int, request: Request) -> str:
        user_sessions = [s for s in self.active_sessions.values() if s.get('user_id') == user_id]
        if len(user_sessions) >= config.MAX_SESSIONS_PER_USER:
            oldest = min(user_sessions, key=lambda x: x['created_at'])
            del self.active_sessions[oldest['token']]
        
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
        if not token or token not in self.active_sessions:
            return None
        
        session = self.active_sessions[token]
        
        if time.time() - session['created_at'] > config.SESSION_TIMEOUT:
            del self.active_sessions[token]
            return None
        
        return session

session_manager = SessionManager()

def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """Get current user with enhanced security using JWT cookies"""
    try:
        token = request.cookies.get("access_token")
        if not token:
            return None
        
        session = session_manager.validate_session(token, request)
        if not session:
            return None
        
        try:
            payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
            user_id = payload.get("user_id")
            if not user_id:
                return None
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            session_manager.active_sessions.pop(token, None)
            return None
        
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

# STEP 14: FIXED Default avatars setup with verification
def setup_default_avatars_for_user(user_id: int):
    """Set up default avatars for new users - FIXED VERSION"""
    try:
        logger.info(f"Setting up default avatars for user ID: {user_id}")
        
        # First, check if user already has avatars to avoid duplicates
        existing_avatars = execute_query(
            "SELECT COUNT(*) as count FROM user_avatars WHERE user_id = %s",
            (user_id,),
            fetch_one=True
        )
        
        if existing_avatars and existing_avatars.get('count', 0) > 0:
            logger.info(f"User {user_id} already has avatars, skipping setup")
            return
        
        default_avatars = [
            {
                'heygen_avatar_id': 'Tyler-insuit-20220721',
                'avatar_name': 'Professional Male',
                'avatar_image_url': 'https://files2.heygen.ai/avatar/v3/25ef6c86b1254a5e8fffe00b32275d93/25ef6c86b1254a5e8fffe00b32275d93.jpg',
                'is_default': 1
            },
            {
                'heygen_avatar_id': 'Kristin_public_2_20240108', 
                'avatar_name': 'Professional Female',
                'avatar_image_url': 'https://files2.heygen.ai/avatar/v3/d0b8f0e4e53143ab8b2e8a4c9b2e2e0d/d0b8f0e4e53143ab8b2e8a4c9b2e2e0d.jpg',
                'is_default': 1
            },
            {
                'heygen_avatar_id': 'josh_lite3_20230714',
                'avatar_name': 'Casual Male',
                'avatar_image_url': 'https://files2.heygen.ai/avatar/v3/josh_lite3_20230714/josh_lite3_20230714.jpg',
                'is_default': 1
            },
            {
                'heygen_avatar_id': 'Susan_public_2_20240108',
                'avatar_name': 'Friendly Female',
                'avatar_image_url': 'https://files2.heygen.ai/avatar/v3/Susan_public_2_20240108/Susan_public_2_20240108.jpg',
                'is_default': 1
            }
        ]
        
        for avatar_data in default_avatars:
            try:
                # Check if this specific avatar already exists for the user
                existing_check = execute_query(
                    "SELECT id FROM user_avatars WHERE user_id = %s AND heygen_avatar_id = %s",
                    (user_id, avatar_data['heygen_avatar_id']),
                    fetch_one=True
                )
                
                if existing_check:
                    logger.info(f"Avatar {avatar_data['avatar_name']} already exists for user {user_id}")
                    continue
                
                insert_query = """
                INSERT INTO user_avatars (user_id, heygen_avatar_id, avatar_name, avatar_image_url, is_default, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """
                
                result = execute_query(
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
                
                if result is not None:
                    logger.info(f"✅ Added default avatar '{avatar_data['avatar_name']}' for user {user_id}")
                else:
                    logger.error(f"❌ Failed to add avatar '{avatar_data['avatar_name']}' for user {user_id}")
                    
            except Exception as avatar_error:
                logger.error(f"Error adding individual avatar {avatar_data['avatar_name']} for user {user_id}: {avatar_error}")
        
        # Verify avatars were added
        verification_query = execute_query(
            "SELECT COUNT(*) as count FROM user_avatars WHERE user_id = %s",
            (user_id,),
            fetch_one=True
        )
        
        if verification_query:
            avatar_count = verification_query.get('count', 0)
            logger.info(f"✅ User {user_id} now has {avatar_count} avatars")
        
    except Exception as e:
        logger.error(f"❌ Critical error setting up default avatars for user {user_id}: {e}")
        # Try a simpler fallback approach
        try:
            simple_avatar = {
                'heygen_avatar_id': 'Tyler-insuit-20220721',
                'avatar_name': 'Default Avatar',
                'avatar_image_url': 'https://files2.heygen.ai/avatar/v3/25ef6c86b1254a5e8fffe00b32275d93/25ef6c86b1254a5e8fffe00b32275d93.jpg',
                'is_default': 1
            }
            
            execute_query(
                """INSERT INTO user_avatars (user_id, heygen_avatar_id, avatar_name, avatar_image_url, is_default, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (user_id, simple_avatar['heygen_avatar_id'], simple_avatar['avatar_name'], 
                 simple_avatar['avatar_image_url'], simple_avatar['is_default'], datetime.now())
            )
            logger.info(f"✅ Fallback: Added simple default avatar for user {user_id}")
        except Exception as fallback_error:
            logger.error(f"❌ Even fallback avatar setup failed for user {user_id}: {fallback_error}")

def verify_user_avatars_setup(user_id: int):
    """Verify that user has avatars and fix if missing"""
    try:
        avatars = execute_query(
            "SELECT * FROM user_avatars WHERE user_id = %s",
            (user_id,),
            fetch_all=True
        )
        
        if not avatars or len(avatars) == 0:
            logger.warning(f"🎭 User {user_id} has no avatars - setting up now")
            setup_default_avatars_for_user(user_id)
            
            # Verify again
            avatars = execute_query(
                "SELECT * FROM user_avatars WHERE user_id = %s",
                (user_id,),
                fetch_all=True
            )
            
            if avatars and len(avatars) > 0:
                logger.info(f"✅ Successfully fixed avatars for user {user_id}")
                return True
            else:
                logger.error(f"❌ Still no avatars for user {user_id} after setup attempt")
                return False
        else:
            logger.info(f"✅ User {user_id} has {len(avatars)} avatars")
            return True
            
    except Exception as e:
        logger.error(f"Error verifying user avatars: {e}")
        return False

# STEP 15: EMERGENCY ADMIN RESET SYSTEM
@router.get("/emergency-hint")
async def get_emergency_hint():
    """Get the hint for the emergency master key"""
    return {
        "hint": f"💡 {config.EMERGENCY_KEY_HINT}",
        "note": "Use the answer to this hint as your master_key in emergency endpoints",
        "endpoints": [
            "POST /emergency-admin-reset",
            "POST /create-emergency-admin"
        ],
        "example": {
            "master_key": "[your answer to the hint]",
            "admin_username": "your_admin_username",
            "new_password": "your_new_secure_password"
        }
    }

@router.post("/emergency-admin-reset")
async def emergency_admin_reset(request: Request):
    """Emergency admin password reset with hint-based master key"""
    try:
        data = await request.json()
        master_key = data.get("master_key", "")
        new_password = data.get("new_password", "")
        admin_username = data.get("admin_username", "")
        
        # Master key with hint system
        if not master_key or master_key != config.EMERGENCY_MASTER_KEY:
            return JSONResponse({
                "success": False,
                "error": "Invalid master key",
                "hint": f"💡 Hint: {config.EMERGENCY_KEY_HINT}",
                "note": "Enter the answer to the hint as the master_key"
            }, status_code=401)
        
        if not new_password or len(new_password) < 8:
            return JSONResponse({
                "success": False,
                "error": "Password must be at least 8 characters"
            }, status_code=400)
        
        if not admin_username:
            return JSONResponse({
                "success": False,
                "error": "Admin username required"
            }, status_code=400)
        
        # Find admin user
        admin_user = db.get_user_by_username(admin_username)
        if not admin_user:
            return JSONResponse({
                "success": False,
                "error": "Admin user not found"
            }, status_code=404)
        
        if not admin_user.get('is_admin', 0):
            return JSONResponse({
                "success": False,
                "error": "User is not an admin"
            }, status_code=403)
        
        # Reset password
        new_hashed_password = hash_password(new_password)
        
        # Update password in database
        update_result = execute_query(
            "UPDATE users SET password = %s WHERE id = %s AND is_admin = 1",
            (new_hashed_password, admin_user['id'])
        )
        
        if update_result is not None:
            logger.info(f"🔐 EMERGENCY: Admin password reset for user {admin_username}")
            return JSONResponse({
                "success": True,
                "message": f"Admin password reset successfully for {admin_username}",
                "admin_id": admin_user['id'],
                "note": "Please test login immediately and delete emergency endpoints!"
            })
        else:
            return JSONResponse({
                "success": False,
                "error": "Failed to update password"
            }, status_code=500)
            
    except Exception as e:
        logger.error(f"Emergency admin reset error: {e}")
        return JSONResponse({
            "success": False,
            "error": "Reset failed"
        }, status_code=500)

@router.post("/create-emergency-admin")
async def create_emergency_admin(request: Request):
    """Create emergency admin user with hint-based master key"""
    try:
        data = await request.json()
        master_key = data.get("master_key", "")
        username = data.get("username", "")
        password = data.get("password", "")
        email = data.get("email", "")
        
        # Master key with hint system
        if not master_key or master_key != config.EMERGENCY_MASTER_KEY:
            return JSONResponse({
                "success": False,
                "error": "Invalid master key",
                "hint": f"💡 Hint: {config.EMERGENCY_KEY_HINT}",
                "note": "Enter the answer to the hint as the master_key"
            }, status_code=401)
        
        # Validation
        if not username or not password or not email:
            return JSONResponse({
                "success": False,
                "error": "Username, password, and email required"
            }, status_code=400)
        
        if len(password) < 8:
            return JSONResponse({
                "success": False,
                "error": "Password must be at least 8 characters"
            }, status_code=400)
        
        # Check if user already exists
        if db.get_user_by_username(username):
            return JSONResponse({
                "success": False,
                "error": "Username already exists"
            }, status_code=409)
        
        # Create emergency admin
        hashed_password = hash_password(password)
        api_key = generate_api_key()
        
        user_data = {
            "username": username,
            "email": email,
            "password": hashed_password,
            "api_key": api_key,
            "is_admin": 1,  # Make admin
            "is_locked": 0,
            "avatar_id": "",
            "created_at": datetime.now().isoformat(),
            "email_verified": 1,
            "credits_remaining": config.MAX_CREDITS_PER_USER
        }
        
        user_id = db.create_user(user_data)
        
        if user_id:
            logger.info(f"🚨 EMERGENCY: Created admin user {username} with ID {user_id}")
            
            # Set up avatars for the new admin
            try:
                setup_default_avatars_for_user(user_id)
            except Exception as avatar_error:
                logger.error(f"Avatar setup failed for emergency admin {username}: {avatar_error}")
            
            return JSONResponse({
                "success": True,
                "message": f"Emergency admin created: {username}",
                "user_id": user_id,
                "note": "Please test login immediately and delete emergency endpoints!"
            })
        else:
            return JSONResponse({
                "success": False,
                "error": "Failed to create admin user"
            }, status_code=500)
            
    except Exception as e:
        logger.error(f"Emergency admin creation error: {e}")
        return JSONResponse({
            "success": False,
            "error": "Admin creation failed"
        }, status_code=500)

@router.get("/debug-admin-users")
async def debug_admin_users():
    """List all admin users for debugging"""
    try:
        admins = execute_query(
            "SELECT id, username, email, is_admin, created_at FROM users WHERE is_admin = 1",
            fetch_all=True
        )
        
        admin_list = []
        if admins:
            for admin in admins:
                admin_dict = dict(admin) if hasattr(admin, '_asdict') else admin
                admin_list.append({
                    "id": admin_dict.get('id'),
                    "username": admin_dict.get('username'),
                    "email": admin_dict.get('email'),
                    "is_admin": admin_dict.get('is_admin'),
                    "created_at": str(admin_dict.get('created_at'))
                })
        
        return {
            "success": True,
            "admin_count": len(admin_list),
            "admins": admin_list,
            "emergency_hint": config.EMERGENCY_KEY_HINT,
            "reset_endpoints": [
                "POST /emergency-admin-reset",
                "POST /create-emergency-admin",
                "GET /emergency-hint"
            ]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# STEP 16: VACATION-SAFE ROUTES WITH REAL COST TRACKING
@router.get("/")
async def home_page(request: Request):
    """Home page with vacation mode protection"""
    try:
        emergency_stop, emergency_msg = check_emergency_stop()
        if emergency_stop:
            return JSONResponse({
                "message": emergency_msg,
                "status": "maintenance"
            })
        
        # Check budget limits
        budget_ok, budget_msg = await check_budget_limits()
        if not budget_ok:
            return JSONResponse({
                "message": budget_msg,
                "status": "budget_limit"
            })
        
        user = get_current_user(request)
        if user:
            return RedirectResponse(url="/dashboard", status_code=302)
        
        stats = get_system_stats()
            
        try:
            response = templates.TemplateResponse("index.html", {
                "request": request,
                "user": None,
                "vacation_mode": config.VACATION_MODE,
                "users_percentage": stats['users_percentage'],
                "stats": stats
            })
        except Exception as template_error:
            logger.warning(f"Template error: {template_error}")
            return JSONResponse({
                "message": "🎭 MyAvatar - Create Amazing AI Videos",
                "status": "Template not found - using JSON response",
                "login_url": "/login",
                "register_url": "/register",
                "vacation_mode": config.VACATION_MODE,
                "beta_status": f"Beta Testing - {stats['total_users']}/{config.MAX_TOTAL_USERS} users"
            })
        
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response
    except Exception as e:
        logger.error(f"Error loading home page: {e}")
        return JSONResponse({
            "error": "Service temporarily unavailable",
            "status": "error",
            "login_url": "/login"
        }, status_code=500)

@router.get("/login")
async def login_page(request: Request):
    """Display login page with vacation mode checks"""
    try:
        emergency_stop, emergency_msg = check_emergency_stop()
        if emergency_stop:
            return JSONResponse({
                "message": emergency_msg,
                "status": "maintenance"
            })
        
        user = get_current_user(request)
        if user:
            return RedirectResponse(url="/dashboard", status_code=302)
        
        return templates.TemplateResponse("portal/login.html", {
            "request": request,
            "user": None,
            "error": None,
            "vacation_mode": config.VACATION_MODE
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
    """Handle user login with vacation mode protection"""
    try:
        emergency_stop, emergency_msg = check_emergency_stop()
        if emergency_stop:
            return templates.TemplateResponse("portal/login.html", {
                "request": request,
                "user": None,
                "error": emergency_msg
            })
        
        form = await request.form()
        username = sanitize_input(str(form.get("username", "")))
        password = str(form.get("password", ""))
        
        if not username or not password:
            return templates.TemplateResponse("portal/login.html", {
                "request": request,
                "user": None,
                "error": "Username and password are required"
            }, status_code=400)
        
        user = db.get_user_by_username(username)
        if not user:
            return templates.TemplateResponse("portal/login.html", {
                "request": request,
                "user": None,
                "error": "Invalid username or password"
            }, status_code=401)
        
        stored_password = user.get("hashed_password", "")
        if not stored_password or not verify_password(password, stored_password):
            return templates.TemplateResponse("portal/login.html", {
                "request": request,
                "user": None,
                "error": "Invalid username or password"
            }, status_code=401)
        
        token = session_manager.create_session(user["id"], request)
        db.update_user_login(user["id"])
        
        if user.get("is_admin", 0) == 1:
            response = RedirectResponse(url="/admin", status_code=302)
        else:
            response = RedirectResponse(url="/dashboard", status_code=302)
        
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=86400
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
    """Display registration page with vacation mode protection"""
    try:
        emergency_stop, emergency_msg = check_emergency_stop()
        if emergency_stop:
            return JSONResponse({
                "message": emergency_msg,
                "status": "maintenance"
            })
        
        user = get_current_user(request)
        if user:
            return RedirectResponse(url="/dashboard", status_code=302)
        
        # Check budget limits
        budget_ok, budget_msg = await check_budget_limits()
        if not budget_ok:
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": budget_msg,
                "limits_reached": True
            })
        
        # Check user limits
        can_register, limit_msg = check_user_limits()
        if not can_register:
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": limit_msg,
                "limits_reached": True
            })
            
        stats = get_system_stats()
            
        return templates.TemplateResponse("portal/register.html", {
            "request": request,
            "user": None,
            "vacation_mode": config.VACATION_MODE,
            "stats": stats
        })
    except Exception as e:
        logger.error(f"Error loading register page: {e}")
        return templates.TemplateResponse("portal/register.html", {
            "request": request,
            "user": None,
            "error": "Registration page temporarily unavailable. Please try again."
        })

@router.post("/register")
@limiter.limit(config.RATE_LIMIT_REGISTER)
async def register_user(request: Request):
    """VACATION-SAFE REGISTRATION with real cost tracking and FIXED AVATAR SETUP"""
    try:
        # Check emergency stop
        emergency_stop, emergency_msg = check_emergency_stop()
        if emergency_stop:
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": emergency_msg
            })
        
        # Check budget limits
        budget_ok, budget_msg = await check_budget_limits()
        if not budget_ok:
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": budget_msg,
                "limits_reached": True
            })
        
        # Check user limits
        can_register, limit_msg = check_user_limits()
        if not can_register:
            logger.warning(f"🏖️ VACATION MODE - Registration blocked: {limit_msg}")
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": limit_msg,
                "limits_reached": True
            })
        
        form = await request.form()
        username = sanitize_input(str(form.get("username", "")))
        email = sanitize_input(str(form.get("email", "")))
        password = str(form.get("password", ""))
        confirm_password = str(form.get("confirm_password", ""))
        
        logger.info(f"🏖️ VACATION MODE REGISTRATION - Username: '{username}', Email: '{email}'")
        
        # Validation
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
        
        # Check if user exists
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
        
        # Final budget/limit check before creating user
        budget_ok, budget_msg = await check_budget_limits()
        can_register, limit_msg = check_user_limits()
        
        if not budget_ok:
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": budget_msg,
                "limits_reached": True
            })
        
        if not can_register:
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": limit_msg,
                "limits_reached": True
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
            "is_locked": 0,
            "avatar_id": "",
            "created_at": datetime.now().isoformat(),
            "email_verified": 0,
            "credits_remaining": config.MAX_CREDITS_PER_USER
        }
        
        user_id = db.create_user(user_data)
        
        if not user_id:
            logger.error(f"🏖️ VACATION MODE - User creation failed for {username}")
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": "Registration failed. Please try again."
            }, status_code=500)
        
        logger.info(f"🏖️ VACATION MODE - User {username} created successfully with ID: {user_id}")
        
        # Log cost event for new user registration
        await log_api_cost_event("registration", "create_user", 0.10)
        
        # Set up default avatars with verification
        try:
            setup_default_avatars_for_user(user_id)
            
            # Verify avatars were actually created
            if verify_user_avatars_setup(user_id):
                logger.info(f"🎭 VACATION MODE - Default avatars successfully set up for user {username}")
            else:
                logger.error(f"🎭 VACATION MODE - Avatar setup verification failed for user {username}")
                
        except Exception as avatar_error:
            logger.error(f"🎭 VACATION MODE - Avatar setup failed for user {username}: {avatar_error}")
            # Still allow registration to complete even if avatar setup fails
        
        # Auto-login
        token = session_manager.create_session(user_id, request)
        
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=86400
        )
        
        logger.info(f"🏖️ VACATION MODE - Registration completed successfully for user: {username}")
        return response
        
    except Exception as e:
        error_details = f"Registration error: {type(e).__name__}: {str(e)}"
        logger.error(f"🏖️ VACATION MODE REGISTRATION EXCEPTION: {error_details}")
        
        return templates.TemplateResponse("portal/register.html", {
            "request": request,
            "user": None,
            "error": "🚧 Our registration system is experiencing high demand. Please try again in a few minutes!"
        }, status_code=500)

@router.get("/logout")
async def logout_user(request: Request):
    """Handle user logout"""
    try:
        token = request.cookies.get("access_token")
        if token:
            session_manager.active_sessions.pop(token, None)
        
        response = RedirectResponse(url="/", status_code=302)
        response.delete_cookie("access_token")
        return response
    except Exception as e:
        logger.error(f"Error during logout: {e}")
        response = RedirectResponse(url="/", status_code=302)
        response.delete_cookie("access_token")
        return response

@router.get("/dashboard")
async def dashboard_page(request: Request):
    """Display user dashboard with vacation mode protections and FIXED AVATAR VERIFICATION"""
    user = None
    try:
        emergency_stop, emergency_msg = check_emergency_stop()
        if emergency_stop:
            return JSONResponse({
                "message": emergency_msg,
                "status": "maintenance"
            })
        
        user = get_current_user(request)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        logger.info(f"🏖️ VACATION MODE DASHBOARD - User {user.get('username')} accessing dashboard")
        
        # Get user data
        videos = db.get_user_videos(user["id"])
        logger.info(f"🎬 DEBUG: Got {len(videos) if videos else 0} videos for user {user['id']}")
        user_video_count = len(videos) if videos else 0
        
        # Get user avatars with verification
        user_avatars = []
        try:
            # First verify user has avatars, set up if missing
            verify_user_avatars_setup(user["id"])
            
            avatars = db.get_user_avatars(user["id"])
            if avatars:
                for avatar in avatars:
                    if isinstance(avatar, dict):
                        user_avatars.append({
                            'id': avatar.get('id'),
                            'name': sanitize_input(avatar.get('avatar_name', 'Unnamed Avatar')),
                            'avatar_image_url': avatar.get('avatar_image_url', ''),
                            'heygen_avatar_id': avatar.get('heygen_avatar_id', ''),
                            'avatar_id': avatar.get('heygen_avatar_id', ''),
                            'is_default': avatar.get('is_default', 0)
                        })
            
            # If still no avatars, log the issue
            if not user_avatars:
                logger.error(f"🎭 User {user['username']} still has no avatars after verification")
                
        except Exception as avatar_error:
            logger.error(f"Error fetching user avatars: {avatar_error}")
            # Ensure user has at least one default avatar
            try:
                setup_default_avatars_for_user(user["id"])
            except:
                pass
        
        # Process videos
        logger.info(f"🔍 DEBUG: Raw videos from database: {len(videos) if videos else 0} videos")
        logger.info(f"🔍 DEBUG: Videos type: {type(videos)}")
        if videos:
            logger.info(f"🔍 DEBUG: First video sample: {videos[0] if videos else 'None'}")
        
        processed_videos = []
        if videos:
            for video in videos:
                if isinstance(video, dict):
                    video_url = video.get('video_url')
                    logger.info(f"Processing video {video.get('id')}: status={video.get('status')}, video_url={'YES' if video_url else 'NO'}, url_type={type(video_url)}")
                    processed_videos.append({
                        'id': video.get('id'),
                        'heygen_video_id': video.get('heygen_video_id'),
                        'title': sanitize_input(video.get('title', 'Untitled Video')),
                        'status': sanitize_input(video.get('status', 'unknown')),
                        'duration': video.get('duration', ''),
                        'format': video.get('format', '16:9'),
                        'video_url': video_url,
                        'thumbnail_url': video.get('thumbnail_url'),
                        'created_at': str(video.get('created_at', 'Unknown'))
                    })
        
        # Calculate stats
        total_videos = len(processed_videos)
        credits_remaining = user.get('credits_remaining', config.MAX_CREDITS_PER_USER)
        system_stats = get_system_stats()
        
        # Build template context
        template_context = {
            "request": request,
            "user": user,
            "username": sanitize_input(user.get("username", "User")),
            "is_admin": bool(user.get("is_admin", 0)),
            "user_id": int(user.get("id", 0)),
            "videos": processed_videos,
            "total_videos": total_videos,
            "user_avatars": user_avatars,
            "avatar_count": len(user_avatars),
            "credits_remaining": credits_remaining,
            "max_credits": config.MAX_CREDITS_PER_USER,
            "max_videos_per_user": config.MAX_VIDEOS_PER_USER,
            "user_video_count": user_video_count,
            "vacation_mode": config.VACATION_MODE,
            "system_stats": system_stats,
            "video_limit_reached": user_video_count >= config.MAX_VIDEOS_PER_USER
        }
        
        try:
            logger.error(f"🔍 TEMPLATE DEBUG: About to render dashboard.html")
            logger.error(f"🔍 TEMPLATE DEBUG: Templates dir = {templates_dir}")
            logger.error(f"🔍 TEMPLATE DEBUG: Context keys = {list(template_context.keys())}")
            
            response = templates.TemplateResponse("dashboard.html", template_context)
            
            logger.error(f"✅ TEMPLATE DEBUG: Rendered successfully")
            
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            
            return response
        except Exception as template_error:
            logger.error(f"❌ TEMPLATE ERROR: {str(template_error)}")
            logger.error(f"❌ ERROR TYPE: {type(template_error)}")
            return JSONResponse({
                "message": "Dashboard",
                "user": user.get("username", "User"),
                "total_videos": total_videos,
                "avatar_count": len(user_avatars),
                "credits_remaining": credits_remaining,
                "vacation_mode": True,
                "status": f"Template error: {str(template_error)}"
            })
        
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return JSONResponse({
            "error": "Dashboard temporarily unavailable",
            "user": user.get("username", "User") if user else "Unknown",
            "status": "error"
        }, status_code=500)

# USERNAME CHECKING API
@router.post("/api/check-username")
@limiter.limit("10/minute")
async def check_username_availability(request: Request):
    """API endpoint to check if username is available"""
    try:
        emergency_stop, emergency_msg = check_emergency_stop()
        if emergency_stop:
            return JSONResponse({
                "available": False,
                "error": "Service temporarily unavailable"
            })
        
        data = await request.json()
        username = sanitize_input(data.get("username", "").strip())
        
        if not username:
            return JSONResponse({
                "available": False,
                "error": "Username is required"
            }, status_code=400)
        
        if len(username) < 3 or len(username) > 50:
            return JSONResponse({
                "available": False,
                "error": "Username must be between 3 and 50 characters"
            }, status_code=400)
        
        if not username.replace('_', '').replace('-', '').isalnum():
            return JSONResponse({
                "available": False,
                "error": "Username can only contain letters, numbers, hyphens, and underscores"
            }, status_code=400)
        
        if username.startswith(('-', '_')) or username.endswith(('-', '_')):
            return JSONResponse({
                "available": False,
                "error": "Username cannot start or end with hyphen or underscore"
            }, status_code=400)
        
        existing_user = db.get_user_by_username(username)
        
        if existing_user:
            return JSONResponse({
                "available": False,
                "message": "Username is already taken"
            })
        else:
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

# AVATAR DEBUG AND MANAGEMENT ENDPOINTS
@router.get("/debug-avatars/{user_id}")
async def debug_user_avatars(user_id: int):
    """Debug endpoint to check user avatars and fix if needed"""
    try:
        # Check if user exists
        user = db.get_user_by_id(user_id)
        if not user:
            return {"error": f"User {user_id} not found"}
        
        # Get current avatars
        current_avatars = execute_query(
            "SELECT * FROM user_avatars WHERE user_id = %s",
            (user_id,),
            fetch_all=True
        )
        
        avatar_data = []
        if current_avatars:
            for avatar in current_avatars:
                avatar_dict = dict(avatar) if hasattr(avatar, '_asdict') else avatar
                avatar_data.append(avatar_dict)
        
        # Check database structure
        table_structure = execute_query(
            """SELECT column_name, data_type, is_nullable 
               FROM information_schema.columns 
               WHERE table_name = 'user_avatars'
               ORDER BY ordinal_position""",
            fetch_all=True
        )
        
        structure_data = []
        if table_structure:
            for col in table_structure:
                col_dict = dict(col) if hasattr(col, '_asdict') else col
                structure_data.append(col_dict)
        
        return {
            "user_id": user_id,
            "username": user.get('username'),
            "current_avatars": avatar_data,
            "avatar_count": len(avatar_data),
            "table_structure": structure_data,
            "has_avatars": len(avatar_data) > 0,
            "actions": {
                "setup_avatars": f"/api/setup-avatars/{user_id}",
                "verify_avatars": f"/api/verify-avatars/{user_id}"
            }
        }
        
    except Exception as e:
        return {"error": str(e)}

@router.post("/api/setup-avatars/{user_id}")
async def force_setup_avatars(user_id: int):
    """Force setup default avatars for a user"""
    try:
        user = db.get_user_by_id(user_id)
        if not user:
            return {"error": f"User {user_id} not found"}
        
        # Clear existing avatars first
        execute_query("DELETE FROM user_avatars WHERE user_id = %s", (user_id,))
        
        # Setup new avatars
        setup_default_avatars_for_user(user_id)
        
        # Verify
        new_avatars = execute_query(
            "SELECT * FROM user_avatars WHERE user_id = %s",
            (user_id,),
            fetch_all=True
        )
        
        return {
            "success": True,
            "user_id": user_id,
            "username": user.get('username'),
            "avatars_created": len(new_avatars) if new_avatars else 0,
            "message": f"Set up {len(new_avatars) if new_avatars else 0} default avatars"
        }
        
    except Exception as e:
        return {"error": str(e), "success": False}

@router.get("/api/verify-avatars/{user_id}")
async def verify_avatars_endpoint(user_id: int):
    """Verify user has avatars and return status"""
    try:
        user = db.get_user_by_id(user_id)
        if not user:
            return {"error": f"User {user_id} not found"}
        
        success = verify_user_avatars_setup(user_id)
        
        avatars = execute_query(
            "SELECT * FROM user_avatars WHERE user_id = %s",
            (user_id,),
            fetch_all=True
        )
        
        return {
            "success": success,
            "user_id": user_id,
            "username": user.get('username'),
            "avatar_count": len(avatars) if avatars else 0,
            "has_avatars": len(avatars) > 0 if avatars else False
        }
        
    except Exception as e:
        return {"error": str(e), "success": False}

# VACATION MODE MONITORING WITH REAL COSTS
@router.get("/admin/vacation-stats")
async def vacation_stats():
    """Monitor vacation mode with REAL Railway + HeyGen costs"""
    try:
        stats = get_system_stats()
        
        # Get real costs from APIs
        railway_costs = await get_real_railway_costs()
        heygen_usage = await get_heygen_usage_stats()
        
        total_estimated_cost = 0
        cost_breakdown = {}
        
        # Railway costs
        if railway_costs:
            railway_cost = railway_costs['current_cost']
            railway_percentage = (railway_cost / config.RAILWAY_BUDGET) * 100
            cost_breakdown['railway'] = {
                "current_cost": railway_cost,
                "estimated_monthly": railway_costs['estimated_cost'],
                "budget_limit": config.RAILWAY_BUDGET,
                "percentage_used": round(railway_percentage, 1),
                "source": "Railway API (Real-time)",
                "status": "OK" if railway_percentage < 80 else "WARNING" if railway_percentage < 90 else "CRITICAL"
            }
            total_estimated_cost += railway_cost
        else:
            estimated_railway = stats['total_users'] * 0.30
            cost_breakdown['railway'] = {
                "estimated_cost": estimated_railway,
                "budget_limit": config.RAILWAY_BUDGET,
                "percentage_used": round((estimated_railway / config.RAILWAY_BUDGET) * 100, 1),
                "source": "Estimated (API unavailable)",
                "status": "UNKNOWN"
            }
            total_estimated_cost += estimated_railway
        
        # HeyGen costs
        if heygen_usage:
            heygen_cost = heygen_usage['estimated_cost']
            heygen_percentage = (heygen_cost / config.HEYGEN_BUDGET) * 100
            quota_percentage = (heygen_usage['quota_used'] / max(heygen_usage['quota_total'], 1)) * 100
            
            cost_breakdown['heygen'] = {
                "quota_used": heygen_usage['quota_used'],
                "quota_total": heygen_usage['quota_total'],
                "quota_remaining": heygen_usage['quota_remaining'],
                "quota_percentage": round(quota_percentage, 1),
                "estimated_cost": heygen_cost,
                "budget_limit": config.HEYGEN_BUDGET,
                "percentage_used": round(heygen_percentage, 1),
                "current_month_usage": heygen_usage['current_month_usage'],
                "source": "HeyGen API (Real-time)",
                "status": "OK" if heygen_percentage < 80 else "WARNING" if heygen_percentage < 90 else "CRITICAL"
            }
            total_estimated_cost += heygen_cost
        else:
            estimated_heygen = stats['total_videos'] * 0.60
            cost_breakdown['heygen'] = {
                "estimated_cost": estimated_heygen,
                "budget_limit": config.HEYGEN_BUDGET,
                "percentage_used": round((estimated_heygen / config.HEYGEN_BUDGET) * 100, 1),
                "source": "Estimated (API unavailable)",
                "status": "UNKNOWN"
            }
            total_estimated_cost += estimated_heygen
        
        budget_percentage = (total_estimated_cost / config.TOTAL_BUDGET) * 100
        
        return {
            "success": True,
            "vacation_mode": config.VACATION_MODE,
            "timestamp": datetime.now().isoformat(),
            "budget_summary": {
                "total_budget": config.TOTAL_BUDGET,
                "railway_budget": config.RAILWAY_BUDGET,
                "heygen_budget": config.HEYGEN_BUDGET,
                "total_estimated_cost": round(total_estimated_cost, 2),
                "budget_used_percentage": round(budget_percentage, 1),
                "budget_remaining": round(config.TOTAL_BUDGET - total_estimated_cost, 2),
                "currency": "USD",
                "status": "OK" if budget_percentage < 70 else "WARNING" if budget_percentage < 85 else "CRITICAL"
            },
            "cost_breakdown": cost_breakdown,
            "limits": {
                "max_total_users": config.MAX_TOTAL_USERS,
                "max_daily_registrations": config.MAX_DAILY_REGISTRATIONS,
                "max_videos_per_user": config.MAX_VIDEOS_PER_USER,
                "max_credits_per_user": config.MAX_CREDITS_PER_USER
            },
            "current_usage": stats,
            "alerts": [
                f"🏖️ Vacation Mode: {stats['total_users']}/{config.MAX_TOTAL_USERS} users ({stats['users_percentage']}%)",
                f"💰 Total Budget: ${total_estimated_cost:.2f}/${config.TOTAL_BUDGET} ({budget_percentage:.1f}%)",
                f"🚂 Railway: ${cost_breakdown.get('railway', {}).get('current_cost', 0):.2f}/${config.RAILWAY_BUDGET}",
                f"🎬 HeyGen: ${cost_breakdown.get('heygen', {}).get('estimated_cost', 0):.2f}/${config.HEYGEN_BUDGET}",
                f"📹 Videos: {stats['total_videos']} total created",
                f"📅 Today: {stats['daily_registrations']}/{config.MAX_DAILY_REGISTRATIONS} registrations"
            ]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "vacation_mode": config.VACATION_MODE
        }

@router.get("/admin/emergency-controls")
async def emergency_controls():
    """Emergency controls for vacation mode"""
    return {
        "emergency_stop": config.EMERGENCY_STOP,
        "vacation_mode": config.VACATION_MODE,
        "emergency_reset": {
            "hint": config.EMERGENCY_KEY_HINT,
            "endpoints": [
                "GET /emergency-hint",
                "POST /emergency-admin-reset", 
                "POST /create-emergency-admin",
                "GET /debug-admin-users"
            ]
        },
        "controls": {
            "emergency_stop": "Set environment variable EMERGENCY_STOP=true to immediately stop all new registrations",
            "budget_monitoring": "Visit /admin/vacation-stats for real-time cost tracking",
            "database_status": "Visit /debug-database for database health",
            "system_limits": "All limits are automatically enforced"
        },
        "current_limits": {
            "max_users": config.MAX_TOTAL_USERS,
            "max_daily_registrations": config.MAX_DAILY_REGISTRATIONS,
            "max_videos_per_user": config.MAX_VIDEOS_PER_USER,
            "railway_budget": config.RAILWAY_BUDGET,
            "heygen_budget": config.HEYGEN_BUDGET,
            "total_budget": config.TOTAL_BUDGET
        },
        "api_status": {
            "railway_api": "Configured" if config.RAILWAY_API_KEY != "your-railway-api-key" else "Not configured",
            "heygen_api": "Configured" if config.HEYGEN_API_KEY != "your-heygen-api-key" else "Not configured"
        }
    }

@router.get("/debug-database")
async def debug_database():
    """Check all database tables and structures with vacation mode info"""
    try:
        tables_query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """
        tables_result = execute_query(tables_query, fetch_all=True)
        tables = [dict(row)['table_name'] for row in tables_result] if tables_result else []
        
        table_structures = {}
        for table in tables:
            columns_query = f"""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = '{table}'
                ORDER BY ordinal_position
            """
            columns_result = execute_query(columns_query, fetch_all=True)
            table_structures[table] = [dict(row) for row in columns_result] if columns_result else []
        
        record_counts = {}
        for table in tables:
            try:
                count_query = f"SELECT COUNT(*) as count FROM {table}"
                count_result = execute_query(count_query, fetch_one=True)
                record_counts[table] = dict(count_result)['count'] if count_result else 0
            except:
                record_counts[table] = "Error"
        
        return {
            "success": True,
            "database_type": "PostgreSQL",
            "vacation_mode": config.VACATION_MODE,
            "timestamp": datetime.now().isoformat(),
            "tables": tables,
            "table_structures": table_structures,
            "record_counts": record_counts,
            "total_tables": len(tables),
            "vacation_stats": get_system_stats()
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/test-routes")
async def test_routes():
    """Test endpoint showing vacation mode status with real cost tracking + emergency reset"""
    stats = get_system_stats()
    
    return {
        "message": "🏖️ VACATION-SAFE MyAvatar with EMERGENCY RESET + FIXED AVATARS - Railway $100 + HeyGen $100!", 
        "vacation_mode": config.VACATION_MODE,
        "routes_loaded": True,
        "emergency_reset": {
            "hint": config.EMERGENCY_KEY_HINT,
            "enabled": True,
            "endpoints": [
                "GET /emergency-hint - Get your hint",
                "POST /emergency-admin-reset - Reset admin password",
                "POST /create-emergency-admin - Create new admin",
                "GET /debug-admin-users - List all admins"
            ]
        },
        "avatar_system": {
            "default_avatars": 4,
            "avatar_verification": "Enabled",
            "auto_setup": "On registration + dashboard check",
            "debug_endpoints": [
                "/debug-avatars/{user_id}",
                "/api/setup-avatars/{user_id}",
                "/api/verify-avatars/{user_id}"
            ]
        },
        "real_cost_tracking": {
            "railway_budget": config.RAILWAY_BUDGET,
            "heygen_budget": config.HEYGEN_BUDGET,
            "total_budget": config.TOTAL_BUDGET,
            "railway_api": "Configured" if config.RAILWAY_API_KEY != "your-railway-api-key" else "Not configured",
            "heygen_api": "Configured" if config.HEYGEN_API_KEY != "your-heygen-api-key" else "Not configured"
        },
        "budget_protection": {
            "max_users": config.MAX_TOTAL_USERS,
            "current_users": stats['total_users'],
            "users_remaining": config.MAX_TOTAL_USERS - stats['total_users'],
            "max_videos_per_user": config.MAX_VIDEOS_PER_USER,
            "daily_limit": config.MAX_DAILY_REGISTRATIONS,
            "today_registrations": stats['daily_registrations']
        },
        "features": [
            "🛡️ Hard User Limits (300 max)",
            "🎬 Video Limits per User (7 max)", 
            "📅 Daily Registration Limits (30/day)",
            "🚨 Emergency Stop Controls",
            "🔑 EMERGENCY ADMIN RESET with Hint System",
            "💰 Real Railway Cost Tracking ($100 budget)",
            "🎭 Real HeyGen Usage Tracking ($100 budget)",
            "🎭 FIXED Avatar System (4 default avatars)",
            "✅ Avatar Verification & Auto-Setup",
            "🔧 Avatar Debug Tools",
            "📊 Live Budget Monitoring",
            "🏖️ 10-Day Vacation Mode",
            "🔐 Authentication & Security",
            "🍪 JWT Cookie Sessions",
            "⚡ Smart Rate Limiting",
            "🧹 Input Sanitization", 
            "✅ Real-time Username Validation"
        ],
        "friendly_excuses": [
            "🎉 We've reached our beta capacity - expanding soon!",
            "🔥 Amazing daily interest - try tomorrow!",
            "🚧 Quick maintenance for better service!",
            "🎬 Video creation limit reached - more coming!",
            "⚠️ High demand - back in a few minutes!"
        ],
        "monitoring_endpoints": [
            "/admin/vacation-stats - Real-time cost tracking",
            "/admin/emergency-controls - Emergency management", 
            "/debug-database - Database health",
            "/debug-avatars/{user_id} - Avatar debugging",
            "/api/setup-avatars/{user_id} - Force avatar setup",
            "/emergency-hint - Get emergency reset hint"
        ]
    }

def get_video_url_from_heygen(heygen_video_id):
    """Get video URL from HeyGen API"""
    if not heygen_video_id:
        return None
    
    try:
        heygen_api_key = os.getenv('HEYGEN_API_KEY')
        if not heygen_api_key or heygen_api_key == 'your-heygen-api-key':
            logger.warning("No valid HeyGen API key found")
            return None
            
        headers = {
            'X-API-KEY': heygen_api_key,
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f'https://api.heygen.com/v2/video/{heygen_video_id}',
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 100 and 'data' in data:
                video_url = data['data'].get('video_url')
                if video_url:
                    return video_url
                    
        logger.warning(f"Could not get video URL for HeyGen ID: {heygen_video_id}")
        return None
        
    except Exception as e:
        logger.error(f"Error getting video URL from HeyGen: {e}")
        return None

@router.get("/api/completed-videos")
async def get_completed_videos_api(request: Request):
    """Get only completed videos with URLs - clean approach"""
    logger.info("🎬 API CALLED: /api/completed-videos")
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Authentication required"}
            )
        
        # Direct SQL query - bypass existing methods
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT id, title, thumbnail_url, duration, created_at, heygen_video_id, video_url
            FROM videos 
            WHERE user_id = %s 
            AND status = 'completed' 
            AND video_url IS NOT NULL 
            AND video_url != ''
            ORDER BY created_at DESC
        """, (user["id"],))
        
        videos = cur.fetchall()
        conn.close()
        
        # Convert to dict and format dates
        video_list = []
        for video in videos:
            video_dict = dict(video)
            if video_dict.get('created_at'):
                video_dict['created_at'] = video_dict['created_at'].strftime('%b %d, %Y')
            
            # Check if video_url exists and refresh if needed
            if video_dict.get('video_url'):
                # Check if URL might be expired (simple heuristic)
                video_url = video_dict['video_url']
                if 'Expires=' in video_url:
                    try:
                        # Extract expiry timestamp
                        expires_part = video_url.split('Expires=')[1].split('&')[0]
                        expires_timestamp = int(expires_part)
                        current_timestamp = int(time.time())
                        
                        # If URL expires within 24 hours, refresh it
                        if expires_timestamp - current_timestamp < 86400:  # 24 hours
                            logger.info(f"🔄 Refreshing expired/expiring URL for '{video_dict.get('title')}'")
                            fresh_url = get_video_url_from_heygen(video_dict.get('heygen_video_id'))
                            if fresh_url:
                                video_dict['video_url'] = fresh_url
                                # Update database with fresh URL
                                cur.execute(
                                    "UPDATE videos SET video_url = %s WHERE id = %s",
                                    (fresh_url, video_dict['id'])
                                )
                                conn.commit()
                                logger.info(f"✅ Updated video URL in database for '{video_dict.get('title')}'")
                            else:
                                logger.warning(f"⚠️ Could not refresh URL for '{video_dict.get('title')}'")
                        else:
                            logger.info(f"🎬 Using existing valid URL for '{video_dict.get('title')}'")
                    except (ValueError, IndexError) as e:
                        logger.warning(f"⚠️ Could not parse expiry from URL for '{video_dict.get('title')}': {e}")
                else:
                    logger.info(f"🎬 Using existing URL for '{video_dict.get('title')}'")
            else:
                # No video_url, try to get one from HeyGen
                if video_dict.get('heygen_video_id'):
                    logger.info(f"🔄 Getting fresh URL for '{video_dict.get('title')}'")
                    fresh_url = get_video_url_from_heygen(video_dict.get('heygen_video_id'))
                    if fresh_url:
                        video_dict['video_url'] = fresh_url
                        # Update database
                        cur.execute(
                            "UPDATE videos SET video_url = %s WHERE id = %s",
                            (fresh_url, video_dict['id'])
                        )
                        conn.commit()
                        logger.info(f"✅ Added fresh video URL to database for '{video_dict.get('title')}'")
                    else:
                        logger.warning(f"⚠️ Could not get URL for '{video_dict.get('title')}'")
                else:
                    logger.warning(f"⚠️ No heygen_video_id for video '{video_dict.get('title')}'")
                
            video_list.append(video_dict)
        
        logger.info(f"✅ Completed videos API: Found {len(video_list)} videos for user {user['id']}")
        
        return JSONResponse(
            content={
                "videos": video_list,
                "count": len(video_list),
                "success": True
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error fetching completed videos: {e}")
        return JSONResponse(
            status_code=500,
            content={"videos": [], "count": 0, "error": str(e)}
        )