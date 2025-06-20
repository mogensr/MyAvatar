from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
import logging
import json
import sys
from typing import Dict, Any
from app.utils.dependencies import get_current_user
from app.api.heygen import get_account_info
import os

router = APIRouter(
    prefix="/mobile-debug",
    tags=["mobile-debug"],
    dependencies=[Depends(get_current_user)]
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@router.get("/device-info")
async def device_info(request: Request):
    """
    Returns information about the client device and request headers
    """
    user_agent = request.headers.get("User-Agent", "Unknown")
    
    # Get all headers for inspection
    headers = {key: value for key, value in request.headers.items()}
    
    # Get client IP
    forwarded_for = request.headers.get("X-Forwarded-For")
    client_ip = forwarded_for.split(",")[0] if forwarded_for else request.client.host
    
    return {
        "user_agent": user_agent,
        "headers": headers,
        "client_ip": client_ip,
        "path": request.url.path,
        "query_params": str(request.query_params)
    }

@router.post("/request-echo")
async def request_echo(request: Request):
    """
    Echoes back the entire request body and headers
    Useful for debugging what's being sent from mobile clients
    """
    try:
        # Try to parse body as JSON
        body = await request.json()
    except:
        # If not JSON, get raw bytes
        body_bytes = await request.body()
        body = {"raw_content": str(body_bytes)}
        
    return {
        "headers": dict(request.headers),
        "body": body,
        "method": request.method,
        "url": str(request.url)
    }

@router.post("/test-audio-upload")
async def test_audio_upload(request: Request):
    """
    Test endpoint for audio upload from mobile
    """
    content_type = request.headers.get("content-type", "")
    content_length = request.headers.get("content-length", "unknown")
    
    try:
        form = await request.form()
        audio_files = form.getlist("audio")
        
        if not audio_files:
            return {"success": False, "error": "No audio file found in request"}
            
        audio_file = audio_files[0]
        filename = audio_file.filename
        content_type = audio_file.content_type
        file_size = 0
        
        # Read first few bytes to verify content
        content = await audio_file.read(1024)
        file_size = len(content)
        
        return {
            "success": True,
            "filename": filename,
            "content_type": content_type,
            "size_sample": file_size,
            "form_keys": list(form.keys())
        }
        
    except Exception as e:
        logger.error(f"Error handling audio upload: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "content_type": content_type,
            "content_length": content_length
        }

@router.get("/test-api-access")
async def test_api_access(request: Request):
    """
    Test endpoint to verify API access from mobile
    """
    try:
        # Test database access
        user = await get_current_user(request)
        
        # Test HeyGen API access
        api_key = os.environ.get("HEYGEN_API_KEY", "")
        if api_key:
            account_info = get_account_info(api_key)
            heygen_status = "Success" if account_info.get("success") else "Failed"
        else:
            heygen_status = "No API key found"
            
        return {
            "success": True,
            "user_verified": bool(user),
            "heygen_api_status": heygen_status,
            "environment": "production" if "app.myavatar.dk" in str(request.base_url) else "development"
        }
        
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        logger.error(f"API access test failed: {str(e)} at line {exc_tb.tb_lineno}")
        return {
            "success": False,
            "error": str(e)
        }
