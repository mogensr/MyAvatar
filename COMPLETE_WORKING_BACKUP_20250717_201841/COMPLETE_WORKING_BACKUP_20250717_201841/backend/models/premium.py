# backend/models/premium.py - Updated models for premium background replacement system

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from backend.db import Base
import enum

class SubscriptionType(enum.Enum):
    TRIAL = "trial"
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"

class SubscriptionStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    TRIALING = "trialing"

class BackgroundType(enum.Enum):
    ORIGINAL = "original"
    CUSTOM = "custom"
    AI_GENERATED = "ai_generated"
    STOCK_IMAGE = "stock_image"

class JobStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class User(Base):
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    username = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    subscription = relationship("UserSubscription", back_populates="user", uselist=False)
    avatars = relationship("Avatar", back_populates="user")
    videos = relationship("Video", back_populates="user")
    backgrounds = relationship("UserBackground", back_populates="user")
    background_jobs = relationship("BackgroundReplacementJob", back_populates="user")

class UserSubscription(Base):
    __tablename__ = "user_subscriptions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subscription_type = Column(Enum(SubscriptionType), nullable=False)
    status = Column(Enum(SubscriptionStatus), nullable=False)
    
    # Trial period
    trial_start_date = Column(DateTime, nullable=True)
    trial_end_date = Column(DateTime, nullable=True)
    
    # Paid subscription
    subscription_start_date = Column(DateTime, nullable=True)
    subscription_end_date = Column(DateTime, nullable=True)
    
    # Stripe integration
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="subscription")
    
    def is_trial_active(self):
        if self.status == SubscriptionStatus.TRIALING and self.trial_end_date:
            return datetime.utcnow() < self.trial_end_date
        return False
    
    def is_premium_active(self):
        if self.status == SubscriptionStatus.ACTIVE and self.subscription_end_date:
            return datetime.utcnow() < self.subscription_end_date
        return False
    
    def has_premium_access(self):
        return self.is_trial_active() or self.is_premium_active()

class PremiumFeature(Base):
    __tablename__ = "premium_features"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    feature_key = Column(String, nullable=False, unique=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class UserBackground(Base):
    __tablename__ = "user_backgrounds"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    background_type = Column(Enum(BackgroundType), nullable=False)
    cloudinary_url = Column(String, nullable=False)
    cloudinary_public_id = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="backgrounds")
    background_jobs = relationship("BackgroundReplacementJob", back_populates="background")

class Video(Base):
    __tablename__ = "videos"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    avatar_id = Column(Integer, ForeignKey("avatars.id"), nullable=False)
    
    # Video details
    url = Column(String, nullable=False)  # Now NOT NULL
    status = Column(String, nullable=False, default="pending")  # Now NOT NULL
    title = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    
    # Background information
    background_type = Column(Enum(BackgroundType), nullable=False, default=BackgroundType.ORIGINAL)
    background_url = Column(String, nullable=True)  # URL of custom background if used
    original_video_url = Column(String, nullable=True)  # Original video before background replacement
    
    # HeyGen integration
    heygen_video_id = Column(String, nullable=True)
    heygen_job_id = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="videos")
    avatar = relationship("Avatar", back_populates="videos")
    background_jobs = relationship("BackgroundReplacementJob", back_populates="video")

class BackgroundReplacementJob(Base):
    __tablename__ = "background_replacement_jobs"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    
    # Background options (one of these will be used)
    background_id = Column(Integer, ForeignKey("user_backgrounds.id"), nullable=True)  # Custom uploaded background
    background_prompt = Column(Text, nullable=True)  # AI-generated background prompt
    stock_image_url = Column(String, nullable=True)  # Stock image URL
    
    # Job status and results
    job_status = Column(Enum(JobStatus), nullable=False, default=JobStatus.PENDING)
    heygen_job_id = Column(String, nullable=True)
    result_video_url = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="background_jobs")
    video = relationship("Video", back_populates="background_jobs")
    background = relationship("UserBackground", back_populates="background_jobs")

class Avatar(Base):
    __tablename__ = "avatars"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    heygen_avatar_id = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="avatars")
    videos = relationship("Video", back_populates="avatar")

class UploadedImage(Base):
    __tablename__ = "uploaded_images"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    cloudinary_url = Column(String, nullable=False)
    cloudinary_public_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class LogEntry(Base):
    __tablename__ = "log_entries"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)
    details = Column(Text, nullable=True)
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
