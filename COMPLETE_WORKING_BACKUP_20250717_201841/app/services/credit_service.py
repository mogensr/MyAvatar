# app/services/credit_service.py
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.user import User

class CreditService:
    """Complete credit management system for MyAvatar"""
    
    @staticmethod
    def check_user_access(db: Session, user_id: int) -> Dict:
        """
        Check if user can perform background replacement
        Returns: {
            'can_process': bool,
            'reason': str,
            'credits_remaining': int,
            'is_trial': bool,
            'trial_days_left': int
        }
        """
        user = db.execute(
            text("SELECT credits_remaining, trial_end_date, is_trial_used FROM users WHERE id = :user_id"),
            {"user_id": user_id}
        ).fetchone()
        
        if not user:
            return {
                'can_process': False,
                'reason': 'User not found',
                'credits_remaining': 0,
                'is_trial': False,
                'trial_days_left': 0
            }
        
        now = datetime.now()
        trial_end = user.trial_end_date if user.trial_end_date else None
        
        # Check if still in trial period
        if trial_end and now < trial_end:
            trial_days_left = (trial_end - now).days
            return {
                'can_process': True,
                'reason': 'Trial period active',
                'credits_remaining': user.credits_remaining,
                'is_trial': True,
                'trial_days_left': trial_days_left
            }
        
        # Trial expired, check credits
        if user.credits_remaining > 0:
            return {
                'can_process': True,
                'reason': 'Credits available',
                'credits_remaining': user.credits_remaining,
                'is_trial': False,
                'trial_days_left': 0
            }
        
        # No access
        return {
            'can_process': False,
            'reason': 'No credits remaining - purchase credits to continue',
            'credits_remaining': 0,
            'is_trial': False,
            'trial_days_left': 0
        }
    
    @staticmethod
    def start_trial(db: Session, user_id: int) -> bool:
        """Start 14-day trial for new user"""
        try:
            trial_end = datetime.now() + timedelta(days=14)
            
            db.execute(
                text("""
                UPDATE users 
                SET trial_end_date = :trial_end, is_trial_used = TRUE 
                WHERE id = :user_id AND is_trial_used = FALSE
                """),
                {"trial_end": trial_end, "user_id": user_id}
            )
            
            # Log trial start
            CreditService.log_credit_transaction(
                db, user_id, 0, 'trial_start', 
                f'14-day trial started until {trial_end.strftime("%Y-%m-%d")}'
            )
            
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            print(f"Error starting trial: {e}")
            return False
    
    @staticmethod
    def deduct_credit(db: Session, user_id: int, description: str = "Background replacement") -> bool:
        """Deduct 1 credit for background replacement"""
        try:
            # Check if user is in trial
            access = CreditService.check_user_access(db, user_id)
            
            if not access['can_process']:
                return False
            
            # If in trial, don't deduct credits
            if access['is_trial']:
                CreditService.log_credit_transaction(
                    db, user_id, 0, 'usage', f'{description} (trial period)'
                )
                return True
            
            # Deduct 1 credit
            result = db.execute(
                text("""
                UPDATE users 
                SET credits_remaining = credits_remaining - 1 
                WHERE id = :user_id AND credits_remaining > 0
                """),
                {"user_id": user_id}
            )
            
            if result.rowcount > 0:
                CreditService.log_credit_transaction(
                    db, user_id, -1, 'usage', description
                )
                db.commit()
                return True
            
            return False
            
        except Exception as e:
            db.rollback()
            print(f"Error deducting credit: {e}")
            return False
    
    @staticmethod
    def admin_grant_credits(db: Session, user_id: int, amount: int, admin_id: int, reason: str = "") -> bool:
        """Admin grants credits to user"""
        try:
            db.execute(
                text("""
                UPDATE users 
                SET credits_remaining = credits_remaining + :amount 
                WHERE id = :user_id
                """),
                {"amount": amount, "user_id": user_id}
            )
            
            # Log the transaction
            CreditService.log_credit_transaction(
                db, user_id, amount, 'admin_grant', 
                f'Admin granted credits: {reason}', admin_id
            )
            
            # Log admin activity
            db.execute(
                text("""
                INSERT INTO admin_activities (admin_id, action_type, target_user_id, details)
                VALUES (:admin_id, 'grant_credits', :user_id, :details)
                """),
                {
                    "admin_id": admin_id,
                    "user_id": user_id,
                    "details": f"Granted {amount} credits: {reason}"
                }
            )
            
            db.commit()
            return True
            
        except Exception as e:
            db.rollback()
            print(f"Error granting credits: {e}")
            return False
    
    @staticmethod
    def purchase_credits(db: Session, user_id: int, package_id: int, payment_reference: str) -> bool:
        """User purchases credit package"""
        try:
            # Get package details
            package = db.execute(
                text("SELECT credits, name, price_usd FROM credit_packages WHERE id = :package_id AND is_active = TRUE"),
                {"package_id": package_id}
            ).fetchone()
            
            if not package:
                return False
            
            # Add credits to user
            db.execute(
                text("""
                UPDATE users 
                SET credits_remaining = credits_remaining + :credits,
                    total_credits_purchased = total_credits_purchased + :credits
                WHERE id = :user_id
                """),
                {"credits": package.credits, "user_id": user_id}
            )
            
            # Log the purchase
            CreditService.log_credit_transaction(
                db, user_id, package.credits, 'purchase',
                f'Purchased {package.name} - ${package.price_usd} - Ref: {payment_reference}'
            )
            
            db.commit()
            return True
            
        except Exception as e:
            db.rollback()
            print(f"Error purchasing credits: {e}")
            return False
    
    @staticmethod
    def log_credit_transaction(db: Session, user_id: int, amount: int, 
                             transaction_type: str, description: str, admin_id: Optional[int] = None):
        """Log all credit transactions"""
        try:
            db.execute(
                text("""
                INSERT INTO credit_transactions (user_id, amount, transaction_type, description, created_by_admin_id)
                VALUES (:user_id, :amount, :transaction_type, :description, :admin_id)
                """),
                {
                    "user_id": user_id,
                    "amount": amount,
                    "transaction_type": transaction_type,
                    "description": description,
                    "admin_id": admin_id
                }
            )
        except Exception as e:
            print(f"Error logging transaction: {e}")
    
    @staticmethod
    def get_user_credit_history(db: Session, user_id: int, limit: int = 50) -> List[Dict]:
        """Get user's credit transaction history"""
        try:
            result = db.execute(
                text("""
                SELECT amount, transaction_type, description, created_at
                FROM credit_transactions
                WHERE user_id = :user_id
                ORDER BY created_at DESC
                LIMIT :limit
                """),
                {"user_id": user_id, "limit": limit}
            ).fetchall()
            
            return [
                {
                    'amount': row.amount,
                    'type': row.transaction_type,
                    'description': row.description,
                    'date': row.created_at
                }
                for row in result
            ]
        except Exception as e:
            print(f"Error getting credit history: {e}")
            return []
    
    @staticmethod
    def get_credit_packages(db: Session) -> List[Dict]:
        """Get all active credit packages"""
        try:
            result = db.execute(
                text("SELECT id, name, credits, price_usd FROM credit_packages WHERE is_active = TRUE ORDER BY credits")
            ).fetchall()
            
            return [
                {
                    'id': row.id,
                    'name': row.name,
                    'credits': row.credits,
                    'price': float(row.price_usd)
                }
                for row in result
            ]
        except Exception as e:
            print(f"Error getting packages: {e}")
            return []
