"""
MyAvatar - Complete AI Avatar Video Generation Platform
========================================================
FIXED VERSION: Added direct API endpoints to bypass router loading issues
"""
from fastapi import FastAPI, Request, HTTPException, Depends, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import logging
import traceback
import uuid
import threading
from datetime import datetime
from typing import Optional
from pathlib import Path
import sys
import json
import asyncio

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('myavatar.log', mode='a')
    ]
)
logger = logging.getLogger("MyAvatar")

# Emergency premium fix removed - was causing database schema errors

# FastAPI app
app = FastAPI(
    title="MyAvatar - AI Video Generation Platform",
    description="Complete AI Avatar Video Generation Platform with Premium Features",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Startup event - emergency fix removed
@app.on_event("startup")
async def startup_event():
    """App startup - emergency premium fix removed due to schema conflicts"""
    logger.info("🚀 MyAvatar startup complete - emergency fix disabled")

# CRITICAL FIX: Minimal health check endpoint - absolutely bulletproof
@app.get("/health")
def health_check():
    """Minimal health check endpoint for deployment"""
    return {"status": "ok"}

@app.get("/healthz")  
def health_check_alt():
    """Alternative health check endpoint"""
    return {"status": "ok"}

@app.get("/ping")
def ping():
    """Simple ping endpoint"""
    return {"ping": "pong"}

@app.get("/simple-health")
def simple_health():
    """Railway's expected health endpoint"""
    return {"status": "ok"}

@app.get("/debug/env")
def debug_env():
    """Debug endpoint to check environment variables"""
    return {
        "PORT": os.getenv("PORT", "not set"),
        "HOST": os.getenv("HOST", "not set"),
        "RAILWAY_ENVIRONMENT": os.getenv("RAILWAY_ENVIRONMENT", "not set"),
        "python_version": sys.version,
        "working_directory": os.getcwd()
    }

@app.get("/admin/fix-premium-urgent")
@app.post("/admin/fix-premium-urgent")
async def fix_premium_urgent():
    """URGENT: Fix MogensR premium status in production database"""
    try:
        from app.db.database import execute_query
        
        # Update user 3 (MogensR) to Premium
        execute_query(
            "UPDATE users SET subscription_type = 'Premium' WHERE id = 3",
            ()
        )
        
        # Verify the update
        user = execute_query(
            "SELECT id, username, subscription_type FROM users WHERE id = 3",
            (),
            fetch_one=True
        )
        
        if user and user.get('subscription_type') == 'Premium':
            return {
                "success": True,
                "message": f"✅ User {user.get('username')} (ID: {user.get('id')}) is now Premium",
                "user": dict(user)
            }
        else:
            return {
                "success": False,
                "message": "❌ Premium status update failed",
                "user": dict(user) if user else None
            }
            
    except Exception as e:
        return {
            "success": False,
            "message": f"❌ Error: {str(e)}"
        }

# CRITICAL FIX: Direct root route override - takes precedence over all router conflicts
@app.get("/", include_in_schema=False)
async def redirect_to_login():
    """Override root route to redirect to enhanced login page with MyAvatars.dk logo"""
    return RedirectResponse(url="/login", status_code=302)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Static files
try:
    static_dir = Path("static")
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory="static"), name="static")
        logger.info("✅ Static files mounted successfully")
    else:
        logger.warning("⚠️ Static directory not found")
except Exception as e:
    logger.error(f"❌ Error mounting static files: {e}")

# Templates
try:
    templates_dir = Path("templates")
    if templates_dir.exists():
        templates = Jinja2Templates(directory="templates")
        logger.info("✅ Templates configured successfully")
    else:
        logger.warning("⚠️ Templates directory not found")
        # Create fallback templates object
        templates = None
except Exception as e:
    logger.error(f"❌ Error configuring templates: {e}")
    templates = None

# Import database functions
try:
    from app.db.database import execute_query
    logger.info("✅ Database functions imported successfully")
except Exception as e:
    logger.error(f"❌ Error importing database functions: {e}")

# Import authentication functions
try:
    from app.routes.video_routes import get_current_user_fixed
    logger.info("✅ Authentication functions imported successfully")
except Exception as e:
    logger.error(f"❌ Error importing authentication functions: {e}")

# Import HeyGen integration
try:
    from app.api.heygen import create_video_from_audio_file
    HEYGEN_AVAILABLE = True
    logger.info("✅ HeyGen integration loaded successfully")
except ImportError as e:
    HEYGEN_AVAILABLE = False
    logger.error(f"❌ HeyGen integration not available: {e}")

# Import Cloudinary for audio upload
try:
    import cloudinary
    import cloudinary.uploader
    import cloudinary.api
    
    # Configure Cloudinary
    CLOUDINARY_URL = os.getenv("CLOUDINARY_URL")
    if CLOUDINARY_URL:
        cloudinary.config(cloudinary_url=CLOUDINARY_URL)
        logger.info("✅ Cloudinary configured successfully")
    else:
        logger.warning("⚠️ CLOUDINARY_URL not set")
        
except ImportError as e:
    logger.error(f"❌ Cloudinary not available: {e}")

# Import JWT for authentication
try:
    from jose import jwt
except ImportError:
    try:
        import jwt
    except ImportError:
        logger.error("❌ No JWT library found - authentication will fail")
        jwt = None

# Configuration
class Config:
    JWT_SECRET = os.getenv("JWT_SECRET", "fallback-development-secret-key")
    JWT_ALGORITHM = "HS256"

config = Config()

# =============================================================================
# DIRECT API ENDPOINTS (BYPASS ROUTER LOADING ISSUES)
# =============================================================================

def get_current_user_from_request(request: Request):
    """Get current user with proper JWT validation - PostgreSQL compatible"""
    try:
        token = request.cookies.get("access_token")
        if not token:
            return None
        
        if not jwt:
            return None
        
        # Validate JWT token with expiry check
        try:
            payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        except:
            return None
        
        user_id = payload.get("user_id")
        if not user_id:
            return None
        
        # Get fresh user data from database
        user = execute_query(
            "SELECT * FROM users WHERE id = %s",
            (user_id,),
            fetch_one=True
        )
        
        if not user:
            return None
            
        return user
        
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        return None

def verify_token_from_header(auth_header: str):
    """Verify JWT token from Authorization header for API calls"""
    try:
        if not auth_header or not auth_header.startswith('Bearer '):
            return None
        
        if not jwt:
            return None
        
        token = auth_header.replace('Bearer ', '')
        
        try:
            payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        except:
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
        
        return user
        
    except Exception as e:
        logger.error(f"Error verifying token from header: {e}")
        return None

# =============================================================================
# ENHANCED AVATAR MANAGEMENT SYSTEM WITH SELF-HEALING
# =============================================================================

import requests
from urllib.parse import urlparse
import re
from typing import List, Dict, Optional, Any

class AvatarManager:
    """Self-healing avatar management system"""
    
    def __init__(self):
        self.fallback_avatar = {
            'id': 'fallback',
            'name': 'Default Avatar',
            'avatar_image_url': '/static/images/default-avatar.jpg',
            'heygen_avatar_id': None,
            'is_default': True,
            'status': 'active'
        }
        self.avatar_cache = {}
    
    def validate_avatar_url(self, url: str) -> bool:
        """Validate if avatar URL is accessible"""
        if not url or url == 'None' or 'placeholder' in url.lower():
            return False
        
        try:
            # Check if URL is well-formed
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # Quick HEAD request to check if image exists
            response = requests.head(url, timeout=5, allow_redirects=True)
            return response.status_code == 200
        except:
            return False
    
    def sanitize_avatar_data(self, avatar: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize and validate avatar data"""
        if not avatar:
            return self.fallback_avatar.copy()
        
        # Convert tuple/row to dict if needed
        if hasattr(avatar, '_asdict'):
            avatar = avatar._asdict()
        elif isinstance(avatar, (tuple, list)):
            # Assume standard database column order
            keys = ['id', 'user_id', 'avatar_name', 'avatar_image_url', 'heygen_avatar_id', 
                   'created_at', 'is_default']
            avatar = dict(zip(keys, avatar))
        
        # Ensure required fields exist
        sanitized = {
            'id': avatar.get('id', 'unknown'),
            'name': avatar.get('avatar_name', 'Avatar'),  # Map avatar_name to name for template
            'avatar_image_url': avatar.get('avatar_image_url', ''),
            'heygen_avatar_id': avatar.get('heygen_avatar_id'),
            'is_default': bool(avatar.get('is_default', False)),
            'status': 'active'  # Default status
        }
        
        # Validate and fix avatar URL
        if not self.validate_avatar_url(sanitized['avatar_image_url']):
            logger.warning(f"Invalid avatar URL for {sanitized['name']}: {sanitized['avatar_image_url']}")
            
            # Try to get fresh URL from HeyGen if available
            if sanitized['heygen_avatar_id']:
                fresh_url = self.get_heygen_avatar_url(sanitized['heygen_avatar_id'])
                if fresh_url and self.validate_avatar_url(fresh_url):
                    sanitized['avatar_image_url'] = fresh_url
                    # Update database with fresh URL
                    self.update_avatar_url_in_db(sanitized['id'], fresh_url)
                else:
                    sanitized['avatar_image_url'] = self.fallback_avatar['avatar_image_url']
            else:
                sanitized['avatar_image_url'] = self.fallback_avatar['avatar_image_url']
        
        return sanitized
    
    def get_heygen_avatar_url(self, heygen_avatar_id: str) -> Optional[str]:
        """Get fresh avatar URL from HeyGen API"""
        try:
            # This would be your actual HeyGen API call
            # For now, return None to use fallback
            return None
        except Exception as e:
            logger.error(f"Error fetching HeyGen avatar URL: {e}")
            return None
    
    def update_avatar_url_in_db(self, avatar_id: str, new_url: str):
        """Update avatar URL in database"""
        try:
            execute_query(
                "UPDATE user_avatars SET avatar_image_url = %s, updated_at = NOW() WHERE id = %s",
                (new_url, avatar_id)
            )
            logger.info(f"Updated avatar {avatar_id} with fresh URL")
        except Exception as e:
            logger.error(f"Error updating avatar URL in database: {e}")
    
    def get_user_avatars_safe(self, user_id: int) -> List[Dict[str, Any]]:
        """Get user avatars with self-healing validation"""
        try:
            # Enhanced query with correct field names
            raw_avatars = execute_query(
                """
                SELECT id, user_id, avatar_name, avatar_image_url, heygen_avatar_id, 
                       created_at, is_default
                FROM user_avatars 
                WHERE user_id = %s 
                  AND (avatar_image_url IS NOT NULL AND avatar_image_url != '')
                  AND avatar_image_url NOT ILIKE '%%placeholder%%'
                  AND avatar_image_url NOT ILIKE '%%temp%%'
                ORDER BY is_default DESC, created_at DESC
                """,
                (user_id,),
                fetch_all=True
            )
            
            if not raw_avatars:
                logger.warning(f"No avatars found for user {user_id}")
                return [self.fallback_avatar.copy()]
            
            # Sanitize and validate each avatar
            validated_avatars = []
            for avatar in raw_avatars:
                sanitized = self.sanitize_avatar_data(avatar)
                validated_avatars.append(sanitized)
            
            # Ensure at least one avatar exists
            if not validated_avatars:
                validated_avatars = [self.fallback_avatar.copy()]
            
            logger.info(f"Retrieved {len(validated_avatars)} valid avatars for user {user_id}")
            return validated_avatars
            
        except Exception as e:
            logger.error(f"Error getting user avatars: {e}")
            return [self.fallback_avatar.copy()]

# Global avatar manager instance
avatar_manager = AvatarManager()
# UPDATED ROUTE IMPLEMENTATIONS WITH SELF-HEALING
# =============================================================================

@app.get("/text-to-video", response_class=HTMLResponse)
async def text_to_video_page(request: Request):
    """Text-to-Video creation page - RESTORED to fix HeyGen functionality"""
    try:
        user = get_current_user_from_request(request)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        user_id = int(user['id'])
        username = user.get('username', 'User')
        
        # Get avatars using self-healing avatar manager
        avatars = avatar_manager.get_user_avatars_safe(user_id)
        
        # Additional context for template
        context = {
            "request": request,
            "user": user,
            "username": username,
            "avatars": avatars,
            "user_id": user_id,
            "avatar_count": len(avatars),
            "has_custom_avatars": any(not avatar.get('is_default') for avatar in avatars)
        }
        
        if not templates:
            logger.error("❌ Templates not initialized")
            return RedirectResponse(url="/dashboard", status_code=302)
            
        return templates.TemplateResponse("text_video_component.html", context)
        
    except Exception as e:
        logger.error(f"❌ Error in text-to-video page: {e}")
        logger.error(traceback.format_exc())
        return RedirectResponse(url="/dashboard", status_code=302)

# REMOVED: /text-to-video route - handled by video_routes.py to avoid conflicts

@app.get("/api/test-main-routes")
async def test_main_routes():
    """Test if main routes are working"""
    return {
        "status": "working", 
        "message": "Main routes are working",
        "timestamp": datetime.now().isoformat()
    }

# REMOVED: /voice-to-video route moved back to video_routes.py to avoid conflicts
# This was causing router registration issues

# =============================================================================
# API ENDPOINTS FOR AVATAR MANAGEMENT
# =============================================================================

@app.get("/api/avatars/validate/{user_id}")
async def validate_user_avatars(user_id: int, request: Request):
    """API endpoint to validate and fix user avatars"""
    try:
        user = get_current_user_from_request(request)
        if not user or int(user['id']) != user_id:
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        avatars = avatar_manager.get_user_avatars_safe(user_id)
        
        return {
            "success": True,
            "avatar_count": len(avatars),
            "avatars": avatars,
            "message": f"Validated {len(avatars)} avatars"
        }
        
    except Exception as e:
        logger.error(f"Error validating avatars: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.post("/api/avatars/refresh/{user_id}")
async def refresh_user_avatars(user_id: int, request: Request):
    """API endpoint to refresh avatar URLs from HeyGen"""
    try:
        user = get_current_user_from_request(request)
        if not user or int(user['id']) != user_id:
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        # Clear cache and get fresh avatars
        avatar_manager.avatar_cache.pop(user_id, None)
        avatars = avatar_manager.get_user_avatars_safe(user_id)
        
        return {
            "success": True,
            "avatar_count": len(avatars),
            "message": f"Refreshed {len(avatars)} avatars"
        }
        
    except Exception as e:
        logger.error(f"Error refreshing avatars: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# =============================================================================
# ORIGINAL ROUTER LOADING SYSTEM (KEPT FOR OTHER FUNCTIONALITY)
# =============================================================================

# Import and mount routers with error handling
def load_router(module_path: str, router_name: str, prefix: str = "", description: str = ""):
    """Safely load and include routers"""
    try:
        module = __import__(module_path, fromlist=[router_name])
        router = getattr(module, router_name)
        
        if prefix:
            app.include_router(router, prefix=prefix)
            logger.info(f"✅ Router loaded: {description} -> {prefix}")
        else:
            app.include_router(router)
            logger.info(f"✅ Router loaded: {description}")
        
        return True
    except ImportError as e:
        logger.error(f"❌ Failed to import {module_path}: {e}")
        return False
    except AttributeError as e:
        logger.error(f"❌ Router {router_name} not found in {module_path}: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error loading router {description}: {e}")
        return False

# Track loaded routers
loaded_routers = []
router_errors = []

def try_load_router(module_path: str, router_name: str, prefix: str = "", description: str = ""):
    """Try to load a router and track success/failure"""
    try:
        if load_router(module_path, router_name, prefix, description):
            loaded_routers.append(description)
        else:
            router_errors.append(f"{description} ({module_path})")
    except Exception as e:
        logger.error(f"❌ Critical error loading router {description}: {e}")
        router_errors.append(f"{description} ({module_path}) - CRITICAL: {str(e)}")

# ============================================================================
# CORE ROUTERS - Load in order of importance
# ============================================================================

logger.info("🚀 Starting router loading process...")

# Authentication routes (highest priority)
try_load_router("app.routes.auth_routes", "router", "", "app.routes.auth_routes")

# Admin routes
try_load_router("app.routes.admin_routes", "router", "/admin", "app.routes.admin_routes -> /admin")

# Premium management routes (CRITICAL FIX for premium status sync)
try_load_router("app.routes.premium_management", "router", "/admin", "app.routes.premium_management -> /admin (Premium Management)")

# API routes
try_load_router("app.routes.api_routes", "router", "/api", "app.routes.api_routes -> /api")

# REMOVED: unified_video_routes - keeping existing proven architecture
# HeyGen videos: video_routes.py | Non-HeyGen videos: video_processing_routes.py

# Premium features
try_load_router("app.routes.premium_routes", "router", "", "app.routes.premium_routes")

# BackgroundFX routes
try_load_router("app.routes.backgroundfx_iframe", "router", "", "app.routes.backgroundfx_iframe (HF Space iframe Integration)")

# LeadGenEngine routes
try_load_router("app.routes.leadgen_iframe", "router", "", "app.routes.leadgen_iframe (Distribution Engine iframe Integration)")

# Social Media routes (LeadGenEngine Gradio UI)
try_load_router("app.routes.social_media_routes", "router", "", "app.routes.social_media_routes (Social Media Gradio Integration)")

# Host message routes (News from MyAvatar)
try_load_router("app.routes.host_routes", "router", "", "app.routes.host_routes (News from MyAvatar)")

# AI Assistant routes
{{ ... }}
try_load_router("app.routes.assistant_routes", "router", "", "app.routes.assistant_routes (AI Assistant)")

# Video routes (CRITICAL - contains voice-to-video and avatar APIs)
try_load_router("app.routes.video_routes", "router", "", "app.routes.video_routes (HeyGen video creation)")

# Video processing routes
try_load_router("app.routes.video_processing_routes", "router", "/video-processing", "app.routes.video_processing_routes -> /video-processing")

# Main web routes (should be loaded last to avoid conflicts)
try_load_router("app.routes.web_routes", "router", "", "app.routes.web_routes")

logger.info(f"🏁 Router loading complete. Loaded: {len(loaded_routers)}, Errors: {len(router_errors)}")

# =============================================================================
# HEALTH CHECK ENDPOINTS (RAILWAY REQUIREMENT)
# =============================================================================

@app.get("/simple-health")
@app.get("/health")
@app.get("/healthz")
async def health_check():
    """Health check endpoint for Railway deployment"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "MyAvatar",
        "version": "2.0.0"
    }

# =============================================================================
# VIDEOS PAGE ENDPOINT
# =============================================================================

@app.get("/videos", response_class=HTMLResponse)
async def videos_page(request: Request):
    """All Videos page - renders videos.html template"""
    try:
        # Get current user
        user = get_current_user_fixed(request)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        logger.info(f"🎬 VIDEOS PAGE - User {user.get('username')} accessing videos page")
        
        # Get user videos from database
        videos = execute_query(
            "SELECT * FROM videos WHERE user_id = %s ORDER BY created_at DESC",
            (int(user["id"]),),
            fetch_all=True
        )
        
        # Process videos for template
        processed_videos = []
        if videos:
            for video in videos:
                video_dict = dict(video)
                processed_videos.append({
                    'id': video_dict.get('id'),
                    'title': video_dict.get('title', 'Untitled Video'),
                    'status': video_dict.get('status', 'unknown'),
                    'created_at': video_dict.get('created_at'),
                    'video_path': video_dict.get('video_path'),
                    'audio_path': video_dict.get('audio_path'),
                    'thumbnail_url': video_dict.get('thumbnail_url'),
                    'duration': video_dict.get('duration'),
                    'description': video_dict.get('description'),
                    'format': video_dict.get('format', '16:9')
                })
        
        # Template context
        context = {
            "request": request,
            "user": user,
            "username": user.get("username", "User"),
            "is_admin": user.get("is_admin", False),
            "user_id": user["id"],
            "videos": processed_videos,
            "total_videos": len(processed_videos),
            "user_avatars": [],
            "avatar_count": 0,
            "credits_remaining": user.get("credits_remaining", 0),
            "max_credits": user.get("max_credits", 100),
            "max_videos_per_user": 7,
            "user_video_count": len(processed_videos),
            "vacation_mode": False,
            "video_limit_reached": False
        }
        
        logger.info(f"🎬 VIDEOS PAGE: Rendering videos.html with {len(processed_videos)} videos")
        return templates.TemplateResponse("videos.html", context)
        
    except Exception as e:
        logger.error(f"❌ Error in videos page: {e}")
        return RedirectResponse(url="/dashboard", status_code=302)

# =============================================================================
# ROOT ENDPOINT
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint - redirects to main application"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>MyAvatar - AI Video Platform</title>
        <meta http-equiv="refresh" content="0; url=/dashboard">
        <style>
            body { font-family: system-ui; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #f5f5f5; }
            .container { text-align: center; background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
            .logo { font-size: 3rem; margin-bottom: 1rem; }
            .title { font-size: 2rem; color: #333; margin-bottom: 0.5rem; }
            .subtitle { color: #666; margin-bottom: 2rem; }
            .loading { color: #6366f1; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">🎭</div>
            <h1 class="title">MyAvatar</h1>
            <p class="subtitle">AI Video Generation Platform</p>
            <p class="loading">Redirecting to dashboard...</p>
            <script>
                setTimeout(() => window.location.href = '/dashboard', 100);
            </script>
        </div>
    </body>
    </html>
    """

# =============================================================================
# STARTUP VALIDATION
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Validate system on startup"""
    logger.info("🚀 MyAvatar starting up...")
    
    # Ensure static directory exists for fallback avatar
    static_dir = Path("static/images")
    static_dir.mkdir(parents=True, exist_ok=True)
    
    # Create default avatar image if it doesn't exist
    default_avatar_path = static_dir / "default-avatar.jpg"
    if not default_avatar_path.exists():
        # Create a simple placeholder image or copy from assets
        logger.warning("⚠️ Default avatar image not found - create static/images/default-avatar.jpg")
    
    logger.info("✅ MyAvatar startup complete")

# =============================================================================
# CLAUDE'S AVATAR DEBUG ENDPOINT
# =============================================================================

@app.get("/api/debug/avatar-data/{user_id}")
async def debug_avatar_data(request: Request, user_id: int):
    """Debug avatar data to find the exact issue"""
    try:
        user = get_current_user_from_request(request)
        if not user:
            return {"error": "Not authenticated"}
        
        # Test 1: Check table structure
        table_structure = execute_query(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'user_avatars'
            ORDER BY ordinal_position
            """,
            fetch_all=True
        )
        
        # Test 2: Get ALL avatars for user (no filters)
        all_avatars = execute_query(
            "SELECT * FROM user_avatars WHERE user_id = %s",
            (user_id,),
            fetch_all=True
        )
        
        # Test 3: Try different column name variations
        queries_to_try = [
            ("Current Query", "SELECT id, avatar_name, avatar_image_url, heygen_avatar_id FROM user_avatars WHERE user_id = %s"),
            ("Name Column", "SELECT id, name, avatar_image_url, heygen_avatar_id FROM user_avatars WHERE user_id = %s"),
            ("Image URL Column", "SELECT id, name, image_url, heygen_avatar_id FROM user_avatars WHERE user_id = %s"),
            ("Simple All", "SELECT * FROM user_avatars WHERE user_id = %s")
        ]
        
        query_results = {}
        for query_name, query in queries_to_try:
            try:
                result = execute_query(query, (user_id,), fetch_all=True)
                query_results[query_name] = {
                    "success": True,
                    "count": len(result) if result else 0,
                    "data": [dict(row) for row in result] if result else []
                }
            except Exception as e:
                query_results[query_name] = {
                    "success": False,
                    "error": str(e)
                }
        
        # Convert all_avatars to serializable format
        serialized_avatars = []
        if all_avatars:
            for avatar in all_avatars:
                avatar_dict = dict(avatar)
                # Convert datetime objects to strings
                for key, value in avatar_dict.items():
                    if hasattr(value, 'isoformat'):
                        avatar_dict[key] = value.isoformat()
                serialized_avatars.append(avatar_dict)
        
        return {
            "success": True,
            "user_id": user_id,
            "table_structure": [dict(col) for col in table_structure] if table_structure else [],
            "total_avatars": len(serialized_avatars),
            "all_avatars": serialized_avatars,
            "query_tests": query_results,
            "recommendations": {
                "if_no_avatars": "User has no avatars in database - need to create some",
                "if_wrong_columns": "Check query_tests to see which column names work",
                "if_broken_urls": "Check avatar_image_url values for validity"
            }
        }
        
    except Exception as e:
        return {"success": False, "error": str(e), "user_id": user_id}

# =============================================================================
# CLAUDE'S BACKUP WORKING ROUTE
# =============================================================================

@app.get("/voice-to-video-working")
async def voice_to_video_working(request: Request):
    """Working voice-to-video page - added directly to main.py"""
    try:
        user = get_current_user_from_request(request)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        user_id = int(user['id'])
        
        # Get avatars using the correct column name
        avatars = execute_query(
            "SELECT id, name, avatar_image_url, heygen_avatar_id, is_default FROM user_avatars WHERE user_id = %s ORDER BY created_at DESC",
            (user_id,),
            fetch_all=True
        )
        
        # Process avatars
        processed_avatars = []
        if avatars:
            for avatar in avatars:
                avatar_dict = dict(avatar)
                processed_avatars.append({
                    'id': avatar_dict.get('id'),
                    'name': avatar_dict.get('name', 'Avatar'),
                    'avatar_image_url': avatar_dict.get('avatar_image_url', '/static/images/default-avatar.jpg'),
                    'heygen_avatar_id': avatar_dict.get('heygen_avatar_id', ''),
                    'is_default': bool(avatar_dict.get('is_default', False))
                })
        
        return templates.TemplateResponse("voice_recording.html", {
            "request": request,
            "user": user,
            "user_id": user_id,
            "username": user.get("username", "User"),
            "avatars": processed_avatars,
            "avatar_count": len(processed_avatars),
            "debug_info": {
                "backend_status": "main_py_route_working",
                "raw_avatar_count": len(avatars) if avatars else 0,
                "processed_avatar_count": len(processed_avatars),
                "avatar_loading_log": [
                    f"Found {len(avatars)} raw avatars",
                    f"Processed {len(processed_avatars)} avatars",
                    "Using main.py backup route",
                    "Direct route working"
                ]
            }
        })
        
    except Exception as e:
        return RedirectResponse(url="/dashboard", status_code=302)

# =============================================================================
# NEW CLEAN VOICE-TO-VIDEO SYSTEM
# =============================================================================

@app.get("/voice-video-clean", response_class=HTMLResponse)
async def voice_video_clean_page(request: Request):
    """Clean voice-to-video page - completely new implementation"""
    try:
        user = get_current_user_from_request(request)
        if not user:
            return RedirectResponse(url="/login", status_code=303)
        
        # Get user avatars with correct field mapping
        user_avatars = execute_query(
            """
            SELECT id, avatar_name as name, avatar_image_url, heygen_avatar_id
            FROM user_avatars 
            WHERE user_id = %s 
              AND avatar_image_url IS NOT NULL 
              AND avatar_image_url != ''
              AND avatar_image_url NOT ILIKE '%placeholder%'
            ORDER BY is_default DESC, created_at DESC
            """,
            (user["id"],),
            fetch_all=True
        )
        
        # Ensure we have at least one avatar
        if not user_avatars:
            user_avatars = [{
                "id": "default",
                "name": "Default Avatar",
                "avatar_image_url": "/static/images/default-avatar.jpg",
                "heygen_avatar_id": None
            }]
        
        return templates.TemplateResponse("voice_video_clean.html", {
            "request": request,
            "user": user,
            "user_avatars": user_avatars,
            "user_id": user["id"]
        })
        
    except Exception as e:
        logger.error(f"Error loading clean voice video page: {e}")
        return RedirectResponse(url="/dashboard", status_code=303)

# =============================================================================
# ROOT ROUTE - REDIRECT TO LOGIN
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def root_redirect(request: Request):
    """Root page redirects to enhanced login page with MyAvatars.dk logo"""
    # Force redirect to login page to show enhanced login with logo
    return RedirectResponse(url="/login", status_code=302)

# Distribution route removed - using Dashboard widgets instead

# =============================================================================
# SMS TEST ENDPOINT - Test SMS functionality in production
# =============================================================================

@app.get("/admin/test-sms")
async def admin_test_sms(request: Request):
    """Test SMS functionality in production environment"""
    try:
        # Check credentials
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        from_number = os.getenv('TWILIO_PHONE_NUMBER')
        
        credentials_status = {
            "TWILIO_ACCOUNT_SID": "SET" if account_sid else "MISSING",
            "TWILIO_AUTH_TOKEN": "SET" if auth_token else "MISSING", 
            "TWILIO_PHONE_NUMBER": from_number if from_number else "MISSING"
        }
        
        if not all([account_sid, auth_token, from_number]):
            return JSONResponse({
                "success": False,
                "error": "Missing Twilio credentials",
                "credentials": credentials_status
            })
        
        # Test SMS send
        try:
            from twilio.rest import Client
            
            client = Client(account_sid, auth_token)
            
            # Send test SMS to Mogens
            message = client.messages.create(
                body="🧪 TEST: MyAvatar SMS system is working! This is a production test from Railway.",
                from_=from_number,
                to="+4530604639"  # Mogens' number
            )
            
            logger.info(f"✅ SMS test sent successfully: {message.sid}")
            
            return JSONResponse({
                "success": True,
                "message": "SMS sent successfully!",
                "credentials": credentials_status,
                "sms_details": {
                    "sid": message.sid,
                    "to": message.to,
                    "from": message.from_,
                    "status": message.status
                }
            })
            
        except Exception as sms_error:
            logger.error(f"❌ SMS send failed: {sms_error}")
            return JSONResponse({
                "success": False,
                "error": f"SMS send failed: {str(sms_error)}",
                "credentials": credentials_status
            })
            
    except Exception as e:
        logger.error(f"❌ SMS test error: {e}")
        return JSONResponse({
            "success": False,
            "error": f"SMS test failed: {str(e)}"
        })

@app.post("/api/voice-video/create")
async def create_voice_video_complete(request: Request):
    """Complete voice video creation with HeyGen integration"""
    try:
        # Get current user
        user = get_current_user_from_request(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
        
        # Get form data
        form_data = await request.form()
        
        # Extract data
        audio_file = form_data.get("audio")
        avatar_id = form_data.get("avatar_id", "").strip()
        heygen_avatar_id = form_data.get("heygen_avatar_id", "").strip()
        title = form_data.get("title", "Voice Video").strip()
        video_format = form_data.get("format", "16:9").strip()
        
        user_id = int(user["id"])
        
        # Log the request
        logger.info(f"🎬 Voice video request from user {user_id}")
        logger.info(f"📝 Title: {title}")
        logger.info(f"🎭 Avatar ID: {avatar_id}")
        logger.info(f"🎯 HeyGen ID: {heygen_avatar_id}")
        logger.info(f"🎵 Audio file: {audio_file.filename if audio_file else 'None'}")
        logger.info(f"📐 Format: {video_format}")
        
        # Validate inputs
        if not audio_file:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Audio file is required"}
            )
        
        # Get the actual HeyGen avatar ID from database (same fix as text-to-video)
        if heygen_avatar_id:
            final_avatar_id = heygen_avatar_id
        elif avatar_id:
            # Convert database avatar ID to HeyGen avatar ID
            avatar_result = execute_query(
                """
                SELECT COALESCE(heygen_avatar_id, avatar_id) as heygen_id
                FROM user_avatars 
                WHERE id = %s AND user_id = %s
                """,
                (avatar_id, user_id),
                fetch_one=True
            )
            
            if not avatar_result:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "error": "Avatar not found"}
                )
            
            final_avatar_id = avatar_result['heygen_id']
        else:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Avatar selection is required"}
            )
        
        logger.info(f"🎯 Using HeyGen avatar ID: {final_avatar_id}")
        
        # Read audio data
        audio_content = await audio_file.read()
        audio_size_mb = len(audio_content) / (1024 * 1024)
        
        logger.info(f"📊 Audio file size: {audio_size_mb:.2f} MB")
        
        if len(audio_content) == 0:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Audio file is empty"}
            )
        
        if audio_size_mb > 50:  # 50MB limit
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Audio file too large (max 50MB)"}
            )
        
        # Step 1: Upload audio to Cloudinary to get public URL
        logger.info("☁️ Uploading audio to Cloudinary...")
        
        try:
            # Generate unique filename
            import time
            audio_filename = f"voice_audio_{user_id}_{int(time.time())}.webm"
            
            # Upload to Cloudinary
            cloudinary_result = cloudinary.uploader.upload(
                audio_content,
                public_id=f"myavatar/voice_audio/{audio_filename}",
                resource_type="video",  # Use "video" for audio files
                format="webm"
            )
            
            public_audio_url = cloudinary_result.get("secure_url")
            if not public_audio_url:
                raise Exception("Failed to get public URL from Cloudinary")
            
            logger.info(f"✅ Audio uploaded to Cloudinary: {public_audio_url}")
            
        except Exception as upload_error:
            logger.error(f"❌ Cloudinary upload failed: {upload_error}")
            return JSONResponse(
                status_code=500,
                content={
                    "success": False, 
                    "error": f"Failed to upload audio: {str(upload_error)}"
                }
            )
        
        # Step 2: Create video record in database (initially processing)
        logger.info("💾 Creating video record in database...")
        
        try:
            video_record = execute_query(
                """
                INSERT INTO videos (user_id, title, status, video_path, audio_path, avatar_id, created_at, format)
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s)
                RETURNING id
                """,
                (
                    user_id,
                    title,
                    "processing",
                    "",  # Will be updated when HeyGen completes
                    public_audio_url,  # Store Cloudinary audio URL
                    final_avatar_id,
                    video_format
                ),
                fetch_one=True
            )
            
            if not video_record:
                raise Exception("Failed to create video record")
            
            video_id = video_record['id']
            logger.info(f"✅ Created video record with ID: {video_id}")
            
        except Exception as db_error:
            logger.error(f"❌ Database error: {db_error}")
            return JSONResponse(
                status_code=500,
                content={
                    "success": False, 
                    "error": f"Database error: {str(db_error)}"
                }
            )
        
        # Step 3: Call HeyGen API to create video
        logger.info("🎯 Calling HeyGen API to create video...")
        
        try:
            # Get HeyGen API key
            heygen_api_key = os.getenv('HEYGEN_API_KEY')
            if not heygen_api_key:
                raise Exception("HeyGen API key not configured")
            
            # Call HeyGen API
            heygen_result = create_video_from_audio_file(
                api_key=heygen_api_key,
                avatar_id=final_avatar_id,
                audio_url=public_audio_url,
                video_format=video_format
            )
            
            logger.info(f"📥 HeyGen API result: {heygen_result}")
            
            if not heygen_result.get('success'):
                raise Exception(f"HeyGen API failed: {heygen_result.get('error', 'Unknown error')}")
            
            heygen_video_id = heygen_result.get('video_id')
            if not heygen_video_id:
                raise Exception("HeyGen API did not return video ID")
            
            logger.info(f"✅ HeyGen video created with ID: {heygen_video_id}")
            
            # Step 4: Update database record with HeyGen video ID
            execute_query(
                """
                UPDATE videos 
                SET heygen_video_id = %s, status = %s
                WHERE id = %s
                """,
                (heygen_video_id, "heygen_processing", video_id)
            )
            
            logger.info(f"✅ Updated video record {video_id} with HeyGen ID")
            logger.info(f"🔔 HeyGen will call webhook when video {video_id} completes: /api/heygen/webhook")
            
            # Return success response
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Voice video creation started successfully!",
                    "video_id": video_id,
                    "heygen_video_id": heygen_video_id,
                    "status": "heygen_processing",
                    "title": title,
                    "avatar_id": final_avatar_id,
                    "audio_url": public_audio_url,
                    "estimated_time": "3-7 minutes",
                    "next_steps": "Video is being processed by HeyGen. Status will be automatically updated when ready.",
                    "polling_enabled": True
                }
            )
            
        except Exception as heygen_error:
            logger.error(f"❌ HeyGen API error: {heygen_error}")
            
            # Update database to reflect failure
            execute_query(
                """
                UPDATE videos 
                SET status = %s, video_path = %s
                WHERE id = %s
                """,
                ("failed", f"HeyGen error: {str(heygen_error)}", video_id)
            )
            
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": f"HeyGen video creation failed: {str(heygen_error)}",
                    "video_id": video_id,
                    "audio_uploaded": True,
                    "audio_url": public_audio_url
                }
            )
        
    except Exception as e:
        logger.error(f"❌ Unexpected error in voice video creation: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False, 
                "error": f"Internal server error: {str(e)}"
            }
        )

# Also add the alternative endpoint for compatibility
@app.post("/api/create-voice-video")
async def create_voice_video_alias(request: Request):
    """Alias for voice video creation - redirects to main endpoint"""
    return await create_voice_video_complete(request)

# =============================================================================
# LOAD DISTRIBUTION ROUTES
# =============================================================================

# Load API routes for processing status and other API endpoints
try:
    from app.routes.api_routes import router as api_router
    app.include_router(api_router)
    logger.info("✅ API routes loaded successfully")
except Exception as e:
    logger.error(f"❌ Failed to load API routes: {e}")

# Distribution routes removed - using Dashboard widgets instead
            logger.info("✅ Voice updater service started successfully")
        else:
            logger.warning("⚠️ Voice updater service failed to start")
    except Exception as e:
        logger.error(f"❌ Failed to start voice updater service: {e}")
        import traceback
        traceback.print_exc()
    
    # Start video polling service for HeyGen video status checking
    try:
        from app.services.video_polling_service import video_polling_service
        video_polling_service.start_polling()
        logger.info("✅ Video polling service started successfully - checking every 5 minutes")
    except Exception as e:
        logger.error(f"❌ Failed to start video polling service: {e}")
        import traceback
        traceback.print_exc()
    
    # Start video completion notifier service for SMS/email notifications
    try:
        from app.services.video_completion_notifier import video_completion_notifier
        video_completion_notifier.start()
        logger.info("✅ Video completion notifier started successfully - monitoring for completed videos")
    except Exception as e:
        logger.error(f"❌ Failed to start video completion notifier: {e}")
        import traceback
        traceback.print_exc()
except Exception as e:
    logger.error(f"❌ Failed to load distribution routes: {e}")
    
    # All distribution functionality removed - using Dashboard widgets

# =============================================================================
# LINKEDIN OAUTH & DISTRIBUTION ENDPOINTS - PROFESSIONAL MARKETING SUITE
# =============================================================================

# Import DistributionEngine client
try:
    from distribution_engine_client import distribution_client
    logger.info("✅ DistributionEngine client initialized")
    
except ImportError as e:
    logger.error(f"❌ Failed to import DistributionEngine client: {e}")
    distribution_client = None

@app.get("/linkedin-distribution", response_class=HTMLResponse)
async def linkedin_distribution_page(request: Request):
    """LinkedIn Distribution MVP - Select videos and post to LinkedIn"""
    try:
        user = get_current_user_from_request(request)
        if not user:
            return RedirectResponse(url="/login?next=/linkedin-distribution", status_code=302)
        
        user_id = int(user['id'])
        username = user.get('username', 'User')
        
        # Get user's completed videos for distribution
        videos = execute_query(
            "SELECT id, title, video_path, created_at, status FROM videos WHERE user_id = ? AND status = 'completed' ORDER BY created_at DESC",
            (user_id,)
        )
        
        if not videos:
            videos = []
        
        if not templates:
            logger.error("❌ Templates not initialized")
            return RedirectResponse(url="/dashboard", status_code=302)
            
        return templates.TemplateResponse("linkedin_distribution.html", {
            "request": request,
            "user": user,
            "username": username,
            "videos": videos,
            "total_videos": len(videos)
        })
        
    except Exception as e:
        logger.error(f"❌ Error in LinkedIn distribution: {e}")
        return RedirectResponse(url="/dashboard", status_code=302)

@app.post("/api/linkedin/connect")
async def linkedin_connect(request: Request):
    """Connect user's LinkedIn account via DistributionEngine"""
    try:
        user = get_current_user_from_request(request)
        if not user:
            return JSONResponse({"error": "Authentication required"}, status_code=401)
        
        if not distribution_client:
            return JSONResponse({"error": "DistributionEngine unavailable"}, status_code=503)
        
        # Generate LinkedIn OAuth URL via DistributionEngine
        result = distribution_client.connect_platform(
            user_id=str(user['id']),
            platform="linkedin",
            redirect_url="https://app.myavatar.dk/linkedin-distribution"
        )
        
        if result["success"]:
            data = result["data"]
            return JSONResponse({
                "success": True,
                "message": "LinkedIn OAuth URL generated",
                "auth_url": data.get("auth_url"),
                "state": data.get("state")
            })
        else:
            return JSONResponse({
                "success": False,
                "error": result.get("error", "Unknown error")
            }, status_code=500)
        
    except Exception as e:
        logger.error(f"❌ LinkedIn connect error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/auth/linkedin/callback")
async def linkedin_oauth_callback(request: Request):
    """Handle LinkedIn OAuth callback"""
    try:
        # Get query parameters
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        error = request.query_params.get("error")
        
        if error:
            logger.error(f"❌ LinkedIn OAuth error: {error}")
            return RedirectResponse(url="/linkedin-distribution?error=oauth_denied", status_code=302)
        
        if not code or not state:
            return RedirectResponse(url="/linkedin-distribution?error=invalid_callback", status_code=302)
        
        if not linkedin_service:
            return RedirectResponse(url="/linkedin-distribution?error=service_unavailable", status_code=302)
        
        # Extract user ID from state
        try:
            user_id = int(state.split("_")[0])
        except (ValueError, IndexError):
            return RedirectResponse(url="/linkedin-distribution?error=invalid_state", status_code=302)
        
        # Exchange code for token
        token_result = linkedin_service.exchange_code_for_token(code, state)
        
        if token_result["success"]:
            # Save connection to database
            if linkedin_db:
                connection_id = linkedin_db.save_linkedin_connection(
                    user_id, 
                    token_result, 
                    token_result["profile"]
                )
                
                if connection_id:
                    logger.info(f"✅ LinkedIn connected successfully for user {user_id}")
                    return RedirectResponse(url="/linkedin-distribution?success=connected", status_code=302)
                else:
                    return RedirectResponse(url="/linkedin-distribution?error=save_failed", status_code=302)
            else:
                return RedirectResponse(url="/linkedin-distribution?error=database_unavailable", status_code=302)
        else:
            logger.error(f"❌ LinkedIn token exchange failed: {token_result['error']}")
            return RedirectResponse(url="/linkedin-distribution?error=token_exchange_failed", status_code=302)
        
    except Exception as e:
        logger.error(f"❌ LinkedIn callback error: {e}")
        return RedirectResponse(url="/linkedin-distribution?error=callback_error", status_code=302)

@app.post("/api/linkedin/disconnect")
async def linkedin_disconnect(request: Request):
    """Disconnect user's LinkedIn account"""
    try:
        user = get_current_user_from_request(request)
        if not user:
            return JSONResponse({"error": "Authentication required"}, status_code=401)
        
        if not linkedin_db:
            return JSONResponse({"error": "Database service unavailable"}, status_code=503)
        
        # Disconnect LinkedIn account
        success = linkedin_db.disconnect_linkedin(user['id'])
        
        if success:
            return JSONResponse({
                "success": True,
                "message": "LinkedIn account disconnected successfully"
            })
        else:
            return JSONResponse({
                "success": False,
                "error": "Failed to disconnect LinkedIn account"
            }, status_code=500)
        
    except Exception as e:
        logger.error(f"❌ LinkedIn disconnect error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/linkedin/status")
async def linkedin_connection_status(request: Request):
    """Get user's LinkedIn connection status via DistributionEngine"""
    try:
        user = get_current_user_from_request(request)
        if not user:
            return JSONResponse({"error": "Authentication required"}, status_code=401)
        
        if not distribution_client:
            return JSONResponse({"connected": False, "error": "DistributionEngine unavailable"})
        
        # Get LinkedIn accounts from DistributionEngine
        result = distribution_client.get_user_accounts(str(user['id']), "linkedin")
        
        if result["success"]:
            accounts = result["data"]["accounts"]
            linkedin_accounts = [acc for acc in accounts if acc["platform"] == "linkedin" and acc["is_active"]]
            
            if linkedin_accounts:
                account = linkedin_accounts[0]  # Use first active LinkedIn account
                return JSONResponse({
                    "connected": True,
                    "profile": {
                        "name": account["display_name"],
                        "email": account["username"],
                        "picture": ""  # Would need to be added to DistributionEngine response
                    }
                })
            else:
                return JSONResponse({"connected": False})
        else:
            return JSONResponse({"connected": False, "error": result.get("error", "Unknown error")})
        
    except Exception as e:
        logger.error(f"❌ LinkedIn status error: {e}")
        return JSONResponse({"connected": False, "error": str(e)})

@app.post("/api/linkedin/analyze-video")
async def analyze_video_for_linkedin(request: Request):
    """Analyze video content and generate social media posts via DistributionEngine"""
    try:
        user = get_current_user_from_request(request)
        if not user:
            return JSONResponse({"error": "Authentication required"}, status_code=401)
        
        if not distribution_client:
            return JSONResponse({"error": "DistributionEngine unavailable"}, status_code=503)
        
        data = await request.json()
        video_id = data.get("video_id")
        video_title = data.get("title", "")
        video_description = data.get("description", "")
        target_platforms = data.get("platforms", ["linkedin"])
        
        if not video_id:
            return JSONResponse({"error": "Video ID required"}, status_code=400)
        
        # Get video details from database
        video = execute_query(
            "SELECT id, title, video_path, created_at FROM videos WHERE id = ? AND user_id = ?",
            (video_id, user['id'])
        )
        
        if not video:
            return JSONResponse({"error": "Video not found"}, status_code=404)
        
        video_data = video[0]
        
        # Analyze video via DistributionEngine
        result = distribution_client.analyze_video_for_social_media(
            user_id=str(user['id']),
            video_id=str(video_id),
            video_title=video_title or video_data[1],
            video_description=video_description,
            target_platforms=target_platforms
        )
        
        if result["success"]:
            return JSONResponse({
                "success": True,
                "video_analysis": result["data"].get("video_analysis", {}),
                "post_content": result["data"].get("variations", {}),
                "posting_suggestions": result["data"].get("posting_suggestions", {})
            })
        else:
            return JSONResponse({
                "success": False,
                "error": result.get("error", "Analysis failed")
            }, status_code=500)
        
    except Exception as e:
        logger.error(f"❌ Video analysis error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/linkedin/generate-variations")
async def generate_post_variations(request: Request):
    """Generate multiple LinkedIn post variations for a video"""
    try:
        user = get_current_user_from_request(request)
        if not user:
            return JSONResponse({"error": "Authentication required"}, status_code=401)
        
        if not linkedin_ai_generator:
            return JSONResponse({"error": "AI service unavailable"}, status_code=503)
        
        data = await request.json()
        video_id = data.get("video_id")
        styles = data.get("styles", ["professional", "thought_leader", "casual"])
        
        if not video_id:
            return JSONResponse({"error": "Video ID required"}, status_code=400)
        
        # Get video details
        video = execute_query(
            "SELECT id, title, video_path FROM videos WHERE id = ? AND user_id = ?",
            (video_id, user['id'])
        )
        
        if not video:
            return JSONResponse({"error": "Video not found"}, status_code=404)
        
        video_data = video[0]
        
        # Analyze video content
        analysis = linkedin_ai_generator.analyze_video_content(
            video_data[2],  # video_path
            video_data[1]   # title
        )
        
        # Generate multiple variations
        variations = linkedin_ai_generator.generate_multiple_variations(analysis, styles)
        
        return JSONResponse({
            "success": True,
            "variations": variations,
            "video_analysis": analysis
        })
        
    except Exception as e:
        logger.error(f"❌ Post variations error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/linkedin/content-templates")
async def get_content_templates(request: Request):
    """Get user's LinkedIn content templates"""
    try:
        user = get_current_user_from_request(request)
        if not user:
            return JSONResponse({"error": "Authentication required"}, status_code=401)
        
        if not linkedin_db:
            return JSONResponse({"error": "Database service unavailable"}, status_code=503)
        
        template_type = request.query_params.get("type")
        templates = linkedin_db.get_user_templates(user['id'], template_type)
        
        return JSONResponse({
            "success": True,
            "templates": templates
        })
        
    except Exception as e:
        logger.error(f"❌ Templates fetch error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/linkedin/save-template")
async def save_content_template(request: Request):
    """Save a LinkedIn content template"""
    try:
        user = get_current_user_from_request(request)
        if not user:
            return JSONResponse({"error": "Authentication required"}, status_code=401)
        
        if not linkedin_db:
            return JSONResponse({"error": "Database service unavailable"}, status_code=503)
        
        data = await request.json()
        template_data = {
            "name": data.get("name", ""),
            "type": data.get("type", "post"),
            "content": data.get("content", ""),
            "hashtags": data.get("hashtags", ""),
            "emojis": data.get("emojis", ""),
            "cta": data.get("cta", "")
        }
        
        if not template_data["name"] or not template_data["content"]:
            return JSONResponse({"error": "Template name and content required"}, status_code=400)
        
        template_id = linkedin_db.save_content_template(user['id'], template_data)
        
        if template_id:
            return JSONResponse({
                "success": True,
                "template_id": template_id,
                "message": "Template saved successfully"
            })
        else:
            return JSONResponse({"error": "Failed to save template"}, status_code=500)
        
    except Exception as e:
        logger.error(f"❌ Save template error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/linkedin/post")
async def linkedin_post_video(request: Request):
    """Post selected video to social media platforms via DistributionEngine"""
    try:
        user = get_current_user_from_request(request)
        if not user:
            return JSONResponse({"error": "Authentication required"}, status_code=401)
        
        if not distribution_client:
            return JSONResponse({"error": "DistributionEngine unavailable"}, status_code=503)
        
        data = await request.json()
        video_id = data.get("video_id")
        post_content = data.get("post_content", "")
        hashtags = data.get("hashtags", [])
        platforms = data.get("platforms", ["linkedin"])
        title = data.get("title", "")
        
        if not video_id:
            return JSONResponse({"error": "Video ID required"}, status_code=400)
        
        # Get video details from database
        video = execute_query(
            "SELECT id, title, video_path FROM videos WHERE id = ? AND user_id = ?",
            (video_id, user['id'])
        )
        
        if not video:
            return JSONResponse({"error": "Video not found"}, status_code=404)
        
        video_data = video[0]
        
        # Post video via DistributionEngine
        result = distribution_client.post_content(
            user_id=str(user['id']),
            content_data={
                "content_id": f"video_{video_id}",
                "title": title or video_data[1],
                "description": post_content,
                "video_url": f"/api/videos/{video_id}/download",
                "hashtags": hashtags,
                "platforms": platforms
            }
        )
        
        if result["success"]:
            results = result["data"]["results"]
            return JSONResponse({
                "success": True,
                "message": f"Video posted to {len(platforms)} platform(s)",
                "results": results
            })
        else:
            return JSONResponse({
                "success": False,
                "error": result.get("error", "Posting failed")
            }, status_code=500)
        
    except Exception as e:
        logger.error(f"❌ LinkedIn post error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/social-media", response_class=HTMLResponse)
async def social_media_page(request: Request):
    """Social Media integration page - embeds DistributionEngine self-service UI"""
    try:
        # Get current user
        token = request.cookies.get("access_token")
        if not token:
            return RedirectResponse(url="/login", status_code=302)
        
        user = get_current_user_from_request(request)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        # Embed DistributionEngine self-service UI in iframe
        distribution_engine_url = os.getenv("DISTRIBUTION_ENGINE_URL", "https://distributionengine-production.up.railway.app")
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Social Media - MyAvatar</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
            <style>
                body {{ margin: 0; padding: 0; }}
                .header-bar {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 15px 20px;
                    display: flex;
                    justify-content: between;
                    align-items: center;
                }}
                .iframe-container {{
                    width: 100%;
                    height: calc(100vh - 80px);
                    border: none;
                }}
                .back-btn {{
                    background: rgba(255,255,255,0.2);
                    border: 1px solid rgba(255,255,255,0.3);
                    color: white;
                    padding: 8px 16px;
                    border-radius: 6px;
                    text-decoration: none;
                    transition: all 0.3s ease;
                }}
                .back-btn:hover {{
                    background: rgba(255,255,255,0.3);
                    color: white;
                    text-decoration: none;
                }}
            </style>
        </head>
        <body>
            <div class="header-bar">
                <div>
                    <h3 class="mb-0">
                        <i class="fas fa-share-alt me-2"></i>Social Media Integration
                    </h3>
                    <small class="opacity-75">Connect and manage your social media accounts</small>
                </div>
                <a href="/dashboard" class="back-btn">
                    <i class="fas fa-arrow-left me-2"></i>Back to Dashboard
                </a>
            </div>
            
            <iframe 
                src="{distribution_engine_url}/self-service?user_id={user['id']}&embed=true" 
                class="iframe-container"
                frameborder="0"
                allow="clipboard-read; clipboard-write">
            </iframe>
            
            <script>
                // Handle iframe communication if needed
                window.addEventListener('message', function(event) {{
                    if (event.origin !== '{distribution_engine_url}') return;
                    
                    if (event.data.type === 'redirect') {{
                        window.location.href = event.data.url;
                    }}
                }});
            </script>
        </body>
        </html>
        """
        
        return HTMLResponse(html_content)
        
    except Exception as e:
        logger.error(f"❌ Social media page error: {e}")
        return HTMLResponse(f"<h1>Error</h1><p>Failed to load social media page: {str(e)}</p>", status_code=500)

@app.get("/social-media-setup")
async def social_media_setup_page(request: Request):
    """Social Media Setup page - like other widgets (text-to-video, etc.)"""
    try:
        # Check authentication
        token = request.cookies.get("access_token")
        if not token:
            return RedirectResponse(url="/login", status_code=302)
        
        user = get_current_user_from_request(request)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        # Social Media Setup page with platform connections
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Social Media Setup - MyAvatar</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
            <style>
                body {{ 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                }}
                .container {{ padding: 40px 20px; }}
                .setup-card {{
                    background: rgba(255, 255, 255, 0.95);
                    border-radius: 15px;
                    padding: 30px;
                    margin: 20px 0;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                    transition: transform 0.3s ease;
                }}
                .setup-card:hover {{ transform: translateY(-5px); }}
                .platform-card {{
                    background: white;
                    border-radius: 10px;
                    padding: 25px;
                    margin: 15px 0;
                    border: 2px solid #e9ecef;
                    transition: all 0.3s ease;
                }}
                .platform-card:hover {{ border-color: #007bff; }}
                .platform-icon {{ font-size: 2.5rem; margin-bottom: 15px; }}
                .status-connected {{ color: #28a745; }}
                .status-disconnected {{ color: #6c757d; }}
                .connect-btn {{ width: 100%; margin-top: 15px; }}
                .header-section {{
                    text-align: center;
                    color: white;
                    margin-bottom: 40px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header-section">
                    <h1><i class="fas fa-share-alt me-3"></i>Social Media Setup</h1>
                    <p class="lead">Connect your social media accounts to automatically distribute your AI videos</p>
                </div>

                <div class="row justify-content-center">
                    <div class="col-lg-10">
                        <div class="setup-card">
                            <h3 class="mb-4"><i class="fas fa-link me-2"></i>Connect Your Platforms</h3>
                            
                            <div class="row">
                                <!-- LinkedIn -->
                                <div class="col-md-6 col-lg-4">
                                    <div class="platform-card text-center">
                                        <i class="fab fa-linkedin platform-icon" style="color: #0077b5;"></i>
                                        <h5>LinkedIn</h5>
                                        <p class="text-muted small">Professional networking and business content</p>
                                        <div class="status-disconnected">
                                            <i class="fas fa-times-circle me-1"></i>Not Connected
                                        </div>
                                        <button class="btn btn-primary connect-btn" onclick="connectLinkedIn()">
                                            <i class="fab fa-linkedin me-2"></i>Connect LinkedIn
                                        </button>
                                    </div>
                                </div>

                                <!-- Facebook -->
                                <div class="col-md-6 col-lg-4">
                                    <div class="platform-card text-center">
                                        <i class="fab fa-facebook platform-icon" style="color: #1877f2;"></i>
                                        <h5>Facebook</h5>
                                        <p class="text-muted small">Share with friends and Facebook pages</p>
                                        <div class="status-disconnected">
                                            <i class="fas fa-times-circle me-1"></i>Not Connected
                                        </div>
                                        <button class="btn btn-primary connect-btn" onclick="connectFacebook()">
                                            <i class="fab fa-facebook me-2"></i>Connect Facebook
                                        </button>
                                    </div>
                                </div>

                                <!-- Twitter/X -->
                                <div class="col-md-6 col-lg-4">
                                    <div class="platform-card text-center">
                                        <i class="fab fa-twitter platform-icon" style="color: #1da1f2;"></i>
                                        <h5>Twitter / X</h5>
                                        <p class="text-muted small">Share short-form content and engage</p>
                                        <div class="status-disconnected">
                                            <i class="fas fa-times-circle me-1"></i>Not Connected
                                        </div>
                                        <button class="btn btn-primary connect-btn" onclick="connectTwitter()">
                                            <i class="fab fa-twitter me-2"></i>Connect Twitter
                                        </button>
                                    </div>
                                </div>

                                <!-- Instagram -->
                                <div class="col-md-6 col-lg-4">
                                    <div class="platform-card text-center">
                                        <i class="fab fa-instagram platform-icon" style="color: #e4405f;"></i>
                                        <h5>Instagram</h5>
                                        <p class="text-muted small">Visual content and stories</p>
                                        <div class="status-disconnected">
                                            <i class="fas fa-times-circle me-1"></i>Not Connected
                                        </div>
                                        <button class="btn btn-primary connect-btn" onclick="connectInstagram()">
                                            <i class="fab fa-instagram me-2"></i>Connect Instagram
                                        </button>
                                    </div>
                                </div>

                                <!-- TikTok -->
                                <div class="col-md-6 col-lg-4">
                                    <div class="platform-card text-center">
                                        <i class="fab fa-tiktok platform-icon" style="color: #000000;"></i>
                                        <h5>TikTok</h5>
                                        <p class="text-muted small">Short-form vertical videos</p>
                                        <div class="status-disconnected">
                                            <i class="fas fa-times-circle me-1"></i>Not Connected
                                        </div>
                                        <button class="btn btn-primary connect-btn" onclick="connectTikTok()">
                                            <i class="fab fa-tiktok me-2"></i>Connect TikTok
                                        </button>
                                    </div>
                                </div>

                                <!-- YouTube -->
                                <div class="col-md-6 col-lg-4">
                                    <div class="platform-card text-center">
                                        <i class="fab fa-youtube platform-icon" style="color: #ff0000;"></i>
                                        <h5>YouTube</h5>
                                        <p class="text-muted small">Long-form video content</p>
                                        <div class="status-disconnected">
                                            <i class="fas fa-times-circle me-1"></i>Not Connected
                                        </div>
                                        <button class="btn btn-primary connect-btn" onclick="connectYouTube()">
                                            <i class="fab fa-youtube me-2"></i>Connect YouTube
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Instructions -->
                        <div class="setup-card">
                            <h4><i class="fas fa-info-circle me-2"></i>How It Works</h4>
                            <div class="row">
                                <div class="col-md-4 text-center">
                                    <i class="fas fa-link text-primary" style="font-size: 2rem;"></i>
                                    <h6 class="mt-2">1. Connect</h6>
                                    <p class="small text-muted">Securely connect your social media accounts</p>
                                </div>
                                <div class="col-md-4 text-center">
                                    <i class="fas fa-video text-success" style="font-size: 2rem;"></i>
                                    <h6 class="mt-2">2. Create</h6>
                                    <p class="small text-muted">Generate your AI avatar videos as usual</p>
                                </div>
                                <div class="col-md-4 text-center">
                                    <i class="fas fa-share text-info" style="font-size: 2rem;"></i>
                                    <h6 class="mt-2">3. Distribute</h6>
                                    <p class="small text-muted">Automatically share to all connected platforms</p>
                                </div>
                            </div>
                        </div>

                        <!-- Back Button -->
                        <div class="text-center mt-4">
                            <a href="/distribution" class="btn btn-outline-light btn-lg me-3">
                                <i class="fas fa-arrow-left me-2"></i>Back to Distribution
                            </a>
                            <a href="/dashboard" class="btn btn-light btn-lg">
                                <i class="fas fa-home me-2"></i>Dashboard
                            </a>
                        </div>
                    </div>
                </div>
            </div>

            <script>
                function connectLinkedIn() {{
                    alert('LinkedIn OAuth integration coming soon!');
                    // TODO: Implement LinkedIn OAuth flow
                }}
                
                function connectFacebook() {{
                    alert('Facebook OAuth integration coming soon!');
                    // TODO: Implement Facebook OAuth flow
                }}
                
                function connectTwitter() {{
                    alert('Twitter OAuth integration coming soon!');
                    // TODO: Implement Twitter OAuth flow
                }}
                
                function connectInstagram() {{
                    alert('Instagram OAuth integration coming soon!');
                    // TODO: Implement Instagram OAuth flow
                }}
                
                function connectTikTok() {{
                    alert('TikTok OAuth integration coming soon!');
                    // TODO: Implement TikTok OAuth flow
                }}
                
                function connectYouTube() {{
                    alert('YouTube OAuth integration coming soon!');
                    // TODO: Implement YouTube OAuth flow
                }}
            </script>
        </body>
        </html>
        """
        
        return HTMLResponse(html_content)
        
    except Exception as e:
        logger.error(f"❌ Social media setup error: {e}")
        return HTMLResponse(f"<h1>Error</h1><p>Failed to load social media setup: {str(e)}</p>", status_code=500)

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"🚀 Starting MyAvatar on {host}:{port}")
    
    logger.info(f"🚀 Starting MyAvatar on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False,  # Disable in production
        log_level="info"
    )
