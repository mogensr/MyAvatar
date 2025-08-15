"""
MyAvatar - Complete AI Avatar Video Generation Platform
========================================================
FIXED VERSION: Added direct API endpoints to bypass router loading issues
"""
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import logging
import traceback
import uuid
import threading
from datetime import datetime
from typing import Optional
from pathlib import Path
import sys
import json
import asyncio

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('myavatar.log', mode='a')
    ]
)
logger = logging.getLogger("MyAvatar")

# FastAPI app
app = FastAPI(
    title="MyAvatar - AI Video Generation Platform",
    description="Complete AI Avatar Video Generation Platform with Premium Features",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Static files
try:
    static_dir = Path("static")
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory="static"), name="static")
        logger.info("✅ Static files mounted successfully")
    else:
        logger.warning("⚠️ Static directory not found")
except Exception as e:
    logger.error(f"❌ Error mounting static files: {e}")

# Templates - FIXED INITIALIZATION
try:
    templates_dir = Path("templates")
    if templates_dir.exists():
        templates = Jinja2Templates(directory="templates")
        logger.info("✅ Templates configured successfully")
    else:
        logger.warning("⚠️ Templates directory not found, creating it...")
        templates_dir.mkdir(exist_ok=True)
        templates = Jinja2Templates(directory="templates")
        logger.info("✅ Templates directory created and configured")
except Exception as e:
    logger.error(f"❌ Error configuring templates: {e}")
    # Force create templates object even if there's an error
    try:
        templates = Jinja2Templates(directory="templates")
        logger.info("✅ Templates object created as fallback")
    except:
        logger.error("❌ CRITICAL: Cannot create templates object")
        templates = None

# Import database functions
try:
    from app.db.database import execute_query
    logger.info("✅ Database functions imported successfully")
except Exception as e:
    logger.error(f"❌ Error importing database functions: {e}")

# Import JWT for authentication
try:
    from jose import jwt
except ImportError:
    try:
        import jwt
    except ImportError:
        logger.error("❌ No JWT library found - authentication will fail")
        jwt = None

# Configuration
class Config:
    JWT_SECRET = os.getenv("JWT_SECRET", "fallback-development-secret-key")
    JWT_ALGORITHM = "HS256"

config = Config()

# =============================================================================
# DIRECT API ENDPOINTS (BYPASS ROUTER LOADING ISSUES)
# =============================================================================

def get_current_user_from_request(request: Request):
    """Get current user with proper JWT validation - PostgreSQL compatible"""
    try:
        token = request.cookies.get("access_token")
        if not token:
            return None
        
        if not jwt:
            return None
        
        # Validate JWT token with expiry check
        try:
            payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        except:
            return None
        
        user_id = payload.get("user_id")
        if not user_id:
            return None
        
        # Get fresh user data from database
        user = execute_query(
            "SELECT * FROM users WHERE id = %s",
            (user_id,),
            fetch_one=True
        )
        
        if not user:
            return None
            
        return user
        
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        return None

def verify_token_from_header(auth_header: str):
    """Verify JWT token from Authorization header for API calls"""
    try:
        if not auth_header or not auth_header.startswith('Bearer '):
            return None
        
        if not jwt:
            return None
        
        token = auth_header.replace('Bearer ', '')
        
        try:
            payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        except:
            return None
        
        user_id = payload.get("user_id")
        if not user_id:
            return None
        
        # Get user from database
        user = execute_query(
            "SELECT * FROM users WHERE id = %s",
            (user_id,),
            fetch_one=True
        )
        
        return user
        
    except Exception as e:
        logger.error(f"Error verifying token from header: {e}")
        return None

@app.post("/api/save-video-metadata")
@app.options("/api/save-video-metadata")
async def save_video_metadata_direct(request: Request):
    """
    Save video metadata from external sources (like HF Spaces)
    Video file is already uploaded to Cloudinary - we just save metadata
    DIRECT IMPLEMENTATION - bypassing router loading issues
    """
    
    # Handle CORS preflight request
    if request.method == "OPTIONS":
        return Response(
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            }
        )
    
    try:
        logger.info("📥 DIRECT API: Received save-video-metadata request from HF Spaces")
        
        # Get JSON data from request
        try:
            data = await request.json()
        except Exception as e:
            logger.error(f"Failed to parse JSON: {e}")
            return Response(
                content=json.dumps({
                    "success": False,
                    "error": "Invalid JSON format"
                }),
                status_code=400,
                headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"}
            )
        
        logger.info(f"📊 DIRECT API: Request data: {data}")
        
        # Flexible authentication - try multiple methods
        user = None
        user_id = 1  # Default fallback user for testing
        
        # Method 1: Try Authorization header
        auth_header = request.headers.get('Authorization', '')
        if auth_header:
            user = verify_token_from_header(auth_header)
            if user:
                user_id = int(user['id'])
                logger.info(f"✅ DIRECT API: Authenticated user via header: {user.get('username')}")
        
        # Method 2: Try user_id in data (for testing)
        elif data.get('user_id'):
            try:
                test_user_id = int(data['user_id'])
                user = execute_query(
                    "SELECT * FROM users WHERE id = %s",
                    (test_user_id,),
                    fetch_one=True
                )
                if user:
                    user_id = test_user_id
                    logger.info(f"✅ DIRECT API: Found user via data: {user.get('username')}")
            except:
                pass
        
        # Method 3: Use default user (fallback for testing)
        if not user:
            user = execute_query(
                "SELECT * FROM users WHERE id = %s",
                (user_id,),
                fetch_one=True
            )
            logger.info(f"⚠️ DIRECT API: Using fallback user: {user_id}")
        
        # Validate required fields
        if not data.get('video_url'):
            return Response(
                content=json.dumps({
                    "success": False,
                    "error": "video_url is required"
                }),
                status_code=400,
                headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"}
            )
        
        # Prepare video data for database
        video_title = data.get('title', 'BackgroundFX Video')[:255]  # Limit title length
        
        video_data = {
            "user_id": user_id,
            "title": video_title,
            "status": "completed",
            "video_url": data['video_url'],  # Cloudinary URL
            "thumbnail_url": data.get('thumbnail_url', data['video_url'].replace('.mp4', '.jpg')),
            "duration": str(data.get('duration', 8)),  # Convert to string for PostgreSQL
            "format": data.get('format', '16:9'),
            "source": data.get('source', 'BackgroundFX')
        }
        
        logger.info(f"💾 DIRECT API: Saving video data: {video_data}")
        
        # Insert into videos table with proper error handling
        try:
            # Create a dynamic avatar based on the video title
            video_title_clean = video_data["title"].replace(" ", "_").replace("-", "_")[:50]  # Clean and limit length
            avatar_name = video_title_clean if video_title_clean else "BackgroundFX_Video"
            
            # Check if avatar already exists for this user with this name
            existing_avatar = execute_query(
                "SELECT id FROM user_avatars WHERE user_id = %s AND avatar_name = %s LIMIT 1",
                (user_id, avatar_name),
                fetch_one=True
            )
            
            if existing_avatar:
                avatar_id = existing_avatar['id']
                logger.info(f"🎯 DIRECT API: Using existing avatar '{avatar_name}' (ID: {avatar_id}) for user {user_id}")
            else:
                # Create new avatar with the video name
                # Generate a unique avatar_id (probably should be a string like HeyGen avatars)
                unique_avatar_id = f"bg_{avatar_name.lower()}_{int(datetime.now().timestamp())}"
                
                new_avatar_result = execute_query(
                    """
                    INSERT INTO user_avatars (user_id, avatar_name, avatar_image_url, heygen_avatar_id, avatar_id, created_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                    RETURNING id
                    """,
                    (
                        user_id,
                        avatar_name,
                        "https://via.placeholder.com/150?text=BackgroundFX",  # Placeholder image
                        f"backgroundfx-{avatar_name.lower()}",  # Unique heygen_avatar_id
                        unique_avatar_id  # Unique avatar_id
                    ),
                    fetch_one=True
                )
                
                if new_avatar_result:
                    avatar_id = new_avatar_result['id']
                    logger.info(f"✨ DIRECT API: Created new avatar '{avatar_name}' (ID: {avatar_id}) for user {user_id}")
                else:
                    # Fallback to default
                    avatar_id = 1
                    logger.warning(f"⚠️ DIRECT API: Failed to create avatar, using fallback ID 1")
            
            video_result = execute_query(
                """
                INSERT INTO videos (user_id, title, status, video_path, avatar_id, audio_path, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                RETURNING id
                """,
                (
                    video_data["user_id"],
                    video_data["title"],
                    video_data["status"],
                    video_data["video_url"],  # Store Cloudinary URL in video_path
                    avatar_id,  # Dynamic avatar based on video name
                    video_data["video_url"]  # Same URL - audio is embedded in the video
                ),
                fetch_one=True
            )
            
            if video_result and video_result.get('id'):
                video_id = video_result['id']
                logger.info(f"✅ DIRECT API: Video metadata saved successfully: Video ID {video_id} for user {user_id}")
                
                response_data = {
                    "success": True,
                    "video_id": video_id,
                    "message": "Video saved to My Videos successfully!",
                    "video_url": data['video_url'],
                    "user_id": user_id
                }
                
                return Response(
                    content=json.dumps(response_data),
                    status_code=201,
                    headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"}
                )
            else:
                raise Exception("Database insert returned no ID")
                
        except Exception as db_error:
            logger.error(f"❌ DIRECT API: Database error: {str(db_error)}")
            
            # Return graceful error but don't fail completely
            response_data = {
                "success": False,
                "error": f"Database error: {str(db_error)}",
                "message": "Failed to save to database, but video is available on cloud",
                "video_url": data['video_url']
            }
            
            return Response(
                content=json.dumps(response_data),
                status_code=500,
                headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"}
            )
        
    except Exception as e:
        logger.error(f"❌ DIRECT API: Unexpected error in save-video-metadata: {str(e)}")
        
        error_response = {
            "success": False,
            "error": str(e),
            "message": "Internal server error"
        }
        
        return Response(
            content=json.dumps(error_response),
            status_code=500,
            headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"}
        )

@app.get("/api/test-connection")
async def test_connection_direct(request: Request):
    """Test endpoint to verify API connectivity from HF Spaces - DIRECT IMPLEMENTATION"""
    try:
        logger.info("🔗 DIRECT API: Test connection called")
        
        response_data = {
            "status": "ok",
            "message": "MyAvatar API is running and accessible (DIRECT)",
            "timestamp": datetime.now().isoformat(),
            "endpoints": {
                "save_video_metadata": "/api/save-video-metadata",
                "test_connection": "/api/test-connection"
            },
            "cors_enabled": True,
            "authentication": {
                "methods": ["jwt_header", "user_id_fallback"],
                "required": False  # For testing
            },
            "implementation": "direct_in_main_py"
        }
        
        return Response(
            content=json.dumps(response_data),
            status_code=200,
            headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"}
        )
        
    except Exception as e:
        logger.error(f"❌ DIRECT API: Error in test connection: {e}")
        return Response(
            content=json.dumps({
                "status": "error",
                "error": str(e)
            }),
            status_code=500,
            headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"}
        )

# =============================================================================
# VIDEOS LIBRARY PAGE - All Videos Display
# =============================================================================

# TEST ROUTE - Simple version to isolate issue
@app.get("/videos-test")
async def videos_test():
    """Simple test route to verify routing works"""
    return {"message": "Videos test route works!", "timestamp": "2025-08-01"}

@app.get("/videos", response_class=HTMLResponse)
async def videos_page(request: Request):
    """
    Display all videos for the logged-in user in a dedicated library page.
    Step 1: Basic implementation - displays all videos in a grid.
    """
    try:
        # Get current user (reusing your existing auth logic)
        user = get_current_user_from_request(request)
        
        if not user:
            # Redirect to login if not authenticated
            return RedirectResponse(url="/login", status_code=302)
        
        user_id = int(user['id'])
        username = user.get('username', 'User')
        
        logger.info(f"📚 Loading videos library for user: {username} (ID: {user_id})")
        
        # Fetch all videos for this user (ordered by newest first)
        videos = execute_query(
            """
            SELECT v.*, ua.avatar_name 
            FROM videos v 
            LEFT JOIN user_avatars ua ON v.avatar_id::integer = ua.id 
            WHERE v.user_id = %s 
            ORDER BY v.created_at DESC
            """,
            (user_id,),
            fetch_all=True  # Get all rows
        )
        
        if not videos:
            videos = []
        
        logger.info(f"📊 Found {len(videos)} videos for user {username}")
        
        # Count total videos for stats
        total_videos = len(videos)
        
        # Render the videos page template
        logger.info(f"🎬 Attempting to render videos.html template with {len(videos)} videos")
        
        try:
            if not templates:
                logger.error("❌ Templates not initialized")
                return RedirectResponse(url="/dashboard", status_code=302)
                
            return templates.TemplateResponse("videos.html", {
                "request": request,
                "videos": videos,
                "username": username,
                "total_videos": total_videos,
                "user": user
            })
        except Exception as template_error:
            logger.error(f"❌ Template rendering failed: {template_error}")
            raise template_error
        
    except Exception as e:
        logger.error(f"❌ Error in videos page: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Graceful fallback - redirect to dashboard
        return RedirectResponse(url="/dashboard", status_code=302)

# =============================================================================
# LINKEDIN DISTRIBUTION ENGINE - MVP
# =============================================================================

@app.get("/text-to-video", response_class=HTMLResponse)
async def text_to_video_page(request: Request):
    """Text-to-Video creation page with HeyGen integration"""
    try:
        user = get_current_user_from_request(request)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        user_id = int(user['id'])
        username = user.get('username', 'User')
        
        # DEBUG: Log user info
        logger.info(f"🎭 TEXT-TO-VIDEO: User {username} (ID: {user_id}) accessing text-to-video")
        
        # DEBUG: First get ALL avatars for this user to see what we have
        all_avatars = execute_query(
            "SELECT id, avatar_name, avatar_image_url FROM user_avatars WHERE user_id = %s ORDER BY created_at DESC",
            (user_id,),
            fetch_all=True
        )
        logger.info(f"🎭 TEXT-TO-VIDEO: Found {len(all_avatars or [])} total avatars for user {user_id}")
        for avatar in (all_avatars or []):
            logger.info(f"   - {avatar['avatar_name']}: {avatar['avatar_image_url']}")
        
        # Get user's avatars for text-to-video - FILTERED TO EXCLUDE BACKGROUNDFX PLACEHOLDERS
        avatars = execute_query(
            "SELECT * FROM user_avatars WHERE user_id = %s AND avatar_image_url NOT LIKE '%placeholder%' ORDER BY is_default DESC, created_at DESC",
            (user_id,),
            fetch_all=True
        )
        
        logger.info(f"🎭 TEXT-TO-VIDEO: After filtering, {len(avatars or [])} avatars remain")
        
        if not avatars:
            avatars = []
        
        # NUCLEAR FIX: Force template creation if needed
        if not templates:
            logger.warning("⚠️ Templates not initialized, creating on-the-fly")
            try:
                from fastapi.templating import Jinja2Templates
                templates = Jinja2Templates(directory="templates")
                logger.info("✅ Templates created successfully")
            except Exception as template_error:
                logger.error(f"❌ Cannot create templates: {template_error}")
                return HTMLResponse(content=f"""
                <!DOCTYPE html>
                <html>
                <head><title>Text-to-Video</title></head>
                <body>
                    <h1>🎭 Text-to-Video</h1>
                    <p>Template system error. Please contact support.</p>
                    <p>Error: {template_error}</p>
                    <a href="/dashboard">Back to Dashboard</a>
                </body>
                </html>
                """)
            
        return templates.TemplateResponse("text_video_component.html", {
            "request": request,
            "user": user,
            "username": username,
            "avatars": avatars,
            "user_id": user_id
        })
        
    except Exception as e:
        logger.error(f"❌ Error in text-to-video page: {e}")
        return RedirectResponse(url="/dashboard", status_code=302)

@app.get("/voice-to-video", response_class=HTMLResponse)
async def voice_to_video_page(request: Request):
    """Voice-to-Video creation page with HeyGen integration"""
    try:
        user = get_current_user_from_request(request)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        user_id = int(user['id'])
        username = user.get('username', 'User')
        
        # Get user's avatars for voice-to-video - FILTERED TO EXCLUDE BACKGROUNDFX PLACEHOLDERS
        avatars = execute_query(
            "SELECT * FROM user_avatars WHERE user_id = %s AND avatar_image_url NOT LIKE '%placeholder%' ORDER BY is_default DESC, created_at DESC",
            (user_id,),
            fetch_all=True
        )
        
        if not avatars:
            avatars = []
        
        if not templates:
            logger.error("❌ Templates not initialized")
            return RedirectResponse(url="/dashboard", status_code=302)
            
        return templates.TemplateResponse("voice_recording.html", {
            "request": request,
            "user": user,
            "username": username,
            "avatars": avatars,
            "user_id": user_id
        })
        
    except Exception as e:
        logger.error(f"❌ Error in voice-to-video page: {e}")
        return RedirectResponse(url="/dashboard", status_code=302)

@app.get("/distribution", response_class=HTMLResponse)
async def linkedin_distribution_page(request: Request):
    """LinkedIn Distribution MVP - Select videos and post to LinkedIn"""
    try:
        user = get_current_user_from_request(request)
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        user_id = int(user['id'])
        username = user.get('username', 'User')
        
        # Get user's completed videos for distribution
        videos = execute_query(
            """
            SELECT v.*, ua.avatar_name 
            FROM videos v 
            LEFT JOIN user_avatars ua ON v.avatar_id::integer = ua.id 
            WHERE v.user_id = %s AND v.status = 'completed'
            ORDER BY v.created_at DESC
            """,
            (user_id,),
            fetch_all=True
        )
        
        if not videos:
            videos = []
        
        if not templates:
            logger.error("❌ Templates not initialized")
            return RedirectResponse(url="/dashboard", status_code=302)
            
        return templates.TemplateResponse("linkedin_distribution.html", {
            "request": request,
            "user": user,
            "username": username,
            "videos": videos,
            "total_videos": len(videos)
        })
        
    except Exception as e:
        logger.error(f"❌ Error in LinkedIn distribution: {e}")
        return RedirectResponse(url="/dashboard", status_code=302)

# =============================================================================
# VIDEO MANAGEMENT API ENDPOINTS - Add to main.py after /videos route
# =============================================================================

@app.delete("/api/videos/{video_id}")
async def delete_video_api(video_id: int, request: Request):
    """Delete a video from the user's library"""
    try:
        user = get_current_user_from_request(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Authentication required"}
            )
        
        user_id = int(user['id'])
        logger.info(f"🗑️ Delete video request: Video {video_id} by user {user_id}")
        
        # Verify video belongs to user
        video = execute_query(
            "SELECT * FROM videos WHERE id = %s AND user_id = %s",
            (video_id, user_id),
            fetch_one=True
        )
        
        if not video:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Video not found"}
            )
        
        # Delete video from database
        execute_query(
            "DELETE FROM videos WHERE id = %s AND user_id = %s",
            (video_id, user_id),
            fetch_one=False
        )
        
        logger.info(f"✅ Video {video_id} deleted successfully for user {user_id}")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Video deleted successfully",
                "video_id": video_id
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error deleting video {video_id}: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Failed to delete video"}
        )

@app.post("/api/videos/{video_id}/share")
async def share_video_api(video_id: int, request: Request):
    """Generate a shareable link for a video"""
    try:
        user = get_current_user_from_request(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Authentication required"}
            )
        
        user_id = int(user['id'])
        logger.info(f"📤 Share video request: Video {video_id} by user {user_id}")
        
        # Get video details
        video = execute_query(
            "SELECT * FROM videos WHERE id = %s AND user_id = %s AND status = 'completed'",
            (video_id, user_id),
            fetch_one=True
        )
        
        if not video:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Video not found or not completed"}
            )
        
        # Create share data
        share_data = {
            "video_url": video['video_path'],
            "title": video['title'],
            "share_url": f"{request.base_url}videos/{video_id}/share",
            "direct_url": video['video_path']  # Cloudinary URL for direct sharing
        }
        
        logger.info(f"✅ Share data generated for video {video_id}")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Share link generated",
                "share_data": share_data
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error sharing video {video_id}: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Failed to generate share link"}
        )

@app.post("/api/videos/{video_id}/retry")
async def retry_video_api(video_id: int, request: Request):
    """Retry processing a failed video"""
    try:
        user = get_current_user_from_request(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Authentication required"}
            )
        
        user_id = int(user['id'])
        logger.info(f"🔄 Retry video request: Video {video_id} by user {user_id}")
        
        # Get video details
        video = execute_query(
            "SELECT * FROM videos WHERE id = %s AND user_id = %s AND status = 'failed'",
            (video_id, user_id),
            fetch_one=True
        )
        
        if not video:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Video not found or not in failed state"}
            )
        
        # Update video status to pending for retry
        execute_query(
            "UPDATE videos SET status = 'pending', updated_at = NOW() WHERE id = %s",
            (video_id,),
            fetch_one=False
        )
        
        # TODO: Trigger actual video reprocessing here
        # This would depend on your video processing system
        
        logger.info(f"✅ Video {video_id} marked for retry")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Video queued for retry",
                "video_id": video_id,
                "new_status": "pending"
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error retrying video {video_id}: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Failed to retry video"}
        )

@app.post("/api/videos/{video_id}/cancel")
async def cancel_video_api(video_id: int, request: Request):
    """Cancel a processing video"""
    try:
        user = get_current_user_from_request(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Authentication required"}
            )
        
        user_id = int(user['id'])
        logger.info(f"❌ Cancel video request: Video {video_id} by user {user_id}")
        
        # Get video details
        video = execute_query(
            "SELECT * FROM videos WHERE id = %s AND user_id = %s AND status IN ('processing', 'pending')",
            (video_id, user_id),
            fetch_one=True
        )
        
        if not video:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Video not found or not in processable state"}
            )
        
        # Update video status to cancelled
        execute_query(
            "UPDATE videos SET status = 'cancelled', updated_at = NOW() WHERE id = %s",
            (video_id,),
            fetch_one=False
        )
        
        # TODO: Cancel actual video processing job here
        # This would depend on your video processing system
        
        logger.info(f"✅ Video {video_id} cancelled successfully")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Video processing cancelled",
                "video_id": video_id,
                "new_status": "cancelled"
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error cancelling video {video_id}: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Failed to cancel video"}
        )

@app.post("/api/videos/bulk-delete")
async def bulk_delete_videos_api(request: Request):
    """Delete multiple videos at once"""
    try:
        user = get_current_user_from_request(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Authentication required"}
            )
        
        user_id = int(user['id'])
        
        # Get video IDs from request body
        data = await request.json()
        video_ids = data.get('video_ids', [])
        
        if not video_ids or not isinstance(video_ids, list):
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "video_ids array is required"}
            )
        
        logger.info(f"🗑️ Bulk delete request: {len(video_ids)} videos by user {user_id}")
        
        # Verify all videos belong to user
        placeholders = ','.join(['%s'] * len(video_ids))
        videos = execute_query(
            f"SELECT id FROM videos WHERE id IN ({placeholders}) AND user_id = %s",
            (*video_ids, user_id),
            fetch_one=False
        )
        
        if not videos:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "No videos found"}
            )
        
        found_ids = [v['id'] for v in videos]
        
        # Delete videos
        execute_query(
            f"DELETE FROM videos WHERE id IN ({placeholders}) AND user_id = %s",
            (*found_ids, user_id),
            fetch_one=False
        )
        
        logger.info(f"✅ Bulk deleted {len(found_ids)} videos for user {user_id}")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Successfully deleted {len(found_ids)} videos",
                "deleted_count": len(found_ids),
                "deleted_ids": found_ids
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error in bulk delete: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Failed to delete videos"}
        )

@app.get("/api/videos/{video_id}/status")
async def get_video_status_api(video_id: int, request: Request):
    """Get current status of a video"""
    try:
        user = get_current_user_from_request(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Authentication required"}
            )
        
        user_id = int(user['id'])
        
        # Get video status
        video = execute_query(
            "SELECT id, status, video_path, title, created_at, updated_at FROM videos WHERE id = %s AND user_id = %s",
            (video_id, user_id),
            fetch_one=True
        )
        
        if not video:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Video not found"}
            )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "video": {
                    "id": video['id'],
                    "status": video['status'],
                    "video_path": video['video_path'],
                    "title": video['title'],
                    "created_at": video['created_at'].isoformat() if video['created_at'] else None,
                    "updated_at": video['updated_at'].isoformat() if video.get('updated_at') else None
                }
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error getting video status {video_id}: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Failed to get video status"}
        )

@app.get("/api/videos/stats")
async def get_video_stats_api(request: Request):
    """Get video statistics for the current user"""
    try:
        user = get_current_user_from_request(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Authentication required"}
            )
        
        user_id = int(user['id'])
        
        # Get video counts by status
        stats = execute_query(
            """
            SELECT 
                status,
                COUNT(*) as count
            FROM videos 
            WHERE user_id = %s 
            GROUP BY status
            """,
            (user_id,),
            fetch_one=False
        )
        
        # Format stats
        stats_dict = {stat['status']: stat['count'] for stat in stats or []}
        
        total_videos = sum(stats_dict.values())
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "stats": {
                    "total": total_videos,
                    "completed": stats_dict.get('completed', 0),
                    "processing": stats_dict.get('processing', 0),
                    "pending": stats_dict.get('pending', 0),
                    "failed": stats_dict.get('failed', 0),
                    "cancelled": stats_dict.get('cancelled', 0)
                }
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error getting video stats for user {user_id}: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Failed to get video statistics"}
        )

# =============================================================================
# STARTUP SERVICES
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup"""
    try:
        logger.info("🚀 Starting MyAvatar services...")
        
        # Start avatar refresh service
        from app.startup.avatar_refresh_startup import initialize_avatar_refresh_service
        await initialize_avatar_refresh_service()
        
        logger.info("✅ All startup services initialized")
        
    except Exception as e:
        logger.error(f"❌ Error during startup: {e}")

# =============================================================================
# HEALTH CHECK ENDPOINTS (RAILWAY REQUIREMENT)
# =============================================================================

@app.get("/simple-health")
@app.get("/health")
@app.get("/healthz")
async def health_check():
    """Health check endpoint for Railway deployment"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "MyAvatar",
        "version": "2.0.0"
    }

# =============================================================================
# ORIGINAL ROUTER LOADING SYSTEM (KEPT FOR OTHER FUNCTIONALITY)
# =============================================================================

# Import and mount routers with error handling
def load_router(module_path: str, router_name: str, prefix: str = "", description: str = ""):
    """Safely load and include routers"""
    try:
        module = __import__(module_path, fromlist=[router_name])
        router = getattr(module, router_name)
        
        if prefix:
            app.include_router(router, prefix=prefix)
            logger.info(f"✅ Router loaded: {description} -> {prefix}")
        else:
            app.include_router(router)
            logger.info(f"✅ Router loaded: {description}")
        
        return True
    except ImportError as e:
        logger.error(f"❌ Failed to import {module_path}: {e}")
        return False
    except AttributeError as e:
        logger.error(f"❌ Router {router_name} not found in {module_path}: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error loading router {description}: {e}")
        return False

# Track loaded routers
loaded_routers = []
router_errors = []

def try_load_router(module_path: str, router_name: str, prefix: str = "", description: str = ""):
    """Try to load a router and track success/failure"""
    try:
        if load_router(module_path, router_name, prefix, description):
            loaded_routers.append(description)
        else:
            router_errors.append(f"{description} ({module_path})")
    except Exception as e:
        logger.error(f"❌ Critical error loading router {description}: {e}")
        router_errors.append(f"{description} ({module_path}) - CRITICAL: {str(e)}")

# ============================================================================
# CORE ROUTERS - Load in order of importance
# ============================================================================

logger.info("🚀 Starting router loading process...")

# Authentication routes (highest priority)
try_load_router("app.routes.auth_routes", "router", "", "app.routes.auth_routes")

# Admin routes
try_load_router("app.routes.admin_routes", "router", "/admin", "app.routes.admin_routes -> /admin")

# API routes
try_load_router("app.routes.api_routes", "router", "/api", "app.routes.api_routes -> /api")

# Premium features
try_load_router("app.routes.premium_routes", "router", "", "app.routes.premium_routes")

# BackgroundFX routes
try_load_router("app.routes.backgroundfx_iframe", "router", "", "app.routes.backgroundfx_iframe (HF Space iframe Integration)")
try_load_router("app.routes.backgroundfx_files", "router", "", "app.routes.backgroundfx_files (User File Management)")
try_load_router("app.routes.backgroundfx_automation", "router", "", "app.routes.backgroundfx_automation (Auto-Save Integration)")
try_load_router("app.routes.backgroundfx_webhook", "router", "", "app.routes.backgroundfx_webhook (Auto-Save Webhook)")
try_load_router("app.routes.backgroundfx_save", "router", "", "app.routes.backgroundfx_save (Simple Save-to-Library)")
try_load_router("app.routes.distribution_routes", "router", "", "app.routes.distribution_routes (Distribution Engine SSO)")

# Video processing routes
try_load_router("app.routes.video_processing_routes", "router", "/video-processing", "app.routes.video_processing_routes -> /video-processing")

# Emergency routes
try_load_router("app.routes.emergency_routes", "router", "/emergency", "app.routes.emergency_routes -> /emergency")

# File tracker routes
try_load_router("app.routes.file_tracker_routes", "router", "/admin/file-tracker", "app.routes.file_tracker_routes -> /admin/file-tracker")

# Host Message Routes
try_load_router("app.routes.host_routes", "router", "", "app.routes.host_routes")

# Main web routes (should be loaded last to avoid conflicts)
try_load_router("app.routes.web_routes", "router", "", "app.routes.web_routes")

# Background routes (separate handling)
try_load_router("app.routes.background_routes", "router", "/background", "background_routes -> /background")

logger.info(f"🏁 Router loading complete. Loaded: {len(loaded_routers)}, Errors: {len(router_errors)}")

# ============================================================================
# ROUTE ANALYTICS AND SYSTEM STATUS
# ============================================================================

def get_all_routes():
    """Get all registered routes"""
    routes = []
    for route in app.routes:
        try:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                routes.append({
                    "path": route.path,
                    "methods": list(route.methods),
                    "name": getattr(route, 'name', 'unnamed')
                })
        except AttributeError:
            # Skip routes that don't have the expected attributes
            continue
    return routes

@app.get("/system-status")
async def system_status():
    """System status endpoint with router information"""
    total_routes = len(app.routes)
    all_routes = get_all_routes()
    
    # Check for direct API endpoints
    direct_api_routes = [r for r in all_routes if '/api/' in r['path'] and 'direct' in str(r)]
    
    return {
        "total_routes": total_routes,
        "routes_loaded_successfully": loaded_routers,
        "router_import_errors": router_errors,
        "all_routes": all_routes,
        "direct_api_status": {
            "save_video_metadata_available": any("/api/save-video-metadata" in r['path'] for r in all_routes),
            "test_connection_available": any("/api/test-connection" in r['path'] for r in all_routes),
            "implementation": "direct_in_main_py",
            "bypass_router_system": True
        },
        "hf_spaces_integration": {
            "api_endpoints_available": True,
            "cors_enabled": True,
            "authentication_flexible": True,
            "cloudinary_integration": True
        }
    }

@app.get("/debug-routes")
async def debug_routes():
    """Debug endpoint to see all loaded routes"""
    return {
        "total_routes": len(app.routes),
        "loaded_routers": loaded_routers,
        "router_errors": router_errors,
        "routes": get_all_routes(),
        "direct_api_implementation": True
    }

# ============================================================================
# STARTUP AND ERROR HANDLING
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    logger.info("🚀 MyAvatar starting up...")
    logger.info(f"✅ Total routes loaded: {len(app.routes)}")
    logger.info(f"✅ Successful routers: {len(loaded_routers)}")
    logger.info("🎯 DIRECT API ENDPOINTS: /api/save-video-metadata and /api/test-connection implemented directly")
    
    if router_errors:
        logger.warning(f"⚠️ Router errors: {len(router_errors)}")
        for error in router_errors:
            logger.warning(f"   - {error}")
    
    # Check critical environment variables
    critical_vars = ["DATABASE_URL", "JWT_SECRET"]
    missing_vars = [var for var in critical_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"❌ Missing critical environment variables: {missing_vars}")
    else:
        logger.info("✅ All critical environment variables present")
    
    logger.info("🎭 MyAvatar startup complete with DIRECT API integration!")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Global exception on {request.url}: {exc}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred",
            "path": str(request.url),
            "timestamp": datetime.now().isoformat()
        }
    )

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    """Custom 404 handler"""
    # Build safe route list that handles Mount objects
    available_endpoints = []
    for route in app.routes:
        try:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                available_endpoints.append(f"{route.path} ({list(route.methods)})")
            elif hasattr(route, 'path'):
                available_endpoints.append(f"{route.path} (static)")
        except AttributeError:
            # Skip routes that don't have the expected attributes
            continue
    
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not found",
            "message": f"The requested path {request.url.path} was not found",
            "available_endpoints": available_endpoints,
            "direct_api_available": True
        }
    )

# ============================================================================
# ROOT ENDPOINT
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint - redirects to main application"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>MyAvatar - AI Video Platform</title>
        <meta http-equiv="refresh" content="0; url=/dashboard">
        <style>
            body { font-family: system-ui; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #f5f5f5; }
            .container { text-align: center; background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
            .logo { font-size: 3rem; margin-bottom: 1rem; }
            .title { font-size: 2rem; color: #333; margin-bottom: 0.5rem; }
            .subtitle { color: #666; margin-bottom: 2rem; }
            .loading { color: #6366f1; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">🎭</div>
            <h1 class="title">MyAvatar</h1>
            <p class="subtitle">AI Video Generation Platform</p>
            <p class="loading">Redirecting to dashboard...</p>
            <script>
                setTimeout(() => window.location.href = '/dashboard', 100);
            </script>
        </div>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"🚀 Starting MyAvatar on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False,  # Disable in production
        log_level="info"
    )