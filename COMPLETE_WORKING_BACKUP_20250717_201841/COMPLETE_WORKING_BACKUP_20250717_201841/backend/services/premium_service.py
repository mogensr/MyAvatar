# services/premium_service.py - Premium subscription and background replacement services

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import requests
import cloudinary
import cloudinary.uploader
from backend.models.premium import (
    User, UserSubscription, UserBackground, BackgroundReplacementJob,
    Video, PremiumFeature, SubscriptionType, SubscriptionStatus,
    BackgroundType, JobStatus
)

class PremiumService:
    def __init__(self, db: Session):
        self.db = db
    
    def start_trial(self, user_id: int) -> UserSubscription:
        """Start a 14-day trial for a user"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")
        
        # Check if user already has a subscription
        existing_subscription = self.db.query(UserSubscription).filter(
            UserSubscription.user_id == user_id
        ).first()
        
        if existing_subscription:
            raise ValueError("User already has a subscription")
        
        # Create trial subscription
        trial_subscription = UserSubscription(
            user_id=user_id,
            subscription_type=SubscriptionType.TRIAL,
            status=SubscriptionStatus.TRIALING,
            trial_start_date=datetime.utcnow(),
            trial_end_date=datetime.utcnow() + timedelta(days=14)
        )
        
        self.db.add(trial_subscription)
        self.db.commit()
        self.db.refresh(trial_subscription)
        
        return trial_subscription
    
    def check_premium_access(self, user_id: int) -> bool:
        """Check if user has premium access (trial or paid)"""
        subscription = self.db.query(UserSubscription).filter(
            UserSubscription.user_id == user_id
        ).first()
        
        if not subscription:
            return False
        
        return subscription.has_premium_access()
    
    def get_user_subscription(self, user_id: int) -> Optional[UserSubscription]:
        """Get user's current subscription"""
        return self.db.query(UserSubscription).filter(
            UserSubscription.user_id == user_id
        ).first()
    
    def upgrade_to_premium(self, user_id: int, subscription_type: SubscriptionType, 
                          stripe_customer_id: str, stripe_subscription_id: str) -> UserSubscription:
        """Upgrade user from trial to premium"""
        subscription = self.db.query(UserSubscription).filter(
            UserSubscription.user_id == user_id
        ).first()
        
        if not subscription:
            raise ValueError("User doesn't have a subscription")
        
        # Update subscription
        subscription.subscription_type = subscription_type
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.subscription_start_date = datetime.utcnow()
        subscription.subscription_end_date = datetime.utcnow() + timedelta(days=30)  # Monthly
        subscription.stripe_customer_id = stripe_customer_id
        subscription.stripe_subscription_id = stripe_subscription_id
        subscription.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(subscription)
        
        return subscription

class BackgroundService:
    def __init__(self, db: Session, cloudinary_config: Dict[str, str]):
        self.db = db
        self.cloudinary_config = cloudinary_config
        cloudinary.config(**cloudinary_config)
    
    def upload_custom_background(self, user_id: int, file_data: bytes, 
                                filename: str, name: str) -> UserBackground:
        """Upload a custom background image for a user"""
        # Check if user has premium access
        premium_service = PremiumService(self.db)
        if not premium_service.check_premium_access(user_id):
            raise ValueError("Premium access required for custom backgrounds")
        
        try:
            # Upload to Cloudinary
            result = cloudinary.uploader.upload(
                file_data,
                folder="backgrounds",
                public_id=f"user_{user_id}_{filename}",
                resource_type="image"
            )
            
            # Save to database
            user_background = UserBackground(
                user_id=user_id,
                name=name,
                background_type=BackgroundType.CUSTOM,
                cloudinary_url=result['secure_url'],
                cloudinary_public_id=result['public_id']
            )
            
            self.db.add(user_background)
            self.db.commit()
            self.db.refresh(user_background)
            
            return user_background
            
        except Exception as e:
            self.db.rollback()
            raise ValueError(f"Failed to upload background: {str(e)}")
    
    def get_user_backgrounds(self, user_id: int) -> List[UserBackground]:
        """Get all backgrounds for a user"""
        return self.db.query(UserBackground).filter(
            UserBackground.user_id == user_id,
            UserBackground.is_active == True
        ).all()
    
    def delete_background(self, user_id: int, background_id: int) -> bool:
        """Delete a user's background"""
        background = self.db.query(UserBackground).filter(
            UserBackground.id == background_id,
            UserBackground.user_id == user_id
        ).first()
        
        if not background:
            return False
        
        try:
            # Delete from Cloudinary
            cloudinary.uploader.destroy(background.cloudinary_public_id)
            
            # Soft delete from database
            background.is_active = False
            self.db.commit()
            
            return True
            
        except Exception as e:
            self.db.rollback()
            raise ValueError(f"Failed to delete background: {str(e)}")

class HeyGenService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.heygen.com/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def create_transparent_video(self, avatar_id: str, script: str, 
                                background_url: Optional[str] = None) -> Dict[str, Any]:
        """Create a transparent video with HeyGen API"""
        payload = {
            "avatar_id": avatar_id,
            "script": script,
            "background": "transparent",  # This is key for background replacement
            "dimension": {
                "width": 1920,
                "height": 1080
            }
        }
        
        # Add background if provided
        if background_url:
            payload["background"] = background_url
        
        response = requests.post(
            f"{self.base_url}/video/generate",
            json=payload,
            headers=self.headers
        )
        
        if response.status_code != 200:
            raise ValueError(f"HeyGen API error: {response.text}")
        
        return response.json()
    
    def check_video_status(self, video_id: str) -> Dict[str, Any]:
        """Check the status of a video generation job"""
        response = requests.get(
            f"{self.base_url}/video/{video_id}",
            headers=self.headers
        )
        
        if response.status_code != 200:
            raise ValueError(f"HeyGen API error: {response.text}")
        
        return response.json()
    
    def replace_background(self, video_url: str, background_url: str) -> Dict[str, Any]:
        """Replace background of an existing video"""
        payload = {
            "video_url": video_url,
            "background_url": background_url
        }
        
        response = requests.post(
            f"{self.base_url}/video/background/replace",
            json=payload,
            headers=self.headers
        )
        
        if response.status_code != 200:
            raise ValueError(f"HeyGen API error: {response.text}")
        
        return response.json()

class BackgroundReplacementService:
    def __init__(self, db: Session, heygen_service: HeyGenService):
        self.db = db
        self.heygen_service = heygen_service
    
    def create_background_replacement_job(self, user_id: int, video_id: int,
                                         background_id: Optional[int] = None,
                                         background_prompt: Optional[str] = None,
                                         stock_image_url: Optional[str] = None) -> BackgroundReplacementJob:
        """Create a new background replacement job"""
        # Check premium access
        premium_service = PremiumService(self.db)
        if not premium_service.check_premium_access(user_id):
            raise ValueError("Premium access required for background replacement")
        
        # Validate input
        if not any([background_id, background_prompt, stock_image_url]):
            raise ValueError("Must provide background_id, background_prompt, or stock_image_url")
        
        # Get the video
        video = self.db.query(Video).filter(
            Video.id == video_id,
            Video.user_id == user_id
        ).first()
        
        if not video:
            raise ValueError("Video not found")
        
        # Create the job
        job = BackgroundReplacementJob(
            user_id=user_id,
            video_id=video_id,
            background_id=background_id,
            background_prompt=background_prompt,
            stock_image_url=stock_image_url,
            job_status=JobStatus.PENDING
        )
        
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        
        return job
    
    def process_background_replacement(self, job_id: int) -> BackgroundReplacementJob:
        """Process a background replacement job"""
        job = self.db.query(BackgroundReplacementJob).filter(
            BackgroundReplacementJob.id == job_id
        ).first()
        
        if not job:
            raise ValueError("Job not found")
        
        if job.job_status != JobStatus.PENDING:
            raise ValueError("Job is not in pending status")
        
        try:
            # Update job status
            job.job_status = JobStatus.PROCESSING
            job.updated_at = datetime.utcnow()
            self.db.commit()
            
            # Get background URL
            background_url = None
            if job.background_id:
                background = self.db.query(UserBackground).filter(
                    UserBackground.id == job.background_id
                ).first()
                if background:
                    background_url = background.cloudinary_url
            elif job.stock_image_url:
                background_url = job.stock_image_url
            elif job.background_prompt:
                # Here you would integrate with an AI image generation service
                # For now, we'll use a placeholder
                background_url = "https://example.com/ai-generated-background.jpg"
            
            if not background_url:
                raise ValueError("Could not determine background URL")
            
            # Call HeyGen API for background replacement
            video = job.video
            result = self.heygen_service.replace_background(
                video_url=video.url,
                background_url=background_url
            )
            
            # Update job with HeyGen response
            job.heygen_job_id = result.get('job_id')
            job.updated_at = datetime.utcnow()
            self.db.commit()
            
            return job
            
        except Exception as e:
            # Update job with error
            job.job_status = JobStatus.FAILED
            job.error_message = str(e)
            job.updated_at = datetime.utcnow()
            self.db.commit()
            raise
    
    def update_job_status(self, job_id: int, status: JobStatus, 
                         result_video_url: Optional[str] = None,
                         error_message: Optional[str] = None) -> BackgroundReplacementJob:
        """Update the status of a background replacement job"""
        job = self.db.query(BackgroundReplacementJob).filter(
            BackgroundReplacementJob.id == job_id
        ).first()
        
        if not job:
            raise ValueError("Job not found")
        
        job.job_status = status
        job.updated_at = datetime.utcnow()
        
        if result_video_url:
            job.result_video_url = result_video_url
        
        if error_message:
            job.error_message = error_message
        
        self.db.commit()
        self.db.refresh(job)
        
        return job
    
    def get_user_jobs(self, user_id: int) -> List[BackgroundReplacementJob]:
        """Get all background replacement jobs for a user"""
        return self.db.query(BackgroundReplacementJob).filter(
            BackgroundReplacementJob.user_id == user_id
        ).order_by(BackgroundReplacementJob.created_at.desc()).all()
