"""
Background replacement routes using BackgroundFX microservice
"""
import os
import io
import logging
from typing import List

from fastapi import APIRouter, Request, HTTPException, Depends, File, UploadFile, Form
from fastapi.responses import JSONResponse

from app.services.backgroundfx_client import backgroundfx_client
from app.auth.authentication import get_current_user

# Initialize logger
logger = logging.getLogger("myavatar.routes.background")

# Create router
router = APIRouter()

@router.get("/backgrounds")
async def get_available_backgrounds(current_user = Depends(get_current_user)):
    """
    Get list of available background options from BackgroundFX service
    """
    try:
        # Check if service is available
        if not backgroundfx_client.health_check():
            logger.warning("BackgroundFX service is unavailable")
            return JSONResponse(
                status_code=503,
                content={"error": "Background service is currently unavailable"}
            )
            
        # Get backgrounds from service
        backgrounds = backgroundfx_client.get_available_backgrounds()
        return {"backgrounds": backgrounds}
    except Exception as e:
        logger.error(f"Error retrieving backgrounds: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving background options")

@router.post("/replace-background")
async def replace_background(
    request: Request,
    image: UploadFile = File(...),
    background_id: str = Form(...),
    strength: float = Form(0.8),
    current_user = Depends(get_current_user)
):
    """
    Replace background in uploaded image using BackgroundFX service
    """
    try:
        # Read image data
        image_data = await image.read()
        
        # Check service availability
        if not backgroundfx_client.health_check():
            logger.warning("BackgroundFX service is unavailable")
            return JSONResponse(
                status_code=503,
                content={"error": "Background replacement service is currently unavailable"}
            )
        
        # Call background service
        logger.info(f"Sending background replacement request to service: bg={background_id}")
        result_image = backgroundfx_client.replace_background(
            image_data=image_data,
            background_id=background_id,
            strength=strength,
            return_raw=False  # Get base64 encoded image
        )
        
        return {
            "success": True,
            "image": result_image,
            "background_id": background_id
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions from client
        raise
    except Exception as e:
        logger.error(f"Error in background replacement: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing image")
