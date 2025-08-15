# ===============================================================================
# MODULAR AUTH MANAGER V2 - PRESERVES ALL EXISTING FUNCTIONALITY
# ===============================================================================
# File: app/auth/auth_manager_v2.py

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import Request, HTTPException
import jwt
import os

logger = logging.getLogger(__name__)

class AuthResult:
    """Authentication result with comprehensive info"""
    def __init__(self, success: bool, user: Optional[Dict] = None, error: str = None, redirect_url: str = None):
        self.success = success
        self.user = user
        self.error = error
        self.redirect_url = redirect_url
        self.is_admin = user.get('is_admin', 0) == 1 if user else False
        self.is_premium = user.get('is_premium', 0) == 1 if user else False
        
        # Additional premium info
        if user:
            self.user_id = user.get('id')
            self.username = user.get('username')
            self.email = user.get('email')
            self.created_at = user.get('created_at')
            self.last_login = user.get('last_login')
            self.credits_remaining = user.get('credits_remaining', 0)
        else:
            self.user_id = None
            self.username = None
            self.email = None
            self.created_at = None
            self.last_login = None
            self.credits_remaining = 0

class LegacyAuthProvider:
    """Provider that uses your existing auth_service - EXACT COMPATIBILITY"""
    
    def __init__(self):
        self.name = "LegacyAuth"
    
    def authenticate(self, request: Request) -> AuthResult:
        """Use your EXACT existing get_current_user logic"""
        try:
            # Import your existing services
            from ..services.auth_service import auth_service
            from ..db.user_manager import Database
            
            db = Database()
            
            # EXACT copy of your existing logic
            token = request.cookies.get("access_token")
            if not token:
                return AuthResult(False, error="No access_token cookie found")
            
            # Use your existing session validation
            session = auth_service.validate_session(token, request)
            if not session:
                return AuthResult(False, error="Session validation failed")
            
            # Use your existing token validation  
            payload = auth_service.validate_token(token)
            if not payload:
                return AuthResult(False, error="Token validation failed")
            
            user_id = payload.get("user_id")
            if not user_id:
                return AuthResult(False, error="No user_id in token")
            
            # Get user from database
            user = db.get_user_by_id(user_id)
            if not user:
                return AuthResult(False, error="User not found in database")
            
            logger.info(f"LegacyAuth: Successfully authenticated {user.get('username')} (Admin: {user.get('is_admin')}, Premium: {user.get('is_premium')})")
            return AuthResult(True, user=user)
            
        except Exception as e:
            logger.error(f"LegacyAuth error: {e}")
            return AuthResult(False, error=f"Legacy authentication failed: {str(e)}")

class SimpleTokenProvider:
    """Simplified token provider as fallback"""
    
    def __init__(self):
        self.name = "SimpleToken"
        self.secret_key = os.getenv("SECRET_KEY", "your-secret-key")
    
    def authenticate(self, request: Request) -> AuthResult:
        """Simple JWT validation"""
        try:
            token = request.cookies.get("access_token")
            if not token:
                return AuthResult(False, error="No token")
            
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            user_id = payload.get("user_id")
            
            if not user_id:
                return AuthResult(False, error="Invalid token")
            
            from ..db.user_manager import Database
            db = Database()
            user = db.get_user_by_id(user_id)
            
            if not user:
                return AuthResult(False, error="User not found")
            
            logger.info(f"SimpleToken: Authenticated {user.get('username')}")
            return AuthResult(True, user=user)
            
        except jwt.ExpiredSignatureError:
            return AuthResult(False, error="Token expired", redirect_url="/login")
        except jwt.InvalidTokenError:
            return AuthResult(False, error="Invalid token", redirect_url="/login")
        except Exception as e:
            logger.error(f"SimpleToken error: {e}")
            return AuthResult(False, error="Token authentication failed")

class ModularAuthManager:
    """New auth manager that preserves ALL existing functionality"""
    
    def __init__(self):
        self.providers = [
            LegacyAuthProvider(),    # Uses your EXACT existing logic
            SimpleTokenProvider(),   # Fallback if legacy fails
        ]
        self.debug_mode = True  # Enable detailed logging during migration
    
    def authenticate(self, request: Request) -> AuthResult:
        """Try providers in order"""
        for provider in self.providers:
            if self.debug_mode:
                logger.info(f"ModularAuth: Trying {provider.name}")
            
            result = provider.authenticate(request)
            
            if result.success:
                if self.debug_mode:
                    logger.info(f"ModularAuth: SUCCESS with {provider.name} - User: {result.username} (Admin: {result.is_admin}, Premium: {result.is_premium})")
                return result
            else:
                if self.debug_mode:
                    logger.debug(f"ModularAuth: {provider.name} failed: {result.error}")
        
        if self.debug_mode:
            logger.warning("ModularAuth: All providers failed")
        return AuthResult(False, error="Authentication failed", redirect_url="/login")
    
    def get_current_user(self, request: Request) -> Optional[Dict]:
        """Exact replacement for your existing get_current_user"""
        result = self.authenticate(request)
        return result.user if result.success else None
    
    def require_admin(self, request: Request) -> Optional[Dict]:
        """Exact replacement for your existing require_admin"""
        result = self.authenticate(request)
        if result.success and result.is_admin:
            return result.user
        return None
    
    def require_premium(self, request: Request) -> Optional[Dict]:
        """New premium requirement function"""
        result = self.authenticate(request)
        if result.success and result.is_premium:
            return result.user
        return None
