# ==============================================================================
# PREMIUM SYSTEM - COMPLETE IMPLEMENTATION
# File: app/routes/premium_routes.py
# ==============================================================================

import os
import uuid
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Request, HTTPException, Depends, Form
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import psycopg2
from psycopg2.extras import RealDictCursor

# MyAvatar imports
from app.db.database import execute_query
from app.logger.log_handler import log_info, log_error, log_warning
from app.services.auth_service import auth_service
from app.db.user_manager import Database

router = APIRouter()
security = HTTPBearer(auto_error=False)
db = Database()

# ==============================================================================
# PREMIUM SYSTEM MODELS
# ==============================================================================

class PremiumUser(BaseModel):
    id: int
    username: str
    email: str
    is_premium: bool
    premium_type: str  # 'trial', 'monthly', 'yearly', 'lifetime'
    premium_expires: Optional[datetime]
    trial_used: bool
    features_access: Dict[str, bool]

class PremiumSubscription(BaseModel):
    subscription_id: str
    user_id: int
    plan_type: str  # 'trial', 'monthly', 'yearly', 'lifetime'
    status: str  # 'active', 'cancelled', 'expired', 'pending'
    started_at: datetime
    expires_at: Optional[datetime]
    features: List[str]

class PremiumFeatureAccess(BaseModel):
    feature_name: str
    enabled: bool
    description: str
    premium_required: bool

# ==============================================================================
# PREMIUM FEATURES CONFIGURATION
# ==============================================================================

PREMIUM_FEATURES = {
    "backgroundfx": {
        "name": "BackgroundFX Studio",
        "description": "AI-powered background replacement with HeyGen WebM integration",
        "premium_required": True,
        "endpoints": ["/api/backgrounds/*", "/backgroundfx"]
    },
    "video_processing": {
        "name": "Advanced Video Processing",
        "description": "Professional background replacement with multiple AI models",
        "premium_required": True,
        "endpoints": ["/video-processing/*"]
    },
    "unlimited_videos": {
        "name": "Unlimited Video Generation",
        "description": "Generate unlimited videos without monthly limits",
        "premium_required": True,
        "endpoints": ["/api/videos/*"]
    },
    "priority_processing": {
        "name": "Priority Processing",
        "description": "Faster video processing with priority queue",
        "premium_required": True,
        "endpoints": []
    },
    "advanced_avatars": {
        "name": "Advanced Avatar Library",
        "description": "Access to premium avatar collection",
        "premium_required": True,
        "endpoints": ["/api/avatars/premium"]
    },
    "api_access": {
        "name": "API Access",
        "description": "Full API access for integrations",
        "premium_required": True,
        "endpoints": ["/api/*"]
    }
}

# ==============================================================================
# AUTHENTICATION & AUTHORIZATION
# ==============================================================================

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[Dict]:
    """Get current user from JWT token"""
    try:
        if not credentials:
            return None
        
        payload = auth_service.validate_token(credentials.credentials)
        if not payload:
            return None
            
        user_id = payload.get("user_id")
        if not user_id:
            return None
            
        return db.get_user_by_id(user_id)
        
    except Exception as e:
        log_error(f"Error validating user: {e}", "PremiumRoutes")
        return None

def get_admin_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[Dict]:
    """Get admin user from JWT token"""
    try:
        user = get_current_user(credentials)
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Check if user is admin
        if not user.get('is_admin') and user.get('username') != 'admin':
            raise HTTPException(status_code=403, detail="Admin access required")
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error validating admin user: {e}", "PremiumRoutes")
        raise HTTPException(status_code=500, detail="Admin validation failed")

def check_premium_access(user: Dict, feature: str) -> bool:
    """Check if user has premium access to a feature"""
    try:
        if not user:
            return False
        
        # Admin always has access
        if user.get('is_admin') or user.get('username') == 'admin':
            return True
        
        # Check if feature requires premium
        feature_config = PREMIUM_FEATURES.get(feature)
        if not feature_config or not feature_config.get('premium_required'):
            return True  # Feature is free
        
        # Check premium status
        premium_info = get_user_premium_status(user['id'])
        if not premium_info:
            return False
        
        return premium_info.get('is_premium', False)
        
    except Exception as e:
        log_error(f"Error checking premium access: {e}", "PremiumRoutes")
        return False

def get_user_premium_status(user_id: int) -> Optional[Dict]:
    """Get user's premium status from database"""
    try:
        user_premium = execute_query(
            """SELECT u.*, ps.plan_type, ps.status as subscription_status, 
                      ps.started_at, ps.expires_at, ps.features
               FROM users u
               LEFT JOIN premium_subscriptions ps ON u.id = ps.user_id 
                   AND ps.status = 'active'
               WHERE u.id = %s""",
            (user_id,),
            fetch_one=True
        )
        
        if not user_premium:
            return None
        
        user_dict = dict(user_premium)
        
        # Check if premium is still valid
        is_premium = False
        if user_dict.get('subscription_status') == 'active':
            expires_at = user_dict.get('expires_at')
            if expires_at:
                is_premium = expires_at > datetime.now()
            else:
                is_premium = True  # Lifetime subscription
        
        return {
            'user_id': user_id,
            'is_premium': is_premium,
            'premium_type': user_dict.get('plan_type'),
            'expires_at': user_dict.get('expires_at'),
            'trial_used': user_dict.get('trial_used', False),
            'features': json.loads(user_dict.get('features', '[]')) if user_dict.get('features') else []
        }
        
    except Exception as e:
        log_error(f"Error getting user premium status: {e}", "PremiumRoutes")
        return None

# ==============================================================================
# PREMIUM ACCESS DECORATOR
# ==============================================================================

def require_premium_feature(feature: str):
    """Decorator to require premium access for a feature"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Find user from kwargs
            user = kwargs.get('user')
            if not user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            # Check premium access
            if not check_premium_access(user, feature):
                premium_info = get_user_premium_status(user['id'])
                
                if not premium_info:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Premium subscription required for {feature}. Start your free trial!"
                    )
                
                if premium_info.get('is_premium'):
                    raise HTTPException(
                        status_code=403,
                        detail=f"Feature {feature} not included in your plan"
                    )
                else:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Premium subscription required for {feature}"
                    )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# ==============================================================================
# ADMIN ROUTES - PREMIUM MANAGEMENT
# ==============================================================================

@router.get("/admin/premium/users")
async def get_all_premium_users(admin_user: Dict = Depends(get_admin_user)):
    """Get all users with premium status"""
    try:
        users = execute_query(
            """SELECT u.id, u.username, u.email, u.created_at, u.is_admin,
                      ps.plan_type, ps.status, ps.started_at, ps.expires_at,
                      ps.features
               FROM users u
               LEFT JOIN premium_subscriptions ps ON u.id = ps.user_id
               ORDER BY u.created_at DESC""",
            fetch_all=True
        )
        
        user_list = []
        for user in users:
            user_dict = dict(user)
            
            # Check if premium is active
            is_premium = False
            if user_dict.get('status') == 'active':
                expires_at = user_dict.get('expires_at')
                if expires_at:
                    is_premium = expires_at > datetime.now()
                else:
                    is_premium = True  # Lifetime
            
            user_list.append({
                'id': user_dict['id'],
                'username': user_dict['username'],
                'email': user_dict['email'],
                'is_admin': user_dict.get('is_admin', False),
                'is_premium': is_premium,
                'premium_type': user_dict.get('plan_type'),
                'premium_status': user_dict.get('status'),
                'premium_expires': user_dict.get('expires_at'),
                'created_at': user_dict['created_at'],
                'features': json.loads(user_dict.get('features', '[]')) if user_dict.get('features') else []
            })
        
        return JSONResponse({
            "success": True,
            "users": user_list,
            "count": len(user_list)
        })
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting premium users: {e}", "PremiumRoutes")
        raise HTTPException(status_code=500, detail="Failed to get premium users")

@router.post("/admin/premium/set-user-premium")
async def set_user_premium(
    request: Request,
    admin_user: Dict = Depends(get_admin_user)
):
    """Set a user's premium status (Admin only)"""
    try:
        data = await request.json()
        user_id = data.get('user_id')
        plan_type = data.get('plan_type', 'monthly')  # 'trial', 'monthly', 'yearly', 'lifetime'
        duration_days = data.get('duration_days', 30)
        features = data.get('features', list(PREMIUM_FEATURES.keys()))
        
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID required")
        
        # Check if user exists
        user = execute_query(
            "SELECT * FROM users WHERE id = %s",
            (user_id,),
            fetch_one=True
        )
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Calculate expiration date
        expires_at = None
        if plan_type != 'lifetime':
            expires_at = datetime.now() + timedelta(days=duration_days)
        
        # Create or update premium subscription
        subscription_id = str(uuid.uuid4())
        
        # Remove existing active subscription
        execute_query(
            "UPDATE premium_subscriptions SET status = 'cancelled' WHERE user_id = %s AND status = 'active'",
            (user_id,)
        )
        
        # Add new subscription
        execute_query(
            """INSERT INTO premium_subscriptions 
               (subscription_id, user_id, plan_type, status, started_at, expires_at, features, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (subscription_id, user_id, plan_type, 'active', datetime.now(), 
             expires_at, json.dumps(features), datetime.now())
        )
        
        # Update user trial status if this is a trial
        if plan_type == 'trial':
            execute_query(
                "UPDATE users SET trial_used = true WHERE id = %s",
                (user_id,)
            )
        
        log_info(f"Admin {admin_user['username']} set user {user_id} to premium {plan_type}", "PremiumRoutes")
        
        return JSONResponse({
            "success": True,
            "message": f"User {user['username']} set to premium {plan_type}",
            "subscription_id": subscription_id,
            "plan_type": plan_type,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "features": features
        })
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error setting user premium: {e}", "PremiumRoutes")
        raise HTTPException(status_code=500, detail="Failed to set user premium")

@router.post("/admin/premium/remove-user-premium")
async def remove_user_premium(
    request: Request,
    admin_user: Dict = Depends(get_admin_user)
):
    """Remove a user's premium status (Admin only)"""
    try:
        data = await request.json()
        user_id = data.get('user_id')
        
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID required")
        
        # Cancel active subscriptions
        execute_query(
            "UPDATE premium_subscriptions SET status = 'cancelled' WHERE user_id = %s AND status = 'active'",
            (user_id,)
        )
        
        log_info(f"Admin {admin_user['username']} removed premium from user {user_id}", "PremiumRoutes")
        
        return JSONResponse({
            "success": True,
            "message": "Premium subscription cancelled"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error removing user premium: {e}", "PremiumRoutes")
        raise HTTPException(status_code=500, detail="Failed to remove user premium")

# ==============================================================================
# USER ROUTES - PREMIUM MANAGEMENT
# ==============================================================================

@router.get("/api/premium/status")
async def get_premium_status(user: Dict = Depends(get_current_user)):
    """Get current user's premium status"""
    try:
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        premium_info = get_user_premium_status(user['id'])
        
        if not premium_info:
            premium_info = {
                'user_id': user['id'],
                'is_premium': False,
                'premium_type': None,
                'expires_at': None,
                'trial_used': False,
                'features': []
            }
        
        # Add available features
        available_features = {}
        for feature_key, feature_config in PREMIUM_FEATURES.items():
            available_features[feature_key] = {
                'name': feature_config['name'],
                'description': feature_config['description'],
                'premium_required': feature_config['premium_required'],
                'user_has_access': not feature_config['premium_required'] or premium_info['is_premium']
            }
        
        return JSONResponse({
            "success": True,
            "premium_status": premium_info,
            "available_features": available_features
        })
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting premium status: {e}", "PremiumRoutes")
        raise HTTPException(status_code=500, detail="Failed to get premium status")

@router.post("/api/premium/start-trial")
async def start_premium_trial(user: Dict = Depends(get_current_user)):
    """Start 14-day premium trial"""
    try:
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Check if trial already used
        user_info = execute_query(
            "SELECT trial_used FROM users WHERE id = %s",
            (user['id'],),
            fetch_one=True
        )
        
        if user_info and user_info.get('trial_used'):
            raise HTTPException(status_code=400, detail="Trial already used")
        
        # Check if user already has premium
        premium_info = get_user_premium_status(user['id'])
        if premium_info and premium_info.get('is_premium'):
            raise HTTPException(status_code=400, detail="User already has premium subscription")
        
        # Start 14-day trial
        subscription_id = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(days=14)
        
        execute_query(
            """INSERT INTO premium_subscriptions 
               (subscription_id, user_id, plan_type, status, started_at, expires_at, features, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (subscription_id, user['id'], 'trial', 'active', datetime.now(), 
             expires_at, json.dumps(list(PREMIUM_FEATURES.keys())), datetime.now())
        )
        
        # Mark trial as used
        execute_query(
            "UPDATE users SET trial_used = true WHERE id = %s",
            (user['id'],)
        )
        
        log_info(f"User {user['username']} started premium trial", "PremiumRoutes")
        
        return JSONResponse({
            "success": True,
            "message": "14-day premium trial started!",
            "subscription_id": subscription_id,
            "expires_at": expires_at.isoformat(),
            "features": list(PREMIUM_FEATURES.keys())
        })
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error starting premium trial: {e}", "PremiumRoutes")
        raise HTTPException(status_code=500, detail="Failed to start premium trial")

@router.post("/api/premium/upgrade")
async def upgrade_to_premium(
    request: Request,
    user: Dict = Depends(get_current_user)
):
    """Upgrade to premium subscription (placeholder for payment integration)"""
    try:
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        data = await request.json()
        plan_type = data.get('plan_type', 'monthly')  # 'monthly', 'yearly'
        
        # This would integrate with payment processor (Stripe, PayPal, etc.)
        # For now, return placeholder response
        
        return JSONResponse({
            "success": True,
            "message": "Premium upgrade coming soon!",
            "plan_type": plan_type,
            "note": "This will integrate with payment processor",
            "features": {
                "monthly": {
                    "price": "$9.99/month",
                    "features": list(PREMIUM_FEATURES.keys())
                },
                "yearly": {
                    "price": "$99.99/year",
                    "features": list(PREMIUM_FEATURES.keys()),
                    "savings": "17% off"
                }
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error upgrading to premium: {e}", "PremiumRoutes")
        raise HTTPException(status_code=500, detail="Failed to upgrade to premium")

# ==============================================================================
# PREMIUM FEATURE ACCESS MIDDLEWARE
# ==============================================================================

@router.get("/api/premium/check-feature-access/{feature}")
async def check_feature_access(
    feature: str,
    user: Dict = Depends(get_current_user)
):
    """Check if user has access to a specific premium feature"""
    try:
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        has_access = check_premium_access(user, feature)
        feature_config = PREMIUM_FEATURES.get(feature)
        
        if not feature_config:
            raise HTTPException(status_code=404, detail="Feature not found")
        
        return JSONResponse({
            "success": True,
            "feature": feature,
            "has_access": has_access,
            "feature_info": feature_config,
            "premium_required": feature_config.get('premium_required', False)
        })
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error checking feature access: {e}", "PremiumRoutes")
        raise HTTPException(status_code=500, detail="Failed to check feature access")

# ==============================================================================
# DATABASE SCHEMA INITIALIZATION
# ==============================================================================

def initialize_premium_schema():
    """Initialize database tables for premium system"""
    try:
        # Create premium_subscriptions table
        execute_query("""
            CREATE TABLE IF NOT EXISTS premium_subscriptions (
                id SERIAL PRIMARY KEY,
                subscription_id VARCHAR(255) UNIQUE NOT NULL,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                plan_type VARCHAR(50) NOT NULL,
                status VARCHAR(50) DEFAULT 'active',
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                features TEXT,
                payment_method VARCHAR(50),
                payment_id VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Add premium-related columns to users table if they don't exist
        execute_query("""
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS trial_used BOOLEAN DEFAULT false
        """)
        
        # Create premium_features table for configuration
        execute_query("""
            CREATE TABLE IF NOT EXISTS premium_features (
                id SERIAL PRIMARY KEY,
                feature_key VARCHAR(100) UNIQUE NOT NULL,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                premium_required BOOLEAN DEFAULT true,
                enabled BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert default premium features
        for feature_key, feature_config in PREMIUM_FEATURES.items():
            execute_query("""
                INSERT INTO premium_features (feature_key, name, description, premium_required)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (feature_key) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    premium_required = EXCLUDED.premium_required
            """, (
                feature_key,
                feature_config['name'],
                feature_config['description'],
                feature_config['premium_required']
            ))
        
        log_info("Premium database schema initialized successfully", "PremiumRoutes")
        
    except Exception as e:
        log_error(f"Error initializing premium schema: {e}", "PremiumRoutes")

# Initialize schema when module loads
initialize_premium_schema()

# ==============================================================================
# EXPORT PREMIUM UTILITIES
# ==============================================================================

__all__ = [
    'router',
    'check_premium_access',
    'get_user_premium_status',
    'require_premium_feature',
    'PREMIUM_FEATURES'
]
