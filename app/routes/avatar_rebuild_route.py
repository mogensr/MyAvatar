"""
Avatar rebuild route for Railway deployment
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
import requests
import os
from datetime import datetime
from ..db.database import execute_query
from ..auth.authentication import get_current_user_admin

router = APIRouter()

def get_heygen_avatars():
    """Fetch available avatars from HeyGen API"""
    api_key = os.getenv("HEYGEN_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="HEYGEN_API_KEY not configured")
    
    try:
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            "https://api.heygen.com/v2/avatars",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            avatars = data.get("data", {}).get("avatars", [])
            return avatars
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"HeyGen API error: {response.status_code}"
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching avatars: {str(e)}")

def rebuild_avatars_for_user_id(user_id: int):
    """Rebuild avatars for a specific user ID"""
    try:
        # Get HeyGen avatars
        heygen_avatars = get_heygen_avatars()
        
        # Clear existing avatars for this user
        execute_query(
            "DELETE FROM user_avatars WHERE user_id = ?",
            (user_id,)
        )
        
        # Add new avatars
        added_count = 0
        for avatar in heygen_avatars:
            try:
                avatar_id = avatar.get("avatar_id")
                avatar_name = avatar.get("name", f"Avatar {avatar_id}")
                preview_url = avatar.get("preview_image_url") or avatar.get("preview_video_url")
                
                if not avatar_id:
                    continue
                
                # Insert avatar
                execute_query(
                    """INSERT INTO user_avatars 
                       (user_id, avatar_id, avatar_name, avatar_image_url, is_default, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (user_id, avatar_id, avatar_name, preview_url, 0, datetime.now())
                )
                added_count += 1
                
            except Exception as e:
                print(f"Error adding avatar {avatar.get('avatar_id', 'unknown')}: {e}")
        
        return {"success": True, "avatars_added": added_count}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error rebuilding avatars: {str(e)}")

@router.post("/admin/rebuild-avatars/{user_id}")
async def rebuild_user_avatars(
    user_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user_admin)
):
    """
    Rebuild avatars for a specific user (Admin only)
    """
    try:
        result = rebuild_avatars_for_user_id(user_id)
        return {
            "message": f"Successfully rebuilt avatars for user {user_id}",
            "avatars_added": result["avatars_added"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/rebuild-avatars-bulk")
async def rebuild_avatars_bulk(
    user_ids: list[int],
    current_user: Dict[str, Any] = Depends(get_current_user_admin)
):
    """
    Rebuild avatars for multiple users (Admin only)
    """
    results = []
    
    for user_id in user_ids:
        try:
            result = rebuild_avatars_for_user_id(user_id)
            results.append({
                "user_id": user_id,
                "success": True,
                "avatars_added": result["avatars_added"]
            })
        except Exception as e:
            results.append({
                "user_id": user_id,
                "success": False,
                "error": str(e)
            })
    
    return {
        "message": f"Processed {len(user_ids)} users",
        "results": results
    }
