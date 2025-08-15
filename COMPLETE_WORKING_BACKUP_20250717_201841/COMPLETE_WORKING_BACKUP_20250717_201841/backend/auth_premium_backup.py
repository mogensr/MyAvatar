# backend/auth.py - Basic JWT authentication

from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import Optional
import os

from backend.db import get_db

security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Environment variables
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        return {"user_id": int(user_id)}
    except JWTError:
        return None

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Get the current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Verify the token
    token_data = verify_token(credentials.credentials)
    if token_data is None:
        raise credentials_exception
    
    # Get user from database
    # You'll need to import your User model here
    # For now, we'll return a basic user dict
    # TODO: Replace this with actual user lookup from your User model
    
    user_id = token_data["user_id"]
    
    # Placeholder - replace with actual user lookup:
    # user = db.query(User).filter(User.id == user_id).first()
    # if user is None:
    #     raise credentials_exception
    # return user
    
    # For now, return basic user info
    # Replace this with actual database lookup once you have User model imported
    return {
        "id": user_id,
        "email": f"user{user_id}@example.com",  # Placeholder
        "username": f"user{user_id}"  # Placeholder
    }

def get_current_active_user(current_user: dict = Depends(get_current_user)):
    """Get current active user (extend this with user status checks if needed)"""
    return current_user

# Authentication endpoints helpers
class AuthService:
    """Service class for authentication operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def authenticate_user(self, email: str, password: str):
        """Authenticate a user with email and password"""
        # TODO: Implement user lookup and password verification
        # user = self.db.query(User).filter(User.email == email).first()
        # if not user or not verify_password(password, user.hashed_password):
        #     return None
        # return user
        
        # Placeholder implementation
        if email == "test@example.com" and password == "password":
            return {"id": 1, "email": email, "username": "testuser"}
        return None
    
    def create_user_token(self, user: dict) -> str:
        """Create access token for user"""
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user["id"])}, 
            expires_delta=access_token_expires
        )
        return access_token
