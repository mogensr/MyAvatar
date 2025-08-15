# ===============================================================================
# COMPATIBILITY LAYER - DROP-IN REPLACEMENTS FOR EXISTING FUNCTIONS
# ===============================================================================
# File: app/auth/compatibility.py

from typing import Optional, Dict
from fastapi import Request
import logging

from .auth_manager_v2 import ModularAuthManager

logger = logging.getLogger(__name__)

# Global instance for compatibility
_modular_auth_instance = ModularAuthManager()

def get_current_user_v2(request: Request) -> Optional[Dict]:
    """Drop-in replacement for existing get_current_user"""
    try:
        user = _modular_auth_instance.get_current_user(request)
        if user:
            logger.debug(f"compatibility.get_current_user_v2: Success - {user.get('username')}")
        else:
            logger.debug("compatibility.get_current_user_v2: No user found")
        return user
    except Exception as e:
        logger.error(f"compatibility.get_current_user_v2 error: {e}")
        return None

def require_admin_v2(request: Request) -> Optional[Dict]:
    """Drop-in replacement for existing require_admin"""
    try:
        admin_user = _modular_auth_instance.require_admin(request)
        if admin_user:
            logger.info(f"compatibility.require_admin_v2: Admin access granted - {admin_user.get('username')}")
        else:
            logger.debug("compatibility.require_admin_v2: Admin access denied")
        return admin_user
    except Exception as e:
        logger.error(f"compatibility.require_admin_v2 error: {e}")
        return None

def require_premium_v2(request: Request) -> Optional[Dict]:
    """New premium requirement function"""
    try:
        premium_user = _modular_auth_instance.require_premium(request)
        if premium_user:
            logger.info(f"compatibility.require_premium_v2: Premium access granted - {premium_user.get('username')}")
        else:
            logger.debug("compatibility.require_premium_v2: Premium access denied")
        return premium_user
    except Exception as e:
        logger.error(f"compatibility.require_premium_v2 error: {e}")
        return None

# Additional helper functions for gradual migration
def authenticate_user_v2(request: Request):
    """Get full authentication result with detailed info"""
    try:
        return _modular_auth_instance.authenticate(request)
    except Exception as e:
        logger.error(f"compatibility.authenticate_user_v2 error: {e}")
        from .auth_manager_v2 import AuthResult
        return AuthResult(False, error=str(e))

def is_admin_user_v2(request: Request) -> bool:
    """Check if current user is admin (returns boolean)"""
    try:
        result = _modular_auth_instance.authenticate(request)
        return result.success and result.is_admin
    except Exception as e:
        logger.error(f"compatibility.is_admin_user_v2 error: {e}")
        return False

def is_premium_user_v2(request: Request) -> bool:
    """Check if current user is premium (returns boolean)"""
    try:
        result = _modular_auth_instance.authenticate(request)
        return result.success and result.is_premium
    except Exception as e:
        logger.error(f"compatibility.is_premium_user_v2 error: {e}")
        return False

def get_user_permissions_v2(request: Request) -> Dict:
    """Get comprehensive user permissions info"""
    try:
        result = _modular_auth_instance.authenticate(request)
        return {
            "authenticated": result.success,
            "is_admin": result.is_admin,
            "is_premium": result.is_premium,
            "user_id": result.user_id,
            "username": result.username,
            "credits_remaining": result.credits_remaining,
            "error": result.error if not result.success else None
        }
    except Exception as e:
        logger.error(f"compatibility.get_user_permissions_v2 error: {e}")
        return {
            "authenticated": False,
            "is_admin": False,
            "is_premium": False,
            "user_id": None,
            "username": None,
            "credits_remaining": 0,
            "error": str(e)
        }
