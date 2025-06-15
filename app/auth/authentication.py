"""
Authentication functions for MyAvatar - Enhanced Modular Version
================================================================
Organized in clear sections for easy navigation and editing
"""

#####################################################################
# IMPORTS
#####################################################################
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from typing import Optional, Dict, Any, Tuple
import os
import secrets
from ..logger.log_handler import log_info, log_error, log_warning
from ..db.database import execute_query

#####################################################################
# CONFIGURATION CONSTANTS
#####################################################################
SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", "120"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_DAYS", "7"))

# Password context configuration
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12
)

# Optional Bearer token support
security = HTTPBearer(auto_error=False)

#####################################################################
# CUSTOM EXCEPTIONS
#####################################################################
class AuthenticationError(Exception):
    """Custom exception for authentication errors"""
    pass

#####################################################################
# PASSWORD UTILITIES
#####################################################################
def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt with salt"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against a hash"""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False

def validate_password_strength(password: str) -> Tuple[bool, str]:
    """Validate password meets security requirements"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    return True, "Password is strong"

#####################################################################
# USER AUTHENTICATION - BY USERNAME
#####################################################################
def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate user by username and password"""
    try:
        # Fetch user from database
        user = execute_query(
            "SELECT * FROM users WHERE username = ?", 
            (username,), 
            fetch_one=True
        )
        
        if not user:
            log_info(f"Authentication failed: User {username} not found", "Auth")
            return None
        
        # Check if user is active (optional field)
        if 'is_active' in user and not user['is_active']:
            log_warning(f"Authentication failed: User {username} is inactive", "Auth")
            return None
            
        # Verify password
        if not verify_password(password, user['hashed_password']):
            log_info(f"Authentication failed: Invalid password for user {username}", "Auth")
            return None
        
        # Update last login
        update_last_login(user['id'], username)
        
        log_info(f"User {username} authenticated successfully", "Auth")
        return user
        
    except Exception as e:
        log_error(f"Authentication error for user {username}", "Auth", e)
        return None

#####################################################################
# USER AUTHENTICATION - BY EMAIL
#####################################################################
def authenticate_user_by_email(email: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate user by email and password"""
    try:
        # Normalize email
        email = email.lower().strip()
        
        # Fetch user from database
        user = execute_query(
            "SELECT * FROM users WHERE LOWER(email) = LOWER(?)", 
            (email,), 
            fetch_one=True
        )
        
        if not user:
            log_info(f"Authentication failed: User with email {email} not found", "Auth")
            return None
        
        # Check if user is active (optional field)
        if 'is_active' in user and not user['is_active']:
            log_warning(f"Authentication failed: User with email {email} is inactive", "Auth")
            return None
            
        # Verify password
        if not verify_password(password, user['hashed_password']):
            log_info(f"Authentication failed: Invalid password for email {email}", "Auth")
            return None
        
        # Update last login
        update_last_login(user['id'], email)
        
        log_info(f"User with email {email} authenticated successfully", "Auth")
        return user
        
    except Exception as e:
        log_error(f"Authentication error for email {email}", "Auth", e)
        return None

#####################################################################
# HELPER FUNCTIONS
#####################################################################
def update_last_login(user_id: int, identifier: str) -> None:
    """Update user's last login timestamp"""
    try:
        execute_query(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (datetime.now(timezone.utc), user_id)
        )
    except Exception as e:
        log_error(f"Failed to update last login for {identifier}", "Auth", e)

#####################################################################
# JWT TOKEN - ACCESS TOKEN
#####################################################################
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> Optional[str]:
    """Create a JWT access token with enhanced claims"""
    try:
        to_encode = data.copy()
        
        # Set expiration
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        # Add standard JWT claims
        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "access"
        })
        
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        
        log_info(f"Access token created for user {data.get('sub')}", "Auth")
        return encoded_jwt
        
    except Exception as e:
        log_error("Failed to create access token", "Auth", e)
        return None

#####################################################################
# JWT TOKEN - REFRESH TOKEN
#####################################################################
def create_refresh_token(data: dict) -> Optional[str]:
    """Create a JWT refresh token"""
    try:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "refresh"
        })
        
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        
        log_info(f"Refresh token created for user {data.get('sub')}", "Auth")
        return encoded_jwt
        
    except Exception as e:
        log_error("Failed to create refresh token", "Auth", e)
        return None

#####################################################################
# JWT TOKEN - VERIFICATION
#####################################################################
def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
    """Verify and decode a JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Verify token type
        if payload.get("type") != token_type:
            log_warning(f"Invalid token type: expected {token_type}, got {payload.get('type')}", "Auth")
            return None
            
        return payload
        
    except JWTError as e:
        log_warning(f"JWT validation error: {str(e)}", "Auth")
        return None
    except Exception as e:
        log_error("Token verification error", "Auth", e)
        return None

#####################################################################
# USER SESSION - GET CURRENT USER
#####################################################################
def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """Get the current authenticated user from the request"""
    try:
        # Try to get token from cookie first
        token = request.cookies.get("access_token")
        
        # Fallback to Authorization header
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
        
        if not token:
            return None
        
        # Verify token
        payload = verify_token(token, "access")
        if not payload:
            return None
            
        username = payload.get("sub")
        if not username:
            return None
        
        # Get fresh user data from database with proper SQL formatting
        user = execute_query(
            """SELECT id, username, email, is_admin, created_at, 
               avatar_img_url, phone, logo_url, linkedin_url 
               FROM users WHERE username = ?""", 
            (username,), 
            fetch_one=True
        )
        
        if not user:
            log_warning(f"User {username} from token not found in database", "Auth")
            return None
        
        # Add token expiry info
        user['token_exp'] = payload.get('exp')
        
        return user
        
    except Exception as e:
        log_error("Error getting current user", "Auth", e)
        return None

#####################################################################
# USER SESSION - AUTHENTICATION REQUIREMENTS
#####################################################################
def get_current_user_required(request: Request) -> Dict[str, Any]:
    """Get current user or raise exception if not authenticated"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

#####################################################################
# ADMIN AUTHORIZATION
#####################################################################
def is_admin(request: Request) -> bool:
    """Check if the current user is an admin"""
    user = get_current_user(request)
    return user and user.get('is_admin', 0) == 1

def require_admin(request: Request) -> Dict[str, Any]:
    """Require admin access or raise exception"""
    user = get_current_user_required(request)
    if not user.get('is_admin', 0) == 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user

#####################################################################
# TOKEN REFRESH
#####################################################################
async def refresh_access_token(refresh_token: str) -> Optional[Dict[str, str]]:
    """Refresh an access token using a refresh token"""
    try:
        # Verify refresh token
        payload = verify_token(refresh_token, "refresh")
        if not payload:
            return None
            
        username = payload.get("sub")
        if not username:
            return None
        
        # Verify user still exists and is active
        user = execute_query(
            "SELECT username, is_admin FROM users WHERE username = ?",
            (username,),
            fetch_one=True
        )
        
        if not user:
            return None
        
        # Create new tokens
        access_token = create_access_token({"sub": username, "admin": user['is_admin']})
        new_refresh_token = create_refresh_token({"sub": username})
        
        if not access_token or not new_refresh_token:
            return None
            
        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        }
        
    except Exception as e:
        log_error("Error refreshing token", "Auth", e)
        return None

#####################################################################
# RATE LIMITING
#####################################################################
# Storage for login attempts
login_attempts = {}

def check_rate_limit(identifier: str, max_attempts: int = 5, window_minutes: int = 15) -> bool:
    """Check if login attempts exceed rate limit"""
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=window_minutes)
    
    # Clean old attempts
    login_attempts[identifier] = [
        attempt for attempt in login_attempts.get(identifier, [])
        if attempt > window_start
    ]
    
    # Check limit
    if len(login_attempts.get(identifier, [])) >= max_attempts:
        log_warning(f"Rate limit exceeded for {identifier}", "Auth")
        return False
    
    # Record attempt
    login_attempts.setdefault(identifier, []).append(now)
    return True

def clear_rate_limit(identifier: str):
    """Clear rate limit for successful login"""
    if identifier in login_attempts:
        del login_attempts[identifier]

#####################################################################
# UTILITY FUNCTIONS
#####################################################################
def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user by ID"""
    try:
        user = execute_query(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
            fetch_one=True
        )
        return user
    except Exception as e:
        log_error(f"Error fetching user by ID: {user_id}", "Auth", e)
        return None

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get user by email"""
    try:
        user = execute_query(
            "SELECT * FROM users WHERE LOWER(email) = LOWER(?)",
            (email.lower().strip(),),
            fetch_one=True
        )
        return user
    except Exception as e:
        log_error(f"Error fetching user by email: {email}", "Auth", e)
        return None