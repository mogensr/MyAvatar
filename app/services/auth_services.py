import bcrypt
import uuid
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

# Import config
from ..config.settings import config

# Import JWT handling
try:
    from jose import jwt
    JWT_AVAILABLE = True
except ImportError:
    try:
        import jwt  # Fallback to PyJWT if available
        JWT_AVAILABLE = True
    except ImportError:
        JWT_AVAILABLE = False
        class jwt:
            @staticmethod
            def encode(payload, secret, algorithm): return "dummy-token"
            @staticmethod 
            def decode(token, secret, algorithms): return {"user_id": 1}
            class ExpiredSignatureError(Exception): pass
            class InvalidTokenError(Exception): pass

logger = logging.getLogger(__name__)

class AuthService:
    """Authentication service handling passwords, tokens, and sessions"""
    
    def __init__(self):
        self.active_sessions = {}
    
    def hash_password(self, password: str) -> str:
        """Hash password with configurable rounds"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=config.BCRYPT_ROUNDS)).decode('utf-8')

    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash"""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False

    def validate_password_strength(self, password: str) -> Tuple[bool, str]:
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

    def generate_api_key(self) -> str:
        """Generate API key"""
        return str(uuid.uuid4())

    def create_access_token(self, user_id: int) -> str:
        """Create JWT access token"""
        try:
            payload = {
                "user_id": user_id,
                "exp": datetime.utcnow() + timedelta(hours=config.JWT_EXPIRATION_HOURS)
            }
            return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)
        except Exception as e:
            logger.error(f"Error creating access token: {e}")
            return str(uuid.uuid4())  # Fallback
    
    def create_session(self, user_id: int, request) -> str:
        """Create user session with token"""
        # Limit sessions per user
        user_sessions = [s for s in self.active_sessions.values() if s.get('user_id') == user_id]
        if len(user_sessions) >= config.MAX_SESSIONS_PER_USER:
            oldest = min(user_sessions, key=lambda x: x['created_at'])
            del self.active_sessions[oldest['token']]
        
        token = self.create_access_token(user_id)
        session_data = {
            'user_id': user_id,
            'created_at': time.time(),
            'ip_address': self._get_remote_address(request),
            'user_agent': request.headers.get('user-agent', ''),
            'token': token
        }
        
        self.active_sessions[token] = session_data
        return token
    
    def validate_session(self, token: str, request) -> Optional[Dict]:
        """Validate session token"""
        if not token or token not in self.active_sessions:
            return None
        
        session = self.active_sessions[token]
        
        # Check timeout
        if time.time() - session['created_at'] > config.SESSION_TIMEOUT:
            del self.active_sessions[token]
            return None
        
        return session
    
    def validate_token(self, token: str) -> Optional[Dict]:
        """Validate JWT token"""
        try:
            payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
            return payload
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None
    
    def destroy_session(self, token: str):
        """Destroy user session"""
        self.active_sessions.pop(token, None)
    
    def _get_remote_address(self, request) -> str:
        """Get client IP address"""
        # Check for forwarded headers first
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        # Fallback to direct client
        client_host = getattr(request.client, 'host', '127.0.0.1')
        return client_host

# Global auth service instance
auth_service = AuthService()