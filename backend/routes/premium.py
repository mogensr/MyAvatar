# routers/premium.py - FastAPI endpoints for premium background replacement

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import os

from backend.db import get_db  # Adjust if your get_db is elsewhere
from backend.services.premium_service import (
    PremiumService, BackgroundService, BackgroundReplacementService, HeyGenService
)
from backend.models.premium import (
    UserSubscription, UserBackground, BackgroundReplacementJob,
    SubscriptionType, BackgroundType, JobStatus
)
from backend.auth import get_current_user  # Adjust if your auth is elsewhere

router = APIRouter(prefix="/api/premium", tags=["premium"])
security = HTTPBearer()

# Pydantic models for request/response
class TrialStartRequest(BaseModel):
    pass

class SubscriptionUpgradeRequest(BaseModel):
    subscription_type: str
    stripe_customer_id: str
    stripe_subscription_id: str

class BackgroundUploadRequest(BaseModel):
    name: str

class BackgroundReplacementRequest(BaseModel):
    video_id: int
    background_id: Optional[int] = None
    background_prompt: Optional[str] = None
    stock_image_url: Optional[str] = None

class SubscriptionResponse(BaseModel):
    id: int
    user_id: int
    subscription_type: str
    status: str
    trial_start_date: Optional[datetime]
    trial_end_date: Optional[datetime]
    subscription_start_date: Optional[datetime]
    subscription_end_date: Optional[datetime]
    has_premium_access: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class BackgroundResponse(BaseModel):
    id: int
    user_id: int
    name: str
    background_type: str
    cloudinary_url: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class JobResponse(BaseModel):
    id: int
    user_id: int
    video_id: int
    background_id: Optional[int]
    background_prompt: Optional[str]
    stock_image_url: Optional[str]
    job_status: str
    result_video_url: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# Initialize services
def get_premium_service(db: Session = Depends(get_db)):
    return PremiumService(db)

def get_background_service(db: Session = Depends(get_db)):
    cloudinary_config = {
        "cloud_name": os.getenv("CLOUDINARY_CLOUD_NAME"),
        "api_key": os.getenv("CLOUDINARY_API_KEY"),
        "api_secret": os.getenv("CLOUDINARY_API_SECRET")
    }
    return BackgroundService(db, cloudinary_config)

def get_heygen_service():
    return HeyGenService(os.getenv("HEYGEN_API_KEY"))

def get_background_replacement_service(
    db: Session = Depends(get_db),
    heygen_service: HeyGenService = Depends(get_heygen_service)
):
    return BackgroundReplacementService(db, heygen_service)

# Subscription endpoints
@router.post("/trial/start", response_model=SubscriptionResponse)
async def start_trial(
    current_user: dict = Depends(get_current_user),
    premium_service: PremiumService = Depends(get_premium_service)
):
    """Start a 14-day trial for the current user"""
    try:
        subscription = premium_service.start_trial(current_user["id"])
        return SubscriptionResponse(
            **subscription.__dict__,
            has_premium_access=subscription.has_premium_access()
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/subscription", response_model=Optional[SubscriptionResponse])
async def get_subscription(
    current_user: dict = Depends(get_current_user),
    premium_service: PremiumService = Depends(get_premium_service)
):
    """Get current user's subscription"""
    subscription = premium_service.get_user_subscription(current_user["id"])
    if not subscription:
        return None
    
    return SubscriptionResponse(
        **subscription.__dict__,
        has_premium_access=subscription.has_premium_access()
    )

@router.post("/subscription/upgrade", response_model=SubscriptionResponse)
async def upgrade_subscription(
    request: SubscriptionUpgradeRequest,
    current_user: dict = Depends(get_current_user),
    premium_service: PremiumService = Depends(get_premium_service)
):
    """Upgrade user's subscription to premium"""
    try:
        subscription_type = SubscriptionType(request.subscription_type)
        subscription = premium_service.upgrade_to_premium(
            current_user["id"],
            subscription_type,
            request.stripe_customer_id,
            request.stripe_subscription_id
        )
        return SubscriptionResponse(
            **subscription.__dict__,
            has_premium_access=subscription.has_premium_access()
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/subscription/check-access")
async def check_premium_access(
    current_user: dict = Depends(get_current_user),
    premium_service: PremiumService = Depends(get_premium_service)
):
    """Check if user has premium access"""
    has_access = premium_service.check_premium_access(current_user["id"])
    return {"has_premium_access": has_access}

# Background management endpoints
@router.post("/backgrounds/upload", response_model=BackgroundResponse)
async def upload_background(
    file: UploadFile = File(...),
    name: str = Form(...),
    current_user: dict = Depends(get_current_user),
    background_service: BackgroundService = Depends(get_background_service)
):
    """Upload a custom background image"""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    try:
        file_data = await file.read()
        background = background_service.upload_custom_background(
            current_user["id"],
            file_data,
            file.filename,
            name
        )
        return BackgroundResponse(**background.__dict__)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/backgrounds", response_model=List[BackgroundResponse])
async def get_backgrounds(
    current_user: dict = Depends(get_current_user),
    background_service: BackgroundService = Depends(get_background_service)
):
    """Get all backgrounds for the current user"""
    backgrounds = background_service.get_user_backgrounds(current_user["id"])
    return [BackgroundResponse(**bg.__dict__) for bg in backgrounds]

@router.delete("/backgrounds/{background_id}")
async def delete_background(
    background_id: int,
    current_user: dict = Depends(get_current_user),
    background_service: BackgroundService = Depends(get_background_service)
):
    """Delete a background"""
    try:
        success = background_service.delete_background(current_user["id"], background_id)
        if not success:
            raise HTTPException(status_code=404, detail="Background not found")
        return {"message": "Background deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# Background replacement endpoints
@router.post("/background-replacement", response_model=JobResponse)
async def create_background_replacement(
    request: BackgroundReplacementRequest,
    current_user: dict = Depends(get_current_user),
    replacement_service: BackgroundReplacementService = Depends(get_background_replacement_service)
):
    """Create a new background replacement job"""
    try:
        job = replacement_service.create_background_replacement_job(
            current_user["id"],
            request.video_id,
            request.background_id,
            request.background_prompt,
            request.stock_image_url
        )
        return JobResponse(**job.__dict__)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/background-replacement/{job_id}/process", response_model=JobResponse)
async def process_background_replacement(
    job_id: int,
    current_user: dict = Depends(get_current_user),
    replacement_service: BackgroundReplacementService = Depends(get_background_replacement_service)
):
    """Process a background replacement job"""
    try:
        job = replacement_service.process_background_replacement(job_id)
        return JobResponse(**job.__dict__)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/background-replacement/jobs", response_model=List[JobResponse])
async def get_background_replacement_jobs(
    current_user: dict = Depends(get_current_user),
    replacement_service: BackgroundReplacementService = Depends(get_background_replacement_service)
):
    """Get all background replacement jobs for the current user"""
    jobs = replacement_service.get_user_jobs(current_user["id"])
    return [JobResponse(**job.__dict__) for job in jobs]

@router.get("/background-replacement/{job_id}", response_model=JobResponse)
async def get_background_replacement_job(
    job_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific background replacement job"""
    job = db.query(BackgroundReplacementJob).filter(
        BackgroundReplacementJob.id == job_id,
        BackgroundReplacementJob.user_id == current_user["id"]
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobResponse(**job.__dict__)

# Webhook endpoint for HeyGen status updates
@router.post("/webhook/heygen")
async def heygen_webhook(
    payload: dict,
    db: Session = Depends(get_db),
    replacement_service: BackgroundReplacementService = Depends(get_background_replacement_service)
):
    """Handle HeyGen webhook for job status updates"""
    try:
        heygen_job_id = payload.get("job_id")
        status = payload.get("status")
        video_url = payload.get("video_url")
        error_message = payload.get("error_message")
        
        if not heygen_job_id:
            raise HTTPException(status_code=400, detail="Missing job_id in payload")
        
        # Find the job by HeyGen job ID
        job = db.query(BackgroundReplacementJob).filter(
            BackgroundReplacementJob.heygen_job_id == heygen_job_id
        ).first()
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Map HeyGen status to our JobStatus
        status_mapping = {
            "completed": JobStatus.COMPLETED,
            "failed": JobStatus.FAILED,
            "processing": JobStatus.PROCESSING
        }
        
        job_status = status_mapping.get(status, JobStatus.PROCESSING)
        
        # Update the job
        replacement_service.update_job_status(
            job.id,
            job_status,
            result_video_url=video_url,
            error_message=error_message
        )
        
        return {"message": "Webhook processed successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Stock image search endpoint (placeholder)
@router.get("/stock-images/search")
async def search_stock_images(
    query: str,
    page: int = 1,
    per_page: int = 20,
    current_user: dict = Depends(get_current_user),
    premium_service: PremiumService = Depends(get_premium_service)
):
    """Search for stock images (integrate with your preferred stock image API)"""
    # Check premium access
    if not premium_service.check_premium_access(current_user["id"]):
        raise HTTPException(status_code=403, detail="Premium access required")
    
    # This is a placeholder - integrate with Unsplash, Pexels, or other stock image APIs
    return {
        "images": [
            {
                "id": "1",
                "url": "https://example.com/image1.jpg",
                "thumbnail_url": "https://example.com/thumb1.jpg",
                "description": "Sample stock image"
            }
        ],
        "total": 1,
        "page": page,
        "per_page": per_page
    }
