"""
Voice ID management routes for MyAvatar
"""
import os
from fastapi import APIRouter, Depends, HTTPException, Request, Form, Body
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional
from datetime import datetime

from ..db.database import execute_query
from ..auth.authentication import get_current_user, require_admin
from ..logger.log_handler import log_info, log_error, log_warning
from ..api.heygen import get_available_voices

# Define templates
templates_path = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_path))

# Create router
router = APIRouter(tags=["voice"])

@router.get("/admin/manage-voices")
async def manage_voices(request: Request, message: Optional[str] = None, message_type: Optional[str] = None):
    """Admin voice ID management page"""
    try:
        # Require admin access
        user = require_admin(request)
        
        # Get all users with their voice IDs
        users = execute_query(
            """
            SELECT u.id, u.username, u.email, u.heygen_voice_id,
                   (SELECT setting_value FROM user_settings 
                    WHERE user_id = u.id AND setting_name = 'voice_id' LIMIT 1) as user_setting_voice_id
            FROM users u
            ORDER BY u.id
            """,
            fetch_all=True
        )
        
        # Get HeyGen API key
        api_key = os.environ.get("HEYGEN_API_KEY", "")
        voice_list = None
        
        # Optionally fetch available voices from HeyGen API
        if api_key:
            try:
                voices_result = get_available_voices(api_key)
                if voices_result.get("success"):
                    voice_list = voices_result.get("voices", [])
            except Exception as e:
                log_warning(f"Could not fetch HeyGen voices: {str(e)}", "VoiceRoutes")
        
        # Return voice management page
        return templates.TemplateResponse(
            "portal/admin_manage_voices.html",
            {
                "request": request,
                "user": user,
                "users": users,
                "voice_list": voice_list,
                "title": "Manage User Voice IDs",
                "message": message,
                "message_type": message_type
            }
        )
    except HTTPException as e:
        # If unauthorized, redirect to login
        if e.status_code == 401:
            return RedirectResponse(url="/login", status_code=303)
        # If forbidden (not admin), redirect to dashboard
        elif e.status_code == 403:
            return RedirectResponse(url="/dashboard", status_code=303)
        raise
    except Exception as e:
        log_error("Error displaying voice management page", "VoiceRoutes", e)
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_title": "Voice Management Error",
                "error_message": "An error occurred loading the voice management page."
            }
        )

@router.post("/api/admin/update-voice-id")
async def update_voice_id(request: Request):
    """Update a user's voice ID (admin only)"""
    try:
        # Require admin access
        admin_user = require_admin(request)
        
        # Get request body
        data = await request.json()
        user_id = data.get("user_id")
        voice_id = data.get("voice_id")
        
        # Validate inputs
        if not user_id:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "User ID is required"}
            )
        
        # Check if user exists
        user = execute_query(
            "SELECT id, username FROM users WHERE id = ?",
            (user_id,),
            fetch_one=True
        )
        
        if not user:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "User not found"}
            )
        
        # Update the voice ID in both tables
        
        # 1. Update users table
        execute_query(
            "UPDATE users SET heygen_voice_id = ? WHERE id = ?",
            (voice_id, user_id)
        )
        
        # 2. Update user_settings table
        # First check if setting already exists
        existing_setting = execute_query(
            "SELECT id FROM user_settings WHERE user_id = ? AND setting_name = 'voice_id'",
            (user_id,),
            fetch_one=True
        )
        
        if existing_setting:
            # Update existing setting
            execute_query(
                "UPDATE user_settings SET setting_value = ? WHERE user_id = ? AND setting_name = 'voice_id'",
                (voice_id, user_id)
            )
        else:
            # Insert new setting
            execute_query(
                "INSERT INTO user_settings (user_id, setting_name, setting_value) VALUES (?, ?, ?)",
                (user_id, "voice_id", voice_id)
            )
        
        log_info(f"Admin {admin_user['username']} updated voice ID for user ID {user_id}", "VoiceRoutes")
        
        return JSONResponse(
            content={
                "success": True,
                "message": f"Voice ID updated successfully for user {user['username']}"
            }
        )
    except HTTPException as e:
        if e.status_code == 401:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Authentication required"}
            )
        elif e.status_code == 403:
            return JSONResponse(
                status_code=403,
                content={"success": False, "error": "Admin access required"}
            )
        raise
    except Exception as e:
        log_error(f"Error updating voice ID", "VoiceRoutes", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.post("/admin/update-voices")
async def admin_update_voice(request: Request, data: dict):
    """Admin route to update a voice ID for a user
    """
    try:
        # Require admin
        admin_user = require_admin(request)
        
        # Update voice ID
        user_id = data.get("user_id")
        voice_id = data.get("voice_id")
        
        # Update in users table
        execute_query(
            "UPDATE users SET heygen_voice_id = ? WHERE id = ?",
            (voice_id, user_id)
        )
        
        # Update in user_settings if it exists
        execute_query(
            "UPDATE user_settings SET value = ? WHERE user_id = ? AND key = 'heygen_voice_id'",
            (voice_id, user_id)
        )
        
        log_info(f"Admin {admin_user['username']} updated voice ID for user {user_id} to {voice_id}", "Voice")
        
        return JSONResponse(content={"success": True})
    except HTTPException as e:
        if e.status_code == 401:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Authentication required"}
            )
        elif e.status_code == 403:
            return JSONResponse(
                status_code=403,
                content={"success": False, "error": "Admin access required"}
            )
        raise
    except Exception as e:
        log_error(f"Error updating voice ID: {e}", "VoiceRoutes", e)
        return JSONResponse(
            status_code=500, 
            content={"success": False, "error": str(e)}
        )

@router.post("/admin/update-voice-id")
async def update_voice_id(request: Request):
    """Update voice ID for a user from the avatar management page
    """
    try:
        # Require admin
        admin_user = require_admin(request)
        
        # Parse request body
        data = await request.json()
        user_id = data.get("user_id")
        voice_id = data.get("voice_id")
        
        if not user_id or not voice_id:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Missing user_id or voice_id"}
            )
        
        # Update in users table
        execute_query(
            "UPDATE users SET heygen_voice_id = ? WHERE id = ?",
            (voice_id, user_id)
        )
        
        # Update in user_settings if it exists
        execute_query(
            "UPDATE user_settings SET value = ? WHERE user_id = ? AND key = 'heygen_voice_id'",
            (voice_id, user_id)
        )
        
        log_info(f"Admin {admin_user['username']} updated voice ID for user {user_id} to {voice_id}", "Voice")
        
        return JSONResponse(content={"success": True})
    except HTTPException as e:
        if e.status_code == 401:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Authentication required"}
            )
        elif e.status_code == 403:
            return JSONResponse(
                status_code=403,
                content={"success": False, "error": "Admin access required"}
            )
        raise
    except Exception as e:
        log_error(f"Error updating voice ID: {e}", "VoiceRoutes", e)
        return JSONResponse(
            status_code=500, 
            content={"success": False, "error": str(e)}
        )

@router.get("/api/heygen/voices")
async def get_voices(request: Request):
    """Get available voices from HeyGen API"""
    try:
        # Require authentication
        user = await get_current_user(request)
        
        # Get HeyGen API key
        api_key = os.environ.get("HEYGEN_API_KEY", "")
        if not api_key:
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "HeyGen API key not configured"}
            )
            
        # Get voices from HeyGen API
        result = get_available_voices(api_key)
        return JSONResponse(content=result)
        
    except HTTPException as e:
        if e.status_code == 401:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Authentication required"}
            )
        raise
    except Exception as e:
        log_error(f"Error getting HeyGen voices", "VoiceRoutes", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )
