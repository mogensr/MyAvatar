import os
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

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
        
        # Templates
        self.TEMPLATES_DIR = self._find_templates_directory()
        
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
    
    def _find_templates_directory(self) -> str:
        """Find templates directory - FIXED for your exact Windows path"""
        current_file = Path(__file__)
        
        possible_paths = [
            # Most likely: go up from config to MyAvatar root
            current_file.parent.parent.parent / "templates",  # If settings.py is in app/config/
            current_file.parent.parent / "templates",        # If settings.py is in app/
            current_file.parent / "templates",               # If settings.py is in root
            
            # Your exact absolute path as backup
            Path("C:/Users/mogen/Projects/python/CHATGPT/MyAvatar/templates"),
            
            # Working directory variations
            Path.cwd() / "templates",
            Path("./templates"),
            Path("templates"),
        ]
        
        for path in possible_paths:
            if path.exists() and path.is_dir():
                dashboard_file = path / "dashboard.html"
                if dashboard_file.exists():
                    logger.info(f"✅ Found templates at: {path}")
                    return str(path)
        
        # Fallback to your known path
        fallback = "C:/Users/mogen/Projects/python/CHATGPT/MyAvatar/templates"
        logger.warning(f"❌ Using fallback templates path: {fallback}")
        return fallback
    
    def _validate_config(self):
        """Safe validation that doesn't fail"""
        try:
            # Ensure upload directory exists
            self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create upload directory: {e}")

# Global config instance
config = Config()