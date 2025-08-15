"""
Voice Video Routes - Clean Implementation
Registers both API and page routes for the new voice-to-video system
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from ..core.auth import get_current_user_fixed
from ..core.database import execute_query
from .voice_video_new import router as api_router

# Main router that includes both page and API routes
router = APIRouter()

# Include the API routes
router.include_router(api_router)

# Templates
templates = Jinja2Templates(directory="templates")

@router.get("/voice-video-clean", response_class=HTMLResponse)
async def voice_video_clean_page(request: Request):
    """
    Clean voice-to-video page - completely new implementation
    """
    try:
        user = get_current_user_fixed(request)
        if not user:
            return templates.TemplateResponse("login.html", {"request": request})
        
        # Get user avatars
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
        print(f"Error loading voice video page: {e}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Failed to load voice video page"
        })
