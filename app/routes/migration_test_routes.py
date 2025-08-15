# ===============================================================================
# MIGRATION TEST ROUTES - VERIFY EVERYTHING WORKS
# ===============================================================================
# File: app/routes/migration_test_routes.py

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

test_router = APIRouter(prefix="/migration-test")

# Import the new modular auth system
from ..auth.auth_manager_v2 import ModularAuthManager

# Create modular auth instance
modular_auth = ModularAuthManager()

@test_router.get("/auth-comparison")
async def auth_comparison(request: Request):
    """Compare old vs new authentication - CRITICAL TEST"""
    try:
        # Test your existing function
        old_result = None
        old_error = None
        try:
            # Import your existing function
            from ..routes.auth_routes import get_current_user as old_get_current_user
            old_result = old_get_current_user(request)
        except Exception as e:
            old_error = str(e)
        
        # Test new modular auth
        new_result = modular_auth.authenticate(request)
        
        # Compare results
        comparison = {
            "old_auth": {
                "success": bool(old_result),
                "user": old_result.get('username') if old_result else None,
                "user_id": old_result.get('id') if old_result else None,
                "is_admin": old_result.get('is_admin') if old_result else None,
                "is_premium": old_result.get('is_premium') if old_result else None,
                "error": old_error
            },
            "new_auth": {
                "success": new_result.success,
                "user": new_result.username,
                "user_id": new_result.user_id,
                "is_admin": new_result.is_admin,
                "is_premium": new_result.is_premium,
                "error": new_result.error,
                "provider_used": "Will be filled by debug info"
            },
            "results_match": False
        }
        
        # Check if results match
        if old_result and new_result.success:
            comparison["results_match"] = (
                old_result.get('id') == new_result.user_id and
                old_result.get('username') == new_result.username and
                bool(old_result.get('is_admin')) == new_result.is_admin and
                bool(old_result.get('is_premium')) == new_result.is_premium
            )
        elif not old_result and not new_result.success:
            comparison["results_match"] = True
        
        return comparison
        
    except Exception as e:
        return {"error": f"Comparison test failed: {str(e)}"}

@test_router.get("/admin-test")  
async def admin_test(request: Request):
    """Test admin authentication - CRITICAL for your workflow"""
    try:
        # Test old admin function
        old_admin = None
        old_admin_error = None
        try:
            from ..middleware.vacation_mode import require_admin as old_require_admin
            old_admin = old_require_admin(request)
        except Exception as e:
            old_admin_error = str(e)
        
        # Test new admin function
        new_admin = modular_auth.require_admin(request)
        
        return {
            "old_admin_auth": {
                "success": bool(old_admin),
                "user": old_admin.get('username') if old_admin else None,
                "error": old_admin_error
            },
            "new_admin_auth": {
                "success": bool(new_admin),
                "user": new_admin.get('username') if new_admin else None,
            },
            "admin_access_preserved": bool(old_admin) == bool(new_admin)
        }
        
    except Exception as e:
        return {"error": f"Admin test failed: {str(e)}"}

@test_router.get("/premium-test")
async def premium_test(request: Request):
    """Test premium authentication"""
    try:
        result = modular_auth.authenticate(request)
        
        return {
            "authenticated": result.success,
            "is_premium": result.is_premium,
            "user": result.username,
            "credits_remaining": result.credits_remaining,
            "can_access_premium": result.success and result.is_premium
        }
        
    except Exception as e:
        return {"error": f"Premium test failed: {str(e)}"}

@test_router.get("/dashboard-test")
async def dashboard_test(request: Request):
    """Test dashboard access with new auth"""
    try:
        user = modular_auth.get_current_user(request)
        
        if not user:
            return HTMLResponse(content='''
                <div style="font-family: Arial, sans-serif; margin: 40px; padding: 30px; background: #f8d7da; border-radius: 8px;">
                    <h1>❌ Authentication Failed</h1>
                    <p>Cannot access dashboard - authentication required</p>
                    <p><a href="/login">Go to Login</a></p>
                </div>
            ''')
        
        return HTMLResponse(content=f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>✅ Migration Test Dashboard</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
                .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; }}
                .success {{ color: #28a745; font-size: 1.5em; font-weight: bold; }}
                .info {{ background: #e9ecef; padding: 15px; border-radius: 4px; margin: 10px 0; }}
                .admin {{ background: #d4edda; }}
                .premium {{ background: #fff3cd; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success">✅ MODULAR AUTH SUCCESS!</div>
                
                <div class="info">
                    <h3>Authentication Details:</h3>
                    <p><strong>Username:</strong> {user.get('username')}</p>
                    <p><strong>User ID:</strong> {user.get('id')}</p>
                    <p><strong>Email:</strong> {user.get('email')}</p>
                    <p><strong>Created:</strong> {user.get('created_at')}</p>
                </div>
                
                <div class="info {'admin' if user.get('is_admin') else ''}">
                    <h3>🔐 Admin Access:</h3>
                    <p><strong>Is Admin:</strong> {'✅ YES' if user.get('is_admin') else '❌ No'}</p>
                    {f'<p><a href="/admin" style="color: #28a745; font-weight: bold;">🎛️ Access Admin Panel</a></p>' if user.get('is_admin') else ''}
                </div>
                
                <div class="info {'premium' if user.get('is_premium') else ''}">
                    <h3>💎 Premium Status:</h3>
                    <p><strong>Is Premium:</strong> {'✅ YES' if user.get('is_premium') else '❌ No'}</p>
                    <p><strong>Credits:</strong> {user.get('credits_remaining', 'N/A')}</p>
                </div>
                
                <div class="info">
                    <h3>🧪 Test Links:</h3>
                    <p><a href="/migration-test/auth-comparison">🔄 Compare Old vs New Auth</a></p>
                    <p><a href="/migration-test/admin-test">🔐 Test Admin Access</a></p>
                    <p><a href="/migration-test/premium-test">💎 Test Premium Access</a></p>
                    <p><a href="/dashboard">📊 Real Dashboard</a></p>
                    <p><a href="/logout">🚪 Logout</a></p>
                </div>
            </div>
        </body>
        </html>
        ''')
        
    except Exception as e:
        return HTMLResponse(content=f'''
        <div style="font-family: Arial, sans-serif; margin: 40px; padding: 30px; background: #f8d7da; border-radius: 8px;">
            <h1>❌ Dashboard Test Error</h1>
            <p>Error: {str(e)}</p>
        </div>
        ''')

@test_router.get("/simple-test")
async def simple_test(request: Request):
    """Simple test to verify the router is working"""
    return {
        "message": "✅ Migration test routes are working!",
        "router_status": "active",
        "ready_for_testing": True
    }
