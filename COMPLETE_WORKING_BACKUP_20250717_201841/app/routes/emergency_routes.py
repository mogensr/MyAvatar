import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

# Import services
from ..services.auth_service import auth_service
from ..config.settings import config

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
router = APIRouter()

@router.get("/emergency-hint")
async def get_emergency_hint():
    """Get the hint for the emergency master key"""
    return {
        "hint": f"💡 {config.EMERGENCY_KEY_HINT}",
        "note": "Use the answer to this hint as your master_key in emergency endpoints",
        "endpoints": [
            "POST /emergency-admin-reset",
            "POST /create-emergency-admin"
        ],
        "example": {
            "master_key": "[your answer to the hint]",
            "admin_username": "your_admin_username",
            "new_password": "your_new_secure_password"
        }
    }

@router.post("/emergency-admin-reset")
async def emergency_admin_reset(request: Request):
    """Emergency admin password reset with hint-based master key"""
    try:
        data = await request.json()
        master_key = data.get("master_key", "")
        new_password = data.get("new_password", "")
        admin_username = data.get("admin_username", "")
        
        # Master key with hint system
        if not master_key or master_key != config.EMERGENCY_MASTER_KEY:
            return JSONResponse({
                "success": False,
                "error": "Invalid master key",
                "hint": f"💡 Hint: {config.EMERGENCY_KEY_HINT}",
                "note": "Enter the answer to the hint as the master_key"
            }, status_code=401)
        
        if not new_password or len(new_password) < 8:
            return JSONResponse({
                "success": False,
                "error": "Password must be at least 8 characters"
            }, status_code=400)
        
        if not admin_username:
            return JSONResponse({
                "success": False,
                "error": "Admin username required"
            }, status_code=400)
        
        # Find admin user
        admin_user = db.get_user_by_username(admin_username)
        if not admin_user:
            return JSONResponse({
                "success": False,
                "error": "Admin user not found"
            }, status_code=404)
        
        if not admin_user.get('is_admin', 0):
            return JSONResponse({
                "success": False,
                "error": "User is not an admin"
            }, status_code=403)
        
        # Reset password
        new_hashed_password = auth_service.hash_password(new_password)
        
        # Update password in database
        update_result = execute_query(
            "UPDATE users SET hashed_password = %s WHERE id = %s AND is_admin = 1",
            (new_hashed_password, admin_user['id'])
        )
        
        if update_result is not None:
            logger.info(f"🔐 EMERGENCY: Admin password reset for user {admin_username}")
            return JSONResponse({
                "success": True,
                "message": f"Admin password reset successfully for {admin_username}",
                "admin_id": admin_user['id'],
                "note": "Please test login immediately and delete emergency endpoints!"
            })
        else:
            return JSONResponse({
                "success": False,
                "error": "Failed to update password"
            }, status_code=500)
            
    except Exception as e:
        logger.error(f"Emergency admin reset error: {e}")
        return JSONResponse({
            "success": False,
            "error": "Reset failed"
        }, status_code=500)

@router.post("/create-emergency-admin")
async def create_emergency_admin(request: Request):
    """Create emergency admin user with hint-based master key"""
    try:
        data = await request.json()
        master_key = data.get("master_key", "")
        username = data.get("username", "")
        password = data.get("password", "")
        email = data.get("email", "")
        
        # Master key with hint system
        if not master_key or master_key != config.EMERGENCY_MASTER_KEY:
            return JSONResponse({
                "success": False,
                "error": "Invalid master key",
                "hint": f"💡 Hint: {config.EMERGENCY_KEY_HINT}",
                "note": "Enter the answer to the hint as the master_key"
            }, status_code=401)
        
        # Validation
        if not username or not password or not email:
            return JSONResponse({
                "success": False,
                "error": "Username, password, and email required"
            }, status_code=400)
        
        if len(password) < 8:
            return JSONResponse({
                "success": False,
                "error": "Password must be at least 8 characters"
            }, status_code=400)
        
        # Check if user already exists
        if db.get_user_by_username(username):
            return JSONResponse({
                "success": False,
                "error": "Username already exists"
            }, status_code=409)
        
        # Create emergency admin
        hashed_password = auth_service.hash_password(password)
        api_key = auth_service.generate_api_key()
        
        user_data = {
            "username": username,
            "email": email,
            "password": hashed_password,
            "api_key": api_key,
            "is_admin": 1,  # Make admin
            "is_locked": 0,
            "avatar_id": "",
            "created_at": "now()",
            "email_verified": 1,
            "credits_remaining": config.MAX_CREDITS_PER_USER
        }
        
        user_id = db.create_user(user_data)
        
        if user_id:
            logger.info(f"🚨 EMERGENCY: Created admin user {username} with ID {user_id}")
            
            # Set up avatars for the new admin
            try:
                from ..services.avatar_service import avatar_service
                avatar_service.setup_default_avatars_for_user(user_id)
            except Exception as avatar_error:
                logger.error(f"Avatar setup failed for emergency admin {username}: {avatar_error}")
            
            return JSONResponse({
                "success": True,
                "message": f"Emergency admin created: {username}",
                "user_id": user_id,
                "note": "Please test login immediately and delete emergency endpoints!"
            })
        else:
            return JSONResponse({
                "success": False,
                "error": "Failed to create admin user"
            }, status_code=500)
            
    except Exception as e:
        logger.error(f"Emergency admin creation error: {e}")
        return JSONResponse({
            "success": False,
            "error": "Admin creation failed"
        }, status_code=500)

@router.get("/debug-admin-users")
async def debug_admin_users():
    """List all admin users for debugging"""
    try:
        admins = execute_query(
            "SELECT id, username, email, is_admin, created_at FROM users WHERE is_admin = 1",
            fetch_all=True
        )
        
        admin_list = []
        if admins:
            for admin in admins:
                admin_dict = dict(admin) if hasattr(admin, '_asdict') else admin
                admin_list.append({
                    "id": admin_dict.get('id'),
                    "username": admin_dict.get('username'),
                    "email": admin_dict.get('email'),
                    "is_admin": admin_dict.get('is_admin'),
                    "created_at": str(admin_dict.get('created_at'))
                })
        
        return {
            "success": True,
            "admin_count": len(admin_list),
            "admins": admin_list,
            "emergency_hint": config.EMERGENCY_KEY_HINT,
            "reset_endpoints": [
                "POST /emergency-admin-reset",
                "POST /create-emergency-admin",
                "GET /emergency-hint"
            ]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/debug-database")
async def debug_database():
    """Check all database tables and structures with vacation mode info"""
    try:
        tables_query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """
        tables_result = execute_query(tables_query, fetch_all=True)
        tables = [dict(row)['table_name'] for row in tables_result] if tables_result else []
        
        table_structures = {}
        for table in tables:
            columns_query = f"""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = '{table}'
                ORDER BY ordinal_position
            """
            columns_result = execute_query(columns_query, fetch_all=True)
            table_structures[table] = [dict(row) for row in columns_result] if columns_result else []
        
        record_counts = {}
        for table in tables:
            try:
                count_query = f"SELECT COUNT(*) as count FROM {table}"
                count_result = execute_query(count_query, fetch_one=True)
                record_counts[table] = dict(count_result)['count'] if count_result else 0
            except:
                record_counts[table] = "Error"
        
        return {
            "success": True,
            "database_type": "PostgreSQL",
            "vacation_mode": config.VACATION_MODE,
            "timestamp": "2025-07-08T18:00:00Z",
            "tables": tables,
            "table_structures": table_structures,
            "record_counts": record_counts,
            "total_tables": len(tables)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/debug-avatars/{user_id}")
async def debug_user_avatars(user_id: int):
    """Debug endpoint to check user avatars and fix if needed"""
    try:
        # Check if user exists
        user = db.get_user_by_id(user_id)
        if not user:
            return {"error": f"User {user_id} not found"}
        
        # Get current avatars
        current_avatars = execute_query(
            "SELECT * FROM user_avatars WHERE user_id = %s",
            (user_id,),
            fetch_all=True
        )
        
        avatar_data = []
        if current_avatars:
            for avatar in current_avatars:
                avatar_dict = dict(avatar) if hasattr(avatar, '_asdict') else avatar
                avatar_data.append(avatar_dict)
        
        # Check database structure for user_avatars table
        table_structure = execute_query(
            """SELECT column_name, data_type, is_nullable, column_default
               FROM information_schema.columns 
               WHERE table_name = 'user_avatars'
               ORDER BY ordinal_position""",
            fetch_all=True
        )
        
        structure_data = []
        if table_structure:
            for column in table_structure:
                column_dict = dict(column) if hasattr(column, '_asdict') else column
                structure_data.append(column_dict)
        
        return {
            "success": True,
            "user_id": user_id,
            "username": user.get('username'),
            "avatar_count": len(avatar_data),
            "avatars": avatar_data,
            "table_structure": structure_data,
            "has_avatars": len(avatar_data) > 0
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/fix-avatars/{user_id}")
async def fix_user_avatars(user_id: int):
    """Force fix avatars for a specific user"""
    try:
        # Check if user exists
        user = db.get_user_by_id(user_id)
        if not user:
            return {"error": f"User {user_id} not found"}
        
        # Clear existing avatars
        clear_result = execute_query(
            "DELETE FROM user_avatars WHERE user_id = %s",
            (user_id,)
        )
        
        # Set up new avatars
        try:
            from ..services.avatar_service import avatar_service
            setup_success = avatar_service.setup_default_avatars_for_user(user_id)
            
            # Verify setup
            new_avatars = execute_query(
                "SELECT * FROM user_avatars WHERE user_id = %s",
                (user_id,),
                fetch_all=True
            )
            
            avatar_count = len(new_avatars) if new_avatars else 0
            
            return {
                "success": setup_success,
                "user_id": user_id,
                "username": user.get('username'),
                "avatars_cleared": True,
                "avatars_created": avatar_count,
                "message": f"Fixed avatars for user {user.get('username')} - created {avatar_count} default avatars"
            }
            
        except Exception as avatar_error:
            return {
                "success": False,
                "error": f"Avatar service error: {str(avatar_error)}",
                "user_id": user_id,
                "avatars_cleared": True
            }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/system-overview")
async def system_overview():
    """Complete system overview for emergency diagnostics"""
    try:
        # Get user statistics
        total_users_result = execute_query("SELECT COUNT(*) as count FROM users", fetch_one=True)
        admin_users_result = execute_query("SELECT COUNT(*) as count FROM users WHERE is_admin = 1", fetch_one=True)
        locked_users_result = execute_query("SELECT COUNT(*) as count FROM users WHERE is_locked = 1", fetch_one=True)
        
        # Get video statistics
        total_videos_result = execute_query("SELECT COUNT(*) as count FROM videos", fetch_one=True)
        completed_videos_result = execute_query("SELECT COUNT(*) as count FROM videos WHERE status = 'completed'", fetch_one=True)
        
        # Get avatar statistics
        total_avatars_result = execute_query("SELECT COUNT(*) as count FROM user_avatars", fetch_one=True)
        
        # Get recent activity (last 24 hours)
        recent_users_result = execute_query(
            "SELECT COUNT(*) as count FROM users WHERE created_at >= NOW() - INTERVAL '24 hours'",
            fetch_one=True
        )
        recent_videos_result = execute_query(
            "SELECT COUNT(*) as count FROM videos WHERE created_at >= NOW() - INTERVAL '24 hours'",
            fetch_one=True
        )
        
        # Helper function to safely get count
        def get_count(result):
            if result:
                return dict(result)['count'] if hasattr(result, '_asdict') else result.get('count', 0)
            return 0
        
        return {
            "success": True,
            "timestamp": "2025-07-08T18:00:00Z",
            "vacation_mode": {
                "enabled": config.VACATION_MODE,
                "emergency_stop": config.EMERGENCY_STOP,
                "limits": {
                    "max_users": config.MAX_TOTAL_USERS,
                    "max_videos_per_user": config.MAX_VIDEOS_PER_USER,
                    "max_daily_registrations": config.MAX_DAILY_REGISTRATIONS,
                    "max_credits_per_user": config.MAX_CREDITS_PER_USER
                },
                "budgets": {
                    "total_budget": config.TOTAL_BUDGET,
                    "railway_budget": config.RAILWAY_BUDGET,
                    "heygen_budget": config.HEYGEN_BUDGET
                }
            },
            "statistics": {
                "users": {
                    "total": get_count(total_users_result),
                    "admins": get_count(admin_users_result),
                    "locked": get_count(locked_users_result),
                    "new_24h": get_count(recent_users_result)
                },
                "videos": {
                    "total": get_count(total_videos_result),
                    "completed": get_count(completed_videos_result),
                    "new_24h": get_count(recent_videos_result)
                },
                "avatars": {
                    "total": get_count(total_avatars_result)
                }
            },
            "health_status": {
                "database": "✅ Connected",
                "services": {
                    "auth_service": "✅ Loaded",
                    "avatar_service": "✅ Loaded",
                    "config": "✅ Loaded"
                }
            },
            "emergency_access": {
                "hint": config.EMERGENCY_KEY_HINT,
                "endpoints": [
                    "GET /emergency-hint",
                    "POST /emergency-admin-reset",
                    "POST /create-emergency-admin",
                    "GET /debug-admin-users",
                    "GET /debug-database",
                    "GET /debug-avatars/{user_id}",
                    "POST /fix-avatars/{user_id}",
                    "GET /system-overview"
                ]
            }
        }
        
    except Exception as e:
        logger.error(f"System overview error: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": "2025-07-08T18:00:00Z",
            "emergency_access": {
                "hint": config.EMERGENCY_KEY_HINT,
                "note": "Database connection failed - use emergency endpoints"
            }
        }
