"""
Host Message Routes for MyAvatar
Admin interface for broadcasting messages to all users
"""
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from datetime import datetime
from typing import Optional
import logging
import os

# JWT imports for authentication (same as working dashboard)
try:
    from jose import jwt
except ImportError:
    import jwt

# Import database functions
try:
    from ..db.database import execute_query
    from ..db.user_manager import Database
except ImportError:
    from app.db.database import execute_query
    from app.db.user_manager import Database

# Import logging
try:
    from ..logger.log_handler import log_info, log_error, log_warning
except ImportError:
    # Fallback logging
    logger = logging.getLogger(__name__)
    def log_info(msg, context): logger.info(f"[{context}] {msg}")
    def log_error(msg, context, exc=None): logger.error(f"[{context}] {msg}")
    def log_warning(msg, context): logger.warning(f"[{context}] {msg}")

# Define templates
templates_path = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_path))

# Configuration - same as working web_routes
class Config:
    JWT_SECRET = os.getenv("JWT_SECRET", "fallback-development-secret-key")
    JWT_ALGORITHM = "HS256"

config = Config()
db = Database()

# Create router
router = APIRouter(tags=["host"])

# AUTHENTICATION FUNCTION - Same as working dashboard
def get_current_user_fixed(request: Request):
    """Get current user with proper JWT validation - SAME AS DASHBOARD"""
    try:
        token = request.cookies.get("access_token")
        if not token:
            return None
        
        # Validate JWT token with expiry check
        try:
            payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
        
        user_id = payload.get("user_id")
        if not user_id:
            return None
        
        # Get fresh user data from database
        user = db.get_user_by_id(user_id)
        if not user:
            return None
        
        # Security checks
        if user.get('is_locked', 0) == 1:
            return None
            
        return user
        
    except Exception as e:
        log_error(f"Error getting current user: {e}", "HostRoutes")
        return None

# ============================================================================
# ADMIN ROUTES - For you to manage host messages
# ============================================================================

@router.get("/admin/host-messages")
async def admin_host_messages(request: Request):
    """Admin page to manage host messages"""
    try:
        # Check if user is admin
        user = get_current_user_fixed(request)
        if not user or not user.get('is_admin', 0):
            return RedirectResponse(url="/login", status_code=303)
        
        log_info(f"Admin {user.get('username')} accessing host messages", "HostRoutes")
        
        # Get all host messages with read statistics
        messages = execute_query(
            """SELECT hm.*, 
                      COUNT(uhr.id) as read_count,
                      (SELECT COUNT(*) FROM users WHERE is_admin = 0) as total_users
               FROM host_messages hm
               LEFT JOIN user_host_message_reads uhr ON hm.id = uhr.host_message_id
               GROUP BY hm.id
               ORDER BY hm.created_at DESC""",
            fetch_all=True
        )
        
        return templates.TemplateResponse(
            "admin/host_messages.html",
            {
                "request": request,
                "user": user,
                "messages": messages or [],
                "title": "Host Messages Management"
            }
        )
    except Exception as e:
        log_error(f"Error loading admin host messages: {e}", "HostRoutes")
        return RedirectResponse(url="/admin", status_code=303)

@router.get("/admin/host-messages/create")
async def create_host_message_page(request: Request):
    """Page to create new host message"""
    try:
        user = get_current_user_fixed(request)
        if not user or not user.get('is_admin', 0):
            return RedirectResponse(url="/login", status_code=303)
        
        log_info(f"Admin {user.get('username')} accessing create host message", "HostRoutes")
        
        # Get user's completed videos for selection
        user_videos = execute_query(
            """SELECT id, title, video_path, thumbnail_url, duration, created_at
               FROM videos 
               WHERE user_id = %s AND status = 'completed' AND video_path IS NOT NULL
               ORDER BY created_at DESC""",
            (user['id'],),
            fetch_all=True
        )
        
        return templates.TemplateResponse(
            "admin/create_host_message.html",
            {
                "request": request,
                "user": user,
                "videos": user_videos or [],
                "title": "Create Host Message"
            }
        )
    except Exception as e:
        log_error(f"Error loading create host message page: {e}", "HostRoutes")
        return RedirectResponse(url="/admin", status_code=303)

@router.post("/admin/host-messages/create")
async def create_host_message(request: Request):
    """Create new host message"""
    try:
        user = get_current_user_fixed(request)
        if not user or not user.get('is_admin', 0):
            raise HTTPException(status_code=403, detail="Admin access required")
        
        form = await request.form()
        title = form.get("title", "").strip()
        message_text = form.get("message_text", "").strip()
        video_choice = form.get("video_choice", "")  # 'none', 'existing' or 'url'
        video_id = form.get("video_id", "")
        video_url = form.get("video_url", "").strip()
        duration = form.get("duration", "").strip()
        expires_at = form.get("expires_at", "")
        priority = int(form.get("priority", 1))
        
        if not title or not message_text:
            raise HTTPException(status_code=400, detail="Title and message are required")
        
        log_info(f"Admin {user.get('username')} creating host message: {title}", "HostRoutes")
        
        # Handle video selection
        final_video_url = None
        final_video_id = None
        final_thumbnail_url = None
        final_duration = duration
        
        if video_choice == "existing" and video_id:
            # Use existing video from user's videos
            video = execute_query(
                "SELECT video_path, thumbnail_url, duration FROM videos WHERE id = %s AND user_id = %s",
                (video_id, user['id']),
                fetch_one=True
            )
            if video:
                final_video_url = video['video_path']
                final_video_id = video_id
                final_thumbnail_url = video['thumbnail_url']
                final_duration = video['duration'] or duration
        elif video_choice == "url" and video_url:
            # Use custom video URL
            final_video_url = video_url
        
        # Parse expires_at
        expires_at_datetime = None
        if expires_at:
            try:
                expires_at_datetime = datetime.fromisoformat(expires_at)
            except:
                pass
        
        # Insert host message
        message_id = execute_query(
            """INSERT INTO host_messages 
               (title, message_text, video_url, video_id, thumbnail_url, duration, 
                priority, expires_at, created_at, is_active)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (title, message_text, final_video_url, final_video_id, final_thumbnail_url,
             final_duration, priority, expires_at_datetime, datetime.now(), True),
            fetch_one=True
        )
        
        if message_id:
            log_info(f"Host message '{title}' created successfully by {user['username']}", "HostRoutes")
            return RedirectResponse(url="/admin/host-messages?success=created", status_code=303)
        else:
            raise HTTPException(status_code=500, detail="Failed to create host message")
            
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error creating host message: {e}", "HostRoutes")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/admin/host-messages/{message_id}/toggle")
async def toggle_host_message(request: Request, message_id: int):
    """Toggle host message active status"""
    try:
        user = get_current_user_fixed(request)
        if not user or not user.get('is_admin', 0):
            return JSONResponse({"success": False, "error": "Admin access required"})
        
        # Toggle is_active status
        execute_query(
            "UPDATE host_messages SET is_active = NOT is_active, updated_at = %s WHERE id = %s",
            (datetime.now(), message_id)
        )
        
        log_info(f"Admin {user.get('username')} toggled host message {message_id}", "HostRoutes")
        return JSONResponse({"success": True, "message": "Message status updated"})
        
    except Exception as e:
        log_error(f"Error toggling host message: {e}", "HostRoutes")
        return JSONResponse({"success": False, "error": str(e)})

@router.delete("/admin/host-messages/{message_id}")
async def delete_host_message(request: Request, message_id: int):
    """Delete host message"""
    try:
        user = get_current_user_fixed(request)
        if not user or not user.get('is_admin', 0):
            return JSONResponse({"success": False, "error": "Admin access required"})
        
        # Delete message and related reads
        execute_query("DELETE FROM user_host_message_reads WHERE host_message_id = %s", (message_id,))
        execute_query("DELETE FROM host_messages WHERE id = %s", (message_id,))
        
        log_info(f"Admin {user.get('username')} deleted host message {message_id}", "HostRoutes")
        return JSONResponse({"success": True, "message": "Message deleted"})
        
    except Exception as e:
        log_error(f"Error deleting host message: {e}", "HostRoutes")
        return JSONResponse({"success": False, "error": str(e)})

# ============================================================================
# USER API ROUTES - For the dashboard widget
# ============================================================================

@router.get("/api/host-message")
async def get_current_host_message(request: Request):
    """Get current active host message for user"""
    try:
        user = get_current_user_fixed(request)
        if not user:
            return JSONResponse({"success": False, "error": "Authentication required"})
        
        # Get active host message with highest priority
        message = execute_query(
            """SELECT hm.*,
                      CASE WHEN uhr.id IS NOT NULL THEN true ELSE false END as is_read
               FROM host_messages hm
               LEFT JOIN user_host_message_reads uhr 
                   ON hm.id = uhr.host_message_id AND uhr.user_id = %s
               WHERE hm.is_active = true 
                 AND (hm.expires_at IS NULL OR hm.expires_at > %s)
               ORDER BY hm.priority DESC, hm.created_at DESC
               LIMIT 1""",
            (user['id'], datetime.now()),
            fetch_one=True
        )
        
        if not message:
            return JSONResponse({
                "success": True,
                "message": None,
                "has_unread": False
            })
        
        message_data = {
            "id": message['id'],
            "title": message['title'],
            "message_text": message['message_text'],
            "video_url": message['video_url'],
            "thumbnail_url": message['thumbnail_url'],
            "duration": message['duration'],
            "created_at": message['created_at'].strftime('%B %d, %Y') if message['created_at'] else None,
            "is_read": message['is_read']
        }
        
        return JSONResponse({
            "success": True,
            "message": message_data,
            "has_unread": not message['is_read']
        })
        
    except Exception as e:
        log_error(f"Error getting host message: {e}", "HostRoutes")
        return JSONResponse({"success": False, "error": str(e)})

@router.post("/api/host-message/{message_id}/read")
async def mark_host_message_read(request: Request, message_id: int):
    """Mark host message as read by user"""
    try:
        user = get_current_user_fixed(request)
        if not user:
            return JSONResponse({"success": False, "error": "Authentication required"})
        
        # Insert or update read status
        execute_query(
            """INSERT INTO user_host_message_reads (user_id, host_message_id, read_at)
               VALUES (%s, %s, %s)
               ON CONFLICT (user_id, host_message_id) 
               DO UPDATE SET read_at = %s""",
            (user['id'], message_id, datetime.now(), datetime.now())
        )
        
        log_info(f"User {user.get('username')} marked host message {message_id} as read", "HostRoutes")
        return JSONResponse({"success": True, "message": "Marked as read"})
        
    except Exception as e:
        log_error(f"Error marking host message as read: {e}", "HostRoutes")
        return JSONResponse({"success": False, "error": str(e)})

# ============================================================================
# UTILITY ROUTES
# ============================================================================

@router.get("/api/host-message/status")
async def host_message_system_status():
    """Get host message system status"""
    try:
        # Count total messages
        total_messages = execute_query("SELECT COUNT(*) as count FROM host_messages", fetch_one=True)
        active_messages = execute_query("SELECT COUNT(*) as count FROM host_messages WHERE is_active = true", fetch_one=True)
        
        # Count users
        total_users = execute_query("SELECT COUNT(*) as count FROM users WHERE is_admin = 0", fetch_one=True)
        
        return JSONResponse({
            "success": True,
            "status": "operational",
            "total_messages": total_messages['count'] if total_messages else 0,
            "active_messages": active_messages['count'] if active_messages else 0,
            "total_users": total_users['count'] if total_users else 0,
            "features": {
                "admin_interface": True,
                "user_api": True,
                "read_tracking": True,
                "video_support": True,
                "priority_system": True,
                "expiry_dates": True
            }
        })
        
    except Exception as e:
        log_error(f"Error getting host message status: {e}", "HostRoutes")
        return JSONResponse({
            "success": False,
            "status": "error",
            "error": str(e)
        })

# ============================================================================
# ADMIN QUICK ACTIONS
# ============================================================================

@router.post("/admin/host-messages/quick-message")
async def create_quick_message(request: Request):
    """Create a quick text-only message"""
    try:
        user = get_current_user_fixed(request)
        if not user or not user.get('is_admin', 0):
            return JSONResponse({"success": False, "error": "Admin access required"})
        
        data = await request.json()
        title = data.get("title", "").strip()
        message_text = data.get("message", "").strip()
        priority = int(data.get("priority", 1))
        
        if not title or not message_text:
            return JSONResponse({"success": False, "error": "Title and message required"})
        
        # Insert quick message
        message_id = execute_query(
            """INSERT INTO host_messages (title, message_text, priority, created_at, is_active)
               VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (title, message_text, priority, datetime.now(), True),
            fetch_one=True
        )
        
        if message_id:
            log_info(f"Quick message created by {user.get('username')}: {title}", "HostRoutes")
            return JSONResponse({
                "success": True,
                "message_id": message_id['id'],
                "message": "Quick message created successfully"
            })
        else:
            return JSONResponse({"success": False, "error": "Failed to create message"})
            
    except Exception as e:
        log_error(f"Error creating quick message: {e}", "HostRoutes")
        return JSONResponse({"success": False, "error": str(e)})

# Log router initialization
log_info("Host message routes loaded successfully", "HostRoutes")
