# portal/trial_routes.py
"""
Trial User Routes for MyAvatar
Handles trial user-facing functionality and avatar selection
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Form
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from .models import User
from .database import get_db
from .auth import get_current_user
from .trial_management import trial_manager
from .heygen_api import heygen_api
from .trial_registration import setup_trial_for_new_user
from loguru import logger

router = APIRouter(prefix="/trial", tags=["trial"])

@router.get("/demo-avatars")
async def get_demo_avatars(current_user: User = Depends(get_current_user)):
    """Get available demo avatars for trial users"""
    try:
        # Only trial users can access this endpoint
        if current_user.account_type != "trial":
            raise HTTPException(status_code=403, detail="Only available for trial users")
        
        # Return available demo avatars
        return {
            "success": True,
            "avatars": [
                {
                    "gender": "male",
                    "name": trial_manager.male_demo_avatar["avatar_name"],
                    "image_url": trial_manager.male_demo_avatar["avatar_image_url"],
                    "avatar_id": trial_manager.male_demo_avatar["avatar_id"]
                },
                {
                    "gender": "female",
                    "name": trial_manager.female_demo_avatar["avatar_name"],
                    "image_url": trial_manager.female_demo_avatar["avatar_image_url"],
                    "avatar_id": trial_manager.female_demo_avatar["avatar_id"]
                }
            ]
        }
    except Exception as e:
        logger.error(f"❌ Error getting demo avatars: {e}")
        raise HTTPException(status_code=500, detail="Failed to get demo avatars")

@router.post("/select-avatar")
async def select_demo_avatar(
    gender: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Select a demo avatar (male or female) for a trial user"""
    try:
        # Only trial users can access this endpoint
        if current_user.account_type != "trial":
            raise HTTPException(status_code=403, detail="Only available for trial users")
        
        # Validate gender parameter
        if gender.lower() not in ["male", "female"]:
            raise HTTPException(status_code=400, detail="Gender must be 'male' or 'female'")
        
        # Assign the selected demo avatar
        result = trial_manager.assign_demo_avatar(current_user.id, db, gender.lower())
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to assign demo avatar"))
        
        logger.info(f"✅ User {current_user.id} selected {gender} demo avatar")
        
        return {
            "success": True,
            "message": f"Successfully assigned {gender} demo avatar",
            "avatar_id": result.get("avatar_id"),
            "avatar_name": result.get("avatar_name")
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error selecting demo avatar: {e}")
        raise HTTPException(status_code=500, detail="Failed to select demo avatar")

@router.get("/status")
async def get_trial_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get trial status for current user"""
    try:
        # Check trial status
        status = trial_manager.check_trial_status(current_user.id, db)
        
        # Add avatar information if trial is active
        if status.get("active") and current_user.account_type == "trial":
            # Get user's avatars from database
            from sqlalchemy import text
            result = db.execute(
                text("SELECT id, avatar_name, avatar_image_url, avatar_id, heygen_avatar_id, is_default FROM user_avatars WHERE user_id = :user_id"),
                {"user_id": current_user.id}
            )
            avatars = [dict(row) for row in result.fetchall()]
            
            status["avatars"] = avatars
        
        return status
    except Exception as e:
        logger.error(f"❌ Error getting trial status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get trial status")


@router.get("/public-avatars")
async def get_public_avatars(current_user: User = Depends(get_current_user)):
    """Get all available public avatars from HeyGen"""
    try:
        # Both trial users and paid users can access public avatars
        # But we'll track the user type for analytics and business logic
        user_type = current_user.account_type
        
        # Get all public avatars from HeyGen API
        result = heygen_api.get_all_public_avatars()
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to get public avatars"))
        
        # Format the response
        avatars = result.get("data", {}).get("avatar_list", [])
        formatted_avatars = []
        
        for avatar in avatars:
            formatted_avatars.append({
                "id": avatar.get("id"),
                "image_url": avatar.get("image_url"),
                "group_name": avatar.get("group_name", "Unknown"),
                "group_id": avatar.get("group_id"),
                "created_at": avatar.get("created_at")
            })
        
        return {
            "success": True,
            "count": len(formatted_avatars),
            "avatars": formatted_avatars,
            "user_type": user_type  # Include user type in response for frontend logic
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting public avatars: {e}")
        raise HTTPException(status_code=500, detail="Failed to get public avatars")


@router.post("/select-public-avatar")
async def select_public_avatar(
    avatar_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Select a public avatar from HeyGen for the current user"""
    try:
        # Validate request data
        if not avatar_data.get("avatar_id"):
            raise HTTPException(status_code=400, detail="Avatar ID is required")
        
        avatar_id = avatar_data.get("avatar_id")
        avatar_name = avatar_data.get("avatar_name", "My Avatar")
        avatar_image_url = avatar_data.get("avatar_image_url", "")
        
        # Check if this avatar already exists for the user
        from sqlalchemy import text
        result = db.execute(
            text("SELECT id FROM user_avatars WHERE user_id = :user_id AND avatar_id = :avatar_id"),
            {"user_id": current_user.id, "avatar_id": avatar_id}
        )
        existing_avatar = result.fetchone()
        
        if existing_avatar:
            # Avatar already exists, just set it as default
            db.execute(
                text("UPDATE user_avatars SET is_default = FALSE WHERE user_id = :user_id"),
                {"user_id": current_user.id}
            )
            
            db.execute(
                text("UPDATE user_avatars SET is_default = TRUE WHERE id = :avatar_id"),
                {"avatar_id": existing_avatar[0]}
            )
            
            db.commit()
            
            return {
                "success": True,
                "message": "Avatar selected as default",
                "avatar_id": existing_avatar[0]
            }
        
        # If user is a paid user, we need to update HeyGen team membership
        # This is just a placeholder - implement actual HeyGen team membership update here
        if current_user.account_type != "trial":
            logger.info(f"🔔 Paid user {current_user.id} selected avatar {avatar_id} - HeyGen team membership update required")
            # TODO: Implement HeyGen team membership update
            # This would typically involve an API call to HeyGen
        
        # Add the new avatar to the user's avatars
        db.execute(
            text("""
            INSERT INTO user_avatars 
            (user_id, avatar_name, avatar_image_url, avatar_id, is_default, created_at) 
            VALUES (:user_id, :avatar_name, :avatar_image_url, :avatar_id, TRUE, CURRENT_TIMESTAMP)
            """),
            {
                "user_id": current_user.id,
                "avatar_name": avatar_name,
                "avatar_image_url": avatar_image_url,
                "avatar_id": avatar_id
            }
        )
        
        # Set all other avatars as non-default
        db.execute(
            text("""
            UPDATE user_avatars 
            SET is_default = FALSE 
            WHERE user_id = :user_id AND avatar_id != :avatar_id
            """),
            {"user_id": current_user.id, "avatar_id": avatar_id}
        )
        
        db.commit()
        
        return {
            "success": True,
            "message": "Public avatar selected successfully",
            "user_type": current_user.account_type
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error selecting public avatar: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to select public avatar: {str(e)}")

