# app/routes/leadgen_iframe.py - LeadGenEngine Iframe Integration
import logging
import os
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional

# Configure logging
logger = logging.getLogger("LeadGenEngine-iframe")

# Initialize router
router = APIRouter()

# Templates
templates_dir = Path("templates")
if templates_dir.exists():
    templates = Jinja2Templates(directory="templates")
else:
    logger.error("❌ Templates directory not found")
    templates = None

# Configuration - will be updated with actual Railway URL after deployment
DEFAULT_LEADGEN_URL = "https://leadgenengine-production.up.railway.app"
LEADGEN_URL = os.getenv("LEADGEN_URL", DEFAULT_LEADGEN_URL).strip()

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

@router.get("/distribution", response_class=HTMLResponse)
async def distribution_page(request: Request):
    """Distribution Engine page - iframe integration with LeadGenEngine"""
    try:
        # Get current user
        user = await get_current_user(request)
        if not user:
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url="/login", status_code=302)
        
        logger.info(f"🎯 DISTRIBUTION ENGINE - User {user.get('username')} accessing LeadGenEngine")
        
        # Template context
        context = {
            "request": request,
            "user": user,
            "username": user.get("username", "User"),
            "leadgen_url": LEADGEN_URL,
            "user_id": user.get("id"),
            "is_premium": user.get("subscription_type") == "Premium"
        }
        
        if not templates:
            logger.error("❌ Templates not initialized")
            return HTMLResponse("<h1>Template Error</h1>", status_code=500)
            
        return templates.TemplateResponse("distribution_iframe.html", context)
        
    except Exception as e:
        logger.error(f"❌ Error in distribution page: {e}")
        return HTMLResponse("<h1>Distribution Engine Temporarily Unavailable</h1>", status_code=500)

@router.get("/api/leadgen/status")
async def leadgen_status():
    """Check if LeadGenEngine service is available"""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{LEADGEN_URL}/health", timeout=5) as response:
                if response.status == 200:
                    return {"status": "online", "url": LEADGEN_URL}
                else:
                    return {"status": "offline", "url": LEADGEN_URL}
    except Exception as e:
        logger.error(f"LeadGenEngine health check failed: {e}")
        return {"status": "offline", "error": str(e), "url": LEADGEN_URL}
