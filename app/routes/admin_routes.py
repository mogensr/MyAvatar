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

from ..db.database import execute_query, USE_POSTGRES
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
        return JSONResponse(
            status_code=500,
            content={"error": "Admin dashboard error", "detail": str(e)}
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
        return JSONResponse(
            status_code=500,
            content={"error": "Password management error", "detail": str(e)}
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

@router.get("/check-user")
async def check_user_status(request: Request):
    """Check current user status and admin privileges"""
    try:
        # Try to get current user
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                content={
                    "logged_in": False,
                    "message": "No user logged in"
                }
            )
        
        return JSONResponse(
            content={
                "logged_in": True,
                "user_id": user.get("id"),
                "username": user.get("username"),
                "email": user.get("email"),
                "is_admin": user.get("is_admin", False),
                "message": "User found"
            }
        )
    except Exception as e:
        return JSONResponse(
            content={
                "logged_in": False,
                "error": str(e),
                "message": "Error checking user status"
            }
        )

@router.get("/migrate-database")
async def migrate_database_get(request: Request):
    """Migrate database to add missing description column (GET endpoint)"""
    try:
        # Require admin access
        admin_user = require_admin(request)
        
        # Check if column already exists
        try:
            test_result = execute_query("SELECT description FROM videos LIMIT 1", fetch_one=True)
            return JSONResponse(
                content={
                    "success": True,
                    "message": "Database migration not needed - description column already exists"
                }
            )
        except:
            # Column doesn't exist, proceed with migration
            pass
        
        if USE_POSTGRES:
            execute_query("ALTER TABLE videos ADD COLUMN description TEXT")
        else:
            execute_query("ALTER TABLE videos ADD COLUMN description TEXT DEFAULT ''")
        
        log_info(f"Admin {admin_user['username']} migrated database to add missing description column", "AdminRoutes")
        
        return JSONResponse(
            content={
                "success": True,
                "message": "Database migrated successfully - description column added to videos table"
            }
        )
    except HTTPException as e:
        if e.status_code == 401:
            return RedirectResponse(url="/login", status_code=303)
        elif e.status_code == 403:
            return JSONResponse(
                status_code=403,
                content={"success": False, "error": "Admin access required"}
            )
        raise
    except Exception as e:
        log_error(f"Error migrating database", "AdminRoutes", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.post("/api/admin/migrate-database", response_class=JSONResponse)
async def migrate_database(request: Request):
    """Migrate database to add missing description column"""
    try:
        # Require admin access
        admin_user = require_admin(request)
        
        if USE_POSTGRES:
            execute_query("ALTER TABLE videos ADD COLUMN description TEXT")
        else:
            execute_query("ALTER TABLE videos ADD COLUMN description TEXT DEFAULT ''")
        
        log_info(f"Admin {admin_user['username']} migrated database to add missing description column", "AdminRoutes")
        
        return JSONResponse(
            content={
                "success": True,
                "message": "Database migrated successfully"
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
        log_error(f"Error migrating database", "AdminRoutes", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/debug-video/{video_id}")
async def debug_video_status(request: Request, video_id: str):
    """Debug endpoint to check video status and update from HeyGen"""
    try:
        # Require admin access
        admin_user = require_admin(request)
        
        # Get video from database
        video = execute_query(
            "SELECT * FROM videos WHERE id = %s OR heygen_video_id = %s",
            (video_id, video_id),
            fetch_one=True
        )
        
        if not video:
            return JSONResponse(
                content={
                    "success": False,
                    "error": f"Video not found with ID: {video_id}"
                }
            )
        
        # Get HeyGen API key
        api_key = os.getenv("HEYGEN_API_KEY")
        if not api_key:
            return JSONResponse(
                content={
                    "success": False,
                    "error": "HeyGen API key not configured"
                }
            )
        
        # Import get_video_details function
        from ..api.heygen import get_video_details
        
        # Check status on HeyGen
        heygen_video_id = video.get("heygen_video_id")
        if not heygen_video_id:
            return JSONResponse(
                content={
                    "success": False,
                    "error": "Video has no HeyGen video ID"
                }
            )
        
        result = get_video_details(api_key, heygen_video_id)
        
        debug_info = {
            "database_video": {
                "id": video.get("id"),
                "heygen_video_id": video.get("heygen_video_id"),
                "status": video.get("status"),
                "video_url": video.get("video_url"),
                "user_id": video.get("user_id")
            },
            "heygen_api_result": result
        }
        
        # If HeyGen says video is completed, update database
        if result.get("success") and result.get("details"):
            details = result["details"]
            heygen_status = details.get("status")
            heygen_video_url = (details.get("video_url") or 
                               details.get("video_url_caption") or 
                               details.get("url") or 
                               details.get("download_url"))
            
            debug_info["heygen_details"] = {
                "status": heygen_status,
                "video_url": heygen_video_url
            }
            
            if heygen_status == "completed" and heygen_video_url:
                # Update database
                execute_query(
                    "UPDATE videos SET status = %s, video_url = %s WHERE id = %s",
                    ("completed", heygen_video_url, video["id"])
                )
                debug_info["database_updated"] = True
                log_info(f"Admin {admin_user['username']} manually updated video {video['id']} status", "AdminRoutes")
            else:
                debug_info["database_updated"] = False
        
        return JSONResponse(content=debug_info)
        
    except Exception as e:
        log_error(f"Error debugging video status", "AdminRoutes", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/make-me-admin")
async def make_me_admin(request: Request):
    """Grant admin privileges to current user (for initial setup)"""
    try:
        # Get current user
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "error": "Must be logged in to grant admin privileges"
                }
            )
        
        # Update user to admin
        if USE_POSTGRES:
            execute_query(
                "UPDATE users SET is_admin = true WHERE id = %s",
                (user["id"],)
            )
        else:
            execute_query(
                "UPDATE users SET is_admin = 1 WHERE id = ?",
                (user["id"],)
            )
        
        log_info(f"User {user['username']} granted admin privileges", "AdminRoutes")
        
        return JSONResponse(
            content={
                "success": True,
                "message": f"Admin privileges granted to user {user['username']}"
            }
        )
    except Exception as e:
        log_error(f"Error granting admin privileges", "AdminRoutes", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/users")
async def manage_users(request: Request):
    """Admin user management page"""
    try:
        # Require admin access
        user = require_admin(request)
        
        # Get all users with video counts
        users = execute_query("""
            SELECT u.id, u.username, u.email, u.created_at, u.last_login, u.is_admin,
                   COUNT(v.id) as video_count
            FROM users u
            LEFT JOIN videos v ON u.id = v.user_id
            GROUP BY u.id, u.username, u.email, u.created_at, u.last_login, u.is_admin
            ORDER BY u.id
        """, fetch_all=True)
        
        return templates.TemplateResponse(
            "portal/admin_manage_users.html",
            {
                "request": request,
                "user": user,
                "users": users,
                "title": "Manage Users"
            }
        )
    except HTTPException as e:
        if e.status_code == 401:
            return RedirectResponse(url="/login", status_code=303)
        elif e.status_code == 403:
            return RedirectResponse(url="/dashboard", status_code=303)
        raise
    except Exception as e:
        log_error("Error displaying user management page", "AdminRoutes", e)
        return JSONResponse(
            status_code=500,
            content={"error": "User management error", "detail": str(e)}
        )

@router.get("/manage-videos/{user_id}")
async def manage_user_videos(request: Request, user_id: int):
    """Admin video management page for specific user"""
    try:
        # Require admin access
        admin_user = require_admin(request)
        
        # Get user details
        user_to_manage = execute_query(
            "SELECT id, username, email FROM users WHERE id = %s",
            (user_id,),
            fetch_one=True
        )
        
        if not user_to_manage:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get all videos for this user
        videos = execute_query("""
            SELECT id, title, status, heygen_video_id, created_at, video_path
            FROM videos 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """, (user_id,), fetch_all=True)
        
        return templates.TemplateResponse(
            "portal/admin_manage_videos.html",
            {
                "request": request,
                "user": admin_user,
                "user_to_manage": user_to_manage,
                "videos": videos,
                "total_videos": len(videos),
                "title": f"Manage Videos - {user_to_manage['username']}"
            }
        )
    except HTTPException as e:
        if e.status_code == 401:
            return RedirectResponse(url="/login", status_code=303)
        elif e.status_code == 403:
            return RedirectResponse(url="/dashboard", status_code=303)
        raise
    except Exception as e:
        log_error("Error displaying video management page", "AdminRoutes", e)
        return JSONResponse(
            status_code=500,
            content={"error": "Video management error", "detail": str(e)}
        )

@router.post("/delete-video/{video_id}")
async def delete_video(request: Request, video_id: int):
    """Delete a specific video (admin only)"""
    try:
        # Require admin access
        admin_user = require_admin(request)
        
        # Get video details first
        video = execute_query(
            "SELECT id, user_id, title FROM videos WHERE id = %s",
            (video_id,),
            fetch_one=True
        )
        
        if not video:
            return RedirectResponse(
                url=f"/admin/users?error=video_not_found",
                status_code=303
            )
        
        # Delete the video
        execute_query("DELETE FROM videos WHERE id = %s", (video_id,))
        
        log_info(f"Admin {admin_user['username']} deleted video {video_id} ('{video['title']}')", "AdminRoutes")
        
        return RedirectResponse(
            url=f"/admin/manage-videos/{video['user_id']}?success=video_deleted",
            status_code=303
        )
        
    except HTTPException as e:
        if e.status_code == 401:
            return RedirectResponse(url="/login", status_code=303)
        elif e.status_code == 403:
            return RedirectResponse(url="/dashboard", status_code=303)
        raise
    except Exception as e:
        log_error("Error deleting video", "AdminRoutes", e)
        return RedirectResponse(
            url="/admin/users?error=delete_failed",
            status_code=303
        )

@router.post("/clear-user-videos/{user_id}")
async def clear_user_videos(request: Request, user_id: int):
    """Clear all videos for a specific user (admin only)"""
    try:
        # Require admin access
        admin_user = require_admin(request)
        
        # Get user details
        user_to_manage = execute_query(
            "SELECT id, username FROM users WHERE id = %s",
            (user_id,),
            fetch_one=True
        )
        
        if not user_to_manage:
            return RedirectResponse(
                url="/admin/users?error=user_not_found",
                status_code=303
            )
        
        # Count videos before deletion
        video_count = execute_query(
            "SELECT COUNT(*) as count FROM videos WHERE user_id = %s",
            (user_id,),
            fetch_one=True
        )
        
        # Delete all videos for this user
        execute_query("DELETE FROM videos WHERE user_id = %s", (user_id,))
        
        log_info(f"Admin {admin_user['username']} cleared {video_count['count']} videos for user {user_to_manage['username']}", "AdminRoutes")
        
        return RedirectResponse(
            url=f"/admin/manage-videos/{user_id}?success=all_videos_cleared",
            status_code=303
        )
        
    except HTTPException as e:
        if e.status_code == 401:
            return RedirectResponse(url="/login", status_code=303)
        elif e.status_code == 403:
            return RedirectResponse(url="/dashboard", status_code=303)
        raise
    except Exception as e:
        log_error("Error clearing user videos", "AdminRoutes", e)
        return RedirectResponse(
            url=f"/admin/manage-videos/{user_id}?error=clear_failed",
            status_code=303
        )

@router.post("/fetch-heygen-avatar/{user_id}")
async def fetch_avatar_from_heygen(request: Request, user_id: int):
    """Fetch avatar image from HeyGen API and save to user"""
    try:
        # Check admin authentication
        admin_user = get_current_user(request)
        if not admin_user or not admin_user.get("is_admin", 0) == 1:
            raise HTTPException(status_code=401, detail="Admin access required")
        
        # Get form data
        form = await request.form()
        avatar_id = form.get("heygen_avatar_id", "").strip()
        
        if not avatar_id:
            return JSONResponse(
                content={"success": False, "error": "Avatar ID is required"},
                status_code=400
            )
        
        # Get user to manage
        user_to_manage = execute_query(
            "SELECT id, username FROM users WHERE id = %s",
            (user_id,),
            fetch_one=True
        )
        
        if not user_to_manage:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Import HeyGen functions
        from ..api.heygen import get_available_avatars
        
        try:
            # Fetch all avatars from HeyGen and find the specific one
            avatars_result = get_available_avatars(os.getenv("HEYGEN_API_KEY"))
            
            if not avatars_result.get("success"):
                return JSONResponse(
                    content={"success": False, "error": f"Failed to fetch avatars from HeyGen: {avatars_result.get('error', 'Unknown error')}"},
                    status_code=400
                )
            
            # Find the specific avatar by ID
            avatars = avatars_result.get("avatars", [])
            avatar_details = None
            
            for avatar in avatars:
                if avatar.get("avatar_id") == avatar_id:
                    avatar_details = avatar
                    break
            
            if not avatar_details:
                return JSONResponse(
                    content={"success": False, "error": f"Avatar with ID '{avatar_id}' not found in your HeyGen account"},
                    status_code=404
                )
            
            # Extract avatar information
            avatar_name = avatar_details.get("name", f"Avatar {avatar_id}")
            avatar_image_url = avatar_details.get("preview_image_url") or avatar_details.get("image_url")
            
            if not avatar_image_url:
                return JSONResponse(
                    content={"success": False, "error": "No image URL found for this avatar"},
                    status_code=400
                )
            
            # Check if avatar already exists for this user
            existing_avatar = execute_query(
                "SELECT id FROM user_avatars WHERE user_id = ? AND avatar_id = ?",
                (user_id, avatar_id),
                fetch_one=True
            )
            
            if existing_avatar:
                # Update existing avatar
                if USE_POSTGRES:
                    execute_query(
                        "UPDATE user_avatars SET name = ?, image_path = ?, updated_at = NOW() WHERE user_id = ? AND avatar_id = ?",
                        (avatar_name, avatar_image_url, user_id, avatar_id)
                    )
                else:
                    execute_query(
                        "UPDATE user_avatars SET name = ?, image_path = ?, updated_at = datetime('now') WHERE user_id = ? AND avatar_id = ?",
                        (avatar_name, avatar_image_url, user_id, avatar_id)
                    )
                log_info(f"Admin {admin_user['username']} updated avatar {avatar_id} for user {user_to_manage['username']}", "AdminRoutes")
            else:
                # Insert new avatar
                if USE_POSTGRES:
                    execute_query(
                        "INSERT INTO user_avatars (user_id, avatar_id, name, image_path, is_default, created_at) VALUES (?, ?, ?, ?, 0, NOW())",
                        (user_id, avatar_id, avatar_name, avatar_image_url)
                    )
                else:
                    execute_query(
                        "INSERT INTO user_avatars (user_id, avatar_id, name, image_path, is_default, created_at) VALUES (?, ?, ?, ?, 0, datetime('now'))",
                        (user_id, avatar_id, avatar_name, avatar_image_url)
                    )
                log_info(f"Admin {admin_user['username']} added avatar {avatar_id} for user {user_to_manage['username']}", "AdminRoutes")
            
            return JSONResponse(
                content={
                    "success": True, 
                    "message": "Avatar fetched and saved successfully",
                    "avatar": {
                        "id": avatar_id,
                        "name": avatar_name,
                        "image_url": avatar_image_url
                    }
                }
            )
            
        except Exception as heygen_error:
            log_error(f"Error fetching avatar from HeyGen: {str(heygen_error)}", "AdminRoutes", heygen_error)
            return JSONResponse(
                content={"success": False, "error": f"Failed to fetch from HeyGen: {str(heygen_error)}"},
                status_code=500
            )
        
    except HTTPException as e:
        if e.status_code == 401:
            return JSONResponse(content={"success": False, "error": "Admin access required"}, status_code=401)
        elif e.status_code == 403:
            return JSONResponse(content={"success": False, "error": "Access denied"}, status_code=403)
        raise
    except Exception as e:
        log_error("Error in fetch avatar from HeyGen endpoint", "AdminRoutes", e)
        return JSONResponse(
            content={"success": False, "error": f"Server error: {str(e)}"},
            status_code=500
        )
