import logging
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

# Import services
from ..services.auth_service import auth_service
from ..services.avatar_service import avatar_service
from ..config.settings import config
from ..utils.validation import sanitize_input, validate_email, validate_username, validate_password_strength
from ..middleware.vacation_mode import (
    check_emergency_stop, 
    check_user_limits, 
    check_budget_limits,
    get_system_stats,
    log_api_cost_event
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
            return RedirectResponse(url="/dashboard", status_code=302)
        
        stats = get_system_stats()
            
        try:
            response = templates.TemplateResponse("index.html", {
                "request": request,
                "user": None,
                "vacation_mode": config.VACATION_MODE,
                "users_percentage": stats['users_percentage'],
                "stats": stats
            })
        except Exception as template_error:
            logger.warning(f"Template error: {template_error}")
            return HTMLResponse(content="""
                <html><body>
                    <h1>🎭 MyAvatar - Create Amazing AI Videos</h1>
                    <p>Welcome to MyAvatar! Please <a href="/login">login</a> or <a href="/register">register</a>.</p>
                    <p>Beta Status: {}/{} users</p>
                </body></html>
            """.format(stats['total_users'], config.MAX_TOTAL_USERS))
        
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response
    except Exception as e:
        logger.error(f"Error loading home page: {e}")
        return HTMLResponse(content="""
            <html><body>
                <h1>Service Temporarily Unavailable</h1>
                <p><a href="/login">Login</a> | <a href="/register">Register</a></p>
            </body></html>
        """, status_code=500)

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
            return RedirectResponse(url="/dashboard", status_code=302)
        
        return templates.TemplateResponse("portal/login.html", {
            "request": request,
            "user": None,
            "error": None,
            "vacation_mode": config.VACATION_MODE
        })
    except Exception as e:
        logger.error(f"Error loading login page: {e}")
        return HTMLResponse(content="""
            <html><body>
                <h1>Login</h1>
                <form method="post" action="/login">
                    <input type="text" name="username" placeholder="Username" required>
                    <input type="password" name="password" placeholder="Password" required>
                    <button type="submit">Login</button>
                </form>
            </body></html>
        """)

@router.post("/login")
@limiter.limit(config.RATE_LIMIT_LOGIN)
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
        else:
            response = RedirectResponse(url="/dashboard", status_code=302)
        
        # Set secure cookie
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=86400
        )
        
        logger.info(f"✅ User {username} logged in successfully")
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
            "vacation_mode": config.VACATION_MODE,
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
@limiter.limit(config.RATE_LIMIT_REGISTER)
async def register_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...), 
    password: str = Form(...),
    confirm_password: str = Form(...)
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
            logger.warning(f"🏖️ VACATION MODE - Registration blocked: {limit_msg}")
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": limit_msg,
                "limits_reached": True
            })
        
        # Sanitize inputs
        username = sanitize_input(username)
        email = sanitize_input(email)
        
        logger.info(f"🏖️ VACATION MODE REGISTRATION - Username: '{username}', Email: '{email}'")
        
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
            "credits_remaining": config.MAX_CREDITS_PER_USER
        }
        
        user_id = db.create_user(user_data)
        
        if not user_id:
            logger.error(f"🏖️ VACATION MODE - User creation failed for {username}")
            return templates.TemplateResponse("portal/register.html", {
                "request": request,
                "user": None,
                "error": "Registration failed. Please try again."
            }, status_code=500)
        
        logger.info(f"🏖️ VACATION MODE - User {username} created successfully with ID: {user_id}")
        
        # Log cost event for new user registration
        await log_api_cost_event("registration", "create_user", 0.10)
        
        # Set up default avatars with verification
        try:
            avatar_service.setup_default_avatars_for_user(user_id)
            
            # Verify avatars were actually created
            if avatar_service.verify_user_avatars_setup(user_id):
                logger.info(f"🎭 VACATION MODE - Default avatars successfully set up for user {username}")
            else:
                logger.error(f"🎭 VACATION MODE - Avatar setup verification failed for user {username}")
                
        except Exception as avatar_error:
            logger.error(f"🎭 VACATION MODE - Avatar setup failed for user {username}: {avatar_error}")
            # Still allow registration to complete even if avatar setup fails
        
        # Auto-login
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
        
        logger.info(f"🏖️ VACATION MODE - Registration completed successfully for user: {username}")
        return response
        
    except Exception as e:
        error_details = f"Registration error: {type(e).__name__}: {str(e)}"
        logger.error(f"🏖️ VACATION MODE REGISTRATION EXCEPTION: {error_details}")
        
        return templates.TemplateResponse("portal/register.html", {
            "request": request,
            "user": None,
            "error": "🚧 Our registration system is experiencing high demand. Please try again in a few minutes!"
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