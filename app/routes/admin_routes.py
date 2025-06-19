"""
Admin routes for MyAvatar
"""
import os
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional
from datetime import datetime

from ..db.database import execute_query
from ..auth.authentication import get_current_user, require_admin, get_password_hash, validate_password_strength
from ..storage.file_storage import upload_avatar_to_cloudinary
from ..logger.log_handler import log_info, log_error, log_warning

# Define templates
templates_path = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_path))

# Create router
router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/dashboard")
async def admin_dashboard(request: Request):
    """Admin dashboard page"""
    try:
        # Require admin access
        user = require_admin(request)
        
        # Get system stats
        user_count = execute_query("SELECT COUNT(*) as count FROM users", fetch_one=True)
        video_count = execute_query("SELECT COUNT(*) as count FROM videos", fetch_one=True)
        
        # Return admin dashboard
        return templates.TemplateResponse(
            "portal/admin_dashboard.html",
            {
                "request": request,
                "user": user,
                "user_count": user_count["count"] if user_count else 0,
                "video_count": video_count["count"] if video_count else 0,
                "title": "Admin Dashboard"
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
        log_error("Error displaying admin dashboard", "AdminRoutes", e)
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_title": "Admin Dashboard Error",
                "error_message": "An error occurred loading the admin dashboard."
            }
        )

@router.get("/manage-passwords")
async def manage_passwords(request: Request, message: Optional[str] = None, message_type: Optional[str] = None):
    """Admin password management page"""
    try:
        # Require admin access
        user = require_admin(request)
        
        # Get all users
        users = execute_query(
            "SELECT id, username, email, created_at, last_login FROM users ORDER BY id",
            fetch_all=True
        )
        
        # Return password management page
        return templates.TemplateResponse(
            "portal/admin_manage_passwords.html",
            {
                "request": request,
                "user": user,
                "users": users,
                "title": "Manage User Passwords",
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
        log_error("Error displaying password management page", "AdminRoutes", e)
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_title": "Password Management Error",
                "error_message": "An error occurred loading the password management page."
            }
        )

@router.post("/api/admin/reset-password", response_class=JSONResponse)
async def reset_password(request: Request):
    """Reset a user's password (admin only)"""
    try:
        # Require admin access
        admin_user = require_admin(request)
        
        # Get request body
        data = await request.json()
        user_id = data.get("user_id")
        new_password = data.get("new_password")
        
        # Validate inputs
        if not user_id or not new_password:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "User ID and new password are required"}
            )
        
        # Validate password strength
        is_valid, error_message = validate_password_strength(new_password)
        if not is_valid:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": error_message}
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
        
        # Hash the new password
        hashed_password = get_password_hash(new_password)
        
        # Update the password in the database
        execute_query(
            "UPDATE users SET password = ? WHERE id = ?",
            (hashed_password, user_id)
        )
        
        log_info(f"Admin {admin_user['username']} reset password for user ID {user_id}", "AdminRoutes")
        
        return JSONResponse(
            content={
                "success": True,
                "message": f"Password reset successfully for user ID {user_id}"
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
        log_error(f"Error resetting password", "AdminRoutes", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )
