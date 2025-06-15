"""
Authentication functions for MyAvatar
"""
from fastapi import Request, HTTPException, status
from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
import os
from ..logger.log_handler import log_info, log_error
from ..db.database import execute_query

# Constants
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "mysecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120  # 2 hours

# Password handling
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str):
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    """Verify password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)

def authenticate_user(username: str, password: str):
    """Authenticate user by username and password"""
    try:
        user = execute_query(
            "SELECT * FROM users WHERE username = ?", 
            (username,), 
            fetch_one=True
        )
        
        if not user:
            log_info(f"Authentication failed: User {username} not found", "Auth")
            return False
            
        if not verify_password(password, user['password']):
            log_info(f"Authentication failed: Invalid password for user {username}", "Auth")
            return False
            
        log_info(f"User {username} authenticated successfully", "Auth")
        return user
    except Exception as e:
        log_error(f"Authentication error for user {username}", "Auth", e)
        return False

def authenticate_user_by_email(email: str, password: str):
    """Authenticate user by email and password"""
    try:
        user = execute_query(
            "SELECT * FROM users WHERE email = ?", 
            (email,), 
            fetch_one=True
        )
        
        if not user:
            log_info(f"Authentication failed: User with email {email} not found", "Auth")
            return False
            
        if not verify_password(password, user['password']):
            log_info(f"Authentication failed: Invalid password for email {email}", "Auth")
            return False
            
        log_info(f"User with email {email} authenticated successfully", "Auth")
        return user
    except Exception as e:
        log_error(f"Authentication error for email {email}", "Auth", e)
        return False

def create_access_token(data: dict, expires_delta: timedelta = None):
    """Create a JWT access token"""
    try:
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        
        log_info(f"Access token created for user {data.get('sub')}", "Auth")
        return encoded_jwt
    except Exception as e:
        log_error("Failed to create access token", "Auth", e)
        return None

def get_current_user(request: Request):
    """Get the current authenticated user from the request"""
    try:
        token = request.cookies.get("access_token")
        if not token:
            return None
            
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("sub")
            if username is None:
                return None
        except JWTError:
            return None
            
        user = execute_query(
            "SELECT * FROM users WHERE username = ?", 
            (username,), 
            fetch_one=True
        )
        
        return user
    except Exception as e:
        log_error("Error getting current user", "Auth", e)
        return None

def is_admin(request: Request):
    """Check if the current user is an admin"""
    user = get_current_user(request)
    return user and user['is_admin'] == 1
