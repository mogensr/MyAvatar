"""
AI Assistant routes for MyAvatar - TEMPORARILY DISABLED
"""
import os
import json
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from ..auth.authentication import get_current_user
from ..logger.log_handler import log_info, log_error

# Create router
router = APIRouter(tags=["assistant"])

# Simple memory for each user's conversation history (kept for future re-enablement)
user_conversations = {}

@router.post("/api/assistant/chat")
async def chat_with_assistant(request: Request):
    """
    Chat with AI assistant - TEMPORARILY DISABLED
    """
    try:
        # Log the attempt to use the disabled feature
        log_info("AI Assistant feature is temporarily disabled", "ASSISTANT")
        
        # Return a message that the AI Assistant is temporarily disabled
        return JSONResponse(
            content={
                "success": True,
                "message": "The AI Assistant feature is temporarily disabled for maintenance. Please check back later."
            }
        )
        
    except Exception as e:
        log_error(f"Assistant chat error: {str(e)}", "ASSISTANT")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )
