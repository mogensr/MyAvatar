from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Dict, Any
import sqlite3
import os
import httpx
import logging
from datetime import datetime
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="MyAvatar Video Generation API")

# Mount static files directory
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Security
security = HTTPBearer()

# Database configuration
DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/videos.db")
HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY")
HEYGEN_API_URL = "https://api.heygen.com/v2/video/generate"
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://your-app-name.railway.app/webhook/heygen")

# Pydantic models
class VideoGenerationRequest(BaseModel):
    avatar_id: str
    script: str
    voice_id: Optional[str] = None
    background: Optional[str] = None

class HeyGenWebhookPayload(BaseModel):
    event: str
    data: Dict[str, Any]

class VideoResponse(BaseModel):
    id: int
    user_id: int
    heygen_job_id: str
    video_url: Optional[str]
    status: str
    created_at: str
    updated_at: Optional[str]

# Database helper functions
def get_db_connection():
    """Create a database connection"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def execute_query(query: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = False):
    """Execute a database query"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(query, params)
        
        if fetch_one:
            result = cursor.fetchone()
            return dict(result) if result else None
        elif fetch_all:
            results = cursor.fetchall()
            return [dict(row) for row in results]
        else:
            conn.commit()
            return cursor.lastrowid
    finally:
        conn.close()

def init_database():
    """Initialize the database with required tables"""
    # Create data directory if it doesn't exist (for Railway persistent storage)
    data_dir = os.path.dirname(DATABASE_PATH)
    if data_dir and not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            heygen_job_id TEXT UNIQUE,
            video_url TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP,
            metadata TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            api_key TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()

# Authentication
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Validate API key and return user"""
    api_key = credentials.credentials
    
    user = execute_query(
        "SELECT * FROM users WHERE api_key = ?",
        (api_key,),
        fetch_one=True
    )
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return user

# HeyGen API integration
async def generate_heygen_video(avatar_id: str, script: str, voice_id: Optional[str] = None, 
                               background: Optional[str] = None) -> Dict[str, Any]:
    """Call HeyGen API to generate video"""
    
    headers = {
        "X-Api-Key": HEYGEN_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "video_inputs": [{
            "character": {
                "type": "avatar",
                "avatar_id": avatar_id
            },
            "voice": {
                "type": "text",
                "input_text": script,
                "voice_id": voice_id or "default_voice"
            }
        }],
        "dimension": {
            "width": 1920,
            "height": 1080
        },
        "webhook_url": WEBHOOK_URL
    }
    
    if background:
        payload["background"] = {"type": "color", "value": background}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                HEYGEN_API_URL,
                headers=headers,
                json=payload,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HeyGen API error: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to generate video")

# API Endpoints
@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_database()
    logger.info("Database initialized")

@app.get("/")
async def root():
    """Serve the dashboard.html from static folder"""
    dashboard_path = "static/dashboard.html"
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path)
    else:
        return {"error": "Dashboard not found", "looking_for": dashboard_path}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "MyAvatar Video Generation API"}

@app.post("/api/videos/generate", response_model=VideoResponse)
async def generate_video(
    request: VideoGenerationRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict = Depends(get_current_user)
):
    """Generate a new video using HeyGen API"""
    
    try:
        # Call HeyGen API
        heygen_response = await generate_heygen_video(
            avatar_id=request.avatar_id,
            script=request.script,
            voice_id=request.voice_id,
            background=request.background
        )
        
        # Extract job ID from HeyGen response
        heygen_job_id = heygen_response.get("data", {}).get("video_id")
        
        if not heygen_job_id:
            raise HTTPException(status_code=500, detail="Failed to get video ID from HeyGen")
        
        # Save video record to database
        video_id = execute_query(
            """
            INSERT INTO videos (user_id, heygen_job_id, status, metadata)
            VALUES (?, ?, ?, ?)
            """,
            (
                current_user["id"],
                heygen_job_id,
                "processing",
                json.dumps({
                    "avatar_id": request.avatar_id,
                    "script": request.script,
                    "voice_id": request.voice_id,
                    "background": request.background
                })
            )
        )
        
        # Fetch and return the created record
        video_record = execute_query(
            "SELECT * FROM videos WHERE id = ?",
            (video_id,),
            fetch_one=True
        )
        
        return VideoResponse(**video_record)
        
    except Exception as e:
        logger.error(f"Video generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
async def get_stats():
    """Get video statistics for dashboard"""
    stats = execute_query(
        """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END) as processing,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
        FROM videos
        """,
        (),
        fetch_one=True
    )
    
    return {
        "total": stats["total"] or 0,
        "completed": stats["completed"] or 0,
        "processing": stats["processing"] or 0,
        "pending": stats["pending"] or 0,
        "failed": stats["failed"] or 0
    }

@app.get("/api/videos/recent")
async def get_recent_videos(limit: int = 10):
    """Get recent videos for dashboard (no auth required)"""
    videos = execute_query(
        """
        SELECT id, heygen_job_id, video_url, status, created_at, updated_at
        FROM videos 
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
        fetch_all=True
    )
    
    return videos

@app.get("/api/videos/{video_id}", response_model=VideoResponse)
async def get_video(video_id: int, current_user: Dict = Depends(get_current_user)):
    """Get video details by ID"""
    
    video_record = execute_query(
        "SELECT * FROM videos WHERE id = ? AND user_id = ?",
        (video_id, current_user["id"]),
        fetch_one=True
    )
    
    if not video_record:
        raise HTTPException(status_code=404, detail="Video not found")
    
    return VideoResponse(**video_record)

@app.get("/api/videos", response_model=list[VideoResponse])
async def list_videos(
    current_user: Dict = Depends(get_current_user),
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """List user's videos with optional filtering"""
    
    if status:
        videos = execute_query(
            """
            SELECT * FROM videos 
            WHERE user_id = ? AND status = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (current_user["id"], status, limit, offset),
            fetch_all=True
        )
    else:
        videos = execute_query(
            """
            SELECT * FROM videos 
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (current_user["id"], limit, offset),
            fetch_all=True
        )
    
    return [VideoResponse(**video) for video in videos]

@app.post("/webhook/heygen")
async def heygen_webhook(request: Request):
    """
    Handle HeyGen webhook callbacks
    
    FIXED: Now correctly searches for heygen_job_id instead of heygen_video_id
    """
    try:
        # Parse webhook payload
        payload = await request.json()
        logger.info(f"Received HeyGen webhook: {json.dumps(payload)}")
        
        # Extract event type and data
        event = payload.get("event")
        data = payload.get("data", {})
        
        # Extract video_id from payload (this is the job_id we stored)
        video_id = data.get("video_id")
        
        if not video_id:
            logger.error("No video_id in webhook payload")
            return JSONResponse(
                status_code=400,
                content={"error": "Missing video_id in payload"}
            )
        
        # FIXED: Search using heygen_job_id column instead of heygen_video_id
        video_record = execute_query(
            "SELECT * FROM videos WHERE heygen_job_id = ?",
            (video_id,),
            fetch_one=True
        )
        
        if not video_record:
            logger.error(f"Video record not found for heygen_job_id: {video_id}")
            return JSONResponse(
                status_code=404,
                content={"error": "Video record not found"}
            )
        
        # Handle different event types
        if event == "avatar_video.success":
            # Video generation completed successfully
            video_url = data.get("video_url")
            
            if video_url:
                # Update video record with URL and status
                execute_query(
                    """
                    UPDATE videos 
                    SET video_url = ?, status = ?, updated_at = ?
                    WHERE heygen_job_id = ?
                    """,
                    (video_url, "completed", datetime.utcnow().isoformat(), video_id)
                )
                logger.info(f"Video completed successfully: {video_id}")
            else:
                logger.error(f"No video_url in success webhook for: {video_id}")
                
        elif event == "avatar_video.failed":
            # Video generation failed
            error_message = data.get("error", "Unknown error")
            
            execute_query(
                """
                UPDATE videos 
                SET status = ?, updated_at = ?, metadata = ?
                WHERE heygen_job_id = ?
                """,
                (
                    "failed",
                    datetime.utcnow().isoformat(),
                    json.dumps({
                        "error": error_message,
                        "failed_at": datetime.utcnow().isoformat()
                    }),
                    video_id
                )
            )
            logger.error(f"Video generation failed for {video_id}: {error_message}")
            
        elif event == "avatar_video.processing":
            # Video is still processing
            progress = data.get("progress", 0)
            
            execute_query(
                """
                UPDATE videos 
                SET updated_at = ?, metadata = ?
                WHERE heygen_job_id = ?
                """,
                (
                    datetime.utcnow().isoformat(),
                    json.dumps({"progress": progress}),
                    video_id
                )
            )
            logger.info(f"Video processing update for {video_id}: {progress}%")
            
        else:
            logger.warning(f"Unknown webhook event: {event}")
        
        return JSONResponse(
            status_code=200,
            content={"status": "success", "message": "Webhook processed"}
        )
        
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"}
        )

@app.delete("/api/videos/{video_id}")
async def delete_video(video_id: int, current_user: Dict = Depends(get_current_user)):
    """Delete a video record"""
    
    # Check if video exists and belongs to user
    video_record = execute_query(
        "SELECT * FROM videos WHERE id = ? AND user_id = ?",
        (video_id, current_user["id"]),
        fetch_one=True
    )
    
    if not video_record:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Delete the video record
    execute_query(
        "DELETE FROM videos WHERE id = ?",
        (video_id,)
    )
    
    return {"message": "Video deleted successfully"}

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=404,
        content={"error": "Resource not found"}
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception):
    logger.error(f"Internal server error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)