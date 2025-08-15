# backend/models/premium.py
# Create this file and paste this content

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from backend.db import Base  # Import your existing Base
import enum

class SubscriptionTier(enum.Enum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"

class FeatureType(enum.Enum):
    BACKGROUND_REPLACEMENT = "background_replacement"
    VIDEO_EDITING = "video_editing"
    AI_IMAGE_GENERATION = "ai_image_generation"
    BULK_PROCESSING = "bulk_processing"

class BackgroundType(enum.Enum):
    UPLOAD = "upload"
    AI_GENERATED = "ai_generated"
    STOCK = "stock"

class JobStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class UserSubscription(Base):
    """User subscription and trial management"""
    __tablename__ = "user_subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    tier = Column(Enum(SubscriptionTier), default=SubscriptionTier.FREE)
    
    # Trial management
    trial_started_at = Column(DateTime, nullable=True)
    trial_expires_at = Column(DateTime, nullable=True)
    
    # Premium subscription
    premium_expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User")
    feature_usage = relationship("UserFeatureUsage", back_populates="subscription")

class PremiumFeature(Base):
    """Available premium features"""
    __tablename__ = "premium_features"
    
    id = Column(Integer, primary_key=True, index=True)
    feature_key = Column(String(64), unique=True, nullable=False)
    feature_name = Column(String(128), nullable=False)
    feature_type = Column(Enum(FeatureType), nullable=False)
    min_tier = Column(Enum(SubscriptionTier), nullable=False)
    trial_access = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

class UserFeatureUsage(Base):
    """Track user feature usage"""
    __tablename__ = "user_feature_usage"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    subscription_id = Column(Integer, ForeignKey("user_subscriptions.id"))
    feature_key = Column(String(64), nullable=False)
    
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")
    subscription = relationship("UserSubscription", back_populates="feature_usage")

class UserBackground(Base):
    """User uploaded/generated backgrounds for premium system"""
    __tablename__ = "user_backgrounds"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    filename = Column(String(256), nullable=False)
    cloudinary_url = Column(String(512), nullable=False)
    background_type = Column(Enum(BackgroundType), nullable=False)
    
    # AI generation details
    ai_prompt = Column(Text, nullable=True)
    
    # Stock image details
    stock_source = Column(String(64), nullable=True)  # freepik, unsplash, etc.
    stock_id = Column(String(128), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")
    replacement_jobs = relationship("BackgroundReplacementJob", back_populates="background")

class BackgroundReplacementJob(Base):
    """Background replacement processing jobs using HeyGen"""
    __tablename__ = "background_replacement_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(128), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    video_id = Column(Integer, ForeignKey("videos.id"))
    background_id = Column(Integer, ForeignKey("user_backgrounds.id"))
    
    status = Column(Enum(JobStatus), default=JobStatus.PENDING)
    
    # HeyGen processing details
    heygen_job_id = Column(String(128), nullable=True)
    transparent_video_url = Column(String(512), nullable=True)
    
    # Output details
    output_video_url = Column(String(512), nullable=True)
    output_thumbnail_url = Column(String(512), nullable=True)
    
    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User")
    video = relationship("Video")
    background = relationship("UserBackground", back_populates="replacement_jobs")
