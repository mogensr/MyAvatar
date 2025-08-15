"""
Debug routes for MyAvatar - Specifically for troubleshooting HeyGen avatar issues
"""
import os
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import JSONResponse
from ..api.heygen import (create_video_from_text, get_available_avatars, 
                         get_video_details, test_heygen_connection)
from ..db.database import execute_query
from ..auth.authentication import get_current_user, is_admin
from ..logger.log_handler import log_info, log_error, log_warning

# Create router with /debug prefix
router = APIRouter(prefix="/debug", tags=["debug"])

@router.get("/pytorch-info")
async def get_pytorch_info():
    try:
        import torch
        import sys
        return {
            "pytorch_version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "python_version": sys.version,
            "torch_cuda_version": torch.version.cuda if hasattr(torch.version, 'cuda') else None,
            "device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/avatar-comparison")
async def debug_avatar_comparison(request: Request):
    """Compare working avatars vs test user's avatars"""
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
            
        # Only allow admins to access this endpoint
        if not user.get("is_admin", False):
            return JSONResponse(
                status_code=403,
                content={"success": False, "error": "Admin access required"}
            )
        
        # Get all users with avatars
        users_with_avatars = execute_query(
            """
            SELECT u.id, u.username, u.avatar_id AS primary_avatar_id 
            FROM users u 
            WHERE u.avatar_id IS NOT NULL
            """,
            fetch_all=True
        )
        
        # Get all user avatars
        all_avatars = execute_query(
            """
            SELECT ua.*, u.username 
            FROM user_avatars ua 
            JOIN users u ON ua.user_id = u.id
            ORDER BY ua.user_id, ua.is_default DESC
            """,
            fetch_all=True
        )
        
        # Try to get HeyGen avatars to check availability
        api_key = os.getenv("HEYGEN_API_KEY")
        if not api_key:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "No API key available"}
            )
        
        heygen_result = get_available_avatars(api_key)
        available_heygen_avatars = []
        if heygen_result.get("success", False):
            available_heygen_avatars = heygen_result.get("avatars", [])
            
        # Find the test user
        test_user = None
        for u in users_with_avatars:
            if u.get("username") == "testuser":
                test_user = u
                break
                
        # Format the result
        result = {
            "success": True,
            "users": users_with_avatars,
            "all_avatars": all_avatars,
            "test_user": test_user,
            "available_heygen_avatars": available_heygen_avatars,
            "avatar_format_analysis": {
                "cloned_avatar_sample": next((a.get("avatar_id") for a in all_avatars if a.get("avatar_id", "").startswith("custom")), None),
                "public_avatar_sample": next((a.get("id") for a in available_heygen_avatars if not a.get("id", "").startswith("custom")), None),
                "format_difference": "Custom avatars typically start with 'custom-' while public avatars may have a different format"
            }
        }
        
        return JSONResponse(content=result)
    except Exception as e:
        log_error(f"Error in debug avatar comparison: {str(e)}", "Debug")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/validate-heygen-avatar/{avatar_id}")
async def validate_heygen_avatar(request: Request, avatar_id: str):
    """Check if a specific HeyGen avatar ID is valid and available"""
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
            
        api_key = os.getenv("HEYGEN_API_KEY") or user.get("api_key")
        if not api_key:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "No API key available"}
            )
        
        # Get all HeyGen avatars
        result = get_available_avatars(api_key)
        
        if not result.get("success", False):
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Failed to fetch HeyGen avatars"}
            )
            
        avatars = result.get("avatars", [])
        
        # Check if the avatar exists
        avatar = next((a for a in avatars if a.get("id") == avatar_id), None)
        
        # Get more avatar details
        meta_info = {
            "is_valid": avatar is not None,
            "avatar_id": avatar_id,
            "avatar_id_format": {
                "starts_with_custom": avatar_id.startswith("custom-") if avatar_id else False,
                "length": len(avatar_id) if avatar_id else 0,
                "format_analysis": "Appears to be a " + 
                                  ("custom avatar" if avatar_id and avatar_id.startswith("custom-") else "public avatar")
            },
            "found_in_heygen": avatar is not None
        }
        
        if avatar:
            # Avatar exists in HeyGen
            meta_info["avatar_details"] = avatar
            return JSONResponse(content={"success": True, "valid": True, "avatar": avatar, "meta": meta_info})
        else:
            # Avatar doesn't exist or is deprecated
            return JSONResponse(content={"success": True, "valid": False, "meta": meta_info})
            
    except Exception as e:
        log_error(f"Error validating HeyGen avatar {avatar_id}: {str(e)}", "Debug")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)})

@router.post("/test-video-creation")
async def test_video_creation(
    request: Request,
    avatar_id: str = Form(...),
    text: str = Form("This is a test of the avatar system.")
):
    """Test video creation with specific avatar ID and detailed error reporting"""
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
            
        if not user.get("is_admin", False):
            return JSONResponse(
                status_code=403,
                content={"success": False, "error": "Admin access required for debug endpoints"}
            )
            
        api_key = os.getenv("HEYGEN_API_KEY") or user.get("api_key")
        if not api_key:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "No API key available"}
            )
        
        # Attempt to create video with detailed logging
        log_info(f"DEBUG: Testing video creation with avatar_id: {avatar_id}", "Debug")
        
        # Try to create video
        result = create_video_from_text(api_key, avatar_id, text)
        
        # Add diagnostic information
        diagnostics = {
            "avatar_id": avatar_id, 
            "avatar_format": avatar_id.startswith("custom-") if avatar_id else "unknown",
            "api_key_length": len(api_key) if api_key else 0,
            "timestamp": str(os.path.getmtime(__file__))
        }
        
        return JSONResponse(content={
            "success": result.get("success", False),
            "result": result,
            "diagnostics": diagnostics
        })
            
    except Exception as e:
        log_error(f"Error in test video creation: {str(e)}", "Debug")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)})

@router.get("/heygen-account-info")
async def heygen_account_info(request: Request):
    """Get information about the HeyGen account status"""
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
            
        if not user.get("is_admin", False):
            return JSONResponse(
                status_code=403,
                content={"success": False, "error": "Admin access required"}
            )
            
        api_key = os.getenv("HEYGEN_API_KEY") or user.get("api_key")
        if not api_key:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "No API key available"}
            )
            
        # Check if we can connect to HeyGen
        connection_test = test_heygen_connection(api_key)
        
        # Get avatars to check what's available
        avatars_result = get_available_avatars(api_key)
        
        # Count avatar types
        avatar_counts = {
            "total": 0,
            "custom": 0,
            "public": 0,
            "other": 0
        }
        
        if avatars_result.get("success", False):
            avatars = avatars_result.get("avatars", [])
            avatar_counts["total"] = len(avatars)
            
            for avatar in avatars:
                avatar_id = avatar.get("id", "")
                if avatar_id.startswith("custom-"):
                    avatar_counts["custom"] += 1
                elif avatar_id.startswith("public-") or not avatar_id.startswith("custom-"):
                    avatar_counts["public"] += 1
                else:
                    avatar_counts["other"] += 1
                    
        return JSONResponse(content={
            "success": True,
            "connection_test": connection_test,
            "avatars": avatar_counts,
            "account_info": {
                "api_key_valid": connection_test,
                "api_key_first_chars": api_key[:5] + "..." + api_key[-5:] if api_key and len(api_key) > 10 else None
            }
        })
        
    except Exception as e:
        log_error(f"Error getting HeyGen account info: {str(e)}", "Debug")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)})

@router.get("/list-my-avatars")
async def list_my_avatars(request: Request):
    """List avatars currently available to your HeyGen account"""
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
            
        api_key = os.getenv("HEYGEN_API_KEY") or user.get("api_key")
        if not api_key:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "No API key available"}
            )
            
        result = get_available_avatars(api_key)
        
        if result.get("success", False):
            # Enhance the result with categories
            avatars = result.get("avatars", [])
            
            # Group avatars by type
            grouped_avatars = {
                "custom": [],
                "public": [],
                "other": []
            }
            
            for avatar in avatars:
                avatar_id = avatar.get("id", "")
                if avatar_id.startswith("custom-"):
                    grouped_avatars["custom"].append(avatar)
                elif avatar_id.startswith("public-") or not avatar_id.startswith("custom-"):
                    grouped_avatars["public"].append(avatar)
                else:
                    grouped_avatars["other"].append(avatar)
                    
            result["avatars_by_type"] = grouped_avatars
            
        return JSONResponse(content=result)
            
    except Exception as e:
        log_error(f"Error listing HeyGen avatars: {str(e)}", "Debug")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)})
