"""
Web routes for MyAvatar
"""
import os
import uuid
import requests
from werkzeug.utils import secure_filename
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta
from typing import Optional
from ..db.database import execute_query
from ..auth.authentication import (get_current_user, authenticate_user, authenticate_user_by_email,
                                  create_access_token, get_password_hash, is_admin)
from ..logger.log_handler import log_info, log_error

# ============================================================================
# ROUTER SETUP
# ============================================================================

# Create router
router = APIRouter(prefix="", tags=["web"])

# Set up templates
templates = Jinja2Templates(directory="templates")

# ============================================================================
# MAIN PAGES - WITH ADMIN REDIRECT
# ============================================================================

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Main page - redirects to appropriate dashboard if logged in, otherwise shows login page
    """
    user = get_current_user(request)
    if user:
        # Redirect admin users to admin dashboard
        if user.get("is_admin", 0) == 1:
            return RedirectResponse(url="/admin/dashboard", status_code=303)
        else:
            return RedirectResponse(url="/dashboard", status_code=303)
    
    return templates.TemplateResponse("portal/login.html", {"request": request})

# ============================================================================
# AUTHENTICATION ROUTES - WITH ADMIN REDIRECT
# ============================================================================

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """
    Login page
    """
    return templates.TemplateResponse("portal/login.html", {"request": request})

@router.post("/auth/login", response_class=HTMLResponse)
async def login_post(
    request: Request,
    username: str = Form(None),
    email: str = Form(None),
    password: str = Form(...)
):
    """
    Process login - WITH ADMIN REDIRECT
    """
    try:
        # Try to authenticate by username or email
        user = None
        if username:
            user = authenticate_user(username, password)
        elif email:
            user = authenticate_user_by_email(email, password)
        
        if not user:
            return templates.TemplateResponse(
                "portal/login.html", 
                {
                    "request": request, 
                    "error": "Invalid username/email or password"
                }
            )
        
        # Create access token
        access_token = create_access_token(
            data={"sub": user["username"]},
            expires_delta=timedelta(minutes=120)
        )
        
        # Create response - redirect admin users to admin dashboard
        if user.get("is_admin", 0) == 1:
            response = RedirectResponse(url="/admin/dashboard", status_code=303)
        else:
            response = RedirectResponse(url="/dashboard", status_code=303)
            
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True
        )
        
        log_info(f"User {user['username']} logged in", "Web")
        return response
        
    except Exception as e:
        log_error("Login error", "Web", e)
        return templates.TemplateResponse(
            "portal/login.html",
            {
                "request": request,
                "error": "Login error"
            }
        )

@router.get("/logout")
async def logout(request: Request):
    """
    Logout user
    """
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response

# ============================================================================
# REGISTRATION ROUTES
# ============================================================================

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """
    Registration page
    """
    return templates.TemplateResponse("portal/register.html", {"request": request})

@router.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    """
    Process registration
    """
    try:
        # Check if user already exists
        existing_user = execute_query(
            "SELECT * FROM users WHERE username = ? OR email = ?",
            (username, email),
            fetch_one=True
        )
        
        if existing_user:
            return templates.TemplateResponse(
                "portal/register.html",
                {
                    "request": request,
                    "error": "Username or email already exists"
                }
            )
        
        # Create user
        hashed_password = get_password_hash(password)
        execute_query(
            """
            INSERT INTO users (username, email, hashed_password, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (username, email, hashed_password, datetime.now().isoformat())
        )
        
        log_info(f"User {username} registered", "Web")
        
        # Redirect to login
        return templates.TemplateResponse(
            "portal/login.html",
            {
                "request": request,
                "success": "Registration successful. Please log in."
            }
        )
        
    except Exception as e:
        log_error("Registration error", "Web", e)
        return templates.TemplateResponse(
            "portal/register.html",
            {
                "request": request,
                "error": "Registration error"
            }
        )

# ============================================================================
# DASHBOARD ROUTE - WITH REAL STATISTICS
# ============================================================================

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """
    User dashboard - With real statistics instead of mock data
    """
    # Check authentication
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    
    # Get user's videos
    videos = execute_query(
        "SELECT * FROM videos WHERE user_id = ? ORDER BY created_at DESC",
        (user["id"],),
        fetch_all=True
    )
    
    # Get user's avatars
    avatars = execute_query(
        "SELECT * FROM user_avatars WHERE user_id = ?",
        (user["id"],),
        fetch_all=True
    )
    
    # Convert database results to list of dicts for videos
    video_list = []
    total_duration = 0
    total_views = 0
    total_shares = 0
    
    for v in videos:
        if isinstance(v, dict):
            video_dict = v
        else:
            # Handle SQLite Row objects
            video_dict = {}
            for key in v.keys():
                video_dict[key] = v[key]
        
        video_list.append(video_dict)
        
        # Calculate real statistics
        if video_dict.get('duration'):
            total_duration += float(video_dict['duration'])
        # Note: views and shares would need to be tracked in your database
        # For now, we'll set them to 0 since those columns don't exist yet
    
    # Convert database results to list of dicts for avatars
    avatar_list = []
    for a in avatars:
        if isinstance(a, dict):
            avatar_list.append(a)
        else:
            # Handle SQLite Row objects
            avatar_dict = {}
            for key in a.keys():
                avatar_dict[key] = a[key]
            avatar_list.append(avatar_dict)
    
    # Calculate real statistics
    total_videos = len(video_list)
    total_duration_hours = round(total_duration / 3600, 1) if total_duration > 0 else 0
    
    # Use proper template rendering with REAL statistics
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "username": user.get("username", ""),
            "is_admin": user.get("is_admin", 0), 
            "avatar_id": user.get("avatar_id", ""),
            "user_id": user.get("id", 0),
            "api_key": user.get("api_key", "") or os.getenv("HEYGEN_API_KEY", ""),
            "videos": video_list,
            "avatars": avatar_list,
            # REAL STATISTICS - not mock data
            "total_videos": total_videos,
            "total_duration": f"{total_duration_hours}h" if total_duration_hours > 0 else "0h",
            "total_views": total_views,  # Will be 0 until view tracking is implemented
            "total_shares": total_shares,  # Will be 0 until share tracking is implemented
        }
    )

# ============================================================================
# ADMIN ROUTES
# ============================================================================

@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users(request: Request):
    """
    Admin users page
    """
    user = get_current_user(request)
    if not user or not is_admin(request):
        return RedirectResponse(url="/login", status_code=303)
    
    # Get all users
    users = execute_query(
        "SELECT * FROM users ORDER BY created_at DESC",
        fetch_all=True
    )
    
    return templates.TemplateResponse(
        "portal/admin_users.html",
        {
            "request": request,
            "users": users
        }
    )

@router.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """
    Admin dashboard
    """
    user = get_current_user(request)
    if not user or not is_admin(request):
        return RedirectResponse(url="/login", status_code=303)
    
    # Get stats
    user_count = execute_query(
        "SELECT COUNT(*) as count FROM users",
        fetch_one=True
    )
    
    video_count = execute_query(
        "SELECT COUNT(*) as count FROM videos",
        fetch_one=True
    )
    
    avatar_count = execute_query(
        "SELECT COUNT(*) as count FROM user_avatars",
        fetch_one=True
    )
    
    return templates.TemplateResponse(
        "portal/admin_dashboard.html",
        {
            "request": request,
            "user_count": user_count["count"] if user_count else 0,
            "video_count": video_count["count"] if video_count else 0,
            "avatar_count": avatar_count["count"] if avatar_count else 0
        }
    )

@router.get("/admin/create-user", response_class=HTMLResponse)
async def admin_create_user_page(request: Request):
    """
    Admin create user page
    """
    user = get_current_user(request)
    if not user or not is_admin(request):
        return RedirectResponse(url="/login", status_code=303)
    
    return templates.TemplateResponse(
        "portal/admin_create_user.html",
        {"request": request}
    )

@router.post("/admin/create-user")
async def admin_create_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    is_admin_user: bool = Form(False),
    api_key: str = Form(None)
):
    """
    Admin create user
    """
    user = get_current_user(request)
    if not user or not is_admin(request):
        return RedirectResponse(url="/login", status_code=303)
    
    try:
        # Check if user already exists
        existing_user = execute_query(
            "SELECT * FROM users WHERE username = ? OR email = ?",
            (username, email),
            fetch_one=True
        )
        
        if existing_user:
            return templates.TemplateResponse(
                "portal/admin_create_user.html",
                {
                    "request": request,
                    "error": "Username or email already exists"
                }
            )
        
        # Create user
        hashed_password = get_password_hash(password)
        execute_query(
            """
            INSERT INTO users (username, email, hashed_password, created_at, is_admin, api_key)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (username, email, hashed_password, datetime.now().isoformat(), is_admin_user, api_key)
        )
        
        log_info(f"Admin {user['username']} created user {username}", "Admin")
        
        # Redirect to users list
        return RedirectResponse(url="/admin/users", status_code=303)
        
    except Exception as e:
        log_error("Admin create user error", "Admin", e)
        return templates.TemplateResponse(
            "portal/admin_create_user.html",
            {
                "request": request,
                "error": "Error creating user"
            }
        )

@router.get("/admin/edit-user/{user_id}", response_class=HTMLResponse)
async def admin_edit_user_page(request: Request, user_id: int):
    """Admin edit user page"""
    user = get_current_user(request)
    if not user or not is_admin(request):
        return RedirectResponse(url="/login", status_code=303)
    
    try:
        # Get the user to edit
        user_to_edit = execute_query(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
            fetch_one=True
        )
        
        if not user_to_edit:
            return RedirectResponse(url="/admin/users?error=user_not_found", status_code=303)
        
        return templates.TemplateResponse("portal/admin_edit_user.html", {
            "request": request,
            "user": user,
            "user_to_edit": user_to_edit,
            "title": f"Edit User: {user_to_edit['username']}"
        })
    except Exception as e:
        log_error(f"Error in admin_edit_user_page: {e}", "Admin", e)
        return RedirectResponse(url="/admin/users?error=system_error", status_code=303)

@router.post("/admin/edit-user/{user_id}")
async def admin_edit_user_submit(request: Request, user_id: int):
    """Handle admin edit user form submission"""
    user = get_current_user(request)
    if not user or not is_admin(request):
        return RedirectResponse(url="/login", status_code=303)
    
    try:
        # Get form data
        form = await request.form()
        username = form.get("username", "").strip()
        email = form.get("email", "").strip()
        is_premium = 1 if form.get("is_premium") == "on" else 0
        is_admin_user = 1 if form.get("is_admin") == "on" else 0
        
        # Update user
        execute_query(
            """
            UPDATE users 
            SET username = ?, email = ?, is_premium = ?, is_admin = ?
            WHERE id = ?
            """,
            (username, email, is_premium, is_admin_user, user_id)
        )
        
        log_info(f"Admin {user['username']} updated user {username}", "Admin")
        return RedirectResponse(url=f"/admin/users?success=user_updated", status_code=303)
    
    except Exception as e:
        log_error(f"Error updating user: {e}", "Admin", e)
        return RedirectResponse(url=f"/admin/edit-user/{user_id}?error=update_failed", status_code=303)

@router.get("/admin/manage-avatars/{user_id}", response_class=HTMLResponse)
async def admin_manage_avatars_page(request: Request, user_id: int):
    """Admin manage user avatars page"""
    user = get_current_user(request)
    if not user or not is_admin(request):
        return RedirectResponse(url="/login", status_code=303)
    
    try:
        # Get the user to manage
        user_to_manage = execute_query(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
            fetch_one=True
        )
        
        if not user_to_manage:
            return RedirectResponse(url="/admin/users?error=user_not_found", status_code=303)
        
        # Get user's avatars
        avatars = execute_query(
            "SELECT * FROM user_avatars WHERE user_id = ?",
            (user_id,),
            fetch_all=True
        )
        
        return templates.TemplateResponse("portal/admin_manage_avatars.html", {
            "request": request,
            "user": user,
            "user_to_manage": user_to_manage,
            "avatars": avatars,
            "title": f"Manage Avatars: {user_to_manage['username']}"
        })
    except Exception as e:
        log_error(f"Error in admin_manage_avatars_page: {e}", "Admin", e)
        return RedirectResponse(url="/admin/users?error=system_error", status_code=303)

@router.post("/admin/delete-avatar/{avatar_id}")
async def admin_delete_avatar(request: Request, avatar_id: int):
    """Admin delete avatar"""
    user = get_current_user(request)
    if not user or not is_admin(request):
        return RedirectResponse(url="/login", status_code=303)
    
    try:
        # Get avatar info first
        avatar = execute_query(
            "SELECT user_id FROM user_avatars WHERE id = ?",
            (avatar_id,),
            fetch_one=True
        )
        
        if avatar:
            user_id = avatar["user_id"]
            # Delete avatar
            execute_query(
                "DELETE FROM user_avatars WHERE id = ?",
                (avatar_id,)
            )
            log_info(f"Admin {user['username']} deleted avatar {avatar_id}", "Admin")
            return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?success=avatar_deleted", status_code=303)
        else:
            return RedirectResponse(url="/admin/users?error=avatar_not_found", status_code=303)
            
    except Exception as e:
        log_error(f"Error deleting avatar: {e}", "Admin", e)
        return RedirectResponse(url="/admin/users?error=delete_failed", status_code=303)

@router.post("/admin/upload-image/{user_id}")
async def admin_upload_image(request: Request, user_id: int):
    """Admin upload image for user - UPDATED"""
    user = get_current_user(request)
    if not user or not is_admin(request):
        return RedirectResponse(url="/login", status_code=303)
    
    try:
        form = await request.form()
        image_file = form.get("image_file")  # Changed from "avatar_file"
        
        if not image_file or not image_file.filename:
            return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?error=no_file", status_code=303)
        
        # Check file type
        allowed_types = ['.png', '.jpg', '.jpeg', '.gif']
        file_ext = os.path.splitext(image_file.filename)[1].lower()
        if file_ext not in allowed_types:
            return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?error=invalid_file", status_code=303)
        
        # Create uploads directory if it doesn't exist
        upload_dir = "static/uploads/avatars"
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate secure filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_ext = os.path.splitext(image_file.filename)[1].lower()
        unique_filename = f"user_{user_id}_{timestamp}{file_ext}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        # Save file
        with open(file_path, "wb") as buffer:
            content = await image_file.read()
            buffer.write(content)
        
        # Save to database
        avatar_url = f"/static/uploads/avatars/{unique_filename}"
        execute_query(
            """
            INSERT INTO user_avatars (user_id, avatar_name, avatar_url, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, unique_filename, avatar_url, datetime.now().isoformat())
        )
        
        log_info(f"Admin {user['username']} uploaded image for user {user_id}: {unique_filename}", "Admin")
        return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?success=image_uploaded", status_code=303)
        
    except Exception as e:
        log_error(f"Error uploading image: {e}", "Admin", e)
        return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?error=upload_failed", status_code=303)

@router.post("/admin/fetch-heygen-avatar/{user_id}")
async def admin_fetch_heygen_avatar(request: Request, user_id: int):
    """Admin fetch avatar from HeyGen - WITH REAL API INTEGRATION"""
    user = get_current_user(request)
    if not user or not is_admin(request):
        return RedirectResponse(url="/login", status_code=303)
    
    try:
        form = await request.form()
        heygen_avatar_id = form.get("heygen_avatar_id", "").strip()
        
        if not heygen_avatar_id:
            return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?error=no_avatar_id", status_code=303)
        
        # Get HeyGen API key from environment
        heygen_api_key = os.getenv("HEYGEN_API_KEY")
        if not heygen_api_key:
            log_error("HeyGen API key not configured", "Admin")
            return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?error=api_key_missing", status_code=303)
        
        # Make request to HeyGen API to get avatar details
        headers = {
            'X-Api-Key': heygen_api_key,
            'Content-Type': 'application/json'
        }
        
        # HeyGen API endpoint to get avatar details
        heygen_url = f"https://api.heygen.com/v1/avatar/{heygen_avatar_id}"
        
        try:
            response = requests.get(heygen_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                avatar_data = response.json()
                
                # Check if avatar exists and get details
                if avatar_data.get('code') == 100:  # Success code for HeyGen
                    avatar_info = avatar_data.get('data', {})
                    avatar_name = avatar_info.get('avatar_name', heygen_avatar_id)
                    avatar_url = avatar_info.get('preview_image_url', '')
                    
                    # Save avatar record to database
                    execute_query(
                        """
                        INSERT INTO user_avatars (user_id, heygen_avatar_id, avatar_name, avatar_url, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (user_id, heygen_avatar_id, avatar_name, avatar_url, datetime.now().isoformat())
                    )
                    
                    log_info(f"Admin {user['username']} fetched HeyGen avatar {heygen_avatar_id} for user {user_id}", "Admin")
                    return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?success=avatar_fetched", status_code=303)
                else:
                    error_msg = avatar_data.get('message', 'Unknown error')
                    log_error(f"HeyGen API error: {error_msg}", "Admin")
                    return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?error=heygen_api_error", status_code=303)
            
            elif response.status_code == 401:
                log_error("Invalid HeyGen API key", "Admin")
                return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?error=invalid_api_key", status_code=303)
            elif response.status_code == 404:
                log_error(f"HeyGen avatar not found: {heygen_avatar_id}", "Admin")
                return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?error=avatar_not_found", status_code=303)
            else:
                log_error(f"HeyGen API error: {response.status_code}", "Admin")
                return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?error=heygen_failed", status_code=303)
                
        except requests.exceptions.Timeout:
            log_error("HeyGen API request timeout", "Admin")
            return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?error=timeout", status_code=303)
        except requests.exceptions.RequestException as e:
            log_error(f"HeyGen API request error: {e}", "Admin")
            return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?error=connection_failed", status_code=303)
        
    except Exception as e:
        log_error(f"Error fetching HeyGen avatar: {e}", "Admin", e)
        return RedirectResponse(url=f"/admin/manage-avatars/{user_id}?error=system_error", status_code=303)

# ============================================================================
# END OF FILE
# ============================================================================