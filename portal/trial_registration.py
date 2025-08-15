# portal/trial_registration.py
"""
Trial Registration Enhancement for MyAvatar
Works alongside existing registration - ADDITIVE ONLY
"""

import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from .models import User
from .trial_management import trial_manager
from loguru import logger

def setup_trial_for_new_user(user_id: int, db: Session, avatar_gender: str = None) -> Dict[str, Any]:
    """
    ADDITIVE function to set up trial for newly registered users
    Call this AFTER existing user creation logic
    
    Args:
        user_id: User ID to set up trial for
        db: Database session
        avatar_gender: Optional gender preference for demo avatar ('male' or 'female')
    """
    try:
        logger.info(f"🎁 Setting up trial for new user {user_id}")
        
        # Use trial manager to set up trial dates
        result = trial_manager.create_trial_user(user_id, db)
        
        # Assign demo avatar to trial user
        avatar_result = trial_manager.assign_demo_avatar(user_id, db, avatar_gender)
        
        if result["success"]:
            logger.info(f"✅ Trial setup complete for user {user_id}")
            avatar_info = {}
            if avatar_result and avatar_result.get("success"):
                avatar_info = {
                    "avatar_id": avatar_result.get("avatar_id"),
                    "avatar_name": avatar_result.get("avatar_name"),
                    "avatar_gender": avatar_result.get("avatar_gender")
                }
            
            return {
                "success": True,
                "message": "Welcome to your 7-day free trial!",
                "trial_end": result["trial_end"],
                "days_remaining": result["days_remaining"],
                "demo_avatar": avatar_info
            }
        else:
            logger.error(f"❌ Trial setup failed for user {user_id}: {result['error']}")
            return {
                "success": False,
                "error": result["error"]
            }
            
    except Exception as e:
        logger.error(f"❌ Exception in trial setup: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def get_trial_welcome_message(user: User) -> str:
    """
    Generate welcome message for trial users
    """
    if user.account_type == "trial" and user.trial_end_date:
        days_remaining = (user.trial_end_date - datetime.date.today()).days
        if days_remaining > 0:
            return f"""
            🎉 Welcome to your 7-day MyAvatar trial!
            
            ✅ You have {days_remaining} days remaining
            ✅ Full access to demo avatar and distribution platform
            ✅ No credit card required
            
            Ready to create amazing content? Let's get started!
            """
    
    return "Welcome to MyAvatar!"

def check_trial_access_for_feature(user: User, feature: str) -> Dict[str, Any]:
    """
    Check if trial user can access specific features
    """
    # Non-trial users have full access
    if user.account_type != "trial":
        return {"allowed": True, "account_type": user.account_type}
    
    # Check if trial is still active
    if not trial_manager.is_trial_user_allowed(user):
        return {
            "allowed": False,
            "reason": "trial_expired",
            "message": "Your trial has expired. Please upgrade to continue using MyAvatar.",
            "upgrade_url": "/upgrade"
        }
    
    # Trial users can access specific features
    trial_allowed_features = [
        "demo_avatar",
        "video_creation_demo",
        "distribution_platform",
        "basic_analytics",
        "dashboard_view"
    ]
    
    # Features restricted to paid users
    premium_features = [
        "custom_avatar_creation",
        "unlimited_videos",
        "advanced_analytics",
        "premium_templates",
        "priority_support"
    ]
    
    if feature in trial_allowed_features:
        days_remaining = (user.trial_end_date - datetime.date.today()).days
        return {
            "allowed": True,
            "trial_user": True,
            "days_remaining": days_remaining,
            "message": f"Trial access - {days_remaining} days remaining"
        }
    
    if feature in premium_features:
        return {
            "allowed": False,
            "reason": "premium_feature",
            "message": "This feature requires a paid subscription. Upgrade to unlock!",
            "upgrade_url": "/upgrade"
        }
    
    # Default allow for unlisted features
    return {"allowed": True, "trial_user": True}

def get_trial_dashboard_banner(user: User) -> Optional[Dict[str, Any]]:
    """
    Generate dashboard banner for trial users
    """
    if user.account_type != "trial" or not user.trial_end_date:
        return None
    
    today = datetime.date.today()
    days_remaining = (user.trial_end_date - today).days
    
    if days_remaining < 0:
        return {
            "type": "error",
            "title": "Trial Expired",
            "message": "Your free trial has ended. Upgrade now to continue using MyAvatar!",
            "action_text": "Upgrade Now",
            "action_url": "/upgrade",
            "dismissible": False
        }
    
    if days_remaining <= 1:
        return {
            "type": "warning",
            "title": "Trial Ending Soon",
            "message": f"Your trial expires {'today' if days_remaining == 0 else 'tomorrow'}! Upgrade to keep your access.",
            "action_text": "Upgrade Now",
            "action_url": "/upgrade",
            "dismissible": False
        }
    
    if days_remaining <= 3:
        return {
            "type": "info",
            "title": f"{days_remaining} Days Left",
            "message": "Your trial is ending soon. Upgrade to unlock custom avatars and unlimited videos!",
            "action_text": "View Plans",
            "action_url": "/upgrade",
            "dismissible": True
        }
    
    return {
        "type": "success",
        "title": f"Free Trial - {days_remaining} Days Left",
        "message": "Enjoying MyAvatar? Upgrade anytime to unlock custom avatars and premium features!",
        "action_text": "View Plans",
        "action_url": "/upgrade",
        "dismissible": True
    }
