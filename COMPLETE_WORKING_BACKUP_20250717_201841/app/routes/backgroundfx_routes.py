# app/routes/backgroundfx_routes.py - COMPLETE BACKGROUNDFX API WITH CLOUDFLARE R2 STORAGE
import logging
import os
import uuid
import requests
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
import boto3
from botocore.exceptions import ClientError

from fastapi import APIRouter, Request, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer(auto_error=False)

# Configuration
HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "your-unsplash-key")
DATABASE_URL = os.getenv("DATABASE_URL")

# Cloudinary Configuration (replacing R2)
CLOUDINARY_URL = os.getenv("CLOUDINARY_URL")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

# Initialize Cloudinary
def get_cloudinary_config():
    """Get Cloudinary configuration"""
    try:
        if CLOUDINARY_URL:
            return True
        elif all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET]):
            return True
        else:
            logger.warning("Cloudinary credentials not configured")
            return False
    except Exception as e:
        logger.error(f"Cloudinary configuration error: {e}")
        return False

def upload_to_cloudinary(file_content: bytes, filename: str) -> Optional[str]:
    """Upload image to Cloudinary and return public URL"""
    try:
        import cloudinary
        import cloudinary.uploader
        
        # Configure Cloudinary if using individual credentials
        if not CLOUDINARY_URL and all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET]):
            cloudinary.config(
                cloud_name=CLOUDINARY_CLOUD_NAME,
                api_key=CLOUDINARY_API_KEY,
                api_secret=CLOUDINARY_API_SECRET
            )
        
        # Generate unique public_id
        import time
        public_id = f"myavatar/backgrounds/{int(time.time())}_{filename.split('.')[0]}"
        
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            file_content,
            public_id=public_id,
            folder="myavatar/backgrounds",
            resource_type="image",
            format="jpg",  # Auto-optimize format
            quality="auto",  # Auto-optimize quality
            fetch_format="auto"  # Auto-optimize format for browser
        )
        
        public_url = result.get("secure_url")
        logger.info(f"Successfully uploaded {filename} to Cloudinary: {public_url}")
        return public_url
        
    except Exception as e:
        logger.error(f"Cloudinary upload error: {e}")
        return None

def delete_from_cloudinary(public_id: str) -> bool:
    """Delete image from Cloudinary"""
    try:
        import cloudinary
        import cloudinary.uploader
        
        result = cloudinary.uploader.destroy(public_id)
        success = result.get("result") == "ok"
        
        if success:
            logger.info(f"Successfully deleted {public_id} from Cloudinary")
        else:
            logger.warning(f"Failed to delete {public_id} from Cloudinary: {result}")
            
        return success
        
    except Exception as e:
        logger.error(f"Cloudinary delete error: {e}")
        return False

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[Dict]:
    """Get current user from JWT token"""
    try:
        if not credentials:
            return None
        
        # Use your existing auth system
        from app.services.auth_service import auth_service
        from app.db.user_manager import Database
        
        payload = auth_service.validate_token(credentials.credentials)
        
        if not payload:
            return None
            
        user_id = payload.get("user_id")
        if not user_id:
            return None
            
        # Get user from database
        db = Database()
        return db.get_user_by_id(user_id)
        
    except Exception as e:
        logger.error(f"Error validating user: {e}")
        return None

def execute_query(query: str, params=(), fetch_one=False, fetch_all=False):
    """Execute database query"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(query, params)
        
        if fetch_one:
            result = cur.fetchone()
        elif fetch_all:
            result = cur.fetchall()
        else:
            result = None
            
        conn.commit()
        conn.close()
        return result
    except Exception as e:
        logger.error(f"Database error: {e}")
        return None

# ===============================================================================
# 1. HEYGEN TRANSPARENT VIDEO INTEGRATION
# ===============================================================================

@router.post("/api/backgrounds/get-transparent-video")
async def get_transparent_video(
    request: Request, 
    video_id: str = Form(...),
    user: Dict = Depends(get_current_user)
):
    """Get transparent version of existing HeyGen video using WebM API"""
    try:
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        if not HEYGEN_API_KEY or HEYGEN_API_KEY == "your-heygen-api-key":
            raise HTTPException(status_code=500, detail="HeyGen API key not configured")
        
        # Get original video details
        video = execute_query(
            "SELECT * FROM videos WHERE id = %s AND user_id = %s",
            (video_id, user["id"]),
            fetch_one=True
        )
        
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        video_dict = dict(video)
        
        # Get the original script/text from the video
        original_text = video_dict.get("script") or video_dict.get("title", "Hello from MyAvatar")
        
        # Get avatar info - you'll need to map this from your avatar system
        avatar_id = video_dict.get("avatar_id", "Angela-inblackskirt-20220820")  # Default fallback
        voice_id = video_dict.get("voice_id", "1bd001e7e50f421d891986aad5158bc8")  # Default fallback
        
        # Call HeyGen WebM API for transparent video
        heygen_headers = {
            "Content-Type": "application/json",
            "X-Api-Key": HEYGEN_API_KEY
        }
        
        heygen_payload = {
            "avatar_pose_id": avatar_id,
            "avatar_style": "normal",
            "input_text": original_text,
            "voice_id": voice_id
        }
        
        logger.info(f"Creating transparent video for user {user['username']}")
        
        response = requests.post(
            "https://api.heygen.com/v1/video.webm",
            headers=heygen_headers,
            json=heygen_payload,
            timeout=30
        )
        
        if not response.ok:
            logger.error(f"HeyGen WebM API error: {response.status_code} - {response.text}")
            raise HTTPException(status_code=500, detail="Failed to create transparent video")
        
        result = response.json()
        
        if "error" in result and result["error"]:
            raise HTTPException(status_code=500, detail=f"HeyGen error: {result['error']}")
        
        transparent_video_id = result["data"]["video_id"]
        
        # Store transparent video info in database
        execute_query(
            """INSERT INTO background_videos (original_video_id, transparent_video_id, heygen_video_id, 
               user_id, status, created_at) VALUES (%s, %s, %s, %s, %s, %s)""",
            (video_id, transparent_video_id, transparent_video_id, user["id"], "processing", datetime.now())
        )
        
        return JSONResponse({
            "success": True,
            "transparent_video_id": transparent_video_id,
            "status": "processing",
            "message": "Transparent video creation started. Check status in a few minutes."
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating transparent video: {e}")
        raise HTTPException(status_code=500, detail="Failed to create transparent video")

@router.get("/api/backgrounds/check-transparent-status/{transparent_video_id}")
async def check_transparent_video_status(
    transparent_video_id: str,
    user: Dict = Depends(get_current_user)
):
    """Check status of transparent video generation"""
    try:
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Check HeyGen video status
        headers = {"X-Api-Key": HEYGEN_API_KEY}
        response = requests.get(
            f"https://api.heygen.com/v1/video.webm/{transparent_video_id}",
            headers=headers,
            timeout=10
        )
        
        if not response.ok:
            raise HTTPException(status_code=500, detail="Failed to check video status")
        
        result = response.json()
        status = result.get("data", {}).get("status", "unknown")
        video_url = result.get("data", {}).get("video_url")
        
        # Update database status
        execute_query(
            "UPDATE background_videos SET status = %s, video_url = %s WHERE transparent_video_id = %s",
            (status, video_url, transparent_video_id)
        )
        
        return JSONResponse({
            "success": True,
            "status": status,
            "video_url": video_url if status == "completed" else None,
            "transparent_video_id": transparent_video_id
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking transparent video status: {e}")
        raise HTTPException(status_code=500, detail="Failed to check video status")

# ===============================================================================
# 2. GREEN SCREEN FALLBACK FOR EXISTING VIDEOS  
# ===============================================================================

@router.post("/api/backgrounds/create-green-screen")
async def create_green_screen_version(
    request: Request,
    video_id: str = Form(...),
    user: Dict = Depends(get_current_user)
):
    """Create green screen version of existing video for background replacement"""
    try:
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Get original video
        video = execute_query(
            "SELECT * FROM videos WHERE id = %s AND user_id = %s",
            (video_id, user["id"]),
            fetch_one=True
        )
        
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        video_dict = dict(video)
        
        # Recreate the video with green screen background
        heygen_headers = {
            "Content-Type": "application/json", 
            "X-Api-Key": HEYGEN_API_KEY
        }
        
        # Get original video parameters
        original_text = video_dict.get("script") or video_dict.get("title", "Hello from MyAvatar")
        avatar_id = video_dict.get("heygen_avatar_id", "Angela-inblackskirt-20220820")
        
        heygen_payload = {
            "video_inputs": [{
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id,
                    "avatar_style": "normal"
                },
                "voice": {
                    "type": "text",
                    "input_text": original_text,
                    "voice_id": "1bd001e7e50f421d891986aad5158bc8"  # Default voice
                },
                "background": {
                    "type": "color",
                    "value": "#008000"  # Green screen
                }
            }],
            "dimension": {
                "width": 1280,
                "height": 720
            }
        }
        
        response = requests.post(
            "https://api.heygen.com/v2/video/generate",
            headers=heygen_headers,
            json=heygen_payload,
            timeout=30
        )
        
        if not response.ok:
            raise HTTPException(status_code=500, detail="Failed to create green screen video")
        
        result = response.json()
        green_screen_video_id = result["data"]["video_id"]
        
        # Store in database
        execute_query(
            """INSERT INTO background_videos (original_video_id, green_screen_video_id, heygen_video_id,
               user_id, status, created_at) VALUES (%s, %s, %s, %s, %s, %s)""",
            (video_id, green_screen_video_id, green_screen_video_id, user["id"], "processing", datetime.now())
        )
        
        return JSONResponse({
            "success": True,
            "green_screen_video_id": green_screen_video_id,
            "status": "processing",
            "message": "Green screen video creation started"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating green screen video: {e}")
        raise HTTPException(status_code=500, detail="Failed to create green screen video")

# ===============================================================================
# 3. BACKGROUND LIBRARY MANAGEMENT WITH R2 STORAGE
# ===============================================================================

@router.get("/api/backgrounds")
async def get_backgrounds(user: Dict = Depends(get_current_user)):
    """Get user's background library"""
    try:
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        backgrounds = execute_query(
            """SELECT id, name, file_path, url, source, source_id, created_at, is_active
               FROM user_backgrounds WHERE user_id = %s AND is_active = true
               ORDER BY created_at DESC""",
            (user["id"],),
            fetch_all=True
        )
        
        background_list = []
        if backgrounds:
            for bg in backgrounds:
                bg_dict = dict(bg)
                background_list.append(bg_dict)
        
        return JSONResponse({
            "success": True,
            "backgrounds": background_list,
            "count": len(background_list)
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting backgrounds: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving backgrounds")

@router.post("/api/backgrounds/upload")
async def upload_background(
    background: UploadFile = File(...),
    name: str = Form(None),
    user: Dict = Depends(get_current_user)
):
    """Upload a background image to Cloudinary"""
    try:
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Validate file type
        if not background.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Only image files are allowed")
        
        # Read file content
        file_content = await background.read()
        
        # Generate unique filename
        file_extension = background.filename.split(".")[-1].lower()
        unique_filename = f"bg_{uuid.uuid4().hex[:8]}.{file_extension}"
        
        # Upload to Cloudinary
        public_url = upload_to_cloudinary(file_content, unique_filename)
        
        if not public_url:
            raise HTTPException(status_code=500, detail="Failed to upload to cloud storage")
        
        # Extract Cloudinary public_id from URL for database storage
        # Example URL: https://res.cloudinary.com/dwnu90g46/image/upload/v1234567890/myavatar/backgrounds/bg_12345678.jpg
        cloudinary_public_id = public_url.split("/upload/")[1].split(".")[0] if "/upload/" in public_url else unique_filename
        
        # Save to database
        bg_name = name or background.filename or "Uploaded Background"
        
        execute_query(
            """INSERT INTO user_backgrounds (user_id, name, file_path, url, source, created_at, is_active)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (user["id"], bg_name, cloudinary_public_id, public_url, "upload", datetime.now(), True)
        )
        
        return JSONResponse({
            "success": True,
            "message": "Background uploaded successfully",
            "background": {
                "name": bg_name,
                "url": public_url,
                "source": "upload"
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading background: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload background")

@router.post("/api/backgrounds/add-from-url")
async def add_background_from_url(
    request: Request,
    user: Dict = Depends(get_current_user)
):
    """Add background from external URL (Unsplash, AI generated, etc.) and store in Cloudinary"""
    try:
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        data = await request.json()
        image_url = data.get("image_url")
        name = data.get("name", "Background Image")
        source = data.get("source", "external")
        source_id = data.get("source_id")
        
        if not image_url:
            raise HTTPException(status_code=400, detail="Image URL is required")
        
        # Download image
        response = requests.get(image_url, timeout=30)
        if not response.ok:
            raise HTTPException(status_code=400, detail="Failed to download image")
        
        # Generate unique filename
        file_extension = "jpg"  # Default to jpg
        unique_filename = f"bg_{source}_{uuid.uuid4().hex[:8]}.{file_extension}"
        
        # Upload to Cloudinary
        public_url = upload_to_cloudinary(response.content, unique_filename)
        
        if not public_url:
            raise HTTPException(status_code=500, detail="Failed to upload to cloud storage")
        
        # Extract Cloudinary public_id from URL for database storage
        cloudinary_public_id = public_url.split("/upload/")[1].split(".")[0] if "/upload/" in public_url else unique_filename
        
        # Save to database
        execute_query(
            """INSERT INTO user_backgrounds (user_id, name, file_path, url, source, source_id, created_at, is_active)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (user["id"], name, cloudinary_public_id, public_url, source, source_id, datetime.now(), True)
        )
        
        return JSONResponse({
            "success": True,
            "message": "Background added successfully",
            "background": {
                "name": name,
                "url": public_url,
                "source": source
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding background from URL: {e}")
        raise HTTPException(status_code=500, detail="Failed to add background")

# ===============================================================================
# 4. UNSPLASH IMAGE SEARCH INTEGRATION
# ===============================================================================

@router.get("/api/backgrounds/search-images")
async def search_images(
    query: str,
    page: int = 1,
    per_page: int = 12,
    user: Dict = Depends(get_current_user)
):
    """Search for images on Unsplash"""
    try:
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        if not query or len(query.strip()) < 2:
            raise HTTPException(status_code=400, detail="Search query must be at least 2 characters")
        
        # Check if Unsplash is configured
        if not UNSPLASH_ACCESS_KEY or UNSPLASH_ACCESS_KEY == "your-unsplash-key":
            # Return demo results
            demo_results = [
                {
                    "id": "demo1",
                    "urls": {
                        "small": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=400",
                        "regular": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=800",
                        "full": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=1600"
                    },
                    "alt_description": "Mountain landscape",
                    "user": {"name": "Demo User", "links": {"html": "#"}},
                    "links": {"download": "#"}
                },
                {
                    "id": "demo2", 
                    "urls": {
                        "small": "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=400",
                        "regular": "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=800",
                        "full": "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=1600"
                    },
                    "alt_description": "Forest path",
                    "user": {"name": "Demo User", "links": {"html": "#"}},
                    "links": {"download": "#"}
                }
            ]
            
            return JSONResponse({
                "success": True,
                "results": demo_results,
                "total": 2,
                "total_pages": 1,
                "demo_mode": True,
                "message": "Demo results shown. Configure UNSPLASH_ACCESS_KEY for full search."
            })
        
        # Real Unsplash API call
        headers = {"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"}
        params = {
            "query": query,
            "page": page,
            "per_page": min(per_page, 30),  # Unsplash max is 30
            "orientation": "landscape"  # Better for video backgrounds
        }
        
        response = requests.get(
            "https://api.unsplash.com/search/photos",
            headers=headers,
            params=params,
            timeout=10
        )
        
        if not response.ok:
            raise HTTPException(status_code=500, detail="Unsplash search failed")
        
        data = response.json()
        
        return JSONResponse({
            "success": True,
            "results": data.get("results", []),
            "total": data.get("total", 0),
            "total_pages": data.get("total_pages", 0),
            "current_page": page
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching images: {e}")
        raise HTTPException(status_code=500, detail="Image search failed")

# ===============================================================================
# 5. AI IMAGE GENERATION WITH OPENAI DALL-E
# ===============================================================================

@router.post("/api/backgrounds/generate-ai-image")
async def generate_ai_image(
    request: Request,
    user: Dict = Depends(get_current_user)
):
    """Generate AI image using OpenAI DALL-E"""
    try:
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        data = await request.json()
        prompt = data.get("prompt", "").strip()
        
        if not prompt or len(prompt) < 10:
            raise HTTPException(status_code=400, detail="Prompt must be at least 10 characters")
        
        if not OPENAI_API_KEY or OPENAI_API_KEY == "your-openai-api-key":
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")
        
        # Call OpenAI DALL-E API
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "dall-e-3",
            "prompt": f"Professional video background: {prompt}. High quality, suitable for video compositing.",
            "size": "1792x1024",  # Good aspect ratio for video backgrounds
            "quality": "standard",
            "n": 1
        }
        
        response = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers=headers,
            json=payload,
            timeout=60  # DALL-E can take a while
        )
        
        if not response.ok:
            error_data = response.json() if response.headers.get("content-type") == "application/json" else {}
            error_message = error_data.get("error", {}).get("message", "AI image generation failed")
            raise HTTPException(status_code=500, detail=error_message)
        
        result = response.json()
        
        if not result.get("data") or len(result["data"]) == 0:
            raise HTTPException(status_code=500, detail="No image generated")
        
        image_url = result["data"][0]["url"]
        
        return JSONResponse({
            "success": True,
            "image_url": image_url,
            "prompt": prompt,
            "source": "dall-e-3"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating AI image: {e}")
        raise HTTPException(status_code=500, detail="AI image generation failed")

# ===============================================================================
# 6. VIDEO COMPOSITION (FUTURE ENHANCEMENT)
# ===============================================================================

@router.post("/api/backgrounds/compose-video")
async def compose_video_with_background(
    request: Request,
    user: Dict = Depends(get_current_user)
):
    """Compose transparent video with selected background (placeholder for future implementation)"""
    try:
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        data = await request.json()
        transparent_video_id = data.get("transparent_video_id")
        background_id = data.get("background_id")
        
        if not transparent_video_id or not background_id:
            raise HTTPException(status_code=400, detail="Both transparent_video_id and background_id are required")
        
        # This would integrate with video processing service
        # For now, return placeholder response
        
        return JSONResponse({
            "success": True,
            "message": "Video composition feature coming soon!",
            "status": "planned",
            "transparent_video_id": transparent_video_id,
            "background_id": background_id,
            "note": "This will combine the transparent video with your selected background"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error composing video: {e}")
        raise HTTPException(status_code=500, detail="Video composition failed")

# ===============================================================================
# 7. STATUS AND UTILITY ENDPOINTS
# ===============================================================================

@router.get("/api/backgrounds/status")
async def backgroundfx_status():
    """Check BackgroundFX service status"""
    cloudinary_configured = get_cloudinary_config()
    
    return JSONResponse({
        "success": True,
        "service": "BackgroundFX API",
        "status": "operational",
        "version": "2.0.0",
        "storage": "Cloudinary CDN",
        "features": {
            "transparent_videos": bool(HEYGEN_API_KEY and HEYGEN_API_KEY != "your-heygen-api-key"),
            "image_search": bool(UNSPLASH_ACCESS_KEY and UNSPLASH_ACCESS_KEY != "your-unsplash-key"),
            "ai_generation": bool(OPENAI_API_KEY and OPENAI_API_KEY != "your-openai-api-key"),
            "background_library": True,
            "green_screen_fallback": True,
            "cloud_storage": cloudinary_configured,
            "image_optimization": True,  # Cloudinary bonus feature!
            "global_cdn": True  # Cloudinary bonus feature!
        },
        "timestamp": datetime.now().isoformat()
    })

@router.get("/api/videos")
async def get_user_videos(user: Dict = Depends(get_current_user)):
    """Get user's videos for BackgroundFX interface"""
    try:
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        videos = execute_query(
            """SELECT id, title, description, status, video_path, thumbnail_url, created_at, heygen_video_id
               FROM videos WHERE user_id = %s ORDER BY created_at DESC""",
            (user["id"],),
            fetch_all=True
        )
        
        video_list = []
        if videos:
            for video in videos:
                video_dict = dict(video)
                video_list.append(video_dict)
        
        return JSONResponse({
            "success": True,
            "videos": video_list,
            "count": len(video_list)
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user videos: {e}")
        raise HTTPException(status_code=500, detail="Failed to get videos")

# ===============================================================================
# 8. BACKGROUND DELETION WITH R2 CLEANUP
# ===============================================================================

@router.delete("/api/backgrounds/{background_id}")
async def delete_background(
    background_id: int,
    user: Dict = Depends(get_current_user)
):
    """Delete background from library and Cloudinary storage"""
    try:
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Get background info
        background = execute_query(
            "SELECT * FROM user_backgrounds WHERE id = %s AND user_id = %s",
            (background_id, user["id"]),
            fetch_one=True
        )
        
        if not background:
            raise HTTPException(status_code=404, detail="Background not found")
        
        bg_dict = dict(background)
        
        # Delete from Cloudinary if file_path exists (contains the public_id)
        if bg_dict.get("file_path"):
            delete_from_cloudinary(bg_dict["file_path"])
        
        # Delete from database
        execute_query(
            "DELETE FROM user_backgrounds WHERE id = %s AND user_id = %s",
            (background_id, user["id"])
        )
        
        return JSONResponse({
            "success": True,
            "message": "Background deleted successfully"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting background: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete background")

# ===============================================================================
# 9. DATABASE SCHEMA INITIALIZATION
# ===============================================================================

def initialize_backgroundfx_schema():
    """Initialize database tables for BackgroundFX"""
    try:
        # Create background_videos table
        execute_query("""
            CREATE TABLE IF NOT EXISTS background_videos (
                id SERIAL PRIMARY KEY,
                original_video_id INTEGER REFERENCES videos(id),
                transparent_video_id VARCHAR(255),
                green_screen_video_id VARCHAR(255),
                heygen_video_id VARCHAR(255),
                user_id INTEGER REFERENCES users(id),
                status VARCHAR(50) DEFAULT 'processing',
                video_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create user_backgrounds table
        execute_query("""
            CREATE TABLE IF NOT EXISTS user_backgrounds (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                name VARCHAR(255) NOT NULL,
                file_path VARCHAR(255),
                url TEXT,
                source VARCHAR(50),
                source_id VARCHAR(255),
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        logger.info("BackgroundFX database schema initialized successfully")
        
    except Exception as e:
        logger.error(f"Error initializing BackgroundFX schema: {e}")

# Initialize schema when module loads
initialize_backgroundfx_schema()
