"""
Text-to-Video Endpoint for MyAvatar
This module provides FastAPI endpoints for text-to-video generation using the HeyGen API.
"""
from fastapi import APIRouter, Depends, HTTPException, Form, status
from fastapi.responses import JSONResponse
import os
from typing import Optional

# Import from your HeyGen API module - this is available
from heygen_api import create_video_from_text, log_info, log_error

# Create router
router = APIRouter()

@router.post("/api/heygen/text")
async def generate_video_from_text(
    avatar_id: str = Form(...),
    text: str = Form(...),
    title: str = Form(...),
    video_format: str = Form("16:9"),
    voice_id: str = Form("en-US-JennyNeural")
):
    """
    Generate a HeyGen AI avatar video from text input with voice selection.
    
    Parameters:
    - avatar_id: The HeyGen avatar ID to use
    - text: The text script to convert to speech and use in the video
    - title: Title for the generated video
    - video_format: Video aspect ratio (16:9, 9:16, or 1:1)
    - voice_id: The voice ID to use for text-to-speech
    """
    try:
        # Log the request
        log_info(f"Text-to-video request: avatar={avatar_id}, format={video_format}, text_length={len(text)}", "API")
        
        # Validate format
        if video_format not in ["16:9", "9:16", "1:1"]:
            log_warning(f"Invalid format: {video_format}, defaulting to 16:9", "API")
            video_format = "16:9"
        
        # Get the API key from environment
        api_key = os.getenv("HEYGEN_API_KEY")
        if not api_key:
            error_msg = "HEYGEN_API_KEY environment variable not set"
            log_error(error_msg, "API")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"success": False, "error": error_msg}
            )
        
        # Generate the video
        result = create_video_from_text(
            api_key=api_key,
            avatar_id=avatar_id,
            text=text,
            video_format=video_format,
            voice_id=voice_id
        )
        
        if result["success"]:
            log_info(f"Text-to-video generation initiated: {result.get('video_id')}", "API")
            return result
        else:
            log_error(f"Failed to generate video: {result.get('error')}", "API")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=result
            )
    
    except Exception as e:
        error_msg = f"Error processing text-to-video request: {str(e)}"
        log_error(error_msg, "API", e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": error_msg}
        )
