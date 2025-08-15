"""
Unified Authentication Service for MyAvatar
==========================================
Single source of truth for all authentication across the platform
"""

import logging
import os
from typing import Optional, Dict, Any
from fastapi import Request

# Import database and logging
from ..db.database import execute_query
from ..logger.log_handler import log_info, log_error, log_warning

logger = logging.getLogger("UnifiedAuthService")

class UnifiedAuthService:
    """
    Unified authentication service for all MyAvatar components
    
    Features:
    - Single authentication method across all routes
    - Consistent JWT validation
    - Standardized user data format
    - Centralized security checks
    """
    
    def __init__(self):
        self.jwt_secret = os.getenv("JWT_SECRET", "fallback-development-secret-key")
        self.jwt_algorithm = "HS256"
        
        # Import JWT library
        try:
            from jose import jwt
            self.jwt = jwt
        except ImportError:
            try:
                import jwt
                self.jwt = jwt
            except ImportError:
                log_error("No JWT library found - authentication will fail", "UnifiedAuthService")
                self.jwt = None
    
    def get_current_user(self, request: Request) -> Optional[Dict[str, Any]]:
        """
        Get current user with unified authentication logic
        This is the single source of truth for user authentication across the entire system
        """
        try:
            # Get token from cookies
            token = request.cookies.get("access_token")
            if not token:
                return None
            
            if not self.jwt:
                log_error("JWT library not available", "UnifiedAuthService")
                return None
            
            # Validate JWT token with expiry check
            try:
                payload = self.jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            except Exception as jwt_error:
                log_warning(f"JWT validation failed: {jwt_error}", "UnifiedAuthService")
                return None
            
            user_id = payload.get("user_id")
            if not user_id:
                log_warning("No user_id in JWT payload", "UnifiedAuthService")
                return None
            
            # Get fresh user data from database
            user = execute_query(
                "SELECT * FROM users WHERE id = %s",
                (user_id,),
                fetch_one=True
            )
            
            if not user:
                log_warning(f"User {user_id} not found in database", "UnifiedAuthService")
                return None
            
            # Convert to dict if needed
            if hasattr(user, '_asdict'):
                user_dict = user._asdict()
            else:
                user_dict = dict(user)
            
            log_info(f"User {user_dict.get('username')} authenticated successfully", "UnifiedAuthService")
            return user_dict
            
        except Exception as e:
            log_error(f"Authentication error: {e}", "UnifiedAuthService")
            return None
    
    def verify_token_from_header(self, auth_header: str) -> Optional[Dict[str, Any]]:
        """
        Verify JWT token from Authorization header for API calls
        """
        try:
            if not auth_header or not auth_header.startswith('Bearer '):
                return None
            
            token = auth_header.replace('Bearer ', '')
            
            if not self.jwt:
                return None
            
            try:
                payload = self.jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            except Exception:
                return None
            
            user_id = payload.get("user_id")
            if not user_id:
                return None
            
            # Get user from database
            user = execute_query(
                "SELECT * FROM users WHERE id = %s",
                (user_id,),
                fetch_one=True
            )
            
            if not user:
                return None
            
            # Convert to dict if needed
            if hasattr(user, '_asdict'):
                return user._asdict()
            else:
                return dict(user)
                
        except Exception as e:
            log_error(f"Header token verification error: {e}", "UnifiedAuthService")
            return None
    
    def require_authentication(self, request: Request) -> Dict[str, Any]:
        """
        Require authentication and return user or raise exception
        """
        user = self.get_current_user(request)
        if not user:
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="Authentication required")
        return user

# Global unified auth service instance
unified_auth_service = UnifiedAuthService()
