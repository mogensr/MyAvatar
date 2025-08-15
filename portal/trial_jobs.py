# portal/trial_jobs.py
"""
Background Jobs for Trial Management
Handles daily trial expiration and reminder emails
"""

import asyncio
import datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from .database import get_db_connection
from .trial_management import trial_manager
from loguru import logger
import schedule
import time
import threading

class TrialJobManager:
    """Manages background jobs for trial system"""
    
    def __init__(self):
        self.running = False
        self.job_thread = None
        
    def start_background_jobs(self):
        """Start the background job scheduler"""
        if self.running:
            logger.warning("🔄 Trial jobs already running")
            return
            
        logger.info("🚀 Starting trial management background jobs")
        
        # Schedule daily jobs
        schedule.every().day.at("09:00").do(self.run_daily_trial_maintenance)
        schedule.every().day.at("10:00").do(self.send_trial_reminders)
        
        # Start scheduler in background thread
        self.running = True
        self.job_thread = threading.Thread(target=self._job_scheduler, daemon=True)
        self.job_thread.start()
        
        logger.info("✅ Trial background jobs started")
        
    def stop_background_jobs(self):
        """Stop the background job scheduler"""
        self.running = False
        schedule.clear()
        logger.info("🛑 Trial background jobs stopped")
        
    def _job_scheduler(self):
        """Internal scheduler loop"""
        while self.running:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
            
    def run_daily_trial_maintenance(self):
        """Daily maintenance: expire trials and cleanup"""
        logger.info("🔧 Running daily trial maintenance")
        
        try:
            with get_db_connection() as db:
                # Expire trials
                expired_result = trial_manager.expire_trial_users(db)
                
                if expired_result["success"]:
                    expired_count = expired_result["expired_count"]
                    logger.info(f"⏰ Expired {expired_count} trial users")
                else:
                    logger.error(f"❌ Trial expiration failed: {expired_result['error']}")
                
                # Log trial statistics
                self._log_trial_statistics(db)
                
        except Exception as e:
            logger.error(f"❌ Daily trial maintenance failed: {e}")
            
    def send_trial_reminders(self):
        """Send reminder emails to users whose trials expire tomorrow"""
        logger.info("📧 Sending trial reminder emails")
        
        try:
            with get_db_connection() as db:
                # Get users needing reminders
                users_needing_reminders = trial_manager.get_users_needing_trial_reminder(db)
                
                reminder_count = 0
                for user in users_needing_reminders:
                    try:
                        result = trial_manager.send_trial_reminder_email(user.id, db)
                        if result["success"]:
                            reminder_count += 1
                            logger.info(f"📧 Sent reminder to user {user.id} ({user.email})")
                        else:
                            logger.error(f"❌ Failed to send reminder to user {user.id}: {result['error']}")
                    except Exception as e:
                        logger.error(f"❌ Exception sending reminder to user {user.id}: {e}")
                
                logger.info(f"📧 Sent {reminder_count} trial reminder emails")
                
        except Exception as e:
            logger.error(f"❌ Trial reminder job failed: {e}")
            
    def _log_trial_statistics(self, db: Session):
        """Log current trial statistics"""
        try:
            from .models import User
            
            # Count trial users by status
            active_trials = db.query(User).filter(
                User.account_type == "trial",
                User.trial_expired == False,
                User.trial_end_date >= datetime.date.today()
            ).count()
            
            expired_trials = db.query(User).filter(
                User.account_type == "trial",
                User.trial_expired == True
            ).count()
            
            expiring_soon = db.query(User).filter(
                User.account_type == "trial",
                User.trial_expired == False,
                User.trial_end_date <= datetime.date.today() + datetime.timedelta(days=2)
            ).count()
            
            logger.info(f"📊 Trial Stats - Active: {active_trials}, Expired: {expired_trials}, Expiring Soon: {expiring_soon}")
            
        except Exception as e:
            logger.error(f"❌ Failed to log trial statistics: {e}")

    def run_manual_trial_check(self) -> Dict[str, Any]:
        """Manual trial check for testing/admin purposes"""
        logger.info("🔍 Running manual trial check")
        
        try:
            with get_db_connection() as db:
                # Check for expired trials
                expired_result = trial_manager.expire_trial_users(db)
                
                # Check for users needing reminders
                users_needing_reminders = trial_manager.get_users_needing_trial_reminder(db)
                
                # Get statistics
                from .models import User
                
                active_trials = db.query(User).filter(
                    User.account_type == "trial",
                    User.trial_expired == False,
                    User.trial_end_date >= datetime.date.today()
                ).count()
                
                return {
                    "success": True,
                    "expired_count": expired_result.get("expired_count", 0),
                    "reminders_needed": len(users_needing_reminders),
                    "active_trials": active_trials,
                    "timestamp": datetime.datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"❌ Manual trial check failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

# Global instance
trial_job_manager = TrialJobManager()

def start_trial_jobs():
    """Convenience function to start trial jobs"""
    trial_job_manager.start_background_jobs()

def stop_trial_jobs():
    """Convenience function to stop trial jobs"""
    trial_job_manager.stop_background_jobs()

def manual_trial_check():
    """Convenience function for manual trial check"""
    return trial_job_manager.run_manual_trial_check()
