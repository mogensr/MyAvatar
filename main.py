"""
MyAvatar - Complete AI Avatar Video Generation Platform
========================================================
Modular version with enhanced organization
"""
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import logging
import traceback
import uuid
from datetime import datetime
from typing import Optional
from app.services.notifications import send_alert, notify_service_status

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MyAvatar")

# Import compatibility mode checking
from app.compatibility import ENABLE_SAFE_MODE, ENABLE_BACKGROUND_REPLACEMENT, log_compatibility_status

# Import modular components
from app.logger.log_handler import log_handler, log_info, log_error, log_warning
from app.db.database import init_database, update_database_schema, get_db_connection
from app.db.admin import create_admin_user
from app.routes.api_routes import router as api_router
from app.routes.web_routes import router as web_router
from app.routes.finance_routes import router as finance_router
from app.routes.health_routes import router as health_router

# Conditionally import background replacement components
if ENABLE_BACKGROUND_REPLACEMENT:
    from app.database.background_schema import initialize_backgrounds_schema, add_default_backgrounds
    from app.routes.background_routes import router as background_router

# FASTAPI APP INITIALIZATION
app = FastAPI(title="MyAvatar", description="AI Avatar Video Generation Platform - Premium Edition")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,  
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request validation (CORRECTED TO MATCH FRONTEND)
class TextVideoRequest(BaseModel):
    title: str
    avatar_id: str
    format: str = "16:9"  # Default format (stored in memory, not DB)
    text: str
    description: Optional[str] = ""

# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log_error(f"Uncaught exception: {str(exc)}", "Server", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "message": str(exc)}
    )

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# TEXT-TO-VIDEO API ENDPOINT (CORRECTED FOR ACTUAL DATABASE SCHEMA)
@app.post("/api/create-text-video")
async def create_text_video(request: TextVideoRequest):
    """
    Create a new text-to-video with the provided text content
    """
    try:
        # Validate required fields
        if not request.title.strip():
            raise HTTPException(status_code=400, detail="Title is required")
        if not request.avatar_id:
            raise HTTPException(status_code=400, detail="Avatar selection is required")
        if not request.text.strip():
            raise HTTPException(status_code=400, detail="Text content is required")
        
        # Get database connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Generate unique video ID (use integer for your database)
        # Get next available ID from database
        cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM videos")
        video_id = cursor.fetchone()[0]
        
        # Insert video record into database (matching your actual table structure)
        # Based on your logs, the videos table has: id, user_id, avatar_id, title, 
        # audio_path, video_path, heygen_video_id, status, created_at, etc.
        query = """
            INSERT INTO videos (id, user_id, avatar_id, title, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        # TODO: Get actual user_id from session - you'll need to add session handling
        # For now using a default - replace this with proper session management
        user_id = 3  # Based on your logs, user_id 3 exists
        
        cursor.execute(query, (
            video_id,
            user_id,
            request.avatar_id,
            request.title.strip(),
            'processing',
            datetime.now()
        ))
        conn.commit()
        
        # Close database connection
        cursor.close()
        conn.close()
        
        log_info(f"Text-to-video creation started - Video ID: {video_id}, Text: {request.text[:50]}...", "Video")
        
        # TODO: Add your video processing logic here
        # This could involve:
        # 1. Queuing the video for processing
        # 2. Calling your text-to-speech service
        # 3. Calling your avatar animation service
        # 4. Combining audio and video
        # 5. Store format and description in a separate table if needed
        
        return JSONResponse(
            status_code=200,
            content={
                'success': True,
                'video_id': video_id,
                'message': 'Video creation started'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error creating text video: {str(e)}", "Video", e)
        raise HTTPException(status_code=500, detail="Failed to create video")

# Register routes
app.include_router(api_router)
app.include_router(web_router)
app.include_router(finance_router)
app.include_router(health_router)

# Conditionally register background routes
if ENABLE_BACKGROUND_REPLACEMENT:
    app.include_router(background_router, prefix="/background", tags=["background"])
    
    # Report successful startup
    notify_service_status("MyAvatar", "up", "Application started successfully")

# Create necessary directories
for directory in ["static/uploads/audio", "static/uploads/images", "output", "processed", "uploads", "temp_audio", "static/backgrounds", "temp/background_processing", "temp/video_processing"]:
    os.makedirs(directory, exist_ok=True)

# Health check endpoint
@app.get("/health")
async def health_check():
    # Check that all required services are available
    try:
        # You could add additional service checks here
        # For example, check database connection, external API accessibility
        
        # Check BackgroundFX service if configured
        from app.services.backgroundfx_client import BackgroundFXClient
        backgroundfx_url = os.environ.get("BACKGROUNDFX_URL")
        
        if backgroundfx_url:
            client = BackgroundFXClient()
            backgroundfx_health = await client.health_check()
            
            if backgroundfx_health.get("status") != "ok":
                send_alert(
                    title="BackgroundFX Health Check Failed",
                    message=f"BackgroundFX service is not responding correctly: {backgroundfx_health}", 
                    severity="warning"
                )
                return {"status": "warning", "details": "BackgroundFX service degraded"}
        
        return {"status": "ok"}
    except Exception as e:
        send_alert(
            title="Health Check Failed",
            message=f"Error during health check: {str(e)}",
            severity="error"
        )
        return {"status": "error", "details": str(e)}

# Startup event
@app.on_event("startup")
async def startup_event():
    # Initialize the notification system
    try:
        from app.services.notifications import notify_service_status
        notify_service_status("MyAvatar", "up", "Application started successfully")
        logging.info("Notification system initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize notification system: {str(e)}")

    """
    Initialize database and update schema on startup
    """
    # Log compatibility status
    status = log_compatibility_status()
    log_info(f"Starting MyAvatar application (Safe Mode: {status['safe_mode']})", "Server")
    
    try:
        init_database()
        update_database_schema()
        create_admin_user()  # Create admin user if not exists
        
        # Initialize background replacement feature only if not in safe mode
        if ENABLE_BACKGROUND_REPLACEMENT:
            logger.info("Background replacement functionality enabled via BackgroundFX microservice")
    except Exception as e:
        log_error(f"Error during startup: {str(e)}", "Server", e)
        log_warning("Application may not function correctly due to startup error", "Server")
    
    # Successfully started
    edition_name = "Premium Edition" if not ENABLE_SAFE_MODE else "Premium Edition (Safe Mode)"
    log_info(f"MyAvatar {edition_name} is running", "Server")

from app.routes import background as background_routes
app.include_router(background_routes.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)