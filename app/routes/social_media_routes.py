# app/routes/social_media_routes.py - Social Media Integration via LeadGenEngine
import logging
import os
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional

# Configure logging
logger = logging.getLogger("SocialMedia")

# Initialize router
router = APIRouter()

# Templates
templates_dir = Path("templates")
if templates_dir.exists():
    templates = Jinja2Templates(directory="templates")
else:
    logger.error("❌ Templates directory not found")
    templates = None

# Configuration - LeadGenEngine Gradio UI
DEFAULT_GRADIO_URL = "http://localhost:7860"
GRADIO_URL = os.getenv("GRADIO_URL", DEFAULT_GRADIO_URL).strip()

# Dependency to get current user (reusing existing auth)
async def get_current_user(request: Request):
    """Get current user from session - reusing MyAvatar auth"""
    try:
        # Try cookie-based auth first
        token = request.cookies.get("access_token")
        if token:
            try:
                from app.routes.video_routes import get_current_user_fixed
                return get_current_user_fixed(request)
            except ImportError:
                pass
        
        # Fallback to session
        user_id = request.session.get("user_id")
        if user_id:
            from app.db.database import execute_query
            user = execute_query(
                "SELECT * FROM users WHERE id = %s",
                (user_id,),
                fetch_one=True
            )
            return user
        
        return None
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        return None

@router.get("/social-media", response_class=HTMLResponse)
async def social_media_page(request: Request):
    """Social Media page - Gradio UI integration for LeadGenEngine"""
    try:
        # Get current user
        user = await get_current_user(request)
        if not user:
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url="/login", status_code=302)
        
        logger.info(f"🔗 SOCIAL MEDIA - User {user.get('username')} accessing LeadGenEngine Gradio UI")
        
        # Template context
        context = {
            "request": request,
            "user": user,
            "username": user.get("username", "User"),
            "gradio_url": GRADIO_URL,
            "user_id": user.get("id"),
            "is_premium": user.get("subscription_type") == "Premium"
        }
        
        if not templates:
            logger.error("❌ Templates not initialized")
            return HTMLResponse("<h1>Template Error</h1>", status_code=500)
            
        return templates.TemplateResponse("social_media_gradio.html", context)
        
    except Exception as e:
        logger.error(f"❌ Error in social media page: {e}")
        return HTMLResponse("<h1>Social Media Temporarily Unavailable</h1>", status_code=500)

@router.get("/api/social-media/status")
async def social_media_status():
    """Check if LeadGenEngine Gradio UI is available"""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{GRADIO_URL}/", timeout=5) as response:
                if response.status == 200:
                    return {"status": "online", "url": GRADIO_URL}
                else:
                    return {"status": "offline", "url": GRADIO_URL}
    except Exception as e:
        logger.error(f"LeadGenEngine Gradio health check failed: {e}")
        return {"status": "offline", "error": str(e), "url": GRADIO_URL}
