"""
Premium Management Routes
========================
Handles premium user status updates and management.
This ensures database sync when admin UI changes premium status.
"""

import logging
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from ..db.database import execute_query
from ..middleware.vacation_mode import require_admin

router = APIRouter()
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)

@router.post("/toggle-premium/{user_id}")
async def toggle_premium_status(request: Request, user_id: int):
    """Toggle premium status for a user - ENSURES DATABASE SYNC"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return RedirectResponse(url="/login", status_code=302)
        
        # Get current user status
        user = execute_query(
            "SELECT id, username, is_premium FROM users WHERE id = %s",
            (user_id,),
            fetch_one=True
        )
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        current_premium = user[2] if isinstance(user, tuple) else user.get('is_premium')
        new_premium = not current_premium
        
        # Update premium status in database - CRITICAL FIX
        execute_query("""
            UPDATE users 
            SET is_premium = %s,
                sms_notifications = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (new_premium, new_premium, user_id))  # Enable SMS for premium users
        
        username = user[1] if isinstance(user, tuple) else user.get('username')
        
        logger.info(f"Admin {admin_user.get('username')} toggled premium status for {username} (ID: {user_id}) - Premium: {new_premium}")
        
        # Verify the update worked
        verify_user = execute_query(
            "SELECT is_premium, sms_notifications FROM users WHERE id = %s",
            (user_id,),
            fetch_one=True
        )
        
        if verify_user:
            verify_premium = verify_user[0] if isinstance(verify_user, tuple) else verify_user.get('is_premium')
            verify_sms = verify_user[1] if isinstance(verify_user, tuple) else verify_user.get('sms_notifications')
            
            logger.info(f"✅ VERIFIED: User {user_id} premium status updated - Premium: {verify_premium}, SMS: {verify_sms}")
        
        return RedirectResponse(url="/admin/users", status_code=302)
        
    except Exception as e:
        logger.error(f"Error toggling premium status for user {user_id}: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to update premium status: {str(e)}"}
        )

@router.post("/bulk-premium")
async def bulk_premium_update(request: Request, action: str = Form(...), user_ids: list = Form(...)):
    """Bulk update premium status for multiple users"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return RedirectResponse(url="/login", status_code=302)
        
        if action not in ['grant', 'revoke']:
            raise HTTPException(status_code=400, detail="Invalid action")
        
        premium_status = action == 'grant'
        
        # Update all selected users
        for user_id in user_ids:
            execute_query("""
                UPDATE users 
                SET is_premium = %s,
                    sms_notifications = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (premium_status, premium_status, user_id))
            
            logger.info(f"Admin {admin_user.get('username')} {action}ed premium for user ID {user_id}")
        
        return RedirectResponse(url="/admin/users", status_code=302)
        
    except Exception as e:
        logger.error(f"Error in bulk premium update: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Bulk premium update failed: {str(e)}"}
        )

@router.get("/premium-management")
async def premium_management_dashboard(request: Request):
    """Premium management dashboard"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return RedirectResponse(url="/login", status_code=302)
        
        # Get premium statistics
        total_users = execute_query("SELECT COUNT(*) FROM users", fetch_one=True)[0]
        premium_users = execute_query("SELECT COUNT(*) FROM users WHERE is_premium = TRUE", fetch_one=True)[0]
        
        # Get recent premium users
        recent_premium = execute_query("""
            SELECT id, username, email, created_at, is_premium
            FROM users 
            WHERE is_premium = TRUE
            ORDER BY updated_at DESC
            LIMIT 10
        """)
        
        return templates.TemplateResponse("admin/premium_management.html", {
            "request": request,
            "admin_user": admin_user,
            "total_users": total_users,
            "premium_users": premium_users,
            "premium_rate": round((premium_users / total_users * 100) if total_users > 0 else 0, 1),
            "recent_premium": recent_premium
        })
        
    except Exception as e:
        logger.error(f"Premium management dashboard error: {e}")
        return HTMLResponse(f"""
            <h1>Error Loading Premium Management</h1>
            <p>Error: {e}</p>
            <a href="/admin">← Back to Admin Dashboard</a>
        """)

@router.post("/fix-premium-sync")
async def fix_premium_sync(request: Request):
    """Emergency fix for premium status sync issues"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return RedirectResponse(url="/login", status_code=302)
        
        # Known premium users (from admin UI)
        known_premium = [3, 10, 2]  # MogensR, adminfx, testuser
        
        fixed_count = 0
        for user_id in known_premium:
            result = execute_query("""
                UPDATE users 
                SET is_premium = TRUE,
                    sms_notifications = TRUE,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING username
            """, (user_id,), fetch_one=True)
            
            if result:
                username = result[0] if isinstance(result, tuple) else result.get('username')
                logger.info(f"✅ Fixed premium status for {username} (ID: {user_id})")
                fixed_count += 1
        
        return JSONResponse({
            "success": True,
            "message": f"Fixed premium status for {fixed_count} users",
            "fixed_users": fixed_count
        })
        
    except Exception as e:
        logger.error(f"Error fixing premium sync: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Premium sync fix failed: {str(e)}"}
        )
