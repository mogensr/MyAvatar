import os
import uuid
import aiofiles
import httpx
import logging
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Request, Depends
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader
import traceback
import sqlite3

# Load env vars
load_dotenv()

HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY")
HEYGEN_VOICE_ID = os.getenv("HEYGEN_VOICE_ID")
DEFAULT_AVATAR_ID = os.getenv("HEYGEN_AVATAR_ID", "default_avatar_id")

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

router = APIRouter(prefix="/api/video", tags=["video"])

# Helper function to get current user from session
def get_current_user(request: Request):
    return request.session.get("user", None)

@router.post("/generate")
async def generate_video(
    request: Request,  # Add request to get session
    file: UploadFile = File(...),
    avatar_id: Optional[str] = Query(None),
    voice_id: Optional[str] = Query(None)
):
    # Get the current user
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        # Windows-kompatibel midlertidig mappe
        temp_dir = os.path.join(os.getcwd(), "temp_audio")
        os.makedirs(temp_dir, exist_ok=True)
        temp_filename = os.path.join(temp_dir, f"{uuid.uuid4()}_{file.filename}")

        async with aiofiles.open(temp_filename, 'wb') as out_file:
            content = await file.read()
            await out_file.write(content)

        logging.info(f"[DEBUG] Lydfil gemt til: {temp_filename}")

        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            temp_filename,
            folder="myavatar/audio/",
            resource_type="video"
        )
        audio_url = upload_result.get("secure_url")
        logging.info(f"[DEBUG] Cloudinary secure_url: {audio_url}")

        # Clean up temp file
        try:
            os.remove(temp_filename)
        except:
            pass

        if not audio_url:
            raise HTTPException(status_code=500, detail="Cloudinary upload failed")

        # HeyGen v2 payload with callback URL
        payload = {
            "video_inputs": [{
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id or DEFAULT_AVATAR_ID,
                    "avatar_style": "normal"
                },
                "voice": {
                    "type": "audio",
                    "audio_url": audio_url
                }
            }],
            "test": False,
            "caption": False,
            "private": False,
            "callback_url": "https://app.myavatar.dk/api/heygen/webhook"
        }

        logging.info(f"[DEBUG] Payload til HeyGen: {payload}")

        headers = {
            "X-Api-Key": HEYGEN_API_KEY,
            "Content-Type": "application/json"
        }

        # Call HeyGen v2 API
        async with httpx.AsyncClient() as client:
            response = await client.post("https://api.heygen.com/v2/video/generate", json=payload, headers=headers)

        # Save to database if successful
        if response.status_code == 200:
            result_data = response.json()
            video_id = result_data.get("data", {}).get("video_id")
            
            if video_id:
                # Get avatar details from database
                conn = sqlite3.connect("myavatar.db", timeout=10.0)
                cur = conn.cursor()
                
                # Find the avatar record by heygen_avatar_id
                cur.execute(
                    "SELECT id FROM avatars WHERE heygen_avatar_id = ? AND user_id = ?",
                    (avatar_id, user["id"])
                )
                avatar_record = cur.fetchone()
                avatar_db_id = avatar_record[0] if avatar_record else None
                
                # Save to database with the current user's ID
                cur.execute(
                    "INSERT INTO videos (user_id, avatar_id, title, heygen_job_id, status) VALUES (?, ?, ?, ?, ?)",
                    (user["id"], avatar_db_id, "Video from API", video_id, "processing")
                )
                conn.commit()
                conn.close()
                
                logging.info(f"[DEBUG] Video saved to DB with ID: {video_id} for user: {user['username']}")
                return {"success": True, "video_id": video_id, "status": "processing", "message": "Video generation started."}
            else:
                # No video_id, but API call succeeded: return pending status
                return {"success": True, "status": "pending", "message": "Video generation started, waiting for HeyGen to finish."}
        else:
            logging.error(f"[ERROR] HeyGen response: {response.text}")
            raise HTTPException(status_code=response.status_code, detail=response.text)

    except Exception as e:
        # Crash debug log
        tb = traceback.format_exc()
        print("[CRASH] Video generation failed:\n", tb)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{video_id}")
async def check_video_status(video_id: str, request: Request):
    # Get the current user
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        headers = {"X-Api-Key": HEYGEN_API_KEY}
        
        # Use correct v2 endpoint - it's different from what we had!
        async with httpx.AsyncClient() as client:
            # Try the v1 endpoint which still works for status
            response = await client.get(
                f"https://api.heygen.com/v1/video_status.get?video_id={video_id}", 
                headers=headers
            )
        
        logging.info(f"[DEBUG] Status check for {video_id}: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            logging.info(f"[DEBUG] Status response: {result}")
            
            # Check both possible status fields
            status = result.get("data", {}).get("status") or result.get("status")
            video_url = result.get("data", {}).get("video_url") or result.get("video_url")
            
            # Update database if video is completed - only for user's own videos
            if status == "completed" and video_url:
                conn = sqlite3.connect("myavatar.db", timeout=10.0)
                cur = conn.cursor()
                cur.execute(
                    "UPDATE videos SET status = 'completed', video_url = ? WHERE heygen_job_id = ? AND user_id = ?",
                    (video_url, video_id, user["id"])
                )
                conn.commit()
                conn.close()
                logging.info(f"[DEBUG] Video {video_id} marked as completed with URL: {video_url}")
        
        data = response.json().get("data", {})
        status = data.get("status", "processing")
        video_url = data.get("video_url", "")
        # Optionally update your DB here as before...
        return {
            "status": status,
            "video_url": video_url,
            "raw": response.json()  # Optional: include the full raw response for debugging
        }
    except Exception as e:
        logging.error(f"[ERROR] Status check failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_videos():
    try:
        headers = {"X-Api-Key": HEYGEN_API_KEY}
        async with httpx.AsyncClient() as client:
            # Use v1 endpoint for list - v2 might not have this
            response = await client.get("https://api.heygen.com/v1/video.list", headers=headers)
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        
        return response.json()
    except Exception as e:
        logging.error(f"[ERROR] List videos failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))