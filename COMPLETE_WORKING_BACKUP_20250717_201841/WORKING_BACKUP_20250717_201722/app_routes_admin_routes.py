# ===============================================================================
# COMPLETE ADMIN ROUTES WITH PREMIUM MANAGEMENT - FIXED VERSION
# ===============================================================================

import logging
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

# Import the proper middleware we just created
from ..middleware.vacation_mode import (
    require_admin,
    get_system_stats,
    admin_toggle_vacation_mode,
    admin_set_user_limits,
    admin_emergency_stop,
    admin_get_vacation_status,
    vacation_manager
)

# Import other services
from ..services.auth_service import auth_service
from ..config.settings import config
from ..db.database import execute_query
from ..db.user_manager import Database

router = APIRouter()
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)
db = Database()

# ===============================================================================
# CHAPTER 1: MAIN ADMIN DASHBOARD
# ===============================================================================

@router.get("/")
async def admin_dashboard(request: Request):
    """Admin dashboard with vacation mode controls"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return RedirectResponse(url="/login", status_code=302)
        
        # Get current status
        vacation_status = admin_get_vacation_status()
        stats = vacation_status['current_stats']
        settings = vacation_status['settings']
        
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Admin Dashboard - MyAvatar</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
                .stat-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; }}
                .stat-number {{ font-size: 2em; font-weight: bold; color: #007bff; }}
                .vacation-controls {{ background: #fff3cd; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #ffc107; }}
                .control-buttons {{ display: flex; gap: 10px; margin: 10px 0; }}
                .btn {{ padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; text-decoration: none; display: inline-block; }}
                .btn-success {{ background: #28a745; color: white; }}
                .btn-danger {{ background: #dc3545; color: white; }}
                .btn-warning {{ background: #ffc107; color: black; }}
                .btn-primary {{ background: #007bff; color: white; }}
                .status-badge {{ padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
                .status-active {{ background: #28a745; color: white; }}
                .status-inactive {{ background: #6c757d; color: white; }}
                .admin-links {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; margin: 30px 0; }}
                .admin-link {{ display: block; padding: 15px; background: #007bff; color: white; text-decoration: none; border-radius: 8px; text-align: center; }}
                .admin-link:hover {{ background: #0056b3; }}
                .admin-link.premium {{ background: #28a745; }}
                .admin-link.premium:hover {{ background: #1e7e34; }}
                h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎛️ Admin Dashboard</h1>
                <p><strong>Welcome, {admin_user.get('username', 'Admin')}!</strong></p>
                
                <div class="vacation-controls">
                    <h3>🏖️ Vacation Mode Controls</h3>
                    <div>
                        <strong>Status:</strong> 
                        <span class="status-badge {'status-active' if settings['vacation_mode_enabled'] else 'status-inactive'}">
                            {'ENABLED' if settings['vacation_mode_enabled'] else 'DISABLED'}
                        </span>
                        <strong>Emergency Stop:</strong>
                        <span class="status-badge {'status-active' if settings['emergency_stop'] else 'status-inactive'}">
                            {'ACTIVE' if settings['emergency_stop'] else 'INACTIVE'}
                        </span>
                    </div>
                    
                    <div class="control-buttons">
                        <a href="/admin/vacation-mode/enable" class="btn btn-success">Enable Vacation Mode</a>
                        <a href="/admin/vacation-mode/disable" class="btn btn-danger">Disable Vacation Mode</a>
                        <a href="/admin/emergency-stop/enable" class="btn btn-warning">Emergency Stop</a>
                        <a href="/admin/emergency-stop/disable" class="btn btn-primary">Clear Emergency</a>
                    </div>
                    
                    <div>
                        <strong>Current Limits:</strong>
                        Max Users: {settings['limits']['max_total_users']}, 
                        Daily: {settings['limits']['max_daily_registrations']}, 
                        Videos/User: {settings['limits']['max_videos_per_user']}
                    </div>
                </div>
                
                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-number">{stats['total_users']}</div>
                        <div>Total Users ({stats['users_percentage']}%)</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{stats['total_videos']}</div>
                        <div>Total Videos</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{stats['daily_registrations']}</div>
                        <div>Today's Registrations ({stats['daily_percentage']}%)</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">💰</div>
                        <div>Budget: ${settings['budget']['total_budget']}</div>
                    </div>
                </div>
                
                <div class="admin-links">
                    <a href="/admin/users" class="admin-link">👥 Manage Users</a>
                    <a href="/admin/create-user" class="admin-link">➕ Create New User</a>
                    <a href="/admin/premium-management" class="admin-link premium">💎 Premium Management</a>
                    <a href="/admin/vacation-settings" class="admin-link">🏖️ Vacation Settings</a>
                    <a href="/admin/debug-database" class="admin-link">🔧 Database Info</a>
                    <a href="/admin/vacation-stats" class="admin-link">📊 Detailed Stats</a>
                </div>
                
                <div style="margin-top: 30px; text-align: center;">
                    <a href="/dashboard" style="color: #007bff; margin-right: 20px;">← Back to Dashboard</a>
                    <a href="/logout" style="color: #dc3545; text-decoration: none; padding: 8px 16px; border: 1px solid #dc3545; border-radius: 4px;">🚪 Logout</a>
                </div>
            </div>
        </body>
        </html>
        """)
        
    except Exception as e:
        logger.error(f"Admin dashboard error: {e}")
        return HTMLResponse(content=f"<h1>Error</h1><p>Admin dashboard error: {str(e)}</p>")

# ===============================================================================
# CHAPTER 2: VACATION MODE CONTROLS
# ===============================================================================

@router.get("/vacation-mode/enable")
async def enable_vacation_mode(request: Request):
    """Enable vacation mode"""
    admin_user = require_admin(request)
    if not admin_user:
        return RedirectResponse(url="/login", status_code=302)
    
    result = admin_toggle_vacation_mode(True)
    return RedirectResponse(url="/admin", status_code=302)

@router.get("/vacation-mode/disable")
async def disable_vacation_mode(request: Request):
    """Disable vacation mode"""
    admin_user = require_admin(request)
    if not admin_user:
        return RedirectResponse(url="/login", status_code=302)
    
    result = admin_toggle_vacation_mode(False)
    return RedirectResponse(url="/admin", status_code=302)

@router.get("/emergency-stop/enable")
async def enable_emergency_stop(request: Request):
    """Enable emergency stop"""
    admin_user = require_admin(request)
    if not admin_user:
        return RedirectResponse(url="/login", status_code=302)
    
    result = admin_emergency_stop(True)
    return RedirectResponse(url="/admin", status_code=302)

@router.get("/emergency-stop/disable")
async def disable_emergency_stop(request: Request):
    """Disable emergency stop"""
    admin_user = require_admin(request)
    if not admin_user:
        return RedirectResponse(url="/login", status_code=302)
    
    result = admin_emergency_stop(False)
    return RedirectResponse(url="/admin", status_code=302)

# ===============================================================================
# CHAPTER 3: USER MANAGEMENT
# ===============================================================================

@router.get("/users")
async def admin_users(request: Request):
    """List all users with enhanced data"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return RedirectResponse(url="/login", status_code=302)
        
        # Get users with additional data including video count and premium status
        users_query = """
        SELECT u.id, u.username, u.email, u.is_admin, u.is_premium, u.created_at, u.last_login,
               COUNT(DISTINCT v.id) as video_count
        FROM users u
        LEFT JOIN videos v ON u.id = v.user_id
        GROUP BY u.id, u.username, u.email, u.is_admin, u.is_premium, u.created_at, u.last_login
        ORDER BY u.created_at DESC
        LIMIT 50
        """
        
        users = execute_query(users_query, fetch_all=True)
        
        # Build users HTML with premium status
        users_html = ""
        if users:
            for user in users:
                user_dict = dict(user) if hasattr(user, '_asdict') else user
                admin_badge = "👑" if user_dict.get('is_admin') else "👤"
                premium_badge = "💎" if user_dict.get('is_premium') else ""
                
                users_html += f"""
                <tr>
                    <td>{user_dict.get('id')}</td>
                    <td>{admin_badge}{premium_badge} {user_dict.get('username')}</td>
                    <td>{user_dict.get('email', 'N/A')}</td>
                    <td>{user_dict.get('video_count', 0)}</td>
                    <td>{'Yes' if user_dict.get('is_admin') else 'No'}</td>
                    <td>{'Yes' if user_dict.get('is_premium') else 'No'}</td>
                    <td>
                        <a href="/admin/edit-user/{user_dict.get('id')}" style="color: #007bff; margin-right: 10px;">✏️ Edit</a>
                        <a href="/admin/toggle-premium/{user_dict.get('id')}" style="color: #ffc107; margin-right: 10px;">💎 Premium</a>
                        <a href="/admin/manage-videos/{user_dict.get('id')}" style="color: #28a745; margin-right: 10px;">🎬 Videos</a>
                        <a href="/admin/manage-avatars/{user_dict.get('id')}" style="color: #6f42c1;">🎭 Avatars</a>
                    </td>
                </tr>
                """
        
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Manage Users - MyAvatar Admin</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background: #f8f9fa; font-weight: bold; }}
                tr:hover {{ background: #f8f9fa; }}
                h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
                .btn {{ display: inline-block; padding: 10px 20px; margin: 10px 0; background: #007bff; color: white; text-decoration: none; border-radius: 5px; }}
                .btn:hover {{ background: #0056b3; }}
                .btn-success {{ background: #28a745; }}
                .btn-success:hover {{ background: #1e7e34; }}
                .btn-premium {{ background: #ffc107; color: black; }}
                .btn-premium:hover {{ background: #e0a800; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>👥 Manage Users</h1>
                
                <div style="margin: 20px 0;">
                    <a href="/admin/create-user" class="btn btn-success">➕ Create New User</a>
                    <a href="/admin/premium-management" class="btn btn-premium">💎 Premium Management</a>
                </div>
                
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Username</th>
                            <th>Email</th>
                            <th>Videos</th>
                            <th>Admin</th>
                            <th>Premium</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {users_html}
                    </tbody>
                </table>
                
                <div style="margin-top: 30px; text-align: center;">
                    <a href="/admin" style="color: #007bff;">← Back to Admin Dashboard</a>
                </div>
            </div>
        </body>
        </html>
        """)
        
    except Exception as e:
        logger.error(f"Admin users error: {e}")
        return HTMLResponse(content=f"""
        <div style="font-family: Arial, sans-serif; margin: 40px; padding: 30px; background: #f8d7da; border-radius: 8px;">
            <h1>Error Loading Users</h1>
            <p>Error: {str(e)}</p>
            <p><a href="/admin">← Back to Admin Dashboard</a></p>
        </div>
        """)

# ===============================================================================
# CHAPTER 4: EDIT USER FUNCTIONALITY
# ===============================================================================

@router.get("/edit-user/{user_id}")
async def admin_edit_user_page(request: Request, user_id: int):
    """Show edit user form"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return RedirectResponse(url="/login", status_code=302)
        
        # Get user to edit
        user_to_edit = db.get_user_by_id(user_id)
        if not user_to_edit:
            return RedirectResponse(url="/admin/users?error=user_not_found", status_code=302)
        
        # Convert to dict if needed
        user_dict = dict(user_to_edit) if hasattr(user_to_edit, '_asdict') else user_to_edit
        
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Edit User - MyAvatar Admin</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .form-group {{ margin: 20px 0; }}
                label {{ display: block; margin-bottom: 8px; font-weight: bold; color: #333; }}
                input {{ padding: 12px; width: 100%; box-sizing: border-box; border: 1px solid #ddd; border-radius: 4px; }}
                button {{ padding: 12px 24px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }}
                button:hover {{ background: #0056b3; }}
                .checkbox-group {{ display: flex; align-items: center; gap: 8px; }}
                .checkbox-group input {{ width: auto; }}
                h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
                .user-info {{ background: #e9ecef; padding: 15px; border-radius: 4px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>✏️ Edit User</h1>
                
                <div class="user-info">
                    <h3>Current User Info</h3>
                    <p><strong>ID:</strong> {user_dict.get('id')}</p>
                    <p><strong>Created:</strong> {user_dict.get('created_at', 'N/A')}</p>
                    <p><strong>Last Login:</strong> {user_dict.get('last_login', 'Never')}</p>
                </div>
                
                <form method="post" action="/admin/edit-user/{user_id}">
                    <div class="form-group">
                        <label for="username">Username:</label>
                        <input type="text" id="username" name="username" value="{user_dict.get('username', '')}" required>
                    </div>
                    
                    <div class="form-group">
                        <label for="email">Email:</label>
                        <input type="email" id="email" name="email" value="{user_dict.get('email', '')}" required>
                    </div>
                    
                    <div class="form-group">
                        <div class="checkbox-group">
                            <input type="checkbox" id="is_admin" name="is_admin" value="1" {'checked' if user_dict.get('is_admin') else ''}>
                            <label for="is_admin">Admin User</label>
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <div class="checkbox-group">
                            <input type="checkbox" id="is_premium" name="is_premium" value="1" {'checked' if user_dict.get('is_premium') else ''}>
                            <label for="is_premium">💎 Premium User</label>
                        </div>
                    </div>
                    
                    <button type="submit">Update User</button>
                </form>
                
                <div style="margin-top: 30px; text-align: center;">
                    <a href="/admin/users" style="color: #007bff;">← Back to Users</a>
                </div>
            </div>
        </body>
        </html>
        """)
        
    except Exception as e:
        logger.error(f"Edit user page error: {e}")
        return RedirectResponse(url="/admin/users?error=load_failed", status_code=302)

@router.post("/edit-user/{user_id}")
async def admin_edit_user_save(request: Request, user_id: int):
    """Save user edits"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return RedirectResponse(url="/login", status_code=302)
        
        form = await request.form()
        username = str(form.get("username", "")).strip()
        email = str(form.get("email", "")).strip()
        is_premium = bool(form.get("is_premium"))
        is_admin = bool(form.get("is_admin"))
        
        if not username or not email:
            return RedirectResponse(url=f"/admin/edit-user/{user_id}?error=missing_fields", status_code=302)
        
        # Update user
        update_query = """
        UPDATE users 
        SET username = %s, email = %s, is_premium = %s, is_admin = %s 
        WHERE id = %s
        """
        
        result = execute_query(update_query, (username, email, is_premium, is_admin, user_id))
        
        if result is not None:
            logger.info(f"Admin {admin_user.get('username')} updated user {username} (ID: {user_id}) - Premium: {is_premium}")
            return RedirectResponse(url="/admin/users?success=user_updated", status_code=302)
        else:
            return RedirectResponse(url=f"/admin/edit-user/{user_id}?error=update_failed", status_code=302)
            
    except Exception as e:
        logger.error(f"Edit user save error: {e}")
        return RedirectResponse(url=f"/admin/edit-user/{user_id}?error=update_failed", status_code=302)

# ===============================================================================
# CHAPTER 4.5: MANAGE USER VIDEOS AND AVATARS
# ===============================================================================

@router.post("/delete-user/{user_id}")
async def admin_delete_user(request: Request, user_id: int):
    """Delete a user and all their data"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return RedirectResponse(url="/login", status_code=302)
        
        # Get user to delete
        user_to_delete = db.get_user_by_id(user_id)
        if not user_to_delete:
            return RedirectResponse(url="/admin/users?error=user_not_found", status_code=302)
        
        # Prevent deleting yourself
        if user_id == admin_user.get('id'):
            return RedirectResponse(url="/admin/users?error=cannot_delete_yourself", status_code=302)
        
        # Prevent deleting other admins (optional safety)
        if user_to_delete.get('is_admin') and user_to_delete.get('username') != 'testuser':
            return RedirectResponse(url="/admin/users?error=cannot_delete_admin", status_code=302)
        
        username = user_to_delete.get('username', 'Unknown')
        
        # Delete user data (in order due to foreign key constraints)
        delete_queries = [
            ("DELETE FROM user_avatars WHERE user_id = %s", (user_id,)),
            ("DELETE FROM videos WHERE user_id = %s", (user_id,)),
            ("DELETE FROM users WHERE id = %s", (user_id,))
        ]
        
        for query, params in delete_queries:
            execute_query(query, params)
        
        logger.info(f"Admin {admin_user.get('username')} deleted user {username} (ID: {user_id})")
        
        return RedirectResponse(url=f"/admin/users?success=user_deleted&username={username}", status_code=302)
        
    except Exception as e:
        logger.error(f"Delete user error: {e}")
        return RedirectResponse(url="/admin/users?error=delete_failed", status_code=302)

@router.get("/manage-avatars/{user_id}")
async def admin_manage_avatars(request: Request, user_id: int):
    """Manage user avatars - FIXED to use proper template"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return RedirectResponse(url="/login", status_code=302)
        
        # Get user
        user = db.get_user_by_id(user_id)
        if not user:
            return RedirectResponse(url="/admin/users?error=user_not_found", status_code=302)
        
        # Get success/error messages from query parameters
        success_message = None
        error_message = None
        
        if request.query_params.get("success") == "avatar_added":
            success_message = "Avatar successfully added!"
        elif request.query_params.get("success") == "avatar_deleted":
            success_message = "Avatar successfully deleted!"
        elif request.query_params.get("error") == "avatar_exists":
            error_message = "Avatar already exists for this user!"
        elif request.query_params.get("error") == "heygen_failed":
            error_message = "Failed to add HeyGen avatar. Please try again."
        
        # Get user's avatars using proper query
        avatars_query = """
        SELECT id, avatar_name, avatar_image_url, avatar_id, heygen_avatar_id, is_default, created_at 
        FROM user_avatars 
        WHERE user_id = %s 
        ORDER BY created_at DESC
        """
        avatars = execute_query(avatars_query, (user_id,), fetch_all=True)
        
        # Convert to list of dicts for template
        avatars_list = []
        if avatars:
            for avatar in avatars:
                avatar_dict = dict(avatar) if hasattr(avatar, '_asdict') else avatar
                avatars_list.append(avatar_dict)
        
        # Use the proper template with all the data it needs
        return templates.TemplateResponse("portal/admin_manage_avatars.html", {
            "request": request,
            "user_to_manage": user,
            "avatars": avatars_list,
            "admin_user": admin_user,
            "success_message": success_message,
            "error_message": error_message
        })
        
    except Exception as e:
        logger.error(f"Manage avatars error: {e}")
        return RedirectResponse(url="/admin/users?error=avatar_load_failed", status_code=302)

@router.get("/manage-videos/{user_id}")
async def admin_manage_videos(request: Request, user_id: int):
    """Manage user videos - FIXED to use proper template"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return RedirectResponse(url="/login", status_code=302)
        
        # Get user
        user = db.get_user_by_id(user_id)
        if not user:
            return RedirectResponse(url="/admin/users?error=user_not_found", status_code=302)
        
        # Get user's videos using proper query
        videos_query = """
        SELECT id, title, status, created_at, video_path, heygen_video_id, thumbnail_url 
        FROM videos 
        WHERE user_id = %s 
        ORDER BY created_at DESC
        """
        videos = execute_query(videos_query, (user_id,), fetch_all=True)
        
        # Convert to list of dicts for template
        videos_list = []
        if videos:
            for video in videos:
                video_dict = dict(video) if hasattr(video, '_asdict') else video
                videos_list.append(video_dict)
        
        # Use the proper template with all the data it needs
        return templates.TemplateResponse("portal/admin_manage_videos.html", {
            "request": request,
            "user_to_manage": user,
            "videos": videos_list,
            "total_videos": len(videos_list),
            "admin_user": admin_user
        })
        
    except Exception as e:
        logger.error(f"Manage videos error: {e}")
        return RedirectResponse(url="/admin/users?error=video_load_failed", status_code=302)

@router.post("/delete-video/{video_id}")
async def admin_delete_video(request: Request, video_id: int):
    """Delete a specific video"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return RedirectResponse(url="/login", status_code=302)
        
        # Get video info
        video = execute_query("SELECT * FROM videos WHERE id = %s", (video_id,), fetch_one=True)
        if not video:
            return JSONResponse({"success": False, "error": "Video not found"})
        
        video_dict = dict(video) if hasattr(video, '_asdict') else video
        user_id = video_dict.get('user_id')
        title = video_dict.get('title', 'Unknown')
        
        # Delete video
        execute_query("DELETE FROM videos WHERE id = %s", (video_id,))
        
        logger.info(f"Admin {admin_user.get('username')} deleted video '{title}' (ID: {video_id})")
        
        return RedirectResponse(url=f"/admin/manage-videos/{user_id}?success=video_deleted", status_code=302)
        
    except Exception as e:
        logger.error(f"Delete video error: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@router.post("/delete-avatar/{avatar_id}")
async def admin_delete_avatar(request: Request, avatar_id: int):
    """Delete a specific avatar"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return RedirectResponse(url="/login", status_code=302)
        
        # Get avatar info
        avatar = execute_query("SELECT * FROM user_avatars WHERE id = %s", (avatar_id,), fetch_one=True)
        if not avatar:
            return JSONResponse({"success": False, "error": "Avatar not found"})
        
        avatar_dict = dict(avatar) if hasattr(avatar, '_asdict') else avatar
        user_id = avatar_dict.get('user_id')
        name = avatar_dict.get('avatar_name', 'Unknown')
        
        # Delete avatar
        execute_query("DELETE FROM user_avatars WHERE id = %s", (avatar_id,))
        
        logger.info(f"Admin {admin_user.get('username')} deleted avatar '{name}' (ID: {avatar_id})")
        
        return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?success=avatar_deleted", status_code=302)
        
    except Exception as e:
        logger.error(f"Delete avatar error: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@router.post("/fetch-heygen-avatar/{user_id}")
async def admin_fetch_heygen_avatar(request: Request, user_id: int, heygen_avatar_id: str = Form(...)):
    """Fetch and add HeyGen avatar for a user - Enhanced with robust validation and fallback"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return RedirectResponse(url="/login", status_code=302)
        
        # Clean up avatar ID (remove any whitespace)
        heygen_avatar_id = heygen_avatar_id.strip()
        
        # Check if avatar already exists for this user
        existing = execute_query(
            "SELECT id FROM user_avatars WHERE user_id = %s AND avatar_id = %s",
            (user_id, heygen_avatar_id)
        )
        
        if existing:
            return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?error=avatar_exists", status_code=302)
        
        # Get HeyGen API key
        heygen_api_key = os.getenv("HEYGEN_API_KEY")
        if not heygen_api_key:
            logger.warning("HeyGen API key not found - adding avatar without validation")
            # Fallback: Add avatar without validation
            avatar_name = f"HeyGen Avatar {heygen_avatar_id[:8]}"
            avatar_image_url = f"https://files2.heygen.ai/avatar/v3/{heygen_avatar_id}/{heygen_avatar_id}.jpg"
        else:
            # Try to validate avatar with HeyGen API
            logger.info(f"Admin validating HeyGen avatar ID: {heygen_avatar_id}")
            
            try:
                from ..api.heygen import get_avatar_from_any_endpoint
                avatar_result = get_avatar_from_any_endpoint(heygen_api_key, heygen_avatar_id)
                
                if avatar_result and avatar_result.get("error"):
                    # Handle old talking photo error
                    logger.warning(f"HeyGen validation warning for {heygen_avatar_id}: {avatar_result.get('error')}")
                    avatar_name = f"Legacy Avatar {heygen_avatar_id[:8]}"
                    avatar_image_url = f"https://files2.heygen.ai/avatar/v3/{heygen_avatar_id}/{heygen_avatar_id}.jpg"
                elif avatar_result:
                    # Extract avatar details from HeyGen response
                    avatar_data = avatar_result.get("data", {})
                    avatar_type = avatar_result.get("type", "unknown")
                    
                    # Generate avatar name from HeyGen data or fallback
                    heygen_name = avatar_data.get("name") or avatar_data.get("avatar_name")
                    if heygen_name:
                        avatar_name = heygen_name
                    else:
                        avatar_name = f"HeyGen Avatar {heygen_avatar_id[:8]}"
                    
                    # Get avatar image URL from HeyGen data or construct it
                    avatar_image_url = None
                    
                    # Try to get image URL from HeyGen response
                    if avatar_data.get("preview_image_url"):
                        avatar_image_url = avatar_data["preview_image_url"]
                    elif avatar_data.get("image_url"):
                        avatar_image_url = avatar_data["image_url"]
                    elif avatar_data.get("preview_image"):
                        avatar_image_url = avatar_data["preview_image"]
                    else:
                        # Fallback: construct URL based on avatar type
                        avatar_image_url = f"https://files2.heygen.ai/avatar/v3/{heygen_avatar_id}/{heygen_avatar_id}.jpg"
                    
                    logger.info(f"HeyGen avatar validated successfully (type: {avatar_type})")
                else:
                    # Validation failed but we'll add it anyway with a warning
                    logger.warning(f"Could not validate HeyGen avatar {heygen_avatar_id} - adding with fallback data")
                    avatar_name = f"Unvalidated Avatar {heygen_avatar_id[:8]}"
                    avatar_image_url = f"https://files2.heygen.ai/avatar/v3/{heygen_avatar_id}/{heygen_avatar_id}.jpg"
                    
            except Exception as validation_error:
                logger.error(f"HeyGen validation error for {heygen_avatar_id}: {validation_error}")
                # Fallback: Add avatar without validation
                avatar_name = f"HeyGen Avatar {heygen_avatar_id[:8]}"
                avatar_image_url = f"https://files2.heygen.ai/avatar/v3/{heygen_avatar_id}/{heygen_avatar_id}.jpg"
        
        # Add avatar to database
        execute_query(
            """
            INSERT INTO user_avatars (user_id, avatar_id, heygen_avatar_id, avatar_name, avatar_image_url, is_default, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """,
            (user_id, heygen_avatar_id, heygen_avatar_id, avatar_name, avatar_image_url, False)
        )
        
        logger.info(f"Admin added HeyGen avatar {heygen_avatar_id} for user {user_id}")
        
        return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?success=avatar_added", status_code=302)
        
    except Exception as e:
        logger.error(f"Error adding HeyGen avatar: {e}")
        return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?error=heygen_failed", status_code=302)

# ===============================================================================
# CHAPTER 5: CREATE USER FUNCTIONALITY
# ===============================================================================

@router.get("/create-user")
async def admin_create_user_page(request: Request):
    """Create user page"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return RedirectResponse(url="/login", status_code=302)
        
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Create User - MyAvatar Admin</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .form-group {{ margin: 20px 0; }}
                label {{ display: block; margin-bottom: 8px; font-weight: bold; color: #333; }}
                input {{ padding: 12px; width: 100%; box-sizing: border-box; border: 1px solid #ddd; border-radius: 4px; }}
                button {{ padding: 12px 24px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }}
                button:hover {{ background: #0056b3; }}
                .checkbox-group {{ display: flex; align-items: center; gap: 8px; }}
                .checkbox-group input {{ width: auto; }}
                h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>➕ Create New User</h1>
                
                <form method="post" action="/admin/create-user">
                    <div class="form-group">
                        <label for="username">Username:</label>
                        <input type="text" id="username" name="username" required>
                    </div>
                    
                    <div class="form-group">
                        <label for="email">Email:</label>
                        <input type="email" id="email" name="email" required>
                    </div>
                    
                    <div class="form-group">
                        <label for="password">Password:</label>
                        <input type="password" id="password" name="password" required>
                    </div>
                    
                    <div class="form-group">
                        <div class="checkbox-group">
                            <input type="checkbox" id="is_admin" name="is_admin" value="1">
                            <label for="is_admin">Make this user an admin</label>
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <div class="checkbox-group">
                            <input type="checkbox" id="is_premium" name="is_premium" value="1">
                            <label for="is_premium">💎 Make this user premium</label>
                        </div>
                    </div>
                    
                    <button type="submit">Create User</button>
                </form>
                
                <div style="margin-top: 30px; text-align: center;">
                    <a href="/admin">← Back to Admin Dashboard</a>
                </div>
            </div>
        </body>
        </html>
        """)
        
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error</h1><p>{str(e)}</p>")

@router.post("/create-user")
async def admin_create_user(request: Request):
    """Create new user"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return RedirectResponse(url="/login", status_code=302)
        
        form = await request.form()
        username = str(form.get("username", "")).strip()
        email = str(form.get("email", "")).strip()
        password = str(form.get("password", ""))
        is_admin = bool(form.get("is_admin"))
        is_premium = bool(form.get("is_premium"))
        
        if not username or not email or not password:
            return HTMLResponse(content="""
            <h1>Error</h1>
            <p>All fields are required</p>
            <a href="/admin/create-user">← Back to Create User</a>
            """)
        
        # Check if user exists
        if db.get_user_by_username(username):
            return HTMLResponse(content=f"""
            <h1>Error</h1>
            <p>Username '{username}' already exists</p>
            <a href="/admin/create-user">← Back to Create User</a>
            """)
        
        # Create user
        import bcrypt
        import uuid
        from datetime import datetime
        
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        api_key = str(uuid.uuid4())
        
        user_data = {
            "username": username,
            "email": email,
            "password": hashed_password,
            "api_key": api_key,
            "is_admin": 1 if is_admin else 0,
            "is_premium": 1 if is_premium else 0,
            "created_at": datetime.now().isoformat(),
            "email_verified": 1
        }
        
        user_id = db.create_user(user_data)
        
        if user_id:
            logger.info(f"Admin {admin_user.get('username')} created user {username} (ID: {user_id}) - Premium: {is_premium}")
            return HTMLResponse(content=f"""
            <div style="font-family: Arial, sans-serif; margin: 40px; max-width: 600px; margin: 0 auto; padding: 30px; background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <h1 style="color: #28a745;">✅ Success!</h1>
                <p><strong>User '{username}' created successfully!</strong></p>
                <p>User ID: {user_id}</p>
                <p>Admin: {'Yes' if is_admin else 'No'}</p>
                <p>Premium: {'Yes' if is_premium else 'No'}</p>
                <p>
                    <a href="/admin/create-user">Create Another User</a> | 
                    <a href="/admin">Back to Admin Dashboard</a>
                </p>
            </div>
            """)
        else:
            return HTMLResponse(content="""
            <h1>Error</h1>
            <p>Failed to create user</p>
            <a href="/admin/create-user">← Back to Create User</a>
            """)
            
    except Exception as e:
        logger.error(f"Admin create user error: {e}")
        return HTMLResponse(content=f"""
        <h1>Error</h1>
        <p>{str(e)}</p>
        <a href="/admin/create-user">← Back to Create User</a>
        """)

# ===============================================================================
# CHAPTER 6: PREMIUM MANAGEMENT - MAIN DASHBOARD
# ===============================================================================

@router.get("/premium-management")
async def admin_premium_management(request: Request):
    """Premium management dashboard"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return RedirectResponse(url="/login", status_code=302)
        
        # Get premium users statistics
        premium_stats = execute_query("""
            SELECT 
                COUNT(*) as total_users,
                COUNT(CASE WHEN is_premium = true THEN 1 END) as premium_users,
                COUNT(CASE WHEN is_premium = false THEN 1 END) as free_users
            FROM users
        """, fetch_one=True)
        
        stats_dict = dict(premium_stats) if premium_stats else {"total_users": 0, "premium_users": 0, "free_users": 0}
        
        # Get recent premium users
        recent_premium = execute_query("""
            SELECT u.id, u.username, u.email, u.created_at, u.last_login,
                   COUNT(DISTINCT v.id) as video_count
            FROM users u
            LEFT JOIN videos v ON u.id = v.user_id
            WHERE u.is_premium = true
            GROUP BY u.id, u.username, u.email, u.created_at, u.last_login
            ORDER BY u.created_at DESC
            LIMIT 10
        """, fetch_all=True)
        
        # Build premium users HTML table
        premium_users_html = ""
        if recent_premium:
            for user in recent_premium:
                user_dict = dict(user) if hasattr(user, '_asdict') else user
                premium_users_html += f"""
                <tr>
                    <td>{user_dict.get('id')}</td>
                    <td>💎 {user_dict.get('username')}</td>
                    <td>{user_dict.get('email', 'N/A')}</td>
                    <td>{user_dict.get('video_count', 0)}</td>
                    <td>{str(user_dict.get('created_at', 'N/A'))[:10] if user_dict.get('created_at') else 'N/A'}</td>
                    <td>
                        <a href="/admin/toggle-premium/{user_dict.get('id')}" style="color: #dc3545;">Remove Premium</a>
                    </td>
                </tr>
                """
        
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Premium Management - MyAvatar Admin</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
                .stat-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; }}
                .stat-number {{ font-size: 2em; font-weight: bold; color: #ffc107; }}
                .stat-premium {{ color: #28a745; }}
                .stat-free {{ color: #6c757d; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background: #f8f9fa; font-weight: bold; }}
                tr:hover {{ background: #f8f9fa; }}
                h1 {{ color: #333; border-bottom: 2px solid #ffc107; padding-bottom: 10px; }}
                .btn {{ display: inline-block; padding: 10px 20px; margin: 10px 0; background: #007bff; color: white; text-decoration: none; border-radius: 5px; }}
                .btn:hover {{ background: #0056b3; }}
                .btn-premium {{ background: #ffc107; color: black; }}
                .btn-premium:hover {{ background: #e0a800; }}
                .btn-success {{ background: #28a745; }}
                .btn-success:hover {{ background: #1e7e34; }}
                .premium-actions {{ background: #fff3cd; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #ffc107; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>💎 Premium Management</h1>
                
                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-number">{stats_dict['total_users']}</div>
                        <div>Total Users</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number stat-premium">{stats_dict['premium_users']}</div>
                        <div>Premium Users</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number stat-free">{stats_dict['free_users']}</div>
                        <div>Free Users</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number stat-premium">{round((stats_dict['premium_users'] / max(stats_dict['total_users'], 1)) * 100, 1)}%</div>
                        <div>Premium Rate</div>
                    </div>
                </div>
                
                <div class="premium-actions">
                    <h3>🎯 Premium Actions</h3>
                    <div>
                        <a href="/admin/bulk-premium" class="btn btn-premium">Bulk Premium Management</a>
                        <a href="/admin/premium-settings" class="btn btn-success">Premium Settings</a>
                        <a href="/admin/users" class="btn">👥 All Users</a>
                    </div>
                </div>
                
                <h2>Recent Premium Users</h2>
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Username</th>
                            <th>Email</th>
                            <th>Videos</th>
                            <th>Joined</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {premium_users_html}
                    </tbody>
                </table>
                
                <div style="margin-top: 30px; text-align: center;">
                    <a href="/admin" style="color: #007bff;">← Back to Admin Dashboard</a>
                </div>
            </div>
        </body>
        </html>
        """)
        
    except Exception as e:
        logger.error(f"Premium management error: {e}")
        return HTMLResponse(content=f"""
        <div style="font-family: Arial, sans-serif; margin: 40px; padding: 30px; background: #f8d7da; border-radius: 8px;">
            <h1>Error Loading Premium Management</h1>
            <p>Error: {str(e)}</p>
            <p><a href="/admin">← Back to Admin Dashboard</a></p>
        </div>
        """)

# ===============================================================================
# CHAPTER 7: PREMIUM TOGGLE FUNCTIONALITY
# ===============================================================================

@router.get("/toggle-premium/{user_id}")
async def admin_toggle_premium(request: Request, user_id: int):
    """Toggle user premium status"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return RedirectResponse(url="/login", status_code=302)
        
        # Get current user status
        user = db.get_user_by_id(user_id)
        if not user:
            return RedirectResponse(url="/admin/users?error=user_not_found", status_code=302)
        
        current_premium = user.get('is_premium', False)
        new_premium = not current_premium
        
        # Update premium status
        execute_query("UPDATE users SET is_premium = %s WHERE id = %s", (new_premium, user_id))
        
        action = "granted" if new_premium else "revoked"
        logger.info(f"Admin {admin_user.get('username')} {action} premium for user {user.get('username')} (ID: {user_id})")
        
        return RedirectResponse(url=f"/admin/premium-management?success=premium_{action}&username={user.get('username')}", status_code=302)
        
    except Exception as e:
        logger.error(f"Toggle premium error: {e}")
        return RedirectResponse(url="/admin/users?error=premium_toggle_failed", status_code=302)

# ===============================================================================
# CHAPTER 8: BULK PREMIUM MANAGEMENT
# ===============================================================================

@router.get("/bulk-premium")
async def admin_bulk_premium(request: Request):
    """Bulk premium management"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return RedirectResponse(url="/login", status_code=302)
        
        # Get all users for bulk actions
        users = execute_query("""
            SELECT u.id, u.username, u.email, u.is_premium, u.created_at,
                   COUNT(DISTINCT v.id) as video_count
            FROM users u
            LEFT JOIN videos v ON u.id = v.user_id
            GROUP BY u.id, u.username, u.email, u.is_premium, u.created_at
            ORDER BY u.created_at DESC
            LIMIT 100
        """, fetch_all=True)
        
        users_html = ""
        if users:
            for user in users:
                user_dict = dict(user) if hasattr(user, '_asdict') else user
                premium_status = "💎 Premium" if user_dict.get('is_premium') else "Free"
                checkbox_checked = "checked" if user_dict.get('is_premium') else ""
                
                users_html += f"""
                <tr>
                    <td><input type="checkbox" name="user_ids" value="{user_dict.get('id')}" {checkbox_checked}></td>
                    <td>{user_dict.get('id')}</td>
                    <td>{user_dict.get('username')}</td>
                    <td>{user_dict.get('email', 'N/A')}</td>
                    <td>{premium_status}</td>
                    <td>{user_dict.get('video_count', 0)}</td>
                </tr>
                """
        
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Bulk Premium Management - MyAvatar Admin</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background: #f8f9fa; font-weight: bold; }}
                tr:hover {{ background: #f8f9fa; }}
                h1 {{ color: #333; border-bottom: 2px solid #ffc107; padding-bottom: 10px; }}
                .btn {{ display: inline-block; padding: 10px 20px; margin: 10px 5px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; border: none; cursor: pointer; }}
                .btn:hover {{ background: #0056b3; }}
                .btn-success {{ background: #28a745; }}
                .btn-success:hover {{ background: #1e7e34; }}
                .btn-danger {{ background: #dc3545; }}
                .btn-danger:hover {{ background: #c82333; }}
                .actions {{ background: #e9ecef; padding: 15px; border-radius: 4px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>💎 Bulk Premium Management</h1>
                
                <div class="actions">
                    <h3>Bulk Actions</h3>
                    <button type="button" onclick="selectAll()" class="btn">Select All</button>
                    <button type="button" onclick="selectNone()" class="btn">Select None</button>
                    <button type="button" onclick="submitAction('grant')" class="btn btn-success">Grant Premium to Selected</button>
                    <button type="button" onclick="submitAction('revoke')" class="btn btn-danger">Revoke Premium from Selected</button>
                </div>
                
                <form method="post" action="/admin/bulk-premium-action" id="bulkForm">
                    <table>
                        <thead>
                            <tr>
                                <th>Select</th>
                                <th>ID</th>
                                <th>Username</th>
                                <th>Email</th>
                                <th>Status</th>
                                <th>Videos</th>
                            </tr>
                        </thead>
                        <tbody>
                            {users_html}
                        </tbody>
                    </table>
                </form>
                
                <div style="margin-top: 30px; text-align: center;">
                    <a href="/admin/premium-management" style="color: #007bff;">← Back to Premium Management</a>
                </div>
            </div>
            
            <script>
                function selectAll() {{
                    const checkboxes = document.querySelectorAll('input[name="user_ids"]');
                    checkboxes.forEach(cb => cb.checked = true);
                }}
                
                function selectNone() {{
                    const checkboxes = document.querySelectorAll('input[name="user_ids"]');
                    checkboxes.forEach(cb => cb.checked = false);
                }}
                
                function submitAction(action) {{
                    const form = document.getElementById('bulkForm');
                    const actionInput = document.createElement('input');
                    actionInput.type = 'hidden';
                    actionInput.name = 'action';
                    actionInput.value = action;
                    form.appendChild(actionInput);
                    form.submit();
                }}
            </script>
        </body>
        </html>
        """)
        
    except Exception as e:
        logger.error(f"Bulk premium page error: {e}")
        return HTMLResponse(content=f"""
        <div style="font-family: Arial, sans-serif; margin: 40px; padding: 30px; background: #f8d7da; border-radius: 8px;">
            <h1>Error Loading Bulk Premium Management</h1>
            <p>Error: {str(e)}</p>
            <p><a href="/admin/premium-management">← Back to Premium Management</a></p>
        </div>
        """)

@router.post("/bulk-premium-action")
async def admin_bulk_premium_action(request: Request):
    """Process bulk premium actions"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return RedirectResponse(url="/login", status_code=302)
        
        form = await request.form()
        action = form.get("action")
        user_ids = form.getlist("user_ids")
        
        if not action or not user_ids:
            return RedirectResponse(url="/admin/bulk-premium?error=no_selection", status_code=302)
        
        # Convert user_ids to integers
        user_ids = [int(uid) for uid in user_ids if uid.isdigit()]
        
        if not user_ids:
            return RedirectResponse(url="/admin/bulk-premium?error=invalid_selection", status_code=302)
        
        # Perform bulk action
        if action == "grant":
            execute_query("UPDATE users SET is_premium = true WHERE id = ANY(%s)", (user_ids,))
            logger.info(f"Admin {admin_user.get('username')} granted premium to {len(user_ids)} users")
            return RedirectResponse(url=f"/admin/bulk-premium?success=premium_granted&count={len(user_ids)}", status_code=302)
        
        elif action == "revoke":
            execute_query("UPDATE users SET is_premium = false WHERE id = ANY(%s)", (user_ids,))
            logger.info(f"Admin {admin_user.get('username')} revoked premium from {len(user_ids)} users")
            return RedirectResponse(url=f"/admin/bulk-premium?success=premium_revoked&count={len(user_ids)}", status_code=302)
        
        else:
            return RedirectResponse(url="/admin/bulk-premium?error=invalid_action", status_code=302)
            
    except Exception as e:
        logger.error(f"Bulk premium action error: {e}")
        return RedirectResponse(url="/admin/bulk-premium?error=action_failed", status_code=302)

# ===============================================================================
# CHAPTER 9: PREMIUM SETTINGS
# ===============================================================================

@router.get("/premium-settings")
async def admin_premium_settings(request: Request):
    """Premium system settings"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return RedirectResponse(url="/login", status_code=302)
        
        # Get premium statistics
        premium_stats = execute_query("""
            SELECT 
                COUNT(*) as total_users,
                COUNT(CASE WHEN is_premium = true THEN 1 END) as premium_users,
                COUNT(CASE WHEN is_admin = true THEN 1 END) as admin_users,
                COUNT(CASE WHEN is_premium = true AND is_admin = true THEN 1 END) as premium_admins
            FROM users
        """, fetch_one=True)
        
        stats_dict = dict(premium_stats) if premium_stats else {"total_users": 0, "premium_users": 0, "admin_users": 0, "premium_admins": 0}
        
        # Get video statistics
        video_stats = execute_query("""
            SELECT 
                COUNT(*) as total_videos,
                COUNT(CASE WHEN u.is_premium = true THEN 1 END) as premium_videos,
                COUNT(CASE WHEN u.is_premium = false THEN 1 END) as free_videos
            FROM videos v
            JOIN users u ON v.user_id = u.id
        """, fetch_one=True)
        
        video_dict = dict(video_stats) if video_stats else {"total_videos": 0, "premium_videos": 0, "free_videos": 0}
        
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Premium Settings - MyAvatar Admin</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
                .stat-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; }}
                .stat-number {{ font-size: 2em; font-weight: bold; color: #ffc107; }}
                .stat-premium {{ color: #28a745; }}
                .stat-free {{ color: #6c757d; }}
                .stat-admin {{ color: #007bff; }}
                h1 {{ color: #333; border-bottom: 2px solid #ffc107; padding-bottom: 10px; }}
                .settings-section {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .btn {{ display: inline-block; padding: 10px 20px; margin: 10px 5px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; }}
                .btn:hover {{ background: #0056b3; }}
                .btn-success {{ background: #28a745; }}
                .btn-success:hover {{ background: #1e7e34; }}
                .btn-warning {{ background: #ffc107; color: black; }}
                .btn-warning:hover {{ background: #e0a800; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>⚙️ Premium Settings</h1>
                
                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-number">{stats_dict['total_users']}</div>
                        <div>Total Users</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number stat-premium">{stats_dict['premium_users']}</div>
                        <div>Premium Users</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number stat-admin">{stats_dict['admin_users']}</div>
                        <div>Admin Users</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number stat-premium">{round((stats_dict['premium_users'] / max(stats_dict['total_users'], 1)) * 100, 1)}%</div>
                        <div>Premium Rate</div>
                    </div>
                </div>
                
                <div class="settings-section">
                    <h3>📊 Video Statistics</h3>
                    <div class="stats">
                        <div class="stat-card">
                            <div class="stat-number">{video_dict['total_videos']}</div>
                            <div>Total Videos</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number stat-premium">{video_dict['premium_videos']}</div>
                            <div>Premium Videos</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number stat-free">{video_dict['free_videos']}</div>
                            <div>Free Videos</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number stat-premium">{round((video_dict['premium_videos'] / max(video_dict['total_videos'], 1)) * 100, 1)}%</div>
                            <div>Premium Video Rate</div>
                        </div>
                    </div>
                </div>
                
                <div class="settings-section">
                    <h3>🎯 Premium Management Actions</h3>
                    <p>Quick actions for premium user management:</p>
                    <div>
                        <a href="/admin/bulk-premium" class="btn btn-warning">📋 Bulk Premium Management</a>
                        <a href="/admin/premium-management" class="btn btn-success">💎 Premium Dashboard</a>
                        <a href="/admin/users" class="btn">👥 All Users</a>
                    </div>
                </div>
                
                <div class="settings-section">
                    <h3>📈 Premium System Status</h3>
                    <p><strong>System:</strong> Operational ✅</p>
                    <p><strong>Database:</strong> Premium fields active ✅</p>
                    <p><strong>Admin Controls:</strong> Full access enabled ✅</p>
                    <p><strong>Bulk Operations:</strong> Available ✅</p>
                </div>
                
                <div style="margin-top: 30px; text-align: center;">
                    <a href="/admin/premium-management" style="color: #007bff;">← Back to Premium Management</a>
                </div>
            </div>
        </body>
        </html>
        """)
        
    except Exception as e:
        logger.error(f"Premium settings error: {e}")
        return HTMLResponse(content=f"""
        <div style="font-family: Arial, sans-serif; margin: 40px; padding: 30px; background: #f8d7da; border-radius: 8px;">
            <h1>Error Loading Premium Settings</h1>
            <p>Error: {str(e)}</p>
            <p><a href="/admin/premium-management">← Back to Premium Management</a></p>
        </div>
        """)

# ===============================================================================
# CHAPTER 10: UTILITY ROUTES
# ===============================================================================

@router.get("/debug-database")
async def admin_debug_database(request: Request):
    """Database debugging"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return JSONResponse({"error": "Admin access required"}, status_code=403)
        
        # Get basic database info
        tables = []
        try:
            tables_result = execute_query("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'", fetch_all=True)
            tables = [dict(row)['table_name'] for row in tables_result] if tables_result else []
        except Exception as e:
            tables = [f"Error: {str(e)}"]
        
        return {
            "success": True,
            "admin_user": admin_user.get("username"),
            "database_type": "PostgreSQL",
            "tables": tables,
            "total_tables": len(tables)
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/vacation-stats")
async def vacation_stats(request: Request):
    """Detailed vacation mode statistics"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return JSONResponse({"error": "Admin access required"}, status_code=403)
        
        return admin_get_vacation_status()
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/premium-status")
async def admin_premium_status(request: Request):
    """Premium system status"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return JSONResponse({"error": "Admin access required"}, status_code=403)
        
        return {
            "premium_system_status": "operational",
            "admin_user": admin_user.get("username"),
            "timestamp": "2025-07-10T18:00:00Z"
        }
        
    except Exception as e:
        return {"error": str(e)}

# Dashboard redirect
@router.get("/dashboard")
async def admin_dashboard_redirect(request: Request):
    """Redirect to main admin dashboard"""
    return RedirectResponse(url="/admin", status_code=302)

# ===============================================================================
# CHAPTER 11: VACATION MODE SETTINGS
# ===============================================================================

@router.get("/vacation-settings")
async def vacation_settings_page(request: Request):
    """Vacation mode settings page"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return RedirectResponse(url="/login", status_code=302)
        
        settings = vacation_manager.get_settings()
        
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Vacation Mode Settings - MyAvatar Admin</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .form-group {{ margin: 20px 0; }}
                label {{ display: block; margin-bottom: 8px; font-weight: bold; color: #333; }}
                input {{ padding: 12px; width: 100%; box-sizing: border-box; border: 1px solid #ddd; border-radius: 4px; }}
                button {{ padding: 12px 24px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }}
                button:hover {{ background: #0056b3; }}
                h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
                .current-settings {{ background: #e9ecef; padding: 15px; border-radius: 4px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🏖️ Vacation Mode Settings</h1>
                
                <div class="current-settings">
                    <h3>Current Settings</h3>
                    <p><strong>Vacation Mode:</strong> {'Enabled' if settings['vacation_mode_enabled'] else 'Disabled'}</p>
                    <p><strong>Emergency Stop:</strong> {'Active' if settings['emergency_stop'] else 'Inactive'}</p>
                    <p><strong>Max Users:</strong> {settings['limits']['max_total_users']}</p>
                    <p><strong>Max Daily Registrations:</strong> {settings['limits']['max_daily_registrations']}</p>
                    <p><strong>Max Videos per User:</strong> {settings['limits']['max_videos_per_user']}</p>
                </div>
                
                <form method="post" action="/admin/vacation-settings">
                    <div class="form-group">
                        <label for="max_users">Maximum Total Users:</label>
                        <input type="number" id="max_users" name="max_users" value="{settings['limits']['max_total_users']}" required>
                    </div>
                    
                    <div class="form-group">
                        <label for="max_daily">Maximum Daily Registrations:</label>
                        <input type="number" id="max_daily" name="max_daily" value="{settings['limits']['max_daily_registrations']}" required>
                    </div>
                    
                    <div class="form-group">
                        <label for="max_videos">Maximum Videos per User:</label>
                        <input type="number" id="max_videos" name="max_videos" value="{settings['limits']['max_videos_per_user']}" required>
                    </div>
                    
                    <button type="submit">Update Settings</button>
                </form>
                
                <div style="margin-top: 30px; text-align: center;">
                    <a href="/admin" style="color: #007bff;">← Back to Admin Dashboard</a>
                </div>
            </div>
        </body>
        </html>
        """)
        
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error</h1><p>{str(e)}</p>")

@router.post("/vacation-settings")
async def update_vacation_settings(request: Request):
    """Update vacation mode settings"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return RedirectResponse(url="/login", status_code=302)
        
        form = await request.form()
        max_users = int(form.get("max_users", 300))
        max_daily = int(form.get("max_daily", 30))
        max_videos = int(form.get("max_videos", 7))
        
        result = admin_set_user_limits(max_users, max_daily, max_videos)
        
        return RedirectResponse(url="/admin/vacation-settings", status_code=302)
        
    except Exception as e:
        logger.error(f"Error updating vacation settings: {e}")
        return HTMLResponse(content=f"<h1>Error</h1><p>Error updating settings: {str(e)}</p>")

# ===============================================================================
# CHAPTER 12: EMERGENCY ACCESS
# ===============================================================================

@router.get("/emergency")
async def emergency_admin_access(request: Request):
    """Emergency admin access - bypass require_admin"""
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Emergency Admin Access</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; }
            h1 { color: #dc3545; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚨 Emergency Admin Access</h1>
            <p><strong>SUCCESS!</strong> If you can see this, the admin routes are loading!</p>
            <p>The issue is with the require_admin function, not the routing.</p>
            <hr>
            <p><a href="/login">Go to Login</a></p>
            <p><a href="/admin/debug">Try Debug Route</a></p>
            <p><a href="/">Go to Home</a></p>
        </div>
    </body>
    </html>
    """)

@router.get("/debug")
async def debug_admin_no_auth(request: Request):
    """Debug admin dashboard without authentication"""
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Debug Admin - No Auth</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔧 Debug Admin Dashboard</h1>
            <p>This is the admin dashboard WITHOUT authentication checks.</p>
            <p>If you can see this, your admin routes work fine!</p>
            <hr>
            <p><strong>Links to test:</strong></p>
            <ul>
                <li><a href="/admin/users-debug">Test Users Route (No Auth)</a></li>
                <li><a href="/login">Back to Login</a></li>
            </ul>
        </div>
    </body>
    </html>
    """)

@router.get("/users-debug")
async def debug_users_no_auth(request: Request):
    """Debug users route without authentication"""
    try:
        # Simple user query without authentication
        users = execute_query("SELECT id, username, email FROM users LIMIT 5", fetch_all=True)
        
        users_html = ""
        if users:
            for user in users:
                user_dict = dict(user) if hasattr(user, '_asdict') else user
                users_html += f"<li>ID: {user_dict.get('id')} - {user_dict.get('username')} - {user_dict.get('email')}</li>"
        
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Debug Users - No Auth</title>
            <style>body {{ font-family: Arial, sans-serif; margin: 20px; }}</style>
        </head>
        <body>
            <h1>🔧 Debug Users (No Auth)</h1>
            <p>Database connection test:</p>
            <ul>{users_html}</ul>
            <p><a href="/admin/debug">Back to Debug</a></p>
        </body>
        </html>
        """)
        
    except Exception as e:
        return HTMLResponse(content=f"""
        <h1>Debug Users Error</h1>
        <p>Error: {str(e)}</p>
        <p><a href="/admin/debug">Back to Debug</a></p>
        """)
