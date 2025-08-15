# app/routes/backgroundfx_iframe.py - CLEAN IFRAME INTEGRATION FOR MYAVATAR
import logging
import os
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import aiohttp
from typing import Optional

# Configure logging
logger = logging.getLogger("BackgroundFX-iframe")

# Initialize router
router = APIRouter()

# Templates
templates_dir = Path("templates")
if templates_dir.exists():
    templates = Jinja2Templates(directory="templates")
else:
    logger.error("❌ Templates directory not found")
    templates = None

# Configuration
DEFAULT_HF_SPACE_URL = "https://MogensR-VideoBackgroundReplacer.hf.space"
HF_SPACE_URL = os.getenv("HF_SPACE_URL", DEFAULT_HF_SPACE_URL).strip()

# Dependency to get current user (simplified for iframe integration)
async def get_current_user(request: Request):
    """Get current user from session - simplified version for iframe"""
    try:
        # Try cookie-based auth first
        token = request.cookies.get("access_token")
        if token:
            try:
                from app.services.auth_service import auth_service
                payload = auth_service.validate_token(token)
                if payload:
                    user_id = payload.get("user_id")
                    if user_id:
                        from app.db.user_manager import Database
                        db = Database()
                        user = db.get_user_by_id(user_id)
                        if user:
                            return user
            except ImportError:
                pass
        
        # Fallback to session
        if hasattr(request, 'session') and request.session:
            user_data = request.session.get("user", {})
            if isinstance(user_data, dict) and user_data.get("id"):
                return user_data
                
    except Exception as e:
        logger.warning(f"Error getting current user: {e}")
    
    return None

@router.get("/backgroundfx", response_class=HTMLResponse)
async def backgroundfx_page(request: Request, current_user = Depends(get_current_user)):
    """Main BackgroundFX page with HF Space iframe"""
    if not templates:
        raise HTTPException(status_code=500, detail="Templates not configured")
    
    # Require authentication
    if not current_user:
        # Redirect to login
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login?next=/backgroundfx", status_code=302)
    
    try:
        username = current_user.get("username", "User") if isinstance(current_user, dict) else getattr(current_user, "username", "User")
        logger.info(f"🎬 BackgroundFX page accessed by user: {username}")
        
        context = {
            "request": request,
            "page_title": "BackgroundFX - AI Video Background Replacement",
            "username": username,
            "hf_space_url": HF_SPACE_URL,
            "service_status": "active",
            "integration_type": "HF Space iframe"
        }
        
        return templates.TemplateResponse("backgroundfx_iframe.html", context)
        
    except Exception as e:
        logger.error(f"❌ Error serving BackgroundFX page: {e}")
        raise HTTPException(status_code=500, detail=f"Error loading BackgroundFX: {str(e)}")

@router.get("/backgroundfx/status")
async def backgroundfx_status():
    """Check BackgroundFX service status"""
    try:
        # Check if HF Space is accessible
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(HF_SPACE_URL, timeout=10) as response:
                    hf_space_online = response.status == 200
                    logger.info(f"🔍 HF Space status check: {response.status}")
            except Exception as e:
                logger.warning(f"⚠️ HF Space not accessible: {e}")
                hf_space_online = False
        
        return JSONResponse({
            "success": True,
            "service": "BackgroundFX iframe Integration",
            "hf_space_url": HF_SPACE_URL,
            "hf_space_status": "online" if hf_space_online else "offline",
            "integration_type": "HF Space iframe",
            "features": [
                "AI-Powered Video Background Replacement", 
                "Audio Preservation",
                "MatAnyone + MediaPipe Integration",
                "Web-Optimized Output"
            ]
        })
        
    except Exception as e:
        logger.error(f"❌ Status check error: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e),
            "service": "BackgroundFX iframe Integration",
            "hf_space_url": HF_SPACE_URL,
            "hf_space_status": "error"
        }, status_code=500)

@router.get("/backgroundfx/config")
async def backgroundfx_config():
    """Get BackgroundFX configuration"""
    return JSONResponse({
        "hf_space_url": HF_SPACE_URL,
        "default_url": DEFAULT_HF_SPACE_URL,
        "using_custom_url": HF_SPACE_URL != DEFAULT_HF_SPACE_URL,
        "integration_type": "HF Space iframe",
        "iframe_features": {
            "allow_camera": True,
            "allow_microphone": True,
            "allow_clipboard": True,
            "allow_fullscreen": True,
            "sandbox_permissions": [
                "allow-same-origin",
                "allow-scripts", 
                "allow-forms",
                "allow-downloads",
                "allow-popups"
            ]
        },
        "supported_formats": {
            "input": ["MP4", "AVI", "MOV", "WEBM"],
            "output": ["MP4"],
            "background": ["JPG", "PNG", "WEBP"]
        }
    })

@router.get("/backgroundfx/health")
async def backgroundfx_health():
    """Health check endpoint"""
    try:
        health_status = {
            "status": "healthy",
            "service": "BackgroundFX iframe Integration",
            "hf_space_configured": bool(HF_SPACE_URL),
            "templates_available": templates is not None
        }
        
        return JSONResponse(health_status)
        
    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        return JSONResponse({
            "status": "unhealthy",
            "error": str(e),
            "service": "BackgroundFX iframe Integration"
        }, status_code=500)

# Admin endpoints
@router.get("/admin/backgroundfx/info")
async def admin_backgroundfx_info(current_user = Depends(get_current_user)):
    """Admin info about BackgroundFX integration"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    username = current_user.get("username", "User") if isinstance(current_user, dict) else getattr(current_user, "username", "User")
    
    return JSONResponse({
        "integration_info": {
            "type": "HF Space iframe",
            "hf_space_url": HF_SPACE_URL,
            "default_url": DEFAULT_HF_SPACE_URL,
            "custom_url_configured": HF_SPACE_URL != DEFAULT_HF_SPACE_URL,
            "templates_configured": templates is not None
        },
        "routes_available": [
            "/backgroundfx - Main interface",
            "/backgroundfx/status - Service status",
            "/backgroundfx/config - Configuration",
            "/backgroundfx/health - Health check"
        ],
        "features": {
            "ai_background_replacement": True,
            "audio_preservation": True,
            "web_optimized_output": True,
            "iframe_integration": True,
            "hf_space_hosted": True
        },
        "current_user": username
    })

# Startup logging
logger.info("🎬 BackgroundFX iframe router initialized")
logger.info(f"🔗 HF Space URL: {HF_SPACE_URL}")
logger.info("✅ BackgroundFX iframe integration ready")
