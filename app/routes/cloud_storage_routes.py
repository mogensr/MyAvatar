# app/routes/cloud_storage_routes.py - CLOUD STORAGE INTEGRATION
import logging
import os
import json
import uuid
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
import aiohttp
from urllib.parse import urlencode

# Configure logging
logger = logging.getLogger("CloudStorage")

# Initialize router
router = APIRouter()

# Templates
templates = Jinja2Templates(directory="templates")

# OAuth Configuration
OAUTH_CONFIGS = {
    "google_drive": {
        "client_id": os.getenv("GOOGLE_DRIVE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_DRIVE_CLIENT_SECRET"),
        "scope": "https://www.googleapis.com/auth/drive.file",
        "auth_url": "https://accounts.google.com/o/oauth2/auth",
        "token_url": "https://oauth2.googleapis.com/token"
    },
    "dropbox": {
        "client_id": os.getenv("DROPBOX_CLIENT_ID"),
        "client_secret": os.getenv("DROPBOX_CLIENT_SECRET"),
        "scope": "files.metadata.write files.content.write",
        "auth_url": "https://www.dropbox.com/oauth2/authorize",
        "token_url": "https://api.dropboxapi.com/oauth2/token"
    },
    "onedrive": {
        "client_id": os.getenv("ONEDRIVE_CLIENT_ID"),
        "client_secret": os.getenv("ONEDRIVE_CLIENT_SECRET"),
        "scope": "files.readwrite offline_access",
        "auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    }
}

# Models
class CloudStorageSetupRequest(BaseModel):
    provider: str
    folder_name: str = "MyAvatar Videos"

class OAuthCallbackData(BaseModel):
    code: str
    state: str
    provider: str

# Dependency to get current user
async def get_current_user(request: Request):
    """Get current user from session"""
    try:
        if hasattr(request, 'session') and request.session:
            user_data = request.session.get("user", {})
            if isinstance(user_data, dict):
                return user_data
    except Exception as e:
        logger.warning(f"Could not get user from session: {e}")
    return None

@router.get("/cloud-storage-setup", response_class=HTMLResponse)
async def cloud_storage_setup_page(request: Request, user_data: dict = Depends(get_current_user)):
    """Display cloud storage setup page"""
    if not user_data:
        return RedirectResponse(url="/login", status_code=302)
    
    try:
        context = {
            "request": request,
            "user": user_data,
            "username": user_data.get("username", "User")
        }
        
        return templates.TemplateResponse("portal/cloud_storage_setup.html", context)
        
    except Exception as e:
        logger.error(f"❌ Error serving cloud storage setup page: {e}")
        raise HTTPException(status_code=500, detail="Error loading cloud storage setup")

@router.post("/cloud-storage/oauth/initiate")
async def initiate_oauth(request: Request, setup_data: CloudStorageSetupRequest, user_data: dict = Depends(get_current_user)):
    """Initiate OAuth flow for cloud storage provider"""
    if not user_data:
        return JSONResponse({"success": False, "error": "User not authenticated"}, status_code=401)
    
    try:
        provider = setup_data.provider
        
        if provider not in OAUTH_CONFIGS:
            return JSONResponse({"success": False, "error": "Unsupported provider"}, status_code=400)
        
        config = OAUTH_CONFIGS[provider]
        
        if not config["client_id"] or not config["client_secret"]:
            return JSONResponse({"success": False, "error": f"{provider} not configured"}, status_code=500)
        
        # Generate state for security
        state = str(uuid.uuid4())
        
        # Store setup data in session
        request.session[f"oauth_state_{state}"] = {
            "provider": provider,
            "folder_name": setup_data.folder_name,
            "user_id": user_data.get("id"),
            "username": user_data.get("username"),
            "created_at": datetime.now().isoformat()
        }
        
        # Build OAuth URL
        oauth_params = {
            "client_id": config["client_id"],
            "response_type": "code",
            "scope": config["scope"],
            "state": state,
            "redirect_uri": f"{request.base_url}cloud-storage/oauth/callback/{provider}",
            "access_type": "offline" if provider == "google_drive" else None
        }
        
        # Remove None values
        oauth_params = {k: v for k, v in oauth_params.items() if v is not None}
        
        oauth_url = f"{config['auth_url']}?{urlencode(oauth_params)}"
        
        logger.info(f"🔗 OAuth initiated for {provider} by user {user_data.get('username')}")
        
        return JSONResponse({
            "success": True,
            "oauth_url": oauth_url,
            "provider": provider,
            "state": state
        })
        
    except Exception as e:
        logger.error(f"❌ Error initiating OAuth: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@router.get("/cloud-storage/oauth/callback/{provider}")
async def oauth_callback(request: Request, provider: str, code: str = None, state: str = None, error: str = None):
    """Handle OAuth callback from cloud storage provider"""
    try:
        if error:
            logger.warning(f"OAuth error for {provider}: {error}")
            return RedirectResponse(url=f"/cloud-storage-setup?oauth_error={error}", status_code=302)
        
        if not code or not state:
            logger.warning(f"Missing OAuth parameters for {provider}")
            return RedirectResponse(url="/cloud-storage-setup?oauth_error=missing_parameters", status_code=302)
        
        # Retrieve setup data from session
        setup_data = request.session.get(f"oauth_state_{state}")
        if not setup_data:
            logger.warning(f"Invalid OAuth state for {provider}")
            return RedirectResponse(url="/cloud-storage-setup?oauth_error=invalid_state", status_code=302)
        
        # Exchange code for token
        config = OAUTH_CONFIGS[provider]
        token_data = await exchange_code_for_token(provider, code, config, request.base_url)
        
        if not token_data:
            return RedirectResponse(url="/cloud-storage-setup?oauth_error=token_exchange_failed", status_code=302)
        
        # Create folder in cloud storage
        folder_result = await create_cloud_folder(provider, token_data, setup_data["folder_name"])
        
        if not folder_result["success"]:
            logger.warning(f"Failed to create folder for {provider}: {folder_result['error']}")
            return RedirectResponse(url=f"/cloud-storage-setup?oauth_error=folder_creation_failed", status_code=302)
        
        # Save cloud storage configuration to user account
        await save_cloud_config(
            user_id=setup_data["user_id"],
            provider=provider,
            token_data=token_data,
            folder_info=folder_result,
            folder_name=setup_data["folder_name"]
        )
        
        # Clean up session
        del request.session[f"oauth_state_{state}"]
        
        logger.info(f"✅ Cloud storage connected for user {setup_data['username']}: {provider}")
        
        return RedirectResponse(url="/cloud-storage-setup?oauth_success=true", status_code=302)
        
    except Exception as e:
        logger.error(f"❌ OAuth callback error for {provider}: {e}")
        return RedirectResponse(url="/cloud-storage-setup?oauth_error=callback_error", status_code=302)

async def exchange_code_for_token(provider: str, code: str, config: dict, base_url: str):
    """Exchange OAuth code for access token"""
    try:
        token_params = {
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": f"{base_url}cloud-storage/oauth/callback/{provider}"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(config["token_url"], data=token_params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Token exchange failed for {provider}: {response.status}")
                    return None
                    
    except Exception as e:
        logger.error(f"Error exchanging token for {provider}: {e}")
        return None

async def create_cloud_folder(provider: str, token_data: dict, folder_name: str):
    """Create folder in cloud storage"""
    try:
        access_token = token_data.get("access_token")
        if not access_token:
            return {"success": False, "error": "No access token"}
        
        if provider == "google_drive":
            return await create_google_drive_folder(access_token, folder_name)
        elif provider == "dropbox":
            return await create_dropbox_folder(access_token, folder_name)
        elif provider == "onedrive":
            return await create_onedrive_folder(access_token, folder_name)
        else:
            return {"success": False, "error": "Unsupported provider"}
            
    except Exception as e:
        logger.error(f"Error creating folder for {provider}: {e}")
        return {"success": False, "error": str(e)}

async def create_google_drive_folder(access_token: str, folder_name: str):
    """Create folder in Google Drive"""
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        folder_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://www.googleapis.com/drive/v3/files",
                headers=headers,
                json=folder_metadata
            ) as response:
                if response.status == 200:
                    folder_data = await response.json()
                    return {
                        "success": True,
                        "folder_id": folder_data["id"],
                        "folder_name": folder_data["name"]
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"Google Drive folder creation failed: {error_text}")
                    return {"success": False, "error": "Failed to create folder"}
                    
    except Exception as e:
        logger.error(f"Google Drive folder creation error: {e}")
        return {"success": False, "error": str(e)}

async def create_dropbox_folder(access_token: str, folder_name: str):
    """Create folder in Dropbox"""
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        folder_data = {
            "path": f"/{folder_name}",
            "autorename": True
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.dropboxapi.com/2/files/create_folder_v2",
                headers=headers,
                json=folder_data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "success": True,
                        "folder_path": result["metadata"]["path_display"],
                        "folder_id": result["metadata"]["id"]
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"Dropbox folder creation failed: {error_text}")
                    return {"success": False, "error": "Failed to create folder"}
                    
    except Exception as e:
        logger.error(f"Dropbox folder creation error: {e}")
        return {"success": False, "error": str(e)}

async def create_onedrive_folder(access_token: str, folder_name: str):
    """Create folder in OneDrive"""
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        folder_data = {
            "name": folder_name,
            "folder": {}
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://graph.microsoft.com/v1.0/me/drive/root/children",
                headers=headers,
                json=folder_data
            ) as response:
                if response.status == 201:
                    result = await response.json()
                    return {
                        "success": True,
                        "folder_id": result["id"],
                        "folder_name": result["name"]
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"OneDrive folder creation failed: {error_text}")
                    return {"success": False, "error": "Failed to create folder"}
                    
    except Exception as e:
        logger.error(f"OneDrive folder creation error: {e}")
        return {"success": False, "error": str(e)}

async def save_cloud_config(user_id: int, provider: str, token_data: dict, folder_info: dict, folder_name: str):
    """Save cloud storage configuration to user account"""
    try:
        # Import your database connection
        from app.database import get_db_connection
        
        cloud_config = {
            "provider": provider,
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "token_expires_at": token_data.get("expires_in"),
            "folder_id": folder_info.get("folder_id"),
            "folder_name": folder_name,
            "folder_path": folder_info.get("folder_path"),
            "connected_at": datetime.now().isoformat()
        }
        
        async with get_db_connection() as db:
            await db.execute("""
                UPDATE users 
                SET cloud_storage_provider = ?,
                    cloud_storage_config = ?,
                    cloud_storage_quota_gb = ?,
                    cloud_storage_used_gb = 0
                WHERE id = ?
            """, (
                provider,
                json.dumps(cloud_config),
                get_default_quota(provider),
                user_id
            ))
            await db.commit()
        
        logger.info(f"✅ Cloud config saved for user {user_id}: {provider}")
        
    except Exception as e:
        logger.error(f"❌ Error saving cloud config: {e}")
        raise

def get_default_quota(provider: str) -> int:
    """Get default quota for provider (in GB)"""
    quotas = {
        "google_drive": 15,
        "dropbox": 2,
        "onedrive": 5,
        "aws_s3": 999999  # Essentially unlimited
    }
    return quotas.get(provider, 5)

@router.get("/cloud-storage/status")
async def cloud_storage_status(request: Request, user_data: dict = Depends(get_current_user)):
    """Get current cloud storage status for user"""
    if not user_data:
        return JSONResponse({"success": False, "error": "User not authenticated"}, status_code=401)
    
    try:
        # Import your database connection
        from app.database import get_db_connection
        
        async with get_db_connection() as db:
            cursor = await db.execute(
                "SELECT cloud_storage_provider, cloud_storage_config, cloud_storage_quota_gb, cloud_storage_used_gb FROM users WHERE id = ?",
                (user_data.get("id"),)
            )
            result = await cursor.fetchone()
        
        if result and result[0]:  # Has cloud storage configured
            config = json.loads(result[1]) if result[1] else {}
            return JSONResponse({
                "success": True,
                "connected": True,
                "provider": result[0],
                "folder_name": config.get("folder_name"),
                "quota_gb": result[2],
                "used_gb": float(result[3] or 0),
                "connected_at": config.get("connected_at")
            })
        else:
            return JSONResponse({
                "success": True,
                "connected": False,
                "provider": None
            })
            
    except Exception as e:
        logger.error(f"❌ Error getting cloud storage status: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@router.post("/cloud-storage/test-connection")
async def test_cloud_connection(request: Request, user_data: dict = Depends(get_current_user)):
    """Test cloud storage connection"""
    if not user_data:
        return JSONResponse({"success": False, "error": "User not authenticated"}, status_code=401)
    
    try:
        # Get user's cloud config
        from app.database import get_db_connection
        
        async with get_db_connection() as db:
            cursor = await db.execute(
                "SELECT cloud_storage_provider, cloud_storage_config FROM users WHERE id = ?",
                (user_data.get("id"),)
            )
            result = await cursor.fetchone()
        
        if not result or not result[0]:
            return JSONResponse({"success": False, "error": "No cloud storage configured"}, status_code=400)
        
        provider = result[0]
        config = json.loads(result[1]) if result[1] else {}
        access_token = config.get("access_token")
        
        if not access_token:
            return JSONResponse({"success": False, "error": "No access token available"}, status_code=400)
        
        # Test connection based on provider
        test_result = await test_provider_connection(provider, access_token)
        
        return JSONResponse({
            "success": test_result["success"],
            "provider": provider,
            "status": test_result.get("status"),
            "error": test_result.get("error")
        })
        
    except Exception as e:
        logger.error(f"❌ Error testing cloud connection: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

async def test_provider_connection(provider: str, access_token: str):
    """Test connection to specific provider"""
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        
        if provider == "google_drive":
            url = "https://www.googleapis.com/drive/v3/about?fields=user"
        elif provider == "dropbox":
            url = "https://api.dropboxapi.com/2/users/get_current_account"
        elif provider == "onedrive":
            url = "https://graph.microsoft.com/v1.0/me"
        else:
            return {"success": False, "error": "Unsupported provider"}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return {"success": True, "status": "connected"}
                else:
                    return {"success": False, "error": f"HTTP {response.status}"}
                    
    except Exception as e:
        return {"success": False, "error": str(e)}

# Startup logging
logger.info("☁️ Cloud storage router initialized")
logger.info("🔑 OAuth providers configured: " + ", ".join([k for k, v in OAUTH_CONFIGS.items() if v["client_id"]]))