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
import re

from ..db.database import execute_query, USE_POSTGRES
from ..auth.authentication import get_current_user, require_admin, get_password_hash, validate_password_strength
from ..storage.file_storage import upload_avatar_to_cloudinary
from ..logger.log_handler import log_info, log_error, log_warning

# Define templates
templates_path = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_path))

# Create router
router = APIRouter(prefix="/admin", tags=["admin"])

# =============================================================================
# ENHANCED AVATAR NAMING LOGIC
# =============================================================================

def generate_user_friendly_name(avatar_data):
    """
    Generate user-friendly names from HeyGen avatar data.
    Falls back gracefully when ideal fields aren't available.
    """
    
    # Priority 1: Use explicit display/user-friendly fields if available
    display_fields = ['display_name', 'title', 'name', 'friendly_name', 'label']
    for field in display_fields:
        if field in avatar_data and avatar_data[field]:
            name = str(avatar_data[field]).strip()
            if name and not is_technical_id(name):
                return name
    
    # Priority 2: Build name from metadata fields
    name_parts = []
    
    # Gender/type information
    if 'gender' in avatar_data:
        gender = avatar_data['gender'].lower()
        if gender in ['male', 'man', 'm']:
            name_parts.append('Man')
        elif gender in ['female', 'woman', 'f']:
            name_parts.append('Woman')
    
    # Style/type information
    style_keywords = {
        'professional': 'Professional',
        'business': 'Business',
        'casual': 'Casual',
        'formal': 'Formal',
        'corporate': 'Corporate',
        'suit': 'Business',
        'dress': 'Professional',
        'shirt': 'Casual'
    }
    
    # Check various fields for style indicators
    style_fields = ['style', 'type', 'category', 'description', 'outfit', 'clothing']
    found_style = False
    
    for field in style_fields:
        if field in avatar_data and avatar_data[field]:
            field_value = str(avatar_data[field]).lower()
            for keyword, style_name in style_keywords.items():
                if keyword in field_value:
                    name_parts.insert(0, style_name)  # Put style first
                    found_style = True
                    break
            if found_style:
                break
    
    # Priority 3: Use original avatar_id but clean it up
    if not name_parts:
        avatar_id = avatar_data.get('avatar_id', '')
        cleaned_name = clean_technical_id(avatar_id)
        if cleaned_name:
            return cleaned_name
    
    # Combine parts or use fallback
    if name_parts:
        final_name = ' '.join(name_parts)
        if len(name_parts) == 1:  # Only gender, add "Avatar"
            final_name += ' Avatar'
        return final_name
    
    # Ultimate fallback
    return 'Avatar'

def is_technical_id(name):
    """Check if a name looks like a technical ID rather than user-friendly name."""
    name_lower = name.lower()
    
    # Technical ID indicators
    technical_patterns = [
        '_', '-', 'camera', 'costume', 'lite', 'v1', 'v2', 'test',
        '20220', '20230', '20240', '20250',  # Years
        'dev', 'prod', 'staging'
    ]
    
    # Check for technical patterns
    for pattern in technical_patterns:
        if pattern in name_lower:
            return True
    
    # Check for mostly lowercase with numbers/underscores
    if any(c in name for c in '_-') and name.islower():
        return True
        
    # Check for camelCase or snake_case patterns
    if '_' in name or (any(c.isupper() for c in name[1:]) and any(c.islower() for c in name)):
        return True
    
    return False

def clean_technical_id(avatar_id):
    """Convert technical ID to more readable format as last resort."""
    if not avatar_id:
        return None
    
    # Remove common technical suffixes/prefixes
    cleaned = avatar_id
    
    # Remove technical suffixes
    suffixes_to_remove = ['_cameraA', '_cameraB', '_camera1', '_camera2', 
                         '_costume1', '_costume2', '_lite', '_lite2', '_v1', '_v2']
    for suffix in suffixes_to_remove:
        if cleaned.endswith(suffix):
            cleaned = cleaned[:-len(suffix)]
            break
    
    # Remove date patterns (e.g., _20220721)
    cleaned = re.sub(r'_\d{8}', '', cleaned)
    cleaned = re.sub(r'_\d{6}', '', cleaned)
    
    # Capitalize first letter and replace underscores
    if cleaned:
        cleaned = cleaned.replace('_', ' ').title()
        # Don't return single letters or very short names
        if len(cleaned) > 2:
            return cleaned
    
    return None

def get_all_heygen_avatars_with_photo_support():
    """
    Enhanced function to fetch ALL avatars including photo avatars from HeyGen
    """
    try:
        api_key = os.getenv("HEYGEN_API_KEY")
        if not api_key:
            return {"success": False, "error": "API key not configured"}
        
        import requests
        
        all_avatars = []
        
        # 1. Get regular avatars (existing method)
        try:
            regular_response = requests.get(
                "https://api.heygen.com/v2/avatars",
                headers={
                    "X-Api-Key": api_key,
                    "Accept": "application/json"
                },
                timeout=30
            )
            
            if regular_response.status_code == 200:
                regular_data = regular_response.json()
                if regular_data.get("error") is None and regular_data.get("data", {}).get("avatars"):
                    avatars = regular_data["data"]["avatars"]
                    for avatar in avatars:
                        avatar_data = {
                            "avatar_id": avatar.get("avatar_id"),
                            "avatar_name": avatar.get("avatar_name"),
                            "avatar_type": "regular",
                            "preview_image_url": avatar.get("preview_image_url"),
                            "preview_video_url": avatar.get("preview_video_url"),
                            "gender": avatar.get("gender"),
                            "source": "regular_api"
                        }
                        all_avatars.append(avatar_data)
                    log_info(f"Fetched {len(avatars)} regular avatars", "AdminRoutes")
        
        except Exception as e:
            log_error(f"Error fetching regular avatars: {str(e)}", "AdminRoutes")
        
        # 2. Get photo avatar groups
        try:
            photo_groups_response = requests.get(
                "https://api.heygen.com/v2/avatar_group.list",
                headers={
                    "X-Api-Key": api_key,
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            
            if photo_groups_response.status_code == 200:
                groups_data = photo_groups_response.json()
                if groups_data.get("error") is None:
                    groups = groups_data.get("data", {}).get("avatar_group_list", [])
                    log_info(f"Found {len(groups)} photo avatar groups", "AdminRoutes")
                    
                    # Get avatars from each group
                    for group in groups:
                        group_id = group.get("id")
                        if group_id:
                            try:
                                group_avatars_response = requests.get(
                                    f"https://api.heygen.com/v2/avatar_group/{group_id}/avatars",
                                    headers={
                                        "X-Api-Key": api_key,
                                        "Content-Type": "application/json"
                                    },
                                    timeout=30
                                )
                                
                                if group_avatars_response.status_code == 200:
                                    group_data = group_avatars_response.json()
                                    if group_data.get("error") is None:
                                        avatar_list = group_data.get("data", {}).get("avatar_list", [])
                                        for avatar in avatar_list:
                                            if avatar.get("status") == "completed":
                                                # Photo avatars use different field names
                                                avatar_data = {
                                                    "avatar_id": avatar.get("id"),  # Photo avatars use 'id'
                                                    "avatar_name": f"{group.get('name', 'Photo Avatar')} - {avatar.get('name', 'Look')}",
                                                    "avatar_type": "photo",
                                                    "preview_image_url": avatar.get("image_url"),  # THIS IS THE KEY FIX
                                                    "preview_video_url": avatar.get("motion_preview_url"),
                                                    "gender": None,
                                                    "source": "photo_api",
                                                    "group_id": group_id,
                                                    "group_name": group.get("name")
                                                }
                                                all_avatars.append(avatar_data)
                                        log_info(f"Added {len(avatar_list)} avatars from group {group.get('name')}", "AdminRoutes")
                            except Exception as e:
                                log_error(f"Error fetching avatars from group {group_id}: {str(e)}", "AdminRoutes")
        
        except Exception as e:
            log_error(f"Error fetching photo avatar groups: {str(e)}", "AdminRoutes")
        
        log_info(f"Total avatars fetched: {len(all_avatars)}", "AdminRoutes")
        
        return {
            "success": True,
            "avatars": all_avatars,
            "total_count": len(all_avatars)
        }
        
    except Exception as e:
        log_error(f"Error in get_all_heygen_avatars_with_photo_support: {str(e)}", "AdminRoutes")
        return {"success": False, "error": str(e)}

def fetch_and_update_avatars_with_naming():
    """
    Updated function to fetch avatars from HeyGen with enhanced naming logic.
    Use this to replace your existing avatar fetching code.
    """
    try:
        # Use the enhanced avatar fetching function
        result = get_all_heygen_avatars_with_photo_support()
        
        if not result.get('success', False):
            log_error("Failed to fetch avatars from HeyGen", "AdminRoutes")
            return {"success": False, "error": "Failed to fetch from HeyGen"}
        
        avatars_data = result.get('avatars', [])
        log_info(f"Fetched {len(avatars_data)} avatars from HeyGen", "AdminRoutes")
        
        updated_count = 0
        
        # Process each avatar with enhanced naming
        for avatar in avatars_data:
            avatar_id = avatar.get('avatar_id')
            if not avatar_id:
                continue
            
            # Use enhanced naming logic
            user_friendly_name = generate_user_friendly_name(avatar)
            
            # Get other avatar data
            preview_url = avatar.get('preview_image_url', '')
            preview_url_mp4 = avatar.get('preview_video_url', '')
            
            # Check if avatar already exists
            existing_avatar = execute_query(
                "SELECT id, name FROM user_avatars WHERE avatar_id = ?",
                (avatar_id,),
                fetch_one=True
            )
            
            if existing_avatar:
                # Update existing avatar if name has improved
                current_name = existing_avatar['name']
                if is_technical_id(current_name) and not is_technical_id(user_friendly_name):
                    if USE_POSTGRES:
                        execute_query(
                            "UPDATE user_avatars SET name = %s, preview_url = %s, preview_url_mp4 = %s WHERE avatar_id = %s",
                            (user_friendly_name, preview_url, preview_url_mp4, avatar_id)
                        )
                    else:
                        execute_query(
                            "UPDATE user_avatars SET name = ?, preview_url = ?, preview_url_mp4 = ? WHERE avatar_id = ?",
                            (user_friendly_name, preview_url, preview_url_mp4, avatar_id)
                        )
                    log_info(f"Updated avatar {avatar_id}: '{current_name}' → '{user_friendly_name}'", "AdminRoutes")
                    updated_count += 1
            else:
                # Insert new avatar with user-friendly name
                if USE_POSTGRES:
                    execute_query(
                        "INSERT INTO user_avatars (avatar_id, name, preview_url, preview_url_mp4) VALUES (%s, %s, %s, %s)",
                        (avatar_id, user_friendly_name, preview_url, preview_url_mp4)
                    )
                else:
                    execute_query(
                        "INSERT INTO user_avatars (avatar_id, name, preview_url, preview_url_mp4) VALUES (?, ?, ?, ?)",
                        (avatar_id, user_friendly_name, preview_url, preview_url_mp4)
                    )
                log_info(f"Added new avatar {avatar_id}: '{user_friendly_name}'", "AdminRoutes")
                updated_count += 1
        
        return {
            "success": True,
            "total_avatars": len(avatars_data),
            "updated_count": updated_count,
            "message": f"Successfully processed {len(avatars_data)} avatars, updated {updated_count} names"
        }
        
    except Exception as e:
        log_error(f"Error in fetch_and_update_avatars_with_naming: {str(e)}", "AdminRoutes", e)
        return {"success": False, "error": str(e)}

# =============================================================================
# EXISTING ADMIN ROUTES (UNCHANGED)
# =============================================================================

@router.get("/")
async def admin_main(request: Request):
    """Main admin route - redirect to dashboard"""
    try:
        # Require admin access
        require_admin(request)
        # Redirect to dashboard
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    except HTTPException as e:
        if e.status_code == 401:
            return RedirectResponse(url="/login", status_code=303)
        elif e.status_code == 403:
            return RedirectResponse(url="/dashboard", status_code=303)
        raise

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
            "UPDATE users SET hashed_password = ? WHERE id = ?",
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
        
        # FIXED QUERY - Use MAX to pick one avatar per user for GROUP BY
        users = execute_query("""
            SELECT u.id, u.username, u.email, u.created_at, u.last_login, u.is_admin,
                   u.heygen_voice_id,
                   MAX(ua.avatar_id) as avatar_id, 
                   MAX(ua.avatar_name) as avatar_name, 
                   MAX(ua.avatar_image_url) as avatar_image_url,
                   COUNT(DISTINCT v.id) as video_count,
                   COUNT(DISTINCT ua2.id) as avatar_count
            FROM users u
            LEFT JOIN videos v ON u.id = v.user_id
            LEFT JOIN user_avatars ua ON u.id = ua.user_id AND ua.avatar_image_url IS NOT NULL
            LEFT JOIN user_avatars ua2 ON u.id = ua2.user_id
            GROUP BY u.id, u.username, u.email, u.created_at, u.last_login, u.is_admin, u.heygen_voice_id
            ORDER BY u.id
        """, fetch_all=True)
        
        return templates.TemplateResponse(
            "portal/admin_users.html",
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

@router.post("/delete-user/{user_id}")
async def delete_user(request: Request, user_id: int):
    """Delete a user and all their data (admin only) - FIXED VERSION"""
    try:
        # Require admin access
        admin_user = require_admin(request)
        
        # Get user details first for success message
        user_to_delete = execute_query(
            "SELECT id, username FROM users WHERE id = %s",
            (user_id,),
            fetch_one=True
        )
        
        if not user_to_delete:
            log_warning(f"User {user_id} not found for deletion", "AdminRoutes")
            return RedirectResponse(
                url="/admin/users?error=user_not_found",
                status_code=303
            )
        
        username = user_to_delete['username']
        
        # Don't allow deleting yourself
        if user_to_delete['id'] == admin_user['id']:
            log_warning(f"Admin {admin_user['username']} tried to delete themselves", "AdminRoutes")
            return RedirectResponse(
                url="/admin/users?error=cannot_delete_yourself",
                status_code=303
            )
        
        try:
            # Delete user's data in proper order (foreign key constraints)
            log_info(f"Starting deletion of user {username} (ID: {user_id})", "AdminRoutes")
            
            # Delete user's videos first (foreign key constraint)
            execute_query("DELETE FROM videos WHERE user_id = %s", (user_id,))
            
            # Delete user's avatars
            execute_query("DELETE FROM user_avatars WHERE user_id = %s", (user_id,))
            
            # Delete user's images
            execute_query("DELETE FROM user_images WHERE user_id = %s", (user_id,))
            
            # Delete user's voices
            execute_query("DELETE FROM user_voices WHERE user_id = %s", (user_id,))
            
            # Finally delete the user
            execute_query("DELETE FROM users WHERE id = %s", (user_id,))
            
            log_info(f"Admin {admin_user['username']} successfully deleted user {username} (ID: {user_id})", "AdminRoutes")
            
            # FIXED: Redirect with success message
            return RedirectResponse(
                url=f"/admin/users?success=user_deleted&username={username}",
                status_code=303
            )
            
        except Exception as delete_error:
            log_error(f"Error during user deletion process: {str(delete_error)}", "AdminRoutes", delete_error)
            return RedirectResponse(
                url="/admin/users?error=delete_failed",
                status_code=303
            )
        
    except HTTPException as e:
        if e.status_code == 401:
            return RedirectResponse(url="/login", status_code=303)
        elif e.status_code == 403:
            return RedirectResponse(url="/dashboard", status_code=303)
        raise
    except Exception as e:
        log_error("Error in delete_user route", "AdminRoutes", e)
        return RedirectResponse(
            url="/admin/users?error=delete_failed",
            status_code=303
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

@router.get("/manage-avatars/{user_id}")
async def manage_user_avatars(request: Request, user_id: int):
    """Admin avatar management page for specific user - FIXED VERSION"""
    try:
        # Require admin access
        admin_user = require_admin(request)
        
        # Get user details
        if USE_POSTGRES:
            user_to_manage = execute_query(
                "SELECT id, username, email FROM users WHERE id = %s",
                (user_id,),
                fetch_one=True
            )
        else:
            user_to_manage = execute_query(
                "SELECT id, username, email FROM users WHERE id = ?",
                (user_id,),
                fetch_one=True
            )
        
        if not user_to_manage:
            return RedirectResponse(url="/admin/users?error=user_not_found", status_code=303)
        
        # FIXED QUERY - Now includes avatar_image_url
        if USE_POSTGRES:
            avatars = execute_query("""
                SELECT id, avatar_id, avatar_name, avatar_image_url, created_at, is_default
                FROM user_avatars 
                WHERE user_id = %s 
                ORDER BY created_at DESC
            """, (user_id,), fetch_all=True)
        else:
            avatars = execute_query("""
                SELECT id, avatar_id, avatar_name, avatar_image_url, created_at, is_default
                FROM user_avatars 
                WHERE user_id = ? 
                ORDER BY created_at DESC
            """, (user_id,), fetch_all=True)
        
        log_info(f"Found {len(avatars) if avatars else 0} avatars for user {user_to_manage['username']}", "AdminRoutes")
        
        return templates.TemplateResponse(
            "portal/admin_manage_avatars.html",
            {
                "request": request,
                "user": admin_user,
                "user_to_manage": user_to_manage,
                "avatars": avatars or [],
                "total_avatars": len(avatars) if avatars else 0,
                "title": f"Manage Avatars - {user_to_manage['username']}"
            }
        )
    except HTTPException as e:
        if e.status_code == 401:
            return RedirectResponse(url="/login", status_code=303)
        elif e.status_code == 403:
            return RedirectResponse(url="/dashboard", status_code=303)
        raise
    except Exception as e:
        log_error("Error displaying avatar management page", "AdminRoutes", e)
        return JSONResponse(
            status_code=500,
            content={"error": "Avatar management error", "detail": str(e)}
        )

@router.post("/fetch-heygen-avatar/{user_id}")
async def fetch_avatar_from_heygen(request: Request, user_id: int):
    """Fetch avatar image from HeyGen API and save to user - UPDATED WITH ENHANCED NAMING"""
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
        if USE_POSTGRES:
            user_to_manage = execute_query(
                "SELECT id, username FROM users WHERE id = %s",
                (user_id,),
                fetch_one=True
            )
        else:
            user_to_manage = execute_query(
                "SELECT id, username FROM users WHERE id = ?",
                (user_id,),
                fetch_one=True
            )
        
        if not user_to_manage:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Import HeyGen functions
        import requests
        import uuid
        from pathlib import Path
        
        try:
            # Use the enhanced avatar fetching function
            avatars_result = get_all_heygen_avatars_with_photo_support()
            
            if not avatars_result.get("success"):
                return JSONResponse(
                    content={"success": False, "error": f"Failed to fetch avatars from HeyGen: {avatars_result.get('error', 'Unknown error')}"},
                    status_code=400
                )
            
            # Find the specific avatar by ID
            avatars = avatars_result.get("avatars", [])
            avatar_details = None
            
            # Debug: Log the search details
            log_info(f"Searching for avatar ID: {avatar_id}", "AdminRoutes")
            log_info(f"Total avatars available: {len(avatars)}", "AdminRoutes")
            
            for avatar in avatars:
                if avatar.get("avatar_id") == avatar_id:
                    avatar_details = avatar
                    break
            
            if not avatar_details:
                return JSONResponse(
                    content={"success": False, "error": f"Avatar with ID '{avatar_id}' not found in your HeyGen account"},
                    status_code=404
                )
            
            # USE ENHANCED NAMING LOGIC
            avatar_name = generate_user_friendly_name(avatar_details)
            
            # Use the correct image URL field (handles both regular and photo avatars)
            avatar_image_url = avatar_details.get("preview_image_url")
            
            if not avatar_image_url:
                return JSONResponse(
                    content={"success": False, "error": "No image URL found for this avatar"},
                    status_code=400
                )
            
            # Download the avatar image from HeyGen
            try:
                log_info(f"Downloading avatar image from: {avatar_image_url}", "AdminRoutes")
                image_response = requests.get(avatar_image_url, timeout=30)
                image_response.raise_for_status()
                
                # Generate unique filename
                file_extension = ".jpg"  # Default to jpg
                if "png" in avatar_image_url.lower():
                    file_extension = ".png"
                elif "jpeg" in avatar_image_url.lower() or "jpg" in avatar_image_url.lower():
                    file_extension = ".jpg"
                
                unique_filename = f"avatar_{avatar_id}_{uuid.uuid4().hex[:8]}{file_extension}"
                
                # Ensure uploads directory exists
                uploads_dir = Path("static/uploads")
                uploads_dir.mkdir(parents=True, exist_ok=True)
                
                # Save image to local storage
                image_path = uploads_dir / unique_filename
                with open(image_path, "wb") as f:
                    f.write(image_response.content)
                
                log_info(f"Avatar image saved to: {image_path}", "AdminRoutes")
                
                # Save image record to user_images table
                relative_path = f"static/uploads/{unique_filename}"
                
                # Insert image record
                if USE_POSTGRES:
                    execute_query(
                        "INSERT INTO user_images (user_id, filename, original_filename, file_path, file_size, content_type, created_at) VALUES (%s, %s, %s, %s, %s, %s, NOW())",
                        (user_id, unique_filename, f"{avatar_name}{file_extension}", relative_path, len(image_response.content), f"image/{file_extension[1:]}")
                    )
                else:
                    execute_query(
                        "INSERT INTO user_images (user_id, filename, original_filename, file_path, file_size, content_type, created_at) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
                        (user_id, unique_filename, f"{avatar_name}{file_extension}", relative_path, len(image_response.content), f"image/{file_extension[1:]}")
                    )
                
                log_info(f"Avatar image added to user {user_to_manage['username']}'s gallery", "AdminRoutes")
                
            except Exception as img_error:
                log_error(f"Failed to download/save avatar image: {str(img_error)}", "AdminRoutes")
                # Continue with avatar data even if image download fails
                relative_path = avatar_image_url  # Use original URL as fallback
            
            # Check if avatar already exists for this user
            if USE_POSTGRES:
                existing_avatar = execute_query(
                    "SELECT id FROM user_avatars WHERE user_id = %s AND avatar_id = %s",
                    (user_id, avatar_id),
                    fetch_one=True
                )
            else:
                existing_avatar = execute_query(
                    "SELECT id FROM user_avatars WHERE user_id = ? AND avatar_id = ?",
                    (user_id, avatar_id),
                    fetch_one=True
                )
            
            if existing_avatar:
                # Update existing avatar with enhanced name
                if USE_POSTGRES:
                    execute_query(
                        "UPDATE user_avatars SET avatar_name = %s, avatar_image_url = %s WHERE user_id = %s AND avatar_id = %s",
                        (avatar_name, avatar_image_url, user_id, avatar_id)
                    )
                else:
                    execute_query(
                        "UPDATE user_avatars SET avatar_name = ?, avatar_image_url = ? WHERE user_id = ? AND avatar_id = ?",
                        (avatar_name, avatar_image_url, user_id, avatar_id)
                    )
                log_info(f"Admin {admin_user['username']} updated avatar {avatar_id} for user {user_to_manage['username']} with enhanced name: '{avatar_name}'", "AdminRoutes")
            else:
                # Insert new avatar with enhanced name
                if USE_POSTGRES:
                    execute_query(
                        "INSERT INTO user_avatars (user_id, avatar_id, avatar_name, avatar_image_url) VALUES (%s, %s, %s, %s)",
                        (user_id, avatar_id, avatar_name, avatar_image_url)
                    )
                else:
                    execute_query(
                        "INSERT INTO user_avatars (user_id, avatar_id, avatar_name, avatar_image_url) VALUES (?, ?, ?, ?)",
                        (user_id, avatar_id, avatar_name, avatar_image_url)
                    )
                log_info(f"Admin {admin_user['username']} added avatar {avatar_id} for user {user_to_manage['username']} with enhanced name: '{avatar_name}'", "AdminRoutes")
            
            return JSONResponse(
                content={
                    "success": True, 
                    "message": "Avatar fetched and saved successfully with enhanced naming! Image also added to user gallery!",
                    "avatar": {
                        "id": avatar_id,
                        "name": avatar_name,
                        "image_url": avatar_image_url,
                        "local_image_path": relative_path
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

@router.post("/delete-image/{image_id}")
async def delete_user_image(request: Request, image_id: str):
    """Delete a user avatar (admin only) - FIXED VERSION"""
    log_info(f"🚨 DELETE ROUTE CALLED! image_id: {image_id}", "AdminRoutes")
    user_id = None
    try:
        log_info(f"🔍 DEBUG: Delete request for image_id: {image_id} (type: {type(image_id)})", "AdminRoutes")
        
        # Verify admin access
        admin_user = require_admin(request)
        
        # Convert image_id to int if it's numeric, otherwise use as string
        try:
            numeric_id = int(image_id)
            log_info(f"🔍 DEBUG: Converted image_id to int: {numeric_id}", "AdminRoutes")
        except ValueError:
            log_info(f"🔍 DEBUG: Using image_id as string: {image_id}", "AdminRoutes")
            numeric_id = image_id
        
        # Get avatar details before deletion
        if USE_POSTGRES:
            avatar = execute_query(
                "SELECT id, user_id, avatar_name, avatar_image_url FROM user_avatars WHERE id = %s",
                (numeric_id,),
                fetch_one=True
            )
        else:
            avatar = execute_query(
                "SELECT id, user_id, avatar_name, avatar_image_url FROM user_avatars WHERE id = ?",
                (numeric_id,),
                fetch_one=True
            )
        
        log_info(f"🔍 DEBUG: Avatar query result: {avatar}", "AdminRoutes")
        
        if not avatar:
            log_warning(f"🔍 DEBUG: Avatar not found for id: {numeric_id}", "AdminRoutes")
            return RedirectResponse(
                url="/admin/users?error=avatar_not_found",
                status_code=303
            )
        
        user_id = avatar['user_id']  # Store user_id for redirect
        log_info(f"🔍 DEBUG: Found avatar for user_id: {user_id}", "AdminRoutes")
        
        # Get user info for logging
        if USE_POSTGRES:
            user = execute_query(
                "SELECT username FROM users WHERE id = %s",
                (user_id,),
                fetch_one=True
            )
        else:
            user = execute_query(
                "SELECT username FROM users WHERE id = ?",
                (user_id,),
                fetch_one=True
            )
        
        # Note: For HeyGen avatars, we don't delete physical files since they're external URLs
        # Only delete local uploaded files if needed in the future
        
        # Delete from database
        log_info(f"🔍 DEBUG: About to delete avatar with id: {numeric_id}", "AdminRoutes")
        if USE_POSTGRES:
            delete_result = execute_query("DELETE FROM user_avatars WHERE id = %s", (numeric_id,))
        else:
            delete_result = execute_query("DELETE FROM user_avatars WHERE id = ?", (numeric_id,))
        log_info(f"🔍 DEBUG: Delete result: {delete_result}", "AdminRoutes")
        
        log_info(f"Admin {admin_user['username']} deleted avatar {numeric_id} ('{avatar['avatar_name']}') for user {user['username'] if user else 'Unknown'}", "AdminRoutes")
        
        # FIXED: Redirect back to avatar management page with success message
        return RedirectResponse(
            url=f"/admin/manage-avatars/{user_id}?success=avatar_deleted",
            status_code=303
        )
        
    except HTTPException as e:
        if e.status_code == 401:
            return RedirectResponse(url="/login?error=admin_required", status_code=303)
        elif e.status_code == 403:
            return RedirectResponse(url="/admin/users?error=access_denied", status_code=303)
        raise
    except Exception as e:
        log_error("Error deleting user image", "AdminRoutes", e)
        if user_id:
            return RedirectResponse(
                url=f"/admin/manage-avatars/{user_id}?error=delete_failed",
                status_code=303
            )
        else:
            return RedirectResponse(
                url="/admin/users?error=delete_failed",
                status_code=303
            )

# =============================================================================
# NEW ENHANCED AVATAR MANAGEMENT ENDPOINTS
# =============================================================================

@router.post("/update-avatar-name")
async def update_avatar_name(request: Request):
    """Update a specific avatar's name"""
    try:
        # Require admin access
        admin_user = require_admin(request)
        
        # Get form data
        form = await request.form()
        avatar_id = form.get("avatar_id", "").strip()
        new_name = form.get("new_name", "").strip()
        
        if not avatar_id or not new_name:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Avatar ID and new name are required"}
            )
        
        # Update avatar name in database
        if USE_POSTGRES:
            result = execute_query(
                "UPDATE user_avatars SET avatar_name = %s WHERE id = %s",
                (new_name, avatar_id)
            )
        else:
            result = execute_query(
                "UPDATE user_avatars SET avatar_name = ? WHERE id = ?",
                (new_name, avatar_id)
            )
        
        # Get avatar info for logging
        if USE_POSTGRES:
            avatar = execute_query(
                "SELECT user_id, avatar_name FROM user_avatars WHERE id = %s",
                (avatar_id,),
                fetch_one=True
            )
        else:
            avatar = execute_query(
                "SELECT user_id, avatar_name FROM user_avatars WHERE id = ?",
                (avatar_id,),
                fetch_one=True
            )
        
        if avatar:
            log_info(f"Admin {admin_user['username']} updated avatar {avatar_id} name to '{new_name}'", "AdminRoutes")
            return JSONResponse(content={"success": True, "message": "Avatar name updated successfully"})
        else:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Avatar not found"}
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
        log_error("Error updating avatar name", "AdminRoutes", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/update-avatar-names")
async def update_avatar_names_endpoint(request: Request):
    """Admin endpoint to trigger avatar name updates"""
    try:
        # Require admin access
        admin_user = require_admin(request)
        
        # Run the enhanced avatar fetching and naming
        result = fetch_and_update_avatars_with_naming()
        
        log_info(f"Admin {admin_user['username']} triggered avatar name update", "AdminRoutes")
        
        return JSONResponse(content=result)
        
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
        log_error("Error updating avatar names", "AdminRoutes", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/create-user")
async def create_user_form(request: Request):
    """Admin create user form"""
    try:
        # Require admin access
        user = require_admin(request)
        
        return templates.TemplateResponse(
            "portal/admin_create_user.html",
            {
                "request": request,
                "user": user,
                "title": "Create New User"
            }
        )
    except HTTPException as e:
        if e.status_code == 401:
            return RedirectResponse(url="/login", status_code=303)
        elif e.status_code == 403:
            return RedirectResponse(url="/dashboard", status_code=303)
        raise
    except Exception as e:
        log_error("Error displaying create user form", "AdminRoutes", e)
        return JSONResponse(
            status_code=500,
            content={"error": "Create user form error", "detail": str(e)}
        )

@router.get("/edit-user/{user_id}")
async def edit_user_form(request: Request, user_id: int):
    """Admin edit user form"""
    try:
        # Require admin access
        admin_user = require_admin(request)
        
        # Get user to edit
        if USE_POSTGRES:
            user_to_edit = execute_query(
                "SELECT * FROM users WHERE id = %s",
                (user_id,),
                fetch_one=True
            )
        else:
            user_to_edit = execute_query(
                "SELECT * FROM users WHERE id = ?",
                (user_id,),
                fetch_one=True
            )
        
        if not user_to_edit:
            return RedirectResponse(url="/admin/users?error=user_not_found", status_code=303)
        
        return templates.TemplateResponse(
            "portal/admin_edit_user.html",
            {
                "request": request,
                "user": admin_user,
                "user_to_edit": user_to_edit,
                "title": f"Edit User - {user_to_edit['username']}"
            }
        )
    except HTTPException as e:
        if e.status_code == 401:
            return RedirectResponse(url="/login", status_code=303)
        elif e.status_code == 403:
            return RedirectResponse(url="/dashboard", status_code=303)
        raise
    except Exception as e:
        log_error("Error displaying edit user form", "AdminRoutes", e)
        return JSONResponse(
            status_code=500,
            content={"error": "Edit user form error", "detail": str(e)}
        )

@router.get("/emergency-controls")
async def emergency_controls(request: Request):
    """Admin emergency controls page"""
    try:
        # Require admin access
        user = require_admin(request)
        
        # Get system stats for emergency overview
        stats = {
            "total_users": execute_query("SELECT COUNT(*) as count FROM users", fetch_one=True),
            "total_videos": execute_query("SELECT COUNT(*) as count FROM videos", fetch_one=True),
            "failed_videos": execute_query("SELECT COUNT(*) as count FROM videos WHERE status = 'failed'", fetch_one=True),
            "pending_videos": execute_query("SELECT COUNT(*) as count FROM videos WHERE status = 'pending'", fetch_one=True)
        }
        
        return templates.TemplateResponse(
            "portal/admin_emergency_controls.html",
            {
                "request": request,
                "user": user,
                "stats": stats,
                "title": "Emergency Controls"
            }
        )
    except HTTPException as e:
        if e.status_code == 401:
            return RedirectResponse(url="/login", status_code=303)
        elif e.status_code == 403:
            return RedirectResponse(url="/dashboard", status_code=303)
        raise
    except Exception as e:
        log_error("Error displaying emergency controls page", "AdminRoutes", e)
        return JSONResponse(
            status_code=500,
            content={"error": "Emergency controls error", "detail": str(e)}
        )