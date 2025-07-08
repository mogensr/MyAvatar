"""
Admin routes for MyAvatar
"""
import os
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse
import re
import requests

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
# PHOTO AVATAR URL REFRESH FUNCTIONS
# =============================================================================

def is_photo_avatar_url(url):
    """Check if URL is a photo avatar (signed URL that expires)"""
    if not url:
        return False
    return '/talking_photo/' in url and 'Expires=' in url

def is_url_expired(url):
    """Check if a signed URL has expired"""
    if not is_photo_avatar_url(url):
        return False
    
    try:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        expires_timestamp = query_params.get('Expires', [None])[0]
        
        if expires_timestamp:
            expires_time = datetime.fromtimestamp(int(expires_timestamp), tz=timezone.utc)
            current_time = datetime.now(timezone.utc)
            is_expired = current_time >= expires_time
            
            log_info(f"URL expires: {expires_time}, Current: {current_time}, Expired: {is_expired}", "PhotoAvatarRefresh")
            return is_expired
    except Exception as e:
        log_error(f"Error checking URL expiration: {e}", "PhotoAvatarRefresh")
        return True  # Assume expired if we can't parse
    
    return False

def get_fresh_photo_avatar_url(avatar_id):
    """Get a fresh image URL for a photo avatar from HeyGen API"""
    try:
        api_key = os.getenv("HEYGEN_API_KEY")
        if not api_key:
            log_error("No HeyGen API key found", "PhotoAvatarRefresh")
            return None
        
        log_info(f"Refreshing photo avatar URL for: {avatar_id}", "PhotoAvatarRefresh")
        
        # Get all photo avatar groups
        response = requests.get(
            "https://api.heygen.com/v2/avatar_group.list",
            headers={
                "X-Api-Key": api_key,
                "Content-Type": "application/json"
            },
            timeout=30
        )
        
        if response.status_code != 200:
            log_error(f"Failed to get avatar groups: {response.status_code}", "PhotoAvatarRefresh")
            return None
        
        groups_data = response.json()
        groups = groups_data.get("data", {}).get("avatar_group_list", [])
        
        # Search through all groups for the avatar
        for group in groups:
            group_id = group.get("id")
            if not group_id:
                continue
                
            try:
                # Get avatars in this group
                group_response = requests.get(
                    f"https://api.heygen.com/v2/avatar_group/{group_id}/avatars",
                    headers={
                        "X-Api-Key": api_key,
                        "Content-Type": "application/json"
                    },
                    timeout=30
                )
                
                if group_response.status_code == 200:
                    group_data = group_response.json()
                    avatar_list = group_data.get("data", {}).get("avatar_list", [])
                    
                    # Look for our avatar
                    for avatar in avatar_list:
                        if avatar.get("id") == avatar_id and avatar.get("status") == "completed":
                            fresh_url = avatar.get("image_url")
                            if fresh_url:
                                log_info(f"Found fresh URL for {avatar_id}: {fresh_url[:50]}...", "PhotoAvatarRefresh")
                                return fresh_url
                            
            except Exception as e:
                log_error(f"Error checking group {group_id}: {e}", "PhotoAvatarRefresh")
                continue
        
        log_warning(f"Could not find fresh URL for photo avatar: {avatar_id}", "PhotoAvatarRefresh")
        return None
        
    except Exception as e:
        log_error(f"Error getting fresh photo avatar URL: {e}", "PhotoAvatarRefresh")
        return None

def refresh_photo_avatar_urls():
    """Refresh all expired photo avatar URLs in the database"""
    try:
        log_info("Starting photo avatar URL refresh process", "PhotoAvatarRefresh")
        
        # Get all avatars with photo URLs
        avatars = execute_query(
            "SELECT id, avatar_id, avatar_name, avatar_image_url FROM user_avatars WHERE avatar_image_url IS NOT NULL",
            fetch_all=True
        )
        
        refreshed_count = 0
        
        for avatar in avatars:
            avatar_db_id = avatar['id']
            avatar_id = avatar['avatar_id']
            avatar_name = avatar['avatar_name']
            current_url = avatar['avatar_image_url']
            
            # Check if this is a photo avatar and if URL is expired
            if is_photo_avatar_url(current_url) and is_url_expired(current_url):
                log_info(f"Refreshing expired URL for {avatar_name} ({avatar_id})", "PhotoAvatarRefresh")
                
                # Get fresh URL
                fresh_url = get_fresh_photo_avatar_url(avatar_id)
                
                if fresh_url:
                    # Update database with fresh URL
                    if USE_POSTGRES:
                        execute_query(
                            "UPDATE user_avatars SET avatar_image_url = %s WHERE id = %s",
                            (fresh_url, avatar_db_id)
                        )
                    else:
                        execute_query(
                            "UPDATE user_avatars SET avatar_image_url = ? WHERE id = ?",
                            (fresh_url, avatar_db_id)
                        )
                    
                    refreshed_count += 1
                    log_info(f"✅ Refreshed URL for {avatar_name}", "PhotoAvatarRefresh")
                else:
                    log_warning(f"❌ Could not get fresh URL for {avatar_name}", "PhotoAvatarRefresh")
        
        log_info(f"Photo avatar refresh complete. Refreshed {refreshed_count} URLs", "PhotoAvatarRefresh")
        return {
            "success": True,
            "refreshed_count": refreshed_count,
            "message": f"Successfully refreshed {refreshed_count} photo avatar URLs"
        }
        
    except Exception as e:
        log_error(f"Error in refresh_photo_avatar_urls: {e}", "PhotoAvatarRefresh")
        return {
            "success": False,
            "error": str(e)
        }

def refresh_single_avatar_url(avatar_db_id):
    """Refresh URL for a single avatar"""
    try:
        # Get avatar details
        if USE_POSTGRES:
            avatar = execute_query(
                "SELECT id, avatar_id, avatar_name, avatar_image_url FROM user_avatars WHERE id = %s",
                (avatar_db_id,),
                fetch_one=True
            )
        else:
            avatar = execute_query(
                "SELECT id, avatar_id, avatar_name, avatar_image_url FROM user_avatars WHERE id = ?",
                (avatar_db_id,),
                fetch_one=True
            )
        
        if not avatar:
            return {"success": False, "error": "Avatar not found"}
        
        avatar_id = avatar['avatar_id']
        avatar_name = avatar['avatar_name']
        current_url = avatar['avatar_image_url']
        
        # Only refresh if it's a photo avatar
        if not is_photo_avatar_url(current_url):
            return {"success": False, "error": "Not a photo avatar - no refresh needed"}
        
        # Get fresh URL
        fresh_url = get_fresh_photo_avatar_url(avatar_id)
        
        if fresh_url:
            # Update database
            if USE_POSTGRES:
                execute_query(
                    "UPDATE user_avatars SET avatar_image_url = %s WHERE id = %s",
                    (fresh_url, avatar_db_id)
                )
            else:
                execute_query(
                    "UPDATE user_avatars SET avatar_image_url = ? WHERE id = ?",
                    (fresh_url, avatar_db_id)
                )
            
            log_info(f"✅ Refreshed URL for {avatar_name}", "PhotoAvatarRefresh")
            return {
                "success": True,
                "message": f"Successfully refreshed URL for {avatar_name}",
                "new_url": fresh_url
            }
        else:
            return {
                "success": False,
                "error": f"Could not get fresh URL for {avatar_name}"
            }
            
    except Exception as e:
        log_error(f"Error refreshing single avatar URL: {e}", "PhotoAvatarRefresh")
        return {
            "success": False,
            "error": str(e)
        }

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
# ADMIN ROUTES
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
    """Admin dashboard page with auto photo avatar refresh"""
    try:
        # Require admin access
        user = require_admin(request)
        
        # AUTO-REFRESH EXPIRED PHOTO AVATARS when admin accesses dashboard
        try:
            refresh_result = refresh_photo_avatar_urls()
            if refresh_result.get("refreshed_count", 0) > 0:
                log_info(f"🔄 Auto-refreshed {refresh_result['refreshed_count']} expired photo avatars for admin {user['username']}", "AdminRoutes")
        except Exception as refresh_error:
            log_error(f"Auto-refresh failed: {refresh_error}", "AdminRoutes")
        
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

# =============================================================================
# FIXED DELETE FUNCTIONS - CLEAR SEPARATION
# =============================================================================

@router.post("/delete-user/{user_id}")
async def delete_user(request: Request, user_id: int):
    """Delete a user completely (admin only) - FIXED VERSION"""
    try:
        # Require admin access
        admin_user = require_admin(request)
        
        # Get user details first for logging and validation
        if USE_POSTGRES:
            user_to_delete = execute_query(
                "SELECT id, username, email, is_admin FROM users WHERE id = %s",
                (user_id,),
                fetch_one=True
            )
        else:
            user_to_delete = execute_query(
                "SELECT id, username, email, is_admin FROM users WHERE id = ?",
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
        
        # Don't allow deleting other admins (optional security measure)
        if user_to_delete.get('is_admin', 0) == 1:
            log_warning(f"Admin {admin_user['username']} tried to delete another admin: {username}", "AdminRoutes")
            return RedirectResponse(
                url="/admin/users?error=cannot_delete_admin",
                status_code=303
            )
        
        try:
            # Delete user's data in proper order (foreign key constraints)
            log_info(f"Starting deletion of user {username} (ID: {user_id})", "AdminRoutes")
            
            # Delete user's videos first (foreign key constraint)
            if USE_POSTGRES:
                video_count = execute_query("SELECT COUNT(*) as count FROM videos WHERE user_id = %s", (user_id,), fetch_one=True)
                execute_query("DELETE FROM videos WHERE user_id = %s", (user_id,))
            else:
                video_count = execute_query("SELECT COUNT(*) as count FROM videos WHERE user_id = ?", (user_id,), fetch_one=True)
                execute_query("DELETE FROM videos WHERE user_id = ?", (user_id,))
            
            # Delete user's avatars
            if USE_POSTGRES:
                avatar_count = execute_query("SELECT COUNT(*) as count FROM user_avatars WHERE user_id = %s", (user_id,), fetch_one=True)
                execute_query("DELETE FROM user_avatars WHERE user_id = %s", (user_id,))
            else:
                avatar_count = execute_query("SELECT COUNT(*) as count FROM user_avatars WHERE user_id = ?", (user_id,), fetch_one=True)
                execute_query("DELETE FROM user_avatars WHERE user_id = ?", (user_id,))
            
            # REMOVED: user_images deletion - table doesn't exist
            # REMOVED: user_voices deletion - table doesn't exist
            
            # Finally delete the user
            if USE_POSTGRES:
                execute_query("DELETE FROM users WHERE id = %s", (user_id,))
            else:
                execute_query("DELETE FROM users WHERE id = ?", (user_id,))
            
            log_info(f"Admin {admin_user['username']} successfully deleted user {username} (ID: {user_id}) with {video_count['count']} videos and {avatar_count['count']} avatars", "AdminRoutes")
            
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

@router.post("/delete-avatar/{avatar_id}")
async def delete_avatar(request: Request, avatar_id: int):
    """Delete a specific avatar (admin only) - RENAMED FROM delete_user_image"""
    try:
        log_info(f"🚨 DELETE AVATAR ROUTE CALLED! avatar_id: {avatar_id}", "AdminRoutes")
        
        # Verify admin access
        admin_user = require_admin(request)
        
        # Get avatar details before deletion
        if USE_POSTGRES:
            avatar = execute_query(
                "SELECT id, user_id, avatar_name, avatar_image_url, avatar_id as heygen_id FROM user_avatars WHERE id = %s",
                (avatar_id,),
                fetch_one=True
            )
        else:
            avatar = execute_query(
                "SELECT id, user_id, avatar_name, avatar_image_url, avatar_id as heygen_id FROM user_avatars WHERE id = ?",
                (avatar_id,),
                fetch_one=True
            )
        
        log_info(f"🔍 DEBUG: Avatar query result: {avatar}", "AdminRoutes")
        
        if not avatar:
            log_warning(f"Avatar not found for id: {avatar_id}", "AdminRoutes")
            return RedirectResponse(
                url="/admin/users?error=avatar_not_found",
                status_code=303
            )
        
        user_id = avatar['user_id']
        avatar_name = avatar['avatar_name']
        
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
        
        # Delete avatar from database
        log_info(f"🔍 DEBUG: About to delete avatar with id: {avatar_id}", "AdminRoutes")
        if USE_POSTGRES:
            execute_query("DELETE FROM user_avatars WHERE id = %s", (avatar_id,))
        else:
            execute_query("DELETE FROM user_avatars WHERE id = ?", (avatar_id,))
        
        log_info(f"Admin {admin_user['username']} deleted avatar {avatar_id} ('{avatar_name}') for user {user['username'] if user else 'Unknown'}", "AdminRoutes")
        
        # Redirect back to avatar management page with success message
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
        log_error("Error deleting avatar", "AdminRoutes", e)
        # Try to get user_id from the avatar if we can, otherwise go to main users page
        try:
            if USE_POSTGRES:
                avatar = execute_query(
                    "SELECT user_id FROM user_avatars WHERE id = %s",
                    (avatar_id,),
                    fetch_one=True
                )
            else:
                avatar = execute_query(
                    "SELECT user_id FROM user_avatars WHERE id = ?",
                    (avatar_id,),
                    fetch_one=True
                )
            if avatar:
                return RedirectResponse(
                    url=f"/admin/manage-avatars/{avatar['user_id']}?error=delete_failed",
                    status_code=303
                )
        except:
            pass
        
        return RedirectResponse(
            url="/admin/users?error=delete_failed",
            status_code=303
        )

# =============================================================================
# AVATAR MANAGEMENT ROUTES
# =============================================================================

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
                
                # REMOVED: Save image record to user_images table - table doesn't exist
                relative_path = f"static/uploads/{unique_filename}"
                
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
                    "message": "Avatar fetched and saved successfully with enhanced naming!",
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

# =============================================================================
# OTHER ADMIN ROUTES (UNCHANGED)
# =============================================================================

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

@router.post("/create-user")
async def create_user_action(request: Request):
    """Admin create user action"""
    try:
        # Require admin access
        admin_user = require_admin(request)
        
        # Get form data
        form = await request.form()
        username = form.get("username", "").strip()
        email = form.get("email", "").strip()
        password = form.get("password", "").strip()
        is_admin = form.get("is_admin") == "on"
        
        # Validate inputs
        if not username or not email or not password:
            return RedirectResponse(
                url="/admin/create-user?error=missing_fields",
                status_code=303
            )
        
        # Validate password strength
        is_valid, error_message = validate_password_strength(password)
        if not is_valid:
            return RedirectResponse(
                url=f"/admin/create-user?error=weak_password&message={error_message}",
                status_code=303
            )
        
        # Check if user already exists
        if USE_POSTGRES:
            existing_user = execute_query(
                "SELECT id FROM users WHERE username = %s OR LOWER(email) = LOWER(%s)",
                (username, email),
                fetch_one=True
            )
        else:
            existing_user = execute_query(
                "SELECT id FROM users WHERE username = ? OR LOWER(email) = LOWER(?)",
                (username, email),
                fetch_one=True
            )
        
        if existing_user:
            return RedirectResponse(
                url="/admin/create-user?error=user_exists",
                status_code=303
            )
        
        # Hash password
        hashed_password = get_password_hash(password)
        
        # Create user
        if USE_POSTGRES:
            execute_query(
                "INSERT INTO users (username, email, password_hash, is_admin, created_at) VALUES (%s, %s, %s, %s, NOW())",
                (username, email.lower(), hashed_password, is_admin)
            )
        else:
            execute_query(
                "INSERT INTO users (username, email, password_hash, is_admin, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
                (username, email.lower(), hashed_password, 1 if is_admin else 0)
            )
        
        log_info(f"Admin {admin_user['username']} created new user: {username} (admin: {is_admin})", "AdminRoutes")
        
        return RedirectResponse(
            url=f"/admin/users?success=user_created&username={username}",
            status_code=303
        )
        
    except HTTPException as e:
        if e.status_code == 401:
            return RedirectResponse(url="/login", status_code=303)
        elif e.status_code == 403:
            return RedirectResponse(url="/dashboard", status_code=303)
        raise
    except Exception as e:
        log_error("Error creating user", "AdminRoutes", e)
        return RedirectResponse(
            url="/admin/create-user?error=creation_failed",
            status_code=303
        )

# =============================================================================
# PHOTO AVATAR REFRESH ENDPOINTS - ENHANCED
# =============================================================================

@router.post("/refresh-photo-avatars")
async def refresh_photo_avatars_endpoint(request: Request):
    """Admin endpoint to refresh all expired photo avatar URLs"""
    try:
        # Require admin access
        admin_user = require_admin(request)
        
        # Refresh photo avatar URLs
        result = refresh_photo_avatar_urls()
        
        log_info(f"Admin {admin_user['username']} triggered photo avatar refresh", "AdminRoutes")
        
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
        log_error("Error refreshing photo avatars", "AdminRoutes", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/test-refresh-photo-avatars")
async def test_refresh_photo_avatars(request: Request):
    """Test endpoint to manually refresh photo avatars (GET request)"""
    try:
        # Require admin access
        admin_user = require_admin(request)
        
        # Call the refresh function
        result = refresh_photo_avatar_urls()
        
        log_info(f"Admin {admin_user['username']} manually triggered photo avatar refresh", "AdminRoutes")
        
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
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.post("/refresh-avatar-url/{avatar_id}")
async def refresh_single_avatar_endpoint(request: Request, avatar_id: int):
    """Admin endpoint to refresh URL for a single avatar"""
    try:
        # Require admin access
        admin_user = require_admin(request)
        
        # Refresh single avatar URL
        result = refresh_single_avatar_url(avatar_id)
        
        log_info(f"Admin {admin_user['username']} refreshed avatar {avatar_id}", "AdminRoutes")
        
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
        log_error("Error refreshing single avatar URL", "AdminRoutes", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# =============================================================================
# REMAINING ROUTES (UNCHANGED)
# =============================================================================

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
            SELECT id, title, status, heygen_video_id, created_at, video_url
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

# =============================================================================
# QUICK FIX ROUTES - REDIRECTS
# =============================================================================

@router.get("/upload-avatar")
async def upload_avatar_redirect(request: Request):
    """Redirect upload avatar to users management"""
    try:
        require_admin(request)
        return RedirectResponse(url="/admin/users", status_code=302)
    except HTTPException as e:
        if e.status_code == 401:
            return RedirectResponse(url="/login", status_code=303)
        elif e.status_code == 403:
            return RedirectResponse(url="/dashboard", status_code=303)
        raise

@router.get("/manage-voices")
async def manage_voices_redirect(request: Request):
    """Redirect manage voices to users management"""
    try:
        require_admin(request)
        return RedirectResponse(url="/admin/users", status_code=302)
    except HTTPException as e:
        if e.status_code == 401:
            return RedirectResponse(url="/login", status_code=303)
        elif e.status_code == 403:
            return RedirectResponse(url="/dashboard", status_code=303)
        raise

@router.get("/manage-data")
async def manage_data_redirect(request: Request):
    """Redirect manage data to dashboard"""
    try:
        require_admin(request)
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    except HTTPException as e:
        if e.status_code == 401:
            return RedirectResponse(url="/login", status_code=303)
        elif e.status_code == 403:
            return RedirectResponse(url="/dashboard", status_code=303)
        raise

# =============================================================================
# DEBUG AND TEMPORARY ENDPOINTS
# =============================================================================

@router.get("/reset-admin-password")
async def reset_admin_password():
    """Temporary endpoint to reset admin password"""
    try:
        from ..auth.authentication import get_password_hash
        
        # Hash the password correctly
        new_password_hash = get_password_hash("admin123")
        
        # Update admin user password - FIXED COLUMN NAME
        if USE_POSTGRES:
            execute_query(
                "UPDATE users SET hashed_password = %s WHERE username = %s",
                (new_password_hash, "admin")
            )
        else:
            execute_query(
                "UPDATE users SET hashed_password = ? WHERE username = ?",
                (new_password_hash, "admin")
            )
        
        return {"success": True, "message": "Admin password reset to admin123"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/debug-admin-user")
async def debug_admin_user():
    """Debug endpoint to check admin user data"""
    try:
        # Get admin user from database
        if USE_POSTGRES:
            user = execute_query(
                "SELECT id, username, email, hashed_password, is_admin FROM users WHERE username = %s",
                ("admin",),
                fetch_one=True
            )
        else:
            user = execute_query(
                "SELECT id, username, email, hashed_password, is_admin FROM users WHERE username = ?",
                ("admin",),
                fetch_one=True
            )
        
        if not user:
            return {"error": "Admin user not found"}
        
        # Test password verification
        from ..auth.authentication import verify_password
        password_check = verify_password("admin123", user['hashed_password'])
        
        return {
            "user_exists": True,
            "username": user['username'],
            "email": user['email'],
            "is_admin": user['is_admin'],
            "password_hash_starts_with": user['hashed_password'][:20] + "...",
            "password_verification": password_check,
            "user_id": user['id']
        }
    except Exception as e:
        return {"error": str(e)}