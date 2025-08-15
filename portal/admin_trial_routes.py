# portal/admin_trial_routes.py
"""
Admin Routes for Trial Management
Provides admin interface for monitoring and managing trials
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import datetime
from .database import get_db_connection
from .models import User
from .trial_management import trial_manager
from .trial_jobs import trial_job_manager
from .auth import require_admin
from loguru import logger

router = APIRouter(prefix="/admin/trials", tags=["admin", "trials"])
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def trial_dashboard(request: Request, current_user: User = Depends(require_admin)):
    """Admin trial management dashboard"""
    try:
        with get_db_connection() as db:
            # Get trial statistics
            stats = get_trial_statistics(db)
            
            # Get recent trial users
            recent_trials = get_recent_trial_users(db, limit=10)
            
            # Get users expiring soon
            expiring_soon = get_trials_expiring_soon(db, days=3)
            
            return templates.TemplateResponse("admin/trial_dashboard.html", {
                "request": request,
                "user": current_user,
                "stats": stats,
                "recent_trials": recent_trials,
                "expiring_soon": expiring_soon,
                "page_title": "Trial Management"
            })
            
    except Exception as e:
        logger.error(f"❌ Trial dashboard error: {e}")
        raise HTTPException(status_code=500, detail="Failed to load trial dashboard")

@router.get("/api/statistics")
async def get_trial_stats_api(current_user: User = Depends(require_admin)):
    """API endpoint for trial statistics"""
    try:
        with get_db_connection() as db:
            return get_trial_statistics(db)
    except Exception as e:
        logger.error(f"❌ Trial stats API error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get trial statistics")

@router.get("/api/users")
async def get_trial_users_api(
    status: str = "all",
    limit: int = 50,
    current_user: User = Depends(require_admin)
):
    """API endpoint for trial users"""
    try:
        with get_db_connection() as db:
            users = get_trial_users_by_status(db, status, limit)
            return {
                "success": True,
                "users": [format_trial_user(user) for user in users],
                "count": len(users)
            }
    except Exception as e:
        logger.error(f"❌ Trial users API error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get trial users")

@router.post("/api/extend-trial/{user_id}")
async def extend_trial(
    user_id: int,
    days: int = 7,
    current_user: User = Depends(require_admin)
):
    """Extend a user's trial period"""
    try:
        with get_db_connection() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            if user.account_type != "trial":
                raise HTTPException(status_code=400, detail="User is not on trial")
            
            # Extend trial
            new_end_date = user.trial_end_date + datetime.timedelta(days=days)
            user.trial_end_date = new_end_date
            user.trial_expired = False
            user.trial_reminder_sent = False
            
            db.commit()
            
            logger.info(f"🎁 Admin extended trial for user {user_id} by {days} days")
            
            return {
                "success": True,
                "message": f"Trial extended by {days} days",
                "new_end_date": new_end_date.isoformat(),
                "days_remaining": (new_end_date - datetime.date.today()).days
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Trial extension error: {e}")
        raise HTTPException(status_code=500, detail="Failed to extend trial")

@router.post("/api/expire-trial/{user_id}")
async def expire_trial_immediately(
    user_id: int,
    current_user: User = Depends(require_admin)
):
    """Immediately expire a user's trial"""
    try:
        with get_db_connection() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            if user.account_type != "trial":
                raise HTTPException(status_code=400, detail="User is not on trial")
            
            # Expire trial immediately
            user.trial_expired = True
            user.trial_end_date = datetime.date.today() - datetime.timedelta(days=1)
            
            db.commit()
            
            logger.info(f"⏰ Admin expired trial for user {user_id}")
            
            return {
                "success": True,
                "message": "Trial expired immediately"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Trial expiration error: {e}")
        raise HTTPException(status_code=500, detail="Failed to expire trial")

@router.post("/api/send-reminder/{user_id}")
async def send_trial_reminder_manual(
    user_id: int,
    current_user: User = Depends(require_admin)
):
    """Manually send trial reminder email"""
    try:
        with get_db_connection() as db:
            result = trial_manager.send_trial_reminder_email(user_id, db)
            
            if result["success"]:
                logger.info(f"📧 Admin sent manual reminder to user {user_id}")
                return {
                    "success": True,
                    "message": "Reminder email sent successfully"
                }
            else:
                raise HTTPException(status_code=400, detail=result["error"])
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Manual reminder error: {e}")
        raise HTTPException(status_code=500, detail="Failed to send reminder")

@router.post("/api/run-maintenance")
async def run_trial_maintenance(current_user: User = Depends(require_admin)):
    """Manually run trial maintenance jobs"""
    try:
        result = trial_job_manager.run_manual_trial_check()
        
        if result["success"]:
            logger.info("🔧 Admin ran manual trial maintenance")
            return result
        else:
            raise HTTPException(status_code=500, detail=result["error"])
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Manual maintenance error: {e}")
        raise HTTPException(status_code=500, detail="Failed to run maintenance")

def get_trial_statistics(db: Session) -> Dict[str, Any]:
    """Get comprehensive trial statistics"""
    today = datetime.date.today()
    
    # Active trials
    active_trials = db.query(User).filter(
        User.account_type == "trial",
        User.trial_expired == False,
        User.trial_end_date >= today
    ).count()
    
    # Expired trials
    expired_trials = db.query(User).filter(
        User.account_type == "trial",
        User.trial_expired == True
    ).count()
    
    # Expiring today
    expiring_today = db.query(User).filter(
        User.account_type == "trial",
        User.trial_expired == False,
        User.trial_end_date == today
    ).count()
    
    # Expiring this week
    week_end = today + datetime.timedelta(days=7)
    expiring_week = db.query(User).filter(
        User.account_type == "trial",
        User.trial_expired == False,
        User.trial_end_date.between(today, week_end)
    ).count()
    
    # New trials today
    new_today = db.query(User).filter(
        User.account_type == "trial",
        User.trial_start_date == today
    ).count()
    
    # Conversion rate (simplified)
    total_trials = db.query(User).filter(User.account_type == "trial").count()
    converted_users = db.query(User).filter(User.account_type.in_(["basic", "premium", "premium+"])).count()
    conversion_rate = (converted_users / max(total_trials, 1)) * 100
    
    return {
        "active_trials": active_trials,
        "expired_trials": expired_trials,
        "expiring_today": expiring_today,
        "expiring_week": expiring_week,
        "new_today": new_today,
        "total_trials": total_trials,
        "converted_users": converted_users,
        "conversion_rate": round(conversion_rate, 1)
    }

def get_recent_trial_users(db: Session, limit: int = 10) -> List[User]:
    """Get recently registered trial users"""
    return db.query(User).filter(
        User.account_type == "trial"
    ).order_by(User.trial_start_date.desc()).limit(limit).all()

def get_trials_expiring_soon(db: Session, days: int = 3) -> List[User]:
    """Get trials expiring within specified days"""
    end_date = datetime.date.today() + datetime.timedelta(days=days)
    
    return db.query(User).filter(
        User.account_type == "trial",
        User.trial_expired == False,
        User.trial_end_date <= end_date
    ).order_by(User.trial_end_date.asc()).all()

def get_trial_users_by_status(db: Session, status: str, limit: int) -> List[User]:
    """Get trial users filtered by status"""
    query = db.query(User).filter(User.account_type == "trial")
    
    if status == "active":
        query = query.filter(
            User.trial_expired == False,
            User.trial_end_date >= datetime.date.today()
        )
    elif status == "expired":
        query = query.filter(User.trial_expired == True)
    elif status == "expiring":
        end_date = datetime.date.today() + datetime.timedelta(days=2)
        query = query.filter(
            User.trial_expired == False,
            User.trial_end_date <= end_date
        )
    
    return query.order_by(User.trial_start_date.desc()).limit(limit).all()

def format_trial_user(user: User) -> Dict[str, Any]:
    """Format user data for API response"""
    days_remaining = 0
    if user.trial_end_date and not user.trial_expired:
        days_remaining = max(0, (user.trial_end_date - datetime.date.today()).days)
    
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "trial_start_date": user.trial_start_date.isoformat() if user.trial_start_date else None,
        "trial_end_date": user.trial_end_date.isoformat() if user.trial_end_date else None,
        "days_remaining": days_remaining,
        "trial_expired": user.trial_expired,
        "trial_reminder_sent": user.trial_reminder_sent,
        "created_at": user.created_at.isoformat() if user.created_at else None
    }
