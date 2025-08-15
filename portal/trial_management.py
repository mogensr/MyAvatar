# portal/trial_management.py
"""
Trial Management System for MyAvatar
Handles 7-day free trials with demo avatar access
"""

import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from .models import User
from .database import get_db
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
import os
from loguru import logger

class TrialManager:
    """Manages trial user lifecycle and access control"""
    
    def __init__(self):
        self.trial_duration_days = 7
        # Demo avatars for trial users - using testuser's avatars
        self.male_demo_avatar = {
            "avatar_id": "Adrian_public_2_20240312",
            "avatar_name": "Adrian (Demo)",
            "avatar_image_url": "/static/avatars/default_male.png",
            "avatar_gender": "male"
        }
        self.female_demo_avatar = {
            "avatar_id": "Abigail_expressive_2024112501",
            "avatar_name": "Abigail (Demo)",
            "avatar_image_url": "/static/avatars/default_female.png",
            "avatar_gender": "female"
        }
        
    def create_trial_user(self, user_id: int, db: Session, avatar_gender: str = None) -> Dict[str, Any]:
        """
        Set up trial dates for a new user and assign demo avatar
        
        Args:
            user_id: User ID to set up trial for
            db: Database session
            avatar_gender: Optional gender preference for demo avatar ('male' or 'female')
        """
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"success": False, "error": "User not found"}
            
            # Set trial dates
            trial_start = datetime.date.today()
            trial_end = trial_start + datetime.timedelta(days=self.trial_duration_days)
            
            # Update trial fields (NEW fields only)
            user.trial_start_date = trial_start
            user.trial_end_date = trial_end
            user.account_type = "trial"
            user.trial_expired = False
            user.trial_reminder_sent = False
            
            db.commit()
            
            logger.info(f"✅ Trial setup complete for user {user_id}: {trial_start} to {trial_end}")
            
            return {
                "success": True,
                "trial_start": trial_start.isoformat(),
                "trial_end": trial_end.isoformat(),
                "days_remaining": self.trial_duration_days
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to create trial user: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
            
    def assign_demo_avatar(self, user_id: int, db: Session, avatar_gender: str = None) -> Dict[str, Any]:
        """
        Assign a demo avatar to a trial user
        
        Args:
            user_id: User ID to assign avatar to
            db: Database session
            avatar_gender: Optional gender preference ('male' or 'female')
                         If not specified, will be randomly assigned
        """
        try:
            # Determine which avatar to use
            if avatar_gender and avatar_gender.lower() == 'female':
                demo_avatar = self.female_demo_avatar
            elif avatar_gender and avatar_gender.lower() == 'male':
                demo_avatar = self.male_demo_avatar
            else:
                # Random selection if no preference
                import random
                demo_avatar = random.choice([self.male_demo_avatar, self.female_demo_avatar])
                
            # Check if user already has this avatar
            from sqlalchemy import text
            result = db.execute(
                text("SELECT id FROM user_avatars WHERE user_id = :user_id AND avatar_id = :avatar_id"),
                {"user_id": user_id, "avatar_id": demo_avatar['avatar_id']}
            )
            existing_avatar = result.fetchone()
            
            if existing_avatar:
                logger.info(f"Demo avatar already assigned to user {user_id}")
                return {"success": True, "avatar_id": existing_avatar[0], "message": "Demo avatar already assigned"}
            
            # If user doesn't have this avatar yet, add it
            if not result.fetchone():
                # Add avatar to user's collection
                db.execute(
                    text("""
                    INSERT INTO user_avatars 
                    (user_id, avatar_id, heygen_avatar_id, avatar_name, avatar_image_url, is_default) 
                    VALUES (:user_id, :avatar_id, :avatar_id, :avatar_name, :avatar_image_url, 1)
                    """),
                    {
                        "user_id": user_id,
                        "avatar_id": demo_avatar['avatar_id'],
                        "avatar_name": demo_avatar['avatar_name'],
                        "avatar_image_url": demo_avatar['avatar_image_url']
                    }
                )
                
                # Set all other avatars to non-default
                db.execute(
                    text("""
                    UPDATE user_avatars 
                    SET is_default = 0 
                    WHERE user_id = :user_id AND avatar_id != :avatar_id
                    """),
                    {"user_id": user_id, "avatar_id": demo_avatar['avatar_id']}
                )
                
                # Update user's primary avatar_id
                db.execute(
                    text("UPDATE users SET avatar_id = :avatar_id WHERE id = :user_id"),
                    {"user_id": user_id, "avatar_id": demo_avatar['avatar_id']}
                )
                
                logger.info(f"✅ Demo avatar ({demo_avatar['avatar_name']}) assigned to trial user {user_id}")
                
                return {
                    "success": True,
                    "avatar_id": demo_avatar['avatar_id'],
                    "avatar_name": demo_avatar['avatar_name'],
                    "avatar_gender": "female" if demo_avatar == self.female_demo_avatar else "male"
                }
            
        except Exception as e:
            logger.error(f"❌ Failed to assign demo avatar: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
    
    def check_trial_status(self, user_id: int, db: Session) -> Dict[str, Any]:
        """
        Check if user's trial is still active (NON-DESTRUCTIVE check)
        """
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"active": False, "error": "User not found"}
            
            # If not a trial user, return active (existing users unaffected)
            if user.account_type != "trial":
                return {"active": True, "account_type": user.account_type}
            
            # Check trial expiration
            if not user.trial_end_date:
                return {"active": False, "error": "No trial end date set"}
            
            today = datetime.date.today()
            days_remaining = (user.trial_end_date - today).days
            
            # Trial expired
            if days_remaining < 0:
                if not user.trial_expired:
                    user.trial_expired = True
                    db.commit()
                    logger.info(f"⏰ Trial expired for user {user_id}")
                
                return {
                    "active": False,
                    "expired": True,
                    "days_overdue": abs(days_remaining)
                }
            
            # Trial active
            return {
                "active": True,
                "account_type": "trial",
                "days_remaining": days_remaining,
                "trial_end": user.trial_end_date.isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to check trial status: {e}")
            return {"active": False, "error": str(e)}
    
    def get_trial_users_for_reminder(self, db: Session) -> list:
        """
        Get trial users who need day-6 reminder email
        """
        try:
            tomorrow = datetime.date.today() + datetime.timedelta(days=1)
            
            # Find trial users whose trial ends tomorrow and haven't been reminded
            users = db.query(User).filter(
                User.account_type == "trial",
                User.trial_end_date == tomorrow,
                User.trial_reminder_sent == False,
                User.trial_expired == False
            ).all()
            
            logger.info(f"📧 Found {len(users)} users needing trial reminder")
            return users
            
        except Exception as e:
            logger.error(f"❌ Failed to get reminder users: {e}")
            return []
    
    def send_trial_reminder_email(self, user: User, db: Session) -> bool:
        """
        Send day-6 trial reminder email with upgrade links
        """
        try:
            # Email content
            subject = "⏰ Your MyAvatar Trial Expires Tomorrow!"
            
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #667eea;">Hi {user.name or 'there'}!</h2>
                    
                    <p>Your 7-day free trial of MyAvatar ends <strong>tomorrow</strong>. Don't lose access to:</p>
                    
                    <ul style="background: #f8f9fa; padding: 20px; border-radius: 8px;">
                        <li>✅ AI Avatar Creation</li>
                        <li>✅ Content Distribution Platform</li>
                        <li>✅ Advanced Analytics</li>
                        <li>✅ Professional Video Tools</li>
                    </ul>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <h3 style="color: #667eea;">🚀 Upgrade Now to Continue:</h3>
                        
                        <a href="https://app.myavatar.dk/upgrade?plan=basic" 
                           style="display: inline-block; background: #28a745; color: white; padding: 12px 24px; 
                                  text-decoration: none; border-radius: 5px; margin: 5px;">
                            Upgrade to Basic
                        </a>
                        
                        <a href="https://app.myavatar.dk/upgrade?plan=premium" 
                           style="display: inline-block; background: #667eea; color: white; padding: 12px 24px; 
                                  text-decoration: none; border-radius: 5px; margin: 5px;">
                            Upgrade to Premium
                        </a>
                        
                        <a href="https://app.myavatar.dk/upgrade?plan=premium_plus" 
                           style="display: inline-block; background: #6f42c1; color: white; padding: 12px 24px; 
                                  text-decoration: none; border-radius: 5px; margin: 5px;">
                            Upgrade to Premium+
                        </a>
                    </div>
                    
                    <p style="background: #fff3cd; padding: 15px; border-radius: 5px; border-left: 4px solid #ffc107;">
                        <strong>⚠️ Important:</strong> After your trial expires, you'll lose access to all features. 
                        Upgrade now to keep creating amazing content!
                    </p>
                    
                    <p>Questions? Just reply to this email.</p>
                    
                    <p>Best regards,<br>
                    The MyAvatar Team</p>
                </div>
            </body>
            </html>
            """
            
            # TODO: Implement actual email sending (SMTP/SendGrid/etc.)
            # For now, just log the email content
            logger.info(f"📧 TRIAL REMINDER EMAIL for {user.email}:")
            logger.info(f"Subject: {subject}")
            logger.info(f"Content: {html_content[:200]}...")
            
            # Mark reminder as sent
            user.trial_reminder_sent = True
            db.commit()
            
            logger.info(f"✅ Trial reminder sent to {user.email}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send trial reminder: {e}")
            return False
    
    def expire_trial_users(self, db: Session) -> int:
        """
        Mark expired trial users and disable access
        """
        try:
            today = datetime.date.today()
            
            # Find trial users whose trial has expired
            expired_users = db.query(User).filter(
                User.account_type == "trial",
                User.trial_end_date < today,
                User.trial_expired == False
            ).all()
            
            count = 0
            for user in expired_users:
                user.trial_expired = True
                count += 1
                logger.info(f"⏰ Expired trial for user {user.id} ({user.email})")
            
            db.commit()
            logger.info(f"✅ Expired {count} trial users")
            return count
            
        except Exception as e:
            logger.error(f"❌ Failed to expire trial users: {e}")
            return 0
    
    def is_trial_user_allowed(self, user: User) -> bool:
        """
        Check if trial user has access (NON-DESTRUCTIVE check)
        """
        if user.account_type != "trial":
            return True  # Non-trial users always allowed
        
        if user.trial_expired:
            return False  # Expired trial users blocked
        
        if not user.trial_end_date:
            return False  # No trial end date set
        
        # Check if trial is still active
        today = datetime.date.today()
        return today <= user.trial_end_date

# Global instance
trial_manager = TrialManager()
