"""
Web routes for MyAvatar
"""
import os
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta
from typing import Optional
from ..db.database import execute_query
from ..auth.authentication import (get_current_user, authenticate_user, authenticate_user_by_email,
                                  create_access_token, get_password_hash, is_admin)
from ..logger.log_handler import log_info, log_error

# Create router
router = APIRouter(prefix="", tags=["web"])

# Set up templates
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Main page - redirects to dashboard if logged in, otherwise shows login page
    """
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=303)
    
    return templates.TemplateResponse("portal/login.html", {"request": request})

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
    Process login
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
        
        # Create response
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
            INSERT INTO users (username, email, password, created_at)
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

@router.get("/logout")
async def logout(request: Request):
    """
    Logout user
    """
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """
    User dashboard
    """
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
    
    # Render dashboard with embedded HTML
    with open("templates/dashboard.html", "r") as f:
        dashboard_html = f.read()
    
    # Convert to list of dicts for videos and avatars
    video_list = []
    for v in videos:
        if isinstance(v, dict):
            video_list.append(v)
        else:
            # Handle SQLite Row objects
            video_dict = {}
            for key in v.keys():
                video_dict[key] = v[key]
            video_list.append(video_dict)
    
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
    
    return HTMLResponse(content=dashboard_html.format(
        username=user["username"],
        is_admin=user["is_admin"],
        avatar_id=user["avatar_id"],
        user_id=user["id"],
        api_key=user.get("api_key", os.getenv("HEYGEN_API_KEY", "")),
        videos=video_list,
        avatars=avatar_list
    ))

# Admin routes
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
            INSERT INTO users (username, email, password, created_at, is_admin, api_key)
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
