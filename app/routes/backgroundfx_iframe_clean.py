# app/routes/backgroundfx_iframe.py
# FastAPI router for BackgroundFX iframe integration with HF Space

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import logging

router = APIRouter()
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)

# Configuration - HF Space URL for iframe embedding
HF_SPACE_URL = "https://mogensr-videobackgroundreplacer.hf.space"

@router.get('/backgroundfx', response_class=HTMLResponse)
async def backgroundfx_page(request: Request):
    """Main BackgroundFX page with HF Space iframe integration"""
    try:
        # Simple user data for template (you can enhance this with real auth)
        user_data = {
            "username": "User",
            "id": 1
        }
        
        return templates.TemplateResponse(
            "backgroundfx_iframe.html", 
            {
                "request": request,
                "user": user_data,
                "page_title": "BackgroundFX - Video Background Replacement",
                "hf_space_url": HF_SPACE_URL
            }
        )
        
    except Exception as e:
        logger.error(f"Error loading BackgroundFX page: {e}")
        return HTMLResponse(
            content=f"<h1>Error loading BackgroundFX</h1><p>{str(e)}</p>",
            status_code=500
        )

@router.get('/backgroundfx/status')
async def backgroundfx_status():
    """Status endpoint for BackgroundFX iframe integration"""
    return {
        "status": "active",
        "integration": "iframe",
        "hf_space_url": HF_SPACE_URL,
        "message": "BackgroundFX is running via HF Space iframe integration",
        "streamlit_optimized": True,
        "claude_recommendations": "implemented"
    }
