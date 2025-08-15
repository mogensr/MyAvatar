import logging
from datetime import datetime
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

# Import services
from ..services.auth_service import auth_service
from ..services.avatar_service import avatar_service
from ..config.settings import config
from ..utils.validation import sanitize_input, validate_email, validate_username, validate_password_strength

# FIXED IMPORTS - Use the correct function names from our vacation_mode middleware
from ..middleware.vacation_mode import (
    check_vacation_mode_restrictions, 
    check_registration_limits, 
    check_video_creation_limits,
    get_system_stats,
    vacation_manager
)

# Import database
try:
    from ..db.user_manager import Database
    db = Database()
except ImportError:
    from app.db.user_manager import Database
    db = Database()

logger = logging.getLogger(__name__)

# Initialize templates
templates = Jinja2Templates(directory=config.TEMPLATES_DIR)

# Rate limiting
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    limiter = Limiter(key_func=get_remote_address)
    SLOWAPI_AVAILABLE = True
except ImportError:
    class Limiter:
        def limit(self, rate): 
            def decorator(func): return func
            return decorator
    limiter = Limiter()
    SLOWAPI_AVAILABLE = False

router = APIRouter()

def get_current_user(request: Request):
    """Get current user from request"""
    try:
        token = request.cookies.get("access_token")
        if not token:
            return None
        
        session = auth_service.validate_session(token, request)
        if not session:
            return None
        
        payload = auth_service.validate_token(token)
        if not payload:
            return None
        
        user_id = payload.get("user_id")
        if not user_id:
            return None
        
        return db.get_user_by_id(user_id)
        
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        return None

# Helper functions using our vacation_mode middleware
def check_emergency_stop():
    """Check if emergency stop is active"""
    try:
        is_allowed, message = check_vacation_mode_restrictions("general")
        if not is_allowed and "maintenance" in message.lower():
            return True, message
        return False, None
    except Exception as e:
        logger.error(f"Error checking emergency stop: {e}")
        return False, None

def check_user_limits():
    """Check user registration limits"""
    try:
        return check_registration_limits()
    except Exception as e:
        logger.error(f"Error checking user limits: {e}")
        return False, "Unable to check user limits"

async def check_budget_limits():
    """Check budget limits - simplified for now"""
    try:
        # For now, just check if vacation mode allows registration
        is_allowed, message = check_vacation_mode_restrictions("registration")
        if not is_allowed and "budget" in message.lower():
            return False, message
        return True, None
    except Exception as e:
        logger.error(f"Error checking budget limits: {e}")
        return True, None

async def log_api_cost_event(service: str, endpoint: str, cost: float):
    """Log API cost event - simplified for now"""
    try:
        logger.info(f"API Cost Event: {service} - {endpoint} - ${cost}")
    except Exception as e:
        logger.error(f"Error logging API cost: {e}")

def render_video_grid(videos):
    """Render video grid HTML - FIXED to avoid f-string issues"""
    if not videos:
        return '''
        <div class="empty-state">
            <i class="fas fa-video empty-icon"></i>
            <h3>No videos created yet</h3>
            <p>Start by creating your first AI video using one of the methods above!</p>
        </div>
        '''
    
    video_cards = []
    for video in videos[:3]:
        video_id = str(video.get('id', ''))
        video_status = video.get('status', 'unknown')
        video_title = video.get('title', 'Untitled')
        video_path = video.get('video_path', '')
        video_duration = video.get('duration', '')
        video_created = video.get('created_at', 'Unknown')
        video_format = video.get('format', '16:9')
        
        # Duration span
        duration_span = f'<span class="video-duration">{video_duration}</span>' if video_duration else ''
        
        # Video content and actions based on status
        if video_status == 'completed' and video_path:
            video_content = f'''
                <video controls preload="metadata" style="width: 100%; height: 100%; object-fit: cover;">
                    <source src="{video_path}" type="video/mp4">
                </video>
            '''
            actions = f'''
                <button onclick="window.open('/api/videos/{video_id}/download', '_blank')" class="video-action primary">
                    <i class="fas fa-play"></i> Play
                </button>
                <button onclick="downloadVideo('{video_id}', '{video_title}')" class="video-action secondary">
                    <i class="fas fa-download"></i> Download
                </button>
            '''
        else:
            video_content = f'''
                <div class="video-placeholder">
                    <i class="fas fa-video" style="font-size: 3rem;"></i>
                    <div style="font-size: 0.8rem; margin-top: 10px; color: #666;">
                        Status: {video_status}
                    </div>
                </div>
            '''
            if video_status in ['processing', 'pending']:
                actions = '''
                    <span class="video-action secondary" style="opacity: 0.6;">
                        <i class="fas fa-sync-alt" onclick="location.reload()">Refresh
                    </span>
                '''
            else:
                actions = '''
                    <span class="video-action secondary" style="opacity: 0.6;">
                        <i class="fas fa-exclamation-triangle">Failed
                    </span>
                '''
        
        video_card = f'''
        <div class="video-card" data-video-id="{video_id}" data-status="{video_status}">
            <div class="video-thumbnail">
                {video_content}
                <span class="video-status-badge status-{video_status}">
                    {video_status}
                </span>
                {duration_span}
            </div>
            
            <div class="video-info">
                <div class="video-title">{video_title}</div>
                <div class="video-meta">
                    <span><i class="fas fa-calendar"></i> {video_created}</span>     
                    <span><i class="fas fa-film"></i> {video_format}</span>
                </div>
                
                <div class="video-actions">
                    {actions}
                </div>
            </div>
        </div>
        '''
        video_cards.append(video_card)
    
    return "".join(video_cards)

@router.get("/")
async def home_page(request: Request):
    """Home page with vacation mode protection"""
    try:
        emergency_stop, emergency_msg = check_emergency_stop()
        if emergency_stop:
            return templates.TemplateResponse("maintenance.html", {
                "request": request,
                "message": emergency_msg
            })
        
        # Check budget limits
        budget_ok, budget_msg = await check_budget_limits()
        if not budget_ok:
            return templates.TemplateResponse("maintenance.html", {
                "request": request,
                "message": budget_msg
            })
        
        user = get_current_user(request)
        if user:
            # FIXED: Redirect admin to admin dashboard
            if user.get("is_admin", 0) == 1:
                return RedirectResponse(url="/admin", status_code=302)
            else:
                return RedirectResponse(url="/dashboard", status_code=302)
        
        stats = get_system_stats()
            
        try:
            response = templates.TemplateResponse("index.html", {
                "request": request,
                "user": None,
                "vacation_mode": vacation_manager.vacation_mode_enabled,
                "users_percentage": stats['users_percentage'],
                "stats": stats
            })
        except Exception as template_error:
            logger.warning(f"Template error: {template_error}")
            stats_total = stats.get('total_users', 0)
            max_users = vacation_manager.max_total_users
            return HTMLResponse(content=f'''
                <html><body>
                    <h1>🎭 MyAvatar - Create Amazing AI Videos</h1>
                    <p>Welcome to MyAvatar! Please <a href="/login">login</a> or <a href="/register">register</a>.</p>
                    <p>Beta Status: {stats_total}/{max_users} users</p>
                </body></html>
            ''')
        
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response
    except Exception as e:
        logger.error(f"Error loading home page: {e}")
        return HTMLResponse(content='''
            <html><body>
                <h1>Service Temporarily Unavailable</h1>
                <p><a href="/login">Login</a> | <a href="/register">Register</a></p>
            </body></html>
        ''', status_code=500)

@router.get("/login")
async def login_page(request: Request):
    """Display login page with vacation mode checks"""
    try:
        emergency_stop, emergency_msg = check_emergency_stop()
        if emergency_stop:
            return templates.TemplateResponse("maintenance.html", {
                "request": request,
                "message": emergency_msg
            })
        
        user = get_current_user(request)
        if user:
            # FIXED: Redirect admin to admin dashboard
            if user.get("is_admin", 0) == 1:
                return RedirectResponse(url="/admin", status_code=302)
            else:
                return RedirectResponse(url="/dashboard", status_code=302)
        
        return templates.TemplateResponse("portal/login.html", {
            "request": request,
            "user": None,
            "error": None,
            "vacation_mode": vacation_manager.vacation_mode_enabled
        })
    except Exception as e:
        logger.error(f"Error loading login page: {e}")
        return HTMLResponse(content='''
            <html><body>
                <h1>Login</h1>
                <form method="post" action="/login">
                    <input type="text" name="username" placeholder="Username" required>
                    <input type="password" name="password" placeholder="Password" required>
                    <button type="submit">Login</button>
                </form>
            </body></html>
        ''')

@router.post("/login")
@limiter.limit("5/minute")
async def login_user(request: Request, username: str = Form(...), password: str = Form(...)):
    """Handle user login with vacation mode protection"""
    try:
        emergency_stop, emergency_msg = check_emergency_stop()
        if emergency_stop:
            return templates.TemplateResponse("portal/login.html", {
                "request": request,
                "user": None,
                "error": emergency_msg
            })
        
        username = sanitize_input(username)
        
        if not username or not password:
            return templates.TemplateResponse("portal/login.html", {
                "request": request,
                "user": None,
                "error": "Username and password are required"
            }, status_code=400)
        
        user = db.get_user_by_username(username)
        if not user:
            return templates.TemplateResponse("portal/login.html", {
                "request": request,
                "user": None,
                "error": "Invalid username or password"
            }, status_code=401)
        
        stored_password = user.get("hashed_password", "")
        if not stored_password or not auth_service.verify_password(password, stored_password):
            return templates.TemplateResponse("portal/login.html", {
                "request": request,
                "user": None,
                "error": "Invalid username or password"
            }, status_code=401)
        
        # Create session
        token = auth_service.create_session(user["id"], request)
        db.update_user_login(user["id"])
        
        # Redirect based on user role
        if user.get("is_admin", 0) == 1:
            response = RedirectResponse(url="/admin", status_code=302)
            logger.info(f"Admin {username} logged in successfully - redirecting to /admin")
        else:
            response = RedirectResponse(url="/dashboard", status_code=302)
            logger.info(f"User {username} logged in successfully - redirecting to /dashboard")
        
        # Set secure cookie
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=86400
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error during login: {e}")
        return templates.TemplateResponse("portal/login.html", {
            "request": request,
            "user": None,
            "error": "Login failed. Please try again."
        }, status_code=500)

@router.get("/register")
async def register_page(request: Request):
    """Display registration page with vacation mode protection"""
    try:
        emergency_stop, emergency_msg = check_emergency_stop()
        if emergency_stop:
            return templates.TemplateResponse("maintenance.html", {
                "request": request,
                "message": emergency_msg
            })
        
        user = get_current_user(request)
        if user:
            # FIXED: Redirect admin to admin dashboard
            if user.get("is_admin", 0) == 1:
                return RedirectResponse(url="/admin", status_code=302)
            else:
                return RedirectResponse(url="/dashboard", status_code=302)
        
        # Check budget limits
        budget_ok, budget_msg = await check_budget_limits()
        if not budget_ok:
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": budget_msg,
                "limits_reached": True
            })
        
        # Check user limits
        can_register, limit_msg = check_user_limits()
        if not can_register:
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": limit_msg,
                "limits_reached": True
            })
            
        stats = get_system_stats()
            
        return templates.TemplateResponse("portal/register.html", {
            "request": request,
            "user": None,
            "vacation_mode": vacation_manager.vacation_mode_enabled,
            "stats": stats
        })
    except Exception as e:
        logger.error(f"Error loading register page: {e}")
        return templates.TemplateResponse("portal/register.html", {
            "request": request,
            "user": None,
            "error": "Registration page temporarily unavailable. Please try again."
        })

@router.post("/register")
@limiter.limit("3/minute")
async def register_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...), 
    password: str = Form(...),
    confirm_password: str = Form(...),
    phone_number: str = Form(""),
    country_code: str = Form("+45"),
    sms_notifications: bool = Form(False)
):
    """VACATION-SAFE REGISTRATION with real cost tracking and FIXED AVATAR SETUP"""
    try:
        # Check emergency stop
        emergency_stop, emergency_msg = check_emergency_stop()
        if emergency_stop:
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": emergency_msg
            })
        
        # Check budget limits
        budget_ok, budget_msg = await check_budget_limits()
        if not budget_ok:
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": budget_msg,
                "limits_reached": True
            })
        
        # Check user limits
        can_register, limit_msg = check_user_limits()
        if not can_register:
            logger.warning(f"VACATION MODE - Registration blocked: {limit_msg}")
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": limit_msg,
                "limits_reached": True
            })
        
        # Sanitize inputs
        username = sanitize_input(username)
        email = sanitize_input(email)
        
        logger.info(f"VACATION MODE REGISTRATION - Username: {username}, Email: {email}")
        
        # Validation
        if not username or not email or not password:
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": "All fields are required"
            }, status_code=400)
        
        # Username validation
        username_valid, username_msg = validate_username(username)
        if not username_valid:
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": username_msg
            }, status_code=400)
        
        # Email validation
        if not validate_email(email):
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": "Please enter a valid email address"
            }, status_code=400)
        
        # Password validation
        password_valid, password_msg = validate_password_strength(password)
        if not password_valid:
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": password_msg
            }, status_code=400)
        
        if password != confirm_password:
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": "Passwords do not match"
            }, status_code=400)
        
        # Check if user exists
        if db.get_user_by_username(username):
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": "Username already exists"
            }, status_code=409)
        
        if db.get_user_by_email(email):
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": "Email already registered"
            }, status_code=409)
        
        # Final budget/limit check before creating user
        budget_ok, budget_msg = await check_budget_limits()
        can_register, limit_msg = check_user_limits()
        
        if not budget_ok:
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": budget_msg,
                "limits_reached": True
            })
        
        if not can_register:
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": limit_msg,
                "limits_reached": True
            })
        
        # Create user
        hashed_password = auth_service.hash_password(password)
        api_key = auth_service.generate_api_key()
        
        # Process phone number for SMS notifications
        full_phone = None
        if phone_number and phone_number.strip():
            full_phone = f"{country_code}{phone_number.strip()}"
        
        user_data = {
            "username": username,
            "email": email,
            "password": hashed_password,
            "api_key": api_key,
            "is_admin": 0,
            "is_locked": 0,
            "avatar_id": "",
            "created_at": "now()",
            "email_verified": 0,
            "credits_remaining": vacation_manager.max_credits_per_user,
            "phone_number": full_phone,
            "country_code": country_code,
            "sms_notifications": sms_notifications
        }
        
        user_id = db.create_user(user_data)
        
        if not user_id:
            logger.error(f"VACATION MODE - User creation failed for {username}")
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": "Registration failed. Please try again."
            }, status_code=500)
        
        logger.info(f"VACATION MODE - User {username} created successfully with ID: {user_id}")
        
        # Log cost event for new user registration
        await log_api_cost_event("registration", "create_user", 0.10)
        
        # Set up default avatars with verification
        try:
            avatar_service.setup_default_avatars_for_user(user_id)
            
            # Verify avatars were actually created
            if avatar_service.verify_user_avatars_setup(user_id):
                logger.info(f"VACATION MODE - Default avatars successfully set up for user {username}")
            else:
                logger.error(f"VACATION MODE - Avatar setup verification failed for user {username}")
                
        except Exception as avatar_error:
            logger.error(f"VACATION MODE - Avatar setup failed for user {username}: {avatar_error}")
            # Still allow registration to complete even if avatar setup fails
        
        # Auto-login (new users always go to dashboard, not admin)
        token = auth_service.create_session(user_id, request)
        
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=86400
        )
        
        logger.info(f"VACATION MODE - Registration completed successfully for user: {username}")
        return response
        
    except Exception as e:
        error_details = f"Registration error: {type(e).__name__}: {str(e)}"
        logger.error(f"VACATION MODE REGISTRATION EXCEPTION: {error_details}")
        
        return templates.TemplateResponse("portal/register.html", {
            "request": request,
            "user": None,
            "error": "Our registration system is experiencing high demand. Please try again in a few minutes!"
        }, status_code=500)

@router.get("/logout")
async def logout_user(request: Request):
    """Handle user logout"""
    try:
        token = request.cookies.get("access_token")
        if token:
            auth_service.destroy_session(token)
        
        response = RedirectResponse(url="/", status_code=302)
        response.delete_cookie("access_token")
        return response
    except Exception as e:
        logger.error(f"Error during logout: {e}")
        response = RedirectResponse(url="/", status_code=302)
        response.delete_cookie("access_token")
        return response

@router.get("/dashboard-direct")
async def dashboard_direct(request: Request):
    """Emergency direct dashboard access - bypasses redirect loops"""
    try:
        token = request.cookies.get("access_token")
        if not token:
            return RedirectResponse(url="/login", status_code=302)
        
        # Simple token validation without complex auth checks
        try:
            payload = auth_service.validate_token(token)
            user_id = payload.get("user_id")
            if not user_id:
                return RedirectResponse(url="/login", status_code=302)
        except:
            return RedirectResponse(url="/login", status_code=302)
        
        # Get user directly from database
        user = db.get_user_by_id(user_id)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        # Get user info safely
        username = user.get('username', 'User')
        is_admin = user.get('is_admin', 0) == 1
        
        return HTMLResponse(content=f'''
<!DOCTYPE html>
<html>
<head>
    <title>Emergency Dashboard</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #28a745; }}
        .btn {{ display: inline-block; padding: 10px 20px; margin: 10px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; }}
        .btn:hover {{ background: #0056b3; }}
        .btn-admin {{ background: #28a745; }}
        .btn-admin:hover {{ background: #1e7e34; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Emergency Dashboard Works!</h1>
        <p><strong>User:</strong> {username}</p>
        <p><strong>Admin:</strong> {'Yes' if is_admin else 'No'}</p>
        <hr>
        <h3>Quick Actions:</h3>
        <a href="/voice-recording" class="btn">Create Video</a>
        <a href="/api/completed-videos" class="btn">My Videos</a>
        {'<a href="/admin" class="btn btn-admin">Admin Panel</a>' if is_admin else ''}
        <a href="/logout" class="btn" style="background: #dc3545;">Logout</a>
    </div>
</body>
</html>
        ''')
        
    except Exception as e:
        logger.error(f"Emergency dashboard error: {e}")
        return HTMLResponse(content=f'''
        <div style="font-family: Arial, sans-serif; margin: 40px; padding: 30px; background: #f8d7da; border-radius: 8px;">
            <h1>Emergency Dashboard Error</h1>
            <p>Error: {str(e)}</p>
            <p><a href="/login">Back to Login</a></p>
        </div>
        ''')

@router.get("/emergency-logout")
async def emergency_logout_get(request: Request):
    """Emergency logout that clears everything"""
    try:
        response = RedirectResponse(url="/login", status_code=302)
        
        # Clear all possible cookies
        response.delete_cookie("access_token")
        response.delete_cookie("session_id")
        response.delete_cookie("user_session")
        
        # Clear session from auth service if it exists
        token = request.cookies.get("access_token")
        if token:
            try:
                auth_service.destroy_session(token)
            except:
                pass
        
        return response
        
    except Exception as e:
        # Even if there's an error, redirect to login
        response = RedirectResponse(url="/login", status_code=302)
        response.delete_cookie("access_token")
        return response

@router.get("/dashboard-test")
async def dashboard_test(request: Request):
    """Simple test dashboard to debug redirect issues"""
    try:
        logger.info("DASHBOARD TEST: Route accessed")
        
        user = get_current_user(request)
        if not user:
            logger.info("DASHBOARD TEST: No user found - redirecting to login")
            return RedirectResponse(url="/login", status_code=302)
        
        logger.info(f"DASHBOARD TEST: User found - {user.get('username')}")
        
        return HTMLResponse(content=f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Dashboard Test - Working!</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                h1 {{ color: #28a745; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Dashboard Test Works!</h1>
                <p><strong>User:</strong> {user.get('username')}</p>
                <p><strong>User ID:</strong> {user.get('id')}</p>
                <p><strong>Is Admin:</strong> {user.get('is_admin', 0)}</p>
                <p><strong>Email:</strong> {user.get('email')}</p>
                <hr>
                <p><a href="/logout">Logout</a></p>
                <p><a href="/dashboard">Try Real Dashboard</a></p>
                <p><a href="/dashboard-direct">Emergency Dashboard</a></p>
            </div>
        </body>
        </html>
        ''')
        
    except Exception as e:
        logger.error(f"DASHBOARD TEST ERROR: {e}")
        return HTMLResponse(content=f'''
        <h1>Dashboard Test Error</h1>
        <p>Error: {str(e)}</p>
        <p><a href="/login">Back to Login</a></p>
        ''')

@router.post("/api/check-username")
@limiter.limit("10/minute")
async def check_username_availability(request: Request):
    """API endpoint to check if username is available"""
    try:
        emergency_stop, emergency_msg = check_emergency_stop()
        if emergency_stop:
            return {
                "available": False,
                "error": "Service temporarily unavailable"
            }
        
        data = await request.json()
        username = sanitize_input(data.get("username", "").strip())
        
        if not username:
            return {
                "available": False,
                "error": "Username is required"
            }
        
        username_valid, username_msg = validate_username(username)
        if not username_valid:
            return {
                "available": False,
                "error": username_msg
            }
        
        existing_user = db.get_user_by_username(username)
        
        if existing_user:
            return {
                "available": False,
                "message": "Username is already taken"
            }
        else:
            return {
                "available": True,
                "message": "Username is available"
            }
            
    except Exception as e:
        logger.error(f"Error checking username availability: {e}")
        return {
            "available": False,
            "error": "Unable to check username availability"
        }