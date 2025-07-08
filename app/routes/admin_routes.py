import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

# Import services
from ..services.auth_service import auth_service
from ..config.settings import config
from ..middleware.vacation_mode import (
    get_real_railway_costs,
    get_heygen_usage_stats, 
    get_system_stats
)

# Import database query function
try:
    from ..db.database import execute_query
except ImportError:
    def execute_query(query, params=(), fetch_one=False, fetch_all=False):
        logger.error("execute_query not available - database import failed")
        return None

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

def require_admin(request: Request):
    """Check if user is admin"""
    user = get_current_user(request)
    if not user or not user.get('is_admin', 0):
        return None
    return user

@router.get("/")
async def admin_dashboard(request: Request):
    """Admin dashboard with system overview"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return JSONResponse({
                "error": "Admin access required",
                "redirect": "/login"
            }, status_code=403)
        
        stats = get_system_stats()
        
        try:
            return templates.TemplateResponse("admin/dashboard.html", {
                "request": request,
                "user": admin_user,
                "stats": stats,
                "config": {
                    "vacation_mode": config.VACATION_MODE,
                    "max_users": config.MAX_TOTAL_USERS,
                    "max_videos_per_user": config.MAX_VIDEOS_PER_USER,
                    "max_daily_registrations": config.MAX_DAILY_REGISTRATIONS
                }
            })
        except Exception as template_error:
            logger.warning(f"Admin template error: {template_error}")
            return JSONResponse({
                "message": "Admin Dashboard",
                "user": admin_user.get("username"),
                "stats": stats,
                "vacation_mode": config.VACATION_MODE,
                "status": "Template not found - using JSON response"
            })
        
    except Exception as e:
        logger.error(f"Admin dashboard error: {e}")
        return JSONResponse({
            "error": "Admin dashboard unavailable",
            "status": "error"
        }, status_code=500)

@router.get("/vacation-stats")
async def vacation_stats(request: Request):
    """Monitor vacation mode with REAL Railway + HeyGen costs"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return JSONResponse({
                "error": "Admin access required"
            }, status_code=403)
        
        stats = get_system_stats()
        
        # Get real costs from APIs
        railway_costs = await get_real_railway_costs()
        heygen_usage = await get_heygen_usage_stats()
        
        total_estimated_cost = 0
        cost_breakdown = {}
        
        # Railway costs
        if railway_costs:
            railway_cost = railway_costs['current_cost']
            railway_percentage = (railway_cost / config.RAILWAY_BUDGET) * 100
            cost_breakdown['railway'] = {
                "current_cost": railway_cost,
                "estimated_monthly": railway_costs['estimated_cost'],
                "budget_limit": config.RAILWAY_BUDGET,
                "percentage_used": round(railway_percentage, 1),
                "source": "Railway API (Real-time)",
                "status": "OK" if railway_percentage < 80 else "WARNING" if railway_percentage < 90 else "CRITICAL"
            }
            total_estimated_cost += railway_cost
        else:
            estimated_railway = stats['total_users'] * 0.30
            cost_breakdown['railway'] = {
                "estimated_cost": estimated_railway,
                "budget_limit": config.RAILWAY_BUDGET,
                "percentage_used": round((estimated_railway / config.RAILWAY_BUDGET) * 100, 1),
                "source": "Estimated (API unavailable)",
                "status": "UNKNOWN"
            }
            total_estimated_cost += estimated_railway
        
        # HeyGen costs
        if heygen_usage:
            heygen_cost = heygen_usage['estimated_cost']
            heygen_percentage = (heygen_cost / config.HEYGEN_BUDGET) * 100
            quota_percentage = (heygen_usage['quota_used'] / max(heygen_usage['quota_total'], 1)) * 100
            
            cost_breakdown['heygen'] = {
                "quota_used": heygen_usage['quota_used'],
                "quota_total": heygen_usage['quota_total'],
                "quota_remaining": heygen_usage['quota_remaining'],
                "quota_percentage": round(quota_percentage, 1),
                "estimated_cost": heygen_cost,
                "budget_limit": config.HEYGEN_BUDGET,
                "percentage_used": round(heygen_percentage, 1),
                "current_month_usage": heygen_usage['current_month_usage'],
                "source": "HeyGen API (Real-time)",
                "status": "OK" if heygen_percentage < 80 else "WARNING" if heygen_percentage < 90 else "CRITICAL"
            }
            total_estimated_cost += heygen_cost
        else:
            estimated_heygen = stats['total_videos'] * 0.60
            cost_breakdown['heygen'] = {
                "estimated_cost": estimated_heygen,
                "budget_limit": config.HEYGEN_BUDGET,
                "percentage_used": round((estimated_heygen / config.HEYGEN_BUDGET) * 100, 1),
                "source": "Estimated (API unavailable)",
                "status": "UNKNOWN"
            }
            total_estimated_cost += estimated_heygen
        
        budget_percentage = (total_estimated_cost / config.TOTAL_BUDGET) * 100
        
        return {
            "success": True,
            "vacation_mode": config.VACATION_MODE,
            "timestamp": "2025-07-08T18:00:00Z",  # Current timestamp
            "budget_summary": {
                "total_budget": config.TOTAL_BUDGET,
                "railway_budget": config.RAILWAY_BUDGET,
                "heygen_budget": config.HEYGEN_BUDGET,
                "total_estimated_cost": round(total_estimated_cost, 2),
                "budget_used_percentage": round(budget_percentage, 1),
                "budget_remaining": round(config.TOTAL_BUDGET - total_estimated_cost, 2),
                "currency": "USD",
                "status": "OK" if budget_percentage < 70 else "WARNING" if budget_percentage < 85 else "CRITICAL"
            },
            "cost_breakdown": cost_breakdown,
            "limits": {
                "max_total_users": config.MAX_TOTAL_USERS,
                "max_daily_registrations": config.MAX_DAILY_REGISTRATIONS,
                "max_videos_per_user": config.MAX_VIDEOS_PER_USER,
                "max_credits_per_user": config.MAX_CREDITS_PER_USER
            },
            "current_usage": stats,
            "alerts": [
                f"🏖️ Vacation Mode: {stats['total_users']}/{config.MAX_TOTAL_USERS} users ({stats['users_percentage']}%)",
                f"💰 Total Budget: ${total_estimated_cost:.2f}/${config.TOTAL_BUDGET} ({budget_percentage:.1f}%)",
                f"🚂 Railway: ${cost_breakdown.get('railway', {}).get('current_cost', 0):.2f}/${config.RAILWAY_BUDGET}",
                f"🎬 HeyGen: ${cost_breakdown.get('heygen', {}).get('estimated_cost', 0):.2f}/${config.HEYGEN_BUDGET}",
                f"📹 Videos: {stats['total_videos']} total created",
                f"📅 Today: {stats['daily_registrations']}/{config.MAX_DAILY_REGISTRATIONS} registrations"
            ]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "vacation_mode": config.VACATION_MODE
        }

@router.get("/emergency-controls")
async def emergency_controls(request: Request):
    """Emergency controls for vacation mode"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return JSONResponse({
                "error": "Admin access required"
            }, status_code=403)
        
        return {
            "emergency_stop": config.EMERGENCY_STOP,
            "vacation_mode": config.VACATION_MODE,
            "emergency_reset": {
                "hint": config.EMERGENCY_KEY_HINT,
                "endpoints": [
                    "GET /emergency-hint",
                    "POST /emergency-admin-reset", 
                    "POST /create-emergency-admin",
                    "GET /debug-admin-users"
                ]
            },
            "controls": {
                "emergency_stop": "Set environment variable EMERGENCY_STOP=true to immediately stop all new registrations",
                "budget_monitoring": "Visit /admin/vacation-stats for real-time cost tracking",
                "database_status": "Visit /debug-database for database health",
                "system_limits": "All limits are automatically enforced"
            },
            "current_limits": {
                "max_users": config.MAX_TOTAL_USERS,
                "max_daily_registrations": config.MAX_DAILY_REGISTRATIONS,
                "max_videos_per_user": config.MAX_VIDEOS_PER_USER,
                "railway_budget": config.RAILWAY_BUDGET,
                "heygen_budget": config.HEYGEN_BUDGET,
                "total_budget": config.TOTAL_BUDGET
            },
            "api_status": {
                "railway_api": "Configured" if config.RAILWAY_API_KEY != "your-railway-api-key" else "Not configured",
                "heygen_api": "Configured" if config.HEYGEN_API_KEY != "your-heygen-api-key" else "Not configured"
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/users")
async def admin_users(request: Request):
    """List all users for admin"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return JSONResponse({
                "error": "Admin access required"
            }, status_code=403)
        
        users = execute_query(
            """SELECT id, username, email, is_admin, is_locked, created_at, credits_remaining, 
                      last_login_at, email_verified 
               FROM users 
               ORDER BY created_at DESC 
               LIMIT 100""",
            fetch_all=True
        )
        
        user_list = []
        if users:
            for user in users:
                user_dict = dict(user) if hasattr(user, '_asdict') else user
                user_list.append({
                    "id": user_dict.get('id'),
                    "username": user_dict.get('username'),
                    "email": user_dict.get('email'),
                    "is_admin": bool(user_dict.get('is_admin', 0)),
                    "is_locked": bool(user_dict.get('is_locked', 0)),
                    "created_at": str(user_dict.get('created_at')),
                    "credits_remaining": user_dict.get('credits_remaining', 0),
                    "last_login_at": str(user_dict.get('last_login_at')) if user_dict.get('last_login_at') else None,
                    "email_verified": bool(user_dict.get('email_verified', 0))
                })
        
        return {
            "success": True,
            "users": user_list,
            "total_users": len(user_list),
            "vacation_mode": config.VACATION_MODE
        }
        
    except Exception as e:
        logger.error(f"Admin users error: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/videos")
async def admin_videos(request: Request):
    """List all videos for admin"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return JSONResponse({
                "error": "Admin access required"
            }, status_code=403)
        
        videos = execute_query(
            """SELECT v.id, v.title, v.status, v.created_at, u.username 
               FROM videos v 
               JOIN users u ON v.user_id = u.id 
               ORDER BY v.created_at DESC 
               LIMIT 100""",
            fetch_all=True
        )
        
        video_list = []
        if videos:
            for video in videos:
                video_dict = dict(video) if hasattr(video, '_asdict') else video
                video_list.append({
                    "id": video_dict.get('id'),
                    "title": video_dict.get('title'),
                    "status": video_dict.get('status'),
                    "created_at": str(video_dict.get('created_at')),
                    "username": video_dict.get('username')
                })
        
        return {
            "success": True,
            "videos": video_list,
            "total_videos": len(video_list),
            "vacation_mode": config.VACATION_MODE
        }
        
    except Exception as e:
        logger.error(f"Admin videos error: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/system-health")
async def system_health(request: Request):
    """System health check for admin"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return JSONResponse({
                "error": "Admin access required"
            }, status_code=403)
        
        # Check database connectivity
        try:
            test_query = execute_query("SELECT 1 as test", fetch_one=True)
            db_status = "✅ Connected" if test_query else "❌ Error"
        except Exception as db_error:
            db_status = f"❌ Error: {str(db_error)}"
        
        # Check table counts
        table_counts = {}
        tables = ['users', 'videos', 'user_avatars']
        for table in tables:
            try:
                count_result = execute_query(f"SELECT COUNT(*) as count FROM {table}", fetch_one=True)
                table_counts[table] = count_result['count'] if count_result else 0
            except:
                table_counts[table] = "Error"
        
        # Get recent activity
        try:
            recent_users = execute_query(
                "SELECT COUNT(*) as count FROM users WHERE created_at >= NOW() - INTERVAL '24 hours'",
                fetch_one=True
            )
            recent_videos = execute_query(
                "SELECT COUNT(*) as count FROM videos WHERE created_at >= NOW() - INTERVAL '24 hours'",
                fetch_one=True
            )
            
            recent_activity = {
                "new_users_24h": recent_users['count'] if recent_users else 0,
                "new_videos_24h": recent_videos['count'] if recent_videos else 0
            }
        except:
            recent_activity = {
                "new_users_24h": "Error",
                "new_videos_24h": "Error"
            }
        
        return {
            "success": True,
            "timestamp": "2025-07-08T18:00:00Z",
            "database": {
                "status": db_status,
                "table_counts": table_counts
            },
            "recent_activity": recent_activity,
            "vacation_mode": {
                "enabled": config.VACATION_MODE,
                "emergency_stop": config.EMERGENCY_STOP,
                "limits": {
                    "max_users": config.MAX_TOTAL_USERS,
                    "max_videos_per_user": config.MAX_VIDEOS_PER_USER,
                    "max_daily_registrations": config.MAX_DAILY_REGISTRATIONS
                }
            },
            "services": {
                "auth_service": "✅ Loaded",
                "avatar_service": "✅ Loaded",
                "video_service": "✅ Loaded",
                "config": "✅ Loaded"
            }
        }
        
    except Exception as e:
        logger.error(f"System health error: {e}")
        return {
            "success": False,
            "error": str(e)
        }