# app/middleware/vacation_mode.py
import logging
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)

class VacationModeManager:
    """Manages vacation mode settings and restrictions"""
    
    def __init__(self):
        # Load initial settings from environment or defaults
        self.vacation_mode_enabled = os.getenv("VACATION_MODE", "true").lower() == "true"
        self.max_total_users = int(os.getenv("MAX_TOTAL_USERS", "300"))
        self.max_daily_registrations = int(os.getenv("MAX_DAILY_REGISTRATIONS", "30"))
        self.max_videos_per_user = int(os.getenv("MAX_VIDEOS_PER_USER", "7"))
        self.max_credits_per_user = int(os.getenv("MAX_CREDITS_PER_USER", "15"))
        self.emergency_stop = os.getenv("EMERGENCY_STOP", "false").lower() == "true"
        
        # Budget settings
        self.railway_budget = float(os.getenv("RAILWAY_BUDGET", "100.0"))
        self.heygen_budget = float(os.getenv("HEYGEN_BUDGET", "100.0"))
        self.total_budget = self.railway_budget + self.heygen_budget
        
        logger.info(f"🏖️ Vacation Mode Manager initialized: enabled={self.vacation_mode_enabled}")
    
    def toggle_vacation_mode(self, enabled: bool):
        """Toggle vacation mode on/off"""
        self.vacation_mode_enabled = enabled
        logger.info(f"🏖️ Vacation Mode {'ENABLED' if enabled else 'DISABLED'} by admin")
        return self.vacation_mode_enabled
    
    def set_user_limits(self, max_users: int, max_daily: int, max_videos: int):
        """Update user limits"""
        self.max_total_users = max_users
        self.max_daily_registrations = max_daily
        self.max_videos_per_user = max_videos
        logger.info(f"📊 User limits updated: {max_users} users, {max_daily}/day, {max_videos} videos/user")
    
    def set_emergency_stop(self, enabled: bool):
        """Enable/disable emergency stop"""
        self.emergency_stop = enabled
        logger.info(f"🚨 Emergency stop {'ENABLED' if enabled else 'DISABLED'}")
        return self.emergency_stop
    
    def get_settings(self) -> Dict[str, Any]:
        """Get current vacation mode settings"""
        return {
            "vacation_mode_enabled": self.vacation_mode_enabled,
            "emergency_stop": self.emergency_stop,
            "limits": {
                "max_total_users": self.max_total_users,
                "max_daily_registrations": self.max_daily_registrations,
                "max_videos_per_user": self.max_videos_per_user,
                "max_credits_per_user": self.max_credits_per_user
            },
            "budget": {
                "railway_budget": self.railway_budget,
                "heygen_budget": self.heygen_budget,
                "total_budget": self.total_budget
            }
        }

# Global instance
vacation_manager = VacationModeManager()

def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """Get current authenticated user from request - FIXED AUTH SERVICE METHOD"""
    try:
        # Get token from cookies
        token = request.cookies.get("access_token")
        if not token:
            return None
        
        # Import auth service and use the correct method
        from ..services.auth_service import auth_service
        
        # 🔧 FIXED: Use validate_token instead of decode_token
        # The auth_service doesn't have decode_token method!
        try:
            # First validate the session
            session = auth_service.validate_session(token, request)
            if not session:
                return None
            
            # Then validate the token payload
            payload = auth_service.validate_token(token)
            if not payload:
                return None
            
            user_id = payload.get("user_id")
            if not user_id:
                return None
                
        except AttributeError as auth_error:
            logger.error(f"Auth service method error: {auth_error}")
            # Fallback: try to decode JWT directly
            try:
                import jwt
                from ..config.settings import config
                payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
                user_id = payload.get("user_id")
                if not user_id:
                    return None
            except Exception as jwt_error:
                logger.error(f"JWT decode error: {jwt_error}")
                return None
        
        # Get full user info from database
        from ..db.user_manager import Database
        db = Database()
        user = db.get_user_by_id(user_id)
        
        return user
        
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        return None

def require_admin(request: Request) -> Optional[Dict[str, Any]]:
    """Check if current user is admin, return user data if yes"""
    try:
        user = get_current_user(request)
        if not user:
            return None
        
        if not user.get("is_admin", False):
            return None
        
        return user
        
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return None

def require_authenticated_user(request: Request) -> Optional[Dict[str, Any]]:
    """Check if user is authenticated, return user data if yes"""
    return get_current_user(request)

def check_vacation_mode_restrictions(action: str = "general") -> tuple[bool, Optional[str]]:
    """Check if action is allowed under current vacation mode settings"""
    
    # Check emergency stop first
    if vacation_manager.emergency_stop:
        return False, "🚧 MyAvatar is temporarily undergoing maintenance to improve our service. Please check back in a few hours!"
    
    # If vacation mode is disabled, allow everything
    if not vacation_manager.vacation_mode_enabled:
        return True, None
    
    # Check specific action restrictions
    if action == "registration":
        return check_registration_limits()
    elif action == "video_creation":
        return check_video_creation_limits()
    else:
        return True, None

def check_registration_limits() -> tuple[bool, Optional[str]]:
    """Check if new user registration is allowed"""
    try:
        from ..db.database import execute_query
        
        # Check total users
        total_users_result = execute_query("SELECT COUNT(*) as count FROM users", fetch_one=True)
        total_users = total_users_result.get('count', 0) if total_users_result else 0
        
        if total_users >= vacation_manager.max_total_users:
            return False, f"🎉 Incredible! MyAvatar has reached {vacation_manager.max_total_users} beta users! We're scaling up our infrastructure to handle the amazing demand. Please check back next week for expanded capacity!"
        
        # Check daily registrations
        today = datetime.now().date()
        daily_users_result = execute_query(
            "SELECT COUNT(*) as count FROM users WHERE DATE(created_at) = %s", 
            (today,), 
            fetch_one=True
        )
        daily_users = daily_users_result.get('count', 0) if daily_users_result else 0
        
        if daily_users >= vacation_manager.max_daily_registrations:
            return False, f"🔥 What an amazing day! We've had {vacation_manager.max_daily_registrations} new users join MyAvatar today! To ensure the best experience for everyone, we've reached our daily capacity. Please try again tomorrow!"
        
        return True, None
        
    except Exception as e:
        logger.error(f"Error checking registration limits: {e}")
        return False, "⚠️ Our systems are experiencing high demand right now. Please try again in a few minutes!"

def check_video_creation_limits(user_id: int = None) -> tuple[bool, Optional[str]]:
    """Check if video creation is allowed for user"""
    if not user_id:
        return True, None
    
    try:
        from ..db.database import execute_query
        
        user_videos_result = execute_query(
            "SELECT COUNT(*) as count FROM videos WHERE user_id = %s", 
            (user_id,), 
            fetch_one=True
        )
        user_videos = user_videos_result.get('count', 0) if user_videos_result else 0
        
        if user_videos >= vacation_manager.max_videos_per_user:
            return False, f"🎬 Wow! You've created {vacation_manager.max_videos_per_user} amazing videos! You're really exploring MyAvatar's capabilities. To ensure fair access during our beta phase, that's our current limit per user. We're working hard to increase these limits as we scale!"
        
        return True, None
        
    except Exception as e:
        logger.error(f"Error checking video limits: {e}")
        return False, "⚠️ Unable to check video limits right now. Please try again in a moment!"

def get_system_stats() -> Dict[str, Any]:
    """Get current system usage statistics"""
    try:
        from ..db.database import execute_query
        
        stats = {}
        
        # Total users
        total_users_result = execute_query("SELECT COUNT(*) as count FROM users", fetch_one=True)
        stats['total_users'] = total_users_result.get('count', 0) if total_users_result else 0
        
        # Total videos
        total_videos_result = execute_query("SELECT COUNT(*) as count FROM videos", fetch_one=True)
        stats['total_videos'] = total_videos_result.get('count', 0) if total_videos_result else 0
        
        # Today's registrations
        today = datetime.now().date()
        daily_users_result = execute_query(
            "SELECT COUNT(*) as count FROM users WHERE DATE(created_at) = %s", 
            (today,), 
            fetch_one=True
        )
        stats['daily_registrations'] = daily_users_result.get('count', 0) if daily_users_result else 0
        
        # Calculate percentages
        stats['users_percentage'] = round((stats['total_users'] / vacation_manager.max_total_users) * 100, 1)
        stats['daily_percentage'] = round((stats['daily_registrations'] / vacation_manager.max_daily_registrations) * 100, 1)
        
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

# =============================================================================
# COMPATIBILITY FUNCTIONS - For your existing auth_routes.py
# =============================================================================

def check_emergency_stop() -> tuple[bool, Optional[str]]:
    """Check if emergency stop is active - COMPATIBILITY FUNCTION"""
    if vacation_manager.emergency_stop:
        return True, "🚧 MyAvatar is temporarily undergoing maintenance to improve our service. Please check back in a few hours!"
    return False, None

def check_user_limits() -> tuple[bool, Optional[str]]:
    """Check user registration limits - COMPATIBILITY FUNCTION"""
    return check_registration_limits()

async def check_budget_limits() -> tuple[bool, Optional[str]]:
    """Check budget limits - COMPATIBILITY FUNCTION"""
    # For now, just return True - can be enhanced later
    return True, None

async def log_api_cost_event(service: str, endpoint: str, cost: float):
    """Log API cost event - COMPATIBILITY FUNCTION"""
    logger.info(f"💰 API Cost: {service} - {endpoint} - ${cost:.2f}")

# Admin control functions
def admin_toggle_vacation_mode(enabled: bool) -> Dict[str, Any]:
    """Admin function to toggle vacation mode"""
    result = vacation_manager.toggle_vacation_mode(enabled)
    return {
        "success": True,
        "vacation_mode_enabled": result,
        "message": f"Vacation mode {'enabled' if result else 'disabled'}"
    }

def admin_set_user_limits(max_users: int, max_daily: int, max_videos: int) -> Dict[str, Any]:
    """Admin function to update user limits"""
    vacation_manager.set_user_limits(max_users, max_daily, max_videos)
    return {
        "success": True,
        "limits": {
            "max_total_users": max_users,
            "max_daily_registrations": max_daily,
            "max_videos_per_user": max_videos
        },
        "message": "User limits updated successfully"
    }

def admin_emergency_stop(enabled: bool) -> Dict[str, Any]:
    """Admin function to enable/disable emergency stop"""
    result = vacation_manager.set_emergency_stop(enabled)
    return {
        "success": True,
        "emergency_stop": result,
        "message": f"Emergency stop {'enabled' if result else 'disabled'}"
    }

def admin_get_vacation_status() -> Dict[str, Any]:
    """Admin function to get current vacation mode status"""
    settings = vacation_manager.get_settings()
    stats = get_system_stats()
    
    return {
        "success": True,
        "settings": settings,
        "current_stats": stats,
        "timestamp": datetime.now().isoformat()
    }
