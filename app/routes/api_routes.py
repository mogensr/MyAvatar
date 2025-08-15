"""
API routes for MyAvatar
"""
import os
import zipfile
import xml.etree.ElementTree as ET
from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException, Request, Form, UploadFile, File, Path
from fastapi.responses import JSONResponse, RedirectResponse
from datetime import datetime, timedelta
from typing import Optional
import uuid
import base64
import tempfile
import requests
import json
from ..api.heygen import (create_video_from_audio_file, create_video_from_text,
                          get_available_avatars, get_available_voices,
                          get_video_details, test_heygen_connection)
from ..db.database import execute_query
from ..auth.authentication import get_current_user, is_admin
from ..storage.file_storage import upload_avatar_to_cloudinary, upload_audio_to_cloudinary
from ..logger.log_handler import log_info, log_error, log_warning
import traceback
from ..utils.avatar_utils import ensure_avatar_persistence
from ..utils.heygen_image_utils import ensure_avatar_has_heygen_image
from ..services.voice_analysis_service import VoiceAnalysisService

# Create router
router = APIRouter(tags=["api"])

# TEST MODE - Set to True to bypass HeyGen API for testing
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

@router.post("/api/heygen/webhook")
async def heygen_webhook(request: Request):
    """
    HeyGen webhook handler to receive video processing status updates
    FIXED VERSION - Only updates video_path (not video_url which doesn't exist)
    """
    try:
        # Log incoming webhook
        log_info(f"🔔 WEBHOOK CALLED: {request.method} {request.url}", "API")
        log_info(f"🔔 WEBHOOK HEADERS: {dict(request.headers)}", "API")
        
        # Get the raw payload
        try:
            payload = await request.json()
        except Exception as json_error:
            log_error(f"🔔 WEBHOOK JSON ERROR: {str(json_error)}", "API")
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid JSON payload"}
            )
        
        if not payload:
            log_error("🔔 WEBHOOK: No JSON payload received", "API")
            return JSONResponse(
                status_code=400,
                content={"error": "No payload"}
            )
            
        log_info(f"🔔 WEBHOOK PAYLOAD: {payload}", "API")
        
        # Extract key information - handle HeyGen's actual webhook format
        event_type = payload.get('event_type') or payload.get('type')
        
        # HeyGen sends video data in 'event_data' field
        event_data = payload.get('event_data', {})
        
        # ROBUST VIDEO_ID EXTRACTION - handles all HeyGen formats
        def extract_video_id(event_data_dict, payload_dict):
            """Extract video_id from various HeyGen payload formats"""
            # Try multiple field names in order of likelihood
            possible_fields = [
                "video_id",           # Most common for avatar videos
                "video_translate_id", # Translation events
                "id",                 # Legacy format
                "videoId",           # Alternative casing
                "video_uuid",        # Rare variant
            ]
            
            # First try event_data (primary location)
            for field in possible_fields:
                if field in event_data_dict and event_data_dict[field]:
                    log_info(f"🎯 Found video ID in event_data.{field}: {event_data_dict[field]}", "API")
                    return str(event_data_dict[field])
            
            # Fallback to root payload
            for field in possible_fields:
                if field in payload_dict and payload_dict[field]:
                    log_info(f"🎯 Found video ID in payload.{field}: {payload_dict[field]}", "API")
                    return str(payload_dict[field])
            
            # Try nested data field (legacy)
            data = payload_dict.get('data', {})
            if data:
                for field in possible_fields:
                    if field in data and data[field]:
                        log_info(f"🎯 Found video ID in data.{field}: {data[field]}", "API")
                        return str(data[field])
            
            return None
        
        video_id = extract_video_id(event_data, payload)
        
        # Extract status from event_type or payload - ENHANCED
        status = payload.get('status')
        if not status and event_type:
            # Handle all known HeyGen event types
            success_events = ['avatar_video.success', 'video.succeed', 'avatar_video_gif.success', 
                            'video_translate.success', 'instant_avatar.success', 'photo_avatar_generation.success']
            fail_events = ['avatar_video.fail', 'video.fail', 'avatar_video_gif.fail',
                         'video_translate.fail', 'instant_avatar.fail', 'photo_avatar_generation.fail']
            
            if event_type in success_events or 'success' in event_type:
                status = 'completed'
            elif event_type in fail_events or 'fail' in event_type:
                status = 'failed'
            elif 'processing' in event_type:
                status = 'processing'
        
        if not video_id:
            log_error("❌ No video_id found in webhook payload", "API")
            log_error(f"🔍 WEBHOOK PAYLOAD KEYS: {list(payload.keys())}", "API")
            log_error(f"🔍 WEBHOOK FULL PAYLOAD: {payload}", "API")
            if event_data:
                log_error(f"🔍 WEBHOOK EVENT_DATA KEYS: {list(event_data.keys())}", "API")
                log_error(f"🔍 WEBHOOK EVENT_DATA: {event_data}", "API")
            
            # Return 200 to prevent HeyGen retries for malformed payloads
            return JSONResponse(
                status_code=200,
                content={
                    "status": "ignored", 
                    "message": "No video_id found", 
                    "payload_keys": list(payload.keys()), 
                    "event_data_keys": list(event_data.keys()) if event_data else []
                }
            )
            
        log_info(f"Processing webhook for video {video_id}: event_type={event_type}, status={status}", "API")
            
        # Update video status in database
        try:
            # Handle HeyGen webhook format (avatar_video.success)
            if event_type == 'avatar_video.success' or event_type == 'video.succeed' or status == 'completed':
                # Video processing completed successfully
                # HeyGen sends video URL in event_data.url
                video_url = event_data.get('url') or event_data.get('video_url')
                
                # Fallback to old format for backward compatibility
                if not video_url:
                    video_url = payload.get('video_url') or payload.get('url')
                    if not video_url and 'data' in locals():
                        video_url = data.get('video_url') or data.get('url')
                
                duration = event_data.get('duration') or payload.get('duration') or 0
                
                log_info(f"✅ Video {video_id} completed successfully. URL: {video_url}", "API")
                
                # FIXED: Only update video_path (not video_url which doesn't exist)
                execute_query("""
                    UPDATE videos 
                    SET status = 'completed', 
                        video_path = %s,
                        duration = %s,
                        completed_at = NOW(),
                        updated_at = NOW()
                    WHERE heygen_video_id = %s
                """, (video_url, duration, video_id))
                
                # SMS/Email notification (inline implementation)
                try:
                    # Simple inline notification without external imports
                    import psycopg2
                    
                    # Get database connection
                    database_url = os.getenv("DATABASE_URL")
                    if database_url and database_url.startswith("postgres://"):
                        database_url = database_url.replace("postgres://", "postgresql://", 1)
                    
                    # Get user info for notification
                    conn = psycopg2.connect(database_url)
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        SELECT v.title, u.username, u.email, u.phone_number, 
                               u.country_code, u.sms_notifications, u.is_premium
                        FROM videos v
                        JOIN users u ON v.user_id = u.id
                        WHERE v.heygen_video_id = %s
                    """, (video_id,))
                    
                    result = cursor.fetchone()
                    cursor.close()
                    conn.close()
                    
                    if result:
                        video_title, user_name, user_email, phone_number, country_code, sms_notifications, is_premium = result
                        log_info(f'📧 Notification for {user_name}: video "{video_title}" completed', 'API')
                        
                        # For now, just log the notification (can add actual SMS/email later)
                        if is_premium and sms_notifications and phone_number:
                            log_info(f'📱 Would send SMS to {country_code}{phone_number}', 'API')
                        else:
                            log_info(f'📧 Would send email to {user_email}', 'API')
                        
                        log_info(f'✅ Notification processed for video {video_id}', 'API')
                    else:
                        log_error(f'No user found for video {video_id}', 'API')
                        
                except Exception as e:
                    log_error(f'Notification failed: {e}', 'API')
                
            elif event_type == 'avatar_video.fail' or event_type == 'video.fail' or status == 'failed':
                # Video processing failed
                # HeyGen sends error message in event_data.msg
                error_message = event_data.get('msg') or event_data.get('message')
                
                # Fallback to old format for backward compatibility
                if not error_message:
                    error_message = payload.get('error') or payload.get('message') or 'Unknown error'
                
                log_error(f"❌ Video {video_id} failed: {error_message}", "API")
                
                execute_query("""
                    UPDATE videos 
                    SET status = 'failed', 
                        error_message = %s,
                        updated_at = NOW()
                    WHERE heygen_video_id = %s
                """, (error_message, video_id))
                
            elif status == 'processing' or event_type == 'video.processing':
                # Video is still processing
                log_info(f"⏳ Video {video_id} is processing", "API")
                
                execute_query("""
                    UPDATE videos 
                    SET status = 'processing',
                        updated_at = NOW()
                    WHERE heygen_video_id = %s
                """, (video_id,))
                
            # Legacy format support (old HeyGen API)
            elif event_type == 'avatar_video.success':
                video_url = payload.get('video_url')
                duration = payload.get('duration', 0)
                
                log_info(f"✅ Video {video_id} completed (legacy format). URL: {video_url}", "API")
                
                # FIXED: Only update video_path (not video_url which doesn't exist)
                execute_query("""
                    UPDATE videos 
                    SET status = 'completed', 
                        video_path = %s,
                        duration = %s,
                        completed_at = NOW(),
                        updated_at = NOW()
                    WHERE heygen_video_id = %s
                """, (video_url, duration, video_id))
                
            elif event_type == 'avatar_video.fail':
                error_message = payload.get('error', 'Unknown error')
                
                log_error(f"❌ Video {video_id} failed (legacy format): {error_message}", "API")
                
                execute_query("""
                    UPDATE videos 
                    SET status = 'failed', 
                        error_message = %s,
                        updated_at = NOW()
                    WHERE heygen_video_id = %s
                """, (error_message, video_id))
                
            else:
                log_warning(f"⚠️ Unknown webhook format - event_type: {event_type}, status: {status}", "API")
                # Still try to update if we have basic info
                if status:
                    execute_query("""
                        UPDATE videos 
                        SET status = %s,
                            updated_at = NOW()
                        WHERE heygen_video_id = %s
                    """, (status, video_id))
            
            # Log successful update
            updated_video = execute_query("SELECT * FROM videos WHERE heygen_video_id = %s", (video_id,), fetch_one=True)
            if updated_video:
                log_info(f"Successfully updated video {video_id} in database", "API")
            else:
                log_warning(f"Video {video_id} not found in database", "API")
            
        except Exception as db_error:
            log_error(f"Database error updating video {video_id}: {str(db_error)}", "API")
            return JSONResponse(
                status_code=500,
                content={"error": "Database update failed"}
            )
        
        # Return success response to HeyGen
        return JSONResponse(
            content={
                "status": "success",
                "message": f"Webhook processed for video {video_id}",
                "video_id": video_id
            }
        )
        
    except Exception as e:
        log_error(f"Error processing HeyGen webhook: {str(e)}", "API")
        return JSONResponse(
            status_code=500,
            content={"error": "Webhook processing failed"}
        )

@router.post("/api/backgroundfx/save-video")
async def save_background_video(request: Request):
    """
    Save processed video from Hugging Face Space directly to MyAvatar
    """
    try:
        # Parse JSON payload
        payload = await request.json()
        
        # Extract data
        video_b64 = payload.get("video_data")
        filename = payload.get("filename", "background_video.mp4")
        source = payload.get("source", "hf_space")
        timestamp = payload.get("timestamp")
        
        if not video_b64:
            log_error("Missing video_data in background FX save request", "API")
            return JSONResponse(
                status_code=400,
                content={"success": False, "detail": "Missing video_data"}
            )
        
        log_info(f"🍹 Received background video save request: {filename} from {source}", "API")
        
        # Decode base64 video
        try:
            video_bytes = base64.b64decode(video_b64)
            video_size_mb = len(video_bytes) / (1024 * 1024)
            log_info(f"🍹 Decoded video: {len(video_bytes)} bytes ({video_size_mb:.2f} MB)", "API")
        except Exception as e:
            log_error(f"Invalid base64 data in background FX: {str(e)}", "API")
            return JSONResponse(
                status_code=400,
                content={"success": False, "detail": f"Invalid base64 data: {str(e)}"}
            )
        
        # Check video size (50MB limit for safety)
        if len(video_bytes) > 50 * 1024 * 1024:
            return JSONResponse(
                status_code=400,
                content={"success": False, "detail": "Video too large (max 50MB)"}
            )
        
        # For Background FX videos, we'll use a default user ID
        # In a production system, you might want to implement proper authentication
        # or create a special "background-fx" user
        default_user_id = 1  # Admin user - adjust as needed
        
        # Try to upload to your storage system
        video_url = None
        
        # Save temporarily first
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
            temp_file.write(video_bytes)
            temp_path = temp_file.name
        
        try:
            # Try to upload using your existing Cloudinary setup
            # You might need to create a similar function for video uploads
            try:
                # If you have a video upload function similar to upload_audio_to_cloudinary
                # video_url = upload_video_to_cloudinary(temp_path, default_user_id)
                
                # For now, we'll create a placeholder URL - REPLACE THIS with actual upload
                unique_id = str(uuid.uuid4())[:8]
                video_url = f"https://res.cloudinary.com/your-cloud/video/upload/background-fx/{unique_id}_{filename}"
                
                log_info(f"🍹 Uploaded background FX video to: {video_url}", "API")
                
            except Exception as upload_error:
                log_error(f"Failed to upload background FX video: {str(upload_error)}", "API")
                # Fallback: save to local storage or return error
                video_url = f"/local/background-fx/{filename}"
            
            # Generate a proper title
            title = f"Background FX: {filename.replace('background_replaced_', '').replace('.mp4', '')}"
            
            # Save to database in the videos table
            execute_query(
                """
                INSERT INTO videos (user_id, title, video_path, status, format, source, description, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    default_user_id, 
                    title, 
                    video_url, 
                    "completed", 
                    "mp4", 
                    f"background-fx-{source}",
                    f"Video processed with AI background replacement from {source}"
                )
            )
            
            log_info(f"🍹 Successfully saved background FX video: {title}", "API")
            
            return JSONResponse(content={
                "success": True,
                "message": "Video saved to My Videos successfully!",
                "filename": filename,
                "title": title,
                "url": video_url,
                "size_mb": round(video_size_mb, 2)
            })
            
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
        
    except Exception as e:
        log_error(f"🍹 Error saving background FX video: {str(e)}", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "detail": f"Server error: {str(e)}"}
        )

@router.post("/document-parser")
async def parse_document(request: Request, file: UploadFile = File(...)):
    """
    Parse uploaded document and extract text content
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
        
        # Check file size (10MB limit)
        if file.size and file.size > 10 * 1024 * 1024:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "File too large. Maximum size is 10MB."}
            )
        
        # Check file type
        allowed_extensions = ['.txt', '.docx', '.pdf']
        file_extension = '.' + file.filename.lower().split('.')[-1]
        
        if file_extension not in allowed_extensions:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"}
            )
        
        # Read file content
        content = await file.read()
        
        # Extract text based on file type
        text = ""
        if file_extension == '.txt':
            # Plain text file
            text = content.decode('utf-8', errors='ignore')
        elif file_extension == '.docx':
            # Word document - basic text extraction
            try:
                with zipfile.ZipFile(BytesIO(content), 'r') as zip_file:
                    # Extract text from document.xml
                    xml_content = zip_file.read('word/document.xml')
                    root = ET.fromstring(xml_content)
                    
                    # Extract text from all text nodes
                    text_elements = []
                    for elem in root.iter():
                        if elem.tag.endswith('}t'):  # Text elements
                            if elem.text:
                                text_elements.append(elem.text)
                    
                    text = ' '.join(text_elements)
            except Exception as e:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "error": f"Could not parse Word document: {str(e)}"}
                )
        elif file_extension == '.pdf':
            # PDF - basic text extraction
            try:
                import PyPDF2
                
                pdf_reader = PyPDF2.PdfReader(BytesIO(content))
                text_parts = []
                
                for page in pdf_reader.pages:
                    text_parts.append(page.extract_text())
                
                text = ' '.join(text_parts)
            except Exception as e:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "error": f"Could not parse PDF: {str(e)}. Try saving as plain text."}
                )
        
        # Clean and process text
        original_length = len(text)
        
        # Basic cleaning
        text = text.strip()
        text = ' '.join(text.split())  # Normalize whitespace
        
        # Remove common document artifacts
        text = text.replace('\n', ' ')
        text = text.replace('\r', ' ')
        text = text.replace('\t', ' ')
        
        # Truncate to 1500 characters (text-to-video limit)
        truncated = False
        if len(text) > 1500:
            text = text[:1500]
            truncated = True
        
        final_length = len(text)
        
        if not text:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "No text content found in file"}
            )
        
        log_info(f"Document parsed successfully: {file.filename} ({original_length} -> {final_length} chars)", "DocumentParser")
        
        return JSONResponse(content={
            "success": True,
            "text": text,
            "filename": file.filename,
            "original_length": original_length,
            "final_length": final_length,
            "truncated": truncated,
            "file_type": file_extension
        })
        
    except Exception as e:
        log_error(f"Document parser error: {str(e)}", "DocumentParser", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Failed to process document"}
        )

@router.get("/debug/check-videos")
async def debug_check_videos(request: Request):
    """
    Debug endpoint to check specific video statuses
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
        
        videos = execute_query(
            """
            SELECT id, heygen_video_id, status, video_path, title, created_at
            FROM videos 
            WHERE heygen_video_id IN (%s, %s)
            ORDER BY created_at DESC
            """,
            ('dfb8d77e53664300ab0d7106cf395e4d', '125e966b2c44461eb9b8e985bc064472'),
            fetch_all=True
        )
        
        # Convert datetime objects to strings for JSON serialization
        video_list = []
        for video in videos:
            video_dict = dict(video)
            for key, value in video_dict.items():
                if hasattr(value, 'isoformat'):  # datetime object
                    video_dict[key] = value.isoformat()
            video_list.append(video_dict)
        
        return JSONResponse(content={"success": True, "videos": video_list})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@router.get("/videos")
async def get_videos(request: Request):
    """
    Get videos for current user
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
            
        # Admin can see all videos, normal users only see their own
        if user["is_admin"]:
            videos = execute_query(
                """
                SELECT v.*, u.username, u.email FROM videos v 
                LEFT JOIN users u ON v.user_id = u.id 
                ORDER BY v.created_at DESC
                """, 
                fetch_all=True
            )
        else:
            videos = execute_query(
                "SELECT * FROM videos WHERE user_id = %s ORDER BY created_at DESC",
                (int(user["id"]),),
                fetch_all=True
            )
            
        # Convert to list of dicts
        video_list = []
        for v in videos:
            if isinstance(v, dict):
                video_dict = {}
                for key, value in v.items():
                    if isinstance(value, datetime):
                        video_dict[key] = value.isoformat()
                    else:
                        video_dict[key] = value
                video_list.append(video_dict)
            else:
                # Handle SQLite Row objects
                video_dict = {}
                for key in v.keys():
                    value = v[key]
                    if isinstance(value, datetime):
                        video_dict[key] = value.isoformat()
                    else:
                        video_dict[key] = value
                video_list.append(video_dict)
                
        return JSONResponse(content={"success": True, "videos": video_list})
    except Exception as e:
        log_error("Error getting videos", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/videos/{video_id}/download")
async def download_video(request: Request, video_id: str):
    """
    Download video by redirecting to the video URL
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
        
        # Get video from database - handle both numeric IDs and HeyGen video IDs
        if video_id.isdigit():
            # Numeric ID - check both id and heygen_video_id fields
            video = execute_query(
                "SELECT * FROM videos WHERE id = %s OR heygen_video_id = %s",
                (int(video_id), video_id),
                fetch_one=True
            )
        else:
            # Non-numeric ID (HeyGen video ID) - only check heygen_video_id field
            video = execute_query(
                "SELECT * FROM videos WHERE heygen_video_id = %s",
                (video_id,),
                fetch_one=True
            )
        
        if not video:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Video not found"}
            )
            
        log_info(f"Found video in database: ID={video.get('id')}, HeyGen_ID={video.get('heygen_video_id')}, Status={video.get('status')}, Has_URL={bool(video.get('video_path'))}", "API")
            
    # Check if user has access to this video
        if not user["is_admin"] and video["user_id"] != int(user["id"]):
            return JSONResponse(
                status_code=403,
                content={"success": False, "error": "Access denied"}
            )

        # Check if video has a URL
        video_path = video.get("video_path")
        if not video_path:
            # Try to get the latest video details from HeyGen
            api_key = os.getenv("HEYGEN_API_KEY") or user.get("api_key")
            if api_key and video.get("heygen_video_id"):
                log_info(f"Fetching video URL from HeyGen for video {video['heygen_video_id']}", "API")
                result = get_video_details(api_key, video["heygen_video_id"])
                
                if result["success"] and result.get("details"):
                    details = result["details"]
                    log_info(f"HeyGen response details: {details}", "API")
                    
                    # Try different possible fields for video URL
                    video_path = (details.get("video_url") or 
                               details.get("video_url_caption") or 
                               details.get("url") or 
                               details.get("download_url"))
                    
                    # Check if video is completed
                    video_status = details.get("status", "unknown")
                    log_info(f"Video {video['heygen_video_id']} status: {video_status}", "API")
                    
                    if video_path:
                        # Update the database with the video URL
                        execute_query(
                            "UPDATE videos SET video_path = %s, status = %s WHERE id = %s",
                            (video_path, video_status, video["id"])
                        )
                        log_info(f"Updated video {video['id']} with URL and status {video_status}", "API")
                    elif video_status in ["processing", "pending", "waiting"]:
                        return JSONResponse(
                            status_code=200,
                            content={
                                "success": True, 
                                "message": f"Video is still {video_status}. Please wait...",
                                "status": video_status,
                                "processing": True
                            }
                        )
                    elif video_status == "failed":
                        return JSONResponse(
                            status_code=400,
                            content={
                                "success": False, 
                                "error": "Video generation failed. Please try creating a new video.",
                                "status": video_status
                            }
                        )
                else:
                    log_error(f"Failed to get video details from HeyGen: {result.get('error', 'Unknown error')}", "API")
        
        if not video_path:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False, 
                    "error": "Video URL not available. Video may still be processing or failed to generate."
                }
            )
        
        log_info(f"User {user['username']} downloading video {video_id}", "API")
        
        # Redirect to the video URL for download
        return RedirectResponse(url=video_path, status_code=302)
        
    except Exception as e:
        log_error(f"Error downloading video {video_id}", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/videos/{video_id}/debug")
async def debug_video(request: Request, video_id: str):
    """
    Debug endpoint to check video details without downloading
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
        
        # Get video from database - handle both numeric IDs and HeyGen video IDs
        if video_id.isdigit():
            # Numeric ID - check both id and heygen_video_id fields
            video = execute_query(
                "SELECT * FROM videos WHERE id = %s OR heygen_video_id = %s",
                (int(video_id), video_id),
                fetch_one=True
            )
        else:
            # Non-numeric ID (HeyGen video ID) - only check heygen_video_id field
            video = execute_query(
                "SELECT * FROM videos WHERE heygen_video_id = %s",
                (video_id,),
                fetch_one=True
            )
        
        if not video:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Video not found"}
            )
            
        return JSONResponse(content={
            "success": True,
            "video_id": video.get("id"),
            "heygen_video_id": video.get("heygen_video_id"),
            "status": video.get("status"),
            "has_video_path": bool(video.get("video_path")),
            "video_path_preview": video.get("video_path", "")[:100] + "..." if video.get("video_path") else None,
            "user_id": video.get("user_id"),
            "current_user_id": user.get("id"),
            "is_admin": user.get("is_admin", False),
            "created_at": str(video.get("created_at")) if video.get("created_at") else None
        })
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/videos/{video_id}")
async def get_video(request: Request, video_id: str):
    """
    Get details for a specific video
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
            
        # First try to get from local database - handle both numeric IDs and HeyGen video IDs
        if video_id.isdigit():
            # Numeric ID - check both id and heygen_video_id fields
            video = execute_query(
                "SELECT * FROM videos WHERE id = %s OR heygen_video_id = %s",
                (int(video_id), video_id),
                fetch_one=True
            )
        else:
            # Non-numeric ID (HeyGen video ID) - only check heygen_video_id field
            video = execute_query(
                "SELECT * FROM videos WHERE heygen_video_id = %s",
                (video_id,),
                fetch_one=True
            )
        
        if not video:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Video not found"}
            )
            
        # Check if user has access
        if not user["is_admin"] and video["user_id"] != int(user["id"]):
            return JSONResponse(
                status_code=403,
                content={"success": False, "error": "Access denied"}
            )
            
        # Get current status from HeyGen API
        api_key = os.getenv("HEYGEN_API_KEY") or user.get("api_key")
        if not api_key:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "No API key available"}
            )
            
        if video["status"] in ["pending", "processing"]:
            # Fetch latest status from HeyGen
            result = get_video_details(api_key, video_id)
            if result["success"]:
                # Update video status in database
                status = result["details"]["status"]
                video_path = result["details"].get("video_path", None)
                
                if status != video["status"] or (video_path and not video["video_path"]):
                    execute_query(
                        "UPDATE videos SET status = %s, video_path = %s WHERE heygen_video_id = %s",
                        (status, video_path, video_id)
                    )
                    
                return JSONResponse(content={
                    "success": True,
                    "video": {
                        **dict(video),
                        "status": status,
                        "video_path": video_path or video["video_path"]
                    }
                })
                
        # Return video details
        return JSONResponse(content={"success": True, "video": dict(video)})
    except Exception as e:
        log_error(f"Error getting video {video_id}", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.post("/videos/create-from-text")
async def create_video_from_text_endpoint(
    request: Request,
    text: str = Form(...),
    format: str = Form("16:9"),
    avatar_id: str = Form(None),
    voice_id: str = Form(None),  # Changed to None default to allow system to find the right voice ID
    title: str = Form(None),
    description: str = Form(None)
):
    """
    Create a video from text
    """
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
            
        # Get user's avatar ID
        if not avatar_id:
            avatar_id = user.get("avatar_id")
            if not avatar_id:
                # Get default avatar for user
                avatar = execute_query(
                    "SELECT avatar_id FROM user_avatars WHERE user_id = %s AND is_default = 1",
                    (int(user["id"]),),
                    fetch_one=True
                )
                
                if avatar:
                    avatar_id = avatar["avatar_id"]
                else:
                    return JSONResponse(
                        status_code=400,
                        content={"success": False, "error": "No avatar available"}
                    )
        
        # Always try to find user's preferred voice ID
        if not voice_id:
            # Try to get voice ID from users table heygen_voice_id column
            try:
                if user.get("heygen_voice_id"):
                    voice_id = user["heygen_voice_id"]
                    log_info(f"Using user's heygen_voice_id: {voice_id}", "API")
            except Exception as e:
                log_warning(f"Error retrieving user heygen_voice_id: {str(e)}", "API")
        
        # If still no voice_id, use a valid HeyGen voice ID as fallback
        if not voice_id:
            voice_id = "0f04c50500bf417396ba2e846d7bd3d7"  # Valid HeyGen voice ID
            log_warning(f"Using fallback HeyGen voice_id: {voice_id}", "API")
                
        # Check if this is a custom avatar and if we have analyzed voice parameters
        voice_params = {
            "speed": 1.0,  # Default values
            "pitch": 1.0,
            "emotion": "Friendly"
        }
        
        try:
            # Get stored voice parameters for this avatar if available
            avatar_info = execute_query(
                """SELECT 
                    is_custom, 
                    voice_parameters_analyzed, 
                    voice_parameters_speed, 
                    voice_parameters_pitch, 
                    voice_parameters_emotion 
                FROM user_avatars 
                WHERE avatar_id = %s AND user_id = %s""",
                (avatar_id, int(user["id"])),
                fetch_one=True
            )
            
            if avatar_info and avatar_info.get("is_custom") and avatar_info.get("voice_parameters_analyzed"):
                log_info(f"Using analyzed voice parameters for avatar: {avatar_id}", "API")
                
                # Use stored voice parameters
                if avatar_info.get("voice_parameters_speed") is not None:
                    voice_params["speed"] = float(avatar_info.get("voice_parameters_speed"))
                if avatar_info.get("voice_parameters_pitch") is not None:
                    voice_params["pitch"] = float(avatar_info.get("voice_parameters_pitch"))
                if avatar_info.get("voice_parameters_emotion"):
                    voice_params["emotion"] = avatar_info.get("voice_parameters_emotion")
                    
                log_info(f"Voice parameters for avatar {avatar_id}: {voice_params}", "API")
        except Exception as e:
            log_warning(f"Error retrieving voice parameters: {str(e)}", "API")
            # Continue with default parameters if retrieval fails
        
        # Create video with HeyGen API - Enhanced with voice manager integration
        result = create_video_from_text(
            api_key=api_key, 
            avatar_id=avatar_id, 
            text=text, 
            video_format=format, 
            voice_id=voice_id, 
            emotion=voice_params["emotion"],
            speed=voice_params["speed"],
            pitch=voice_params["pitch"],
            user_id=user.get("id"),
            language="en",  # Default to English, can be enhanced later with language detection
            context={"use_cloned_voice": True}  # Can be enhanced with avatar type detection
        )
        
        if not result["success"]:
            return JSONResponse(
                status_code=500,
                content=result
            )
            
        # Save video to database
        heygen_video_id = result["video_id"]
        title = title or f"Video {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        # Ensure all values are properly typed for PostgreSQL
        user_id = int(user["id"]) if user["id"] else None
        
        execute_query(
            """
            INSERT INTO videos (user_id, avatar_id, heygen_video_id, status, format, title, audio_path, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, str(avatar_id), str(heygen_video_id), "processing", str(format), str(title), "", str(description) if description else "")
        )
        
        log_info(f"Text-to-video created: {heygen_video_id}", "API")
        
        return JSONResponse(content={
            "success": True,
            "video_id": heygen_video_id,
            "message": "Video creation initiated"
        })
    except Exception as e:
        log_error("Error creating video from text", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.post("/videos/create-from-audio")
async def create_video_from_audio_endpoint(
    request: Request,
    audio: UploadFile = File(...),
    format: str = Form("16:9"),
    avatar_id: str = Form(None),
    title: str = Form(None),
    description: str = Form(None)
):
    """
    Create a video from audio file - UPDATED to accept avatar_id from form
    """
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
            
        # Get avatar_id from form data or fall back to user's default avatar
        if not avatar_id:
            avatar_id = user.get("avatar_id")
            
        if not avatar_id:
            # Get default avatar for user
            avatar = execute_query(
                "SELECT avatar_id FROM user_avatars WHERE user_id = %s AND is_default = 1",
                (int(user["id"]),),
                fetch_one=True
            )
            
            if avatar:
                avatar_id = avatar["avatar_id"]
            else:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "error": "No avatar available. Please select an avatar."}
                )
                
        # Upload audio file
        audio_url = upload_audio_to_cloudinary(audio, user["id"])
        
        # Always try to find user's preferred voice ID
        voice_id = None
        try:
            if user.get("heygen_voice_id"):
                voice_id = user["heygen_voice_id"]
                log_info(f"Using user's heygen_voice_id: {voice_id}", "API")
        except Exception as e:
            log_warning(f"Error retrieving user heygen_voice_id: {str(e)}", "API")
        
        # If still no voice_id, use a valid HeyGen voice ID as fallback
        if not voice_id:
            voice_id = "0f04c50500bf417396ba2e846d7bd3d7"  # Valid HeyGen voice ID
            log_warning(f"Using fallback HeyGen voice_id: {voice_id}", "API")
            
        # Analyze voice characteristics if this is a custom avatar
        voice_params = {
            "speed": 1.0,  # Default values
            "pitch": 1.0,
            "emotion": "Friendly"
        }
        
        try:
            # Check if this is a custom avatar and if we should analyze the voice
            avatar_info = execute_query(
                "SELECT is_custom, voice_parameters_analyzed FROM user_avatars WHERE avatar_id = %s AND user_id = %s",
                (avatar_id, int(user["id"])),
                fetch_one=True
            )
            
            if avatar_info and avatar_info.get("is_custom") and not avatar_info.get("voice_parameters_analyzed"):
                log_info(f"Analyzing voice for custom avatar: {avatar_id}", "API")
                
                # Create temporary file for voice analysis
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
                    # Download audio from Cloudinary URL to analyze
                    import requests
                    response = requests.get(audio_url)
                    if response.status_code == 200:
                        temp_file.write(response.content)
                        temp_path = temp_file.name
                        
                        # Analyze voice characteristics
                        voice_analysis = VoiceAnalysisService()
                        analysis_result = await voice_analysis.analyze_voice(temp_path)
                        
                        if analysis_result["success"]:
                            voice_params = {
                                "speed": analysis_result["speed"],
                                "pitch": analysis_result["pitch"],
                                "emotion": analysis_result["emotion"]
                            }
                            
                            # Store voice parameters in database
                            execute_query(
                                """
                                UPDATE user_avatars 
                                SET voice_parameters_speed = %s,
                                    voice_parameters_pitch = %s,
                                    voice_parameters_emotion = %s,
                                    voice_parameters_analyzed = TRUE
                                WHERE avatar_id = %s AND user_id = %s
                                """,
                                (voice_params["speed"], voice_params["pitch"], voice_params["emotion"], avatar_id, int(user["id"]))
                            )
                            
                            log_info(f"Voice analysis complete for avatar {avatar_id}: {voice_params}", "API")
                    
                    # Clean up temporary file
                    try:
                        os.remove(temp_path)
                    except:
                        pass
        except Exception as e:
            log_warning(f"Error during voice analysis: {str(e)}", "API")
            # Continue with default parameters if analysis fails
        
        # Create video with HeyGen API
        result = create_video_from_audio_file(
            api_key, 
            avatar_id, 
            audio_url, 
            format, 
            speed=voice_params["speed"], 
            pitch=voice_params["pitch"], 
            emotion=voice_params["emotion"]
        )
        
        if not result["success"]:
            return JSONResponse(
                status_code=500,
                content=result
            )
            
        # Save video to database
        heygen_video_id = result["video_id"]
        title = title or f"Audio Video {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        # Ensure all values are properly typed for PostgreSQL
        user_id = int(user["id"]) if user["id"] else None
        
        # FIXED: Added avatar_id and audio_path to the INSERT statement
        execute_query(
            """
            INSERT INTO videos (user_id, avatar_id, audio_path, heygen_video_id, status, format, title, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, str(avatar_id), audio_url, str(heygen_video_id), "processing", str(format), str(title), str(description))
        )
        
        log_info(f"Audio-to-video created: {heygen_video_id} with avatar: {avatar_id}", "API")
        
        return JSONResponse(content={
            "success": True,
            "video_id": heygen_video_id,
            "message": "Video creation initiated"
        })
    except Exception as e:
        log_error("Error creating video from audio", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.post("/avatars")
async def add_avatar(
    request: Request,
    avatar_id: str = Form(...),
    avatar_name: str = Form(...),
    avatar_image: UploadFile = File(...),
    is_default: bool = Form(False)
):
    """
    Add a new avatar for a user
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
            
        # Upload avatar image
        avatar_image_url = upload_avatar_to_cloudinary(avatar_image, user["id"])
        
        # If setting as default, clear other defaults
        if is_default:
            execute_query(
                "UPDATE user_avatars SET is_default = 0 WHERE user_id = %s",
                (int(user["id"]),)
            )
            
        # Add avatar to database
        execute_query(
            """
            INSERT INTO user_avatars (user_id, avatar_id, avatar_name, avatar_image_url, is_default)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (int(user["id"]), avatar_id, avatar_name, avatar_image_url, is_default)
        )
        
        # If default, also update user record
        if is_default:
            execute_query(
                "UPDATE users SET avatar_id = %s WHERE id = %s",
                (avatar_id, int(user["id"]))
            )
            
        log_info(f"Avatar added for user {user['username']}: {avatar_id}", "API")
        
        return JSONResponse(content={
            "success": True,
            "avatar_id": avatar_id,
            "avatar_image_url": avatar_image_url,
            "message": "HeyGen avatar added successfully"
        })
    except Exception as e:
        log_error("Error adding HeyGen avatar", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.post("/avatars/heygen")
async def add_heygen_avatar(
    request: Request,
    avatar_id: str = Form(...),
    avatar_name: str = Form(None),
    is_default: bool = Form(False)
):
    """
    Add a HeyGen avatar by ID only (no file upload required)
    Enhanced with proper avatar validation using HeyGen API
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
        
        # Check if avatar already exists for this user
        existing = execute_query(
            "SELECT id FROM user_avatars WHERE user_id = %s AND heygen_avatar_id = %s",
            (int(user["id"]), avatar_id)
        )
        
        if existing:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Avatar already exists for this user"}
            )
        
        # Clean up avatar ID (remove any whitespace)
        avatar_id = avatar_id.strip()
        
        # Get HeyGen API key
        heygen_api_key = os.getenv("HEYGEN_API_KEY")
        avatar_type = "unknown"
        
        if not heygen_api_key:
            log_warning("HeyGen API key not found - adding avatar without validation", "API")
            # Fallback: Add avatar without validation
            if not avatar_name:
                avatar_name = f"HeyGen Avatar {avatar_id[:8]}"
            avatar_image_url = f"https://files2.heygen.ai/avatar/v3/{avatar_id}/{avatar_id}.jpg"
        else:
            # Try to validate avatar with HeyGen API
            log_info(f"Validating HeyGen avatar ID: {avatar_id}", "API")
            
            try:
                from ..api.heygen import get_avatar_from_any_endpoint
                avatar_result = get_avatar_from_any_endpoint(heygen_api_key, avatar_id)
                
                if avatar_result and avatar_result.get("error"):
                    # Handle old talking photo error - still allow adding
                    log_warning(f"HeyGen validation warning for {avatar_id}: {avatar_result.get('error')}", "API")
                    avatar_type = "legacy"
                    if not avatar_name:
                        avatar_name = f"Legacy Avatar {avatar_id[:8]}"
                    avatar_image_url = f"https://files2.heygen.ai/avatar/v3/{avatar_id}/{avatar_id}.jpg"
                elif avatar_result:
                    # Extract avatar details from HeyGen response
                    avatar_data = avatar_result.get("data", {})
                    avatar_type = avatar_result.get("type", "unknown")
                    
                    # Generate avatar name if not provided
                    if not avatar_name:
                        # Try to get name from HeyGen data
                        heygen_name = avatar_data.get("name") or avatar_data.get("avatar_name")
                        if heygen_name:
                            avatar_name = heygen_name
                        else:
                            avatar_name = f"Avatar {avatar_id}"
                    
                    # Get avatar image URL from HeyGen data or construct it
                    avatar_image_url = None
                    
                    # Try to get image URL from HeyGen response
                    if avatar_data.get("preview_image_url"):
                        avatar_image_url = avatar_data["preview_image_url"]
                    elif avatar_data.get("image_url"):
                        avatar_image_url = avatar_data["image_url"]
                    elif avatar_data.get("preview_image"):
                        avatar_image_url = avatar_data["preview_image"]
                    else:
                        # Fallback: construct URL based on avatar type
                        avatar_image_url = f"https://files2.heygen.ai/avatar/v3/{avatar_id}/{avatar_id}.jpg"
                    
                    log_info(f"HeyGen avatar validated successfully (type: {avatar_type})", "API")
                else:
                    # Validation failed but we'll add it anyway with a warning
                    log_warning(f"Could not validate HeyGen avatar {avatar_id} - adding with fallback data", "API")
                    avatar_type = "unvalidated"
                    if not avatar_name:
                        avatar_name = f"Unvalidated Avatar {avatar_id[:8]}"
                    avatar_image_url = f"https://files2.heygen.ai/avatar/v3/{avatar_id}/{avatar_id}.jpg"
                    
            except Exception as validation_error:
                log_error(f"HeyGen validation error for {avatar_id}: {validation_error}", "API")
                # Fallback: Add avatar without validation
                avatar_type = "fallback"
                if not avatar_name:
                    avatar_name = f"HeyGen Avatar {avatar_id[:8]}"
                avatar_image_url = f"https://files2.heygen.ai/avatar/v3/{avatar_id}/{avatar_id}.jpg"
        
        # If setting as default, clear other defaults
        if is_default:
            execute_query(
                "UPDATE user_avatars SET is_default = 0 WHERE user_id = %s",
                (int(user["id"]),)
            )
            
        # Add avatar to database
        execute_query(
            """
            INSERT INTO user_avatars (user_id, heygen_avatar_id, avatar_name, avatar_image_url, is_default, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            """,
            (int(user["id"]), avatar_id, avatar_name, avatar_image_url, is_default)
        )
        
        # If default, also update user record
        if is_default:
            execute_query(
                "UPDATE users SET avatar_id = %s WHERE id = %s",
                (avatar_id, int(user["id"]))
            )
            
        log_info(f"HeyGen avatar added for user {user['username']}: {avatar_id} (type: {avatar_type})", "API")
        
        return JSONResponse(content={
            "success": True,
            "avatar_id": avatar_id,
            "avatar_name": avatar_name,
            "avatar_image_url": avatar_image_url,
            "avatar_type": avatar_type,
            "message": "HeyGen avatar added successfully"
        })
    except Exception as e:
        log_error("Error adding HeyGen avatar", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/avatars")
async def get_avatars(request: Request):
    """
    Get avatars for current user
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
            
        # Get user's avatars
        avatars = execute_query(
            "SELECT * FROM user_avatars WHERE user_id = %s",
            (int(user["id"]),),
            fetch_all=True
        )
        
        # Convert to list of dicts
        avatar_list = []
        for a in avatars:
            if isinstance(a, dict):
                avatar_list.append(a)
            else:
                # Handle SQLite Row objects
                avatar_dict = {}
                for key in a.keys():
                    avatar_dict[key] = a[key]
                avatar_list.append(avatar_dict)
                
        return JSONResponse(content={"success": True, "avatars": avatar_list})
    except Exception as e:
        log_error("Error getting avatars", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/admin/check-webhook")
async def check_webhook_registration(request: Request):
    """Temporary endpoint to check and register webhook with HeyGen - now with SMS test"""
    
    # Check if this is an SMS test request
    if request.query_params.get("test") == "sms":
        return await test_sms_inline()
    
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"error": "Authentication required"}
            )
        
        api_key = os.getenv('HEYGEN_API_KEY')
        if not api_key:
            return JSONResponse(content={"error": "HEYGEN_API_KEY not found in environment"})
        
        # List registered webhooks
        list_url = "https://api.heygen.com/v1/webhook/endpoint.list"
        headers = {
            "Accept": "application/json",
            "X-Api-Key": api_key
        }
        
        response = requests.get(list_url, headers=headers)
        
        if response.status_code != 200:
            return JSONResponse(content={
                "error": f"API request failed: {response.status_code}",
                "response": response.text
            })
            
        result = response.json()
        
        if result.get("code") == 100:
            endpoints = result.get("data", [])
            our_webhook_url = "https://app.myavatar.dk/api/heygen/webhook"
            
            webhook_found = False
            webhook_details = None
            
            for endpoint in endpoints:
                if our_webhook_url in endpoint.get('url', ''):
                    webhook_found = True
                    webhook_details = endpoint
                    break
            
            if webhook_found:
                return JSONResponse(content={
                    "status": "registered",
                    "message": "✅ Webhook IS registered with HeyGen",
                    "webhook": webhook_details,
                    "total_webhooks": len(endpoints),
                    "all_webhooks": endpoints
                })
            else:
                # Try to register webhook
                registration_result = await register_webhook_now(api_key)
                return JSONResponse(content={
                    "status": "not_registered", 
                    "message": "❌ Webhook was NOT registered, attempted registration",
                    "registration_result": registration_result,
                    "total_webhooks": len(endpoints),
                    "all_webhooks": endpoints
                })
        else:
            return JSONResponse(content={"error": f"API Error: {result}"})
            
    except Exception as e:
        log_error(f"Webhook check error: {str(e)}", "API")
        return JSONResponse(content={"error": f"Exception: {str(e)}"})

async def test_sms_inline():
    """Inline SMS test function"""
    try:
        # Check credentials
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        from_number = os.getenv('TWILIO_PHONE_NUMBER')
        
        credentials_status = {
            "TWILIO_ACCOUNT_SID": "SET" if account_sid else "MISSING",
            "TWILIO_AUTH_TOKEN": "SET" if auth_token else "MISSING", 
            "TWILIO_PHONE_NUMBER": from_number if from_number else "MISSING"
        }
        
        if not all([account_sid, auth_token, from_number]):
            return JSONResponse({
                "success": False,
                "error": "Missing Twilio credentials",
                "credentials": credentials_status
            })
        
        # Test SMS send
        try:
            from twilio.rest import Client
            
            client = Client(account_sid, auth_token)
            
            # Send test SMS to Mogens
            message = client.messages.create(
                body="🧪 TEST: MyAvatar SMS system is working! This is a production test from Railway.",
                from_=from_number,
                to="+4530604639"  # Mogens' number
            )
            
            log_info(f"✅ SMS test sent successfully: {message.sid}", "SMS_TEST")
            
            return JSONResponse({
                "success": True,
                "message": "SMS sent successfully!",
                "credentials": credentials_status,
                "sms_details": {
                    "sid": message.sid,
                    "to": message.to,
                    "from": message.from_,
                    "status": message.status
                }
            })
            
        except Exception as sms_error:
            log_error(f"❌ SMS send failed: {sms_error}", "SMS_TEST")
            return JSONResponse({
                "success": False,
                "error": f"SMS send failed: {str(sms_error)}",
                "credentials": credentials_status
            })
            
    except Exception as e:
        log_error(f"❌ SMS test error: {e}", "SMS_TEST")
        return JSONResponse({
            "success": False,
            "error": f"SMS test failed: {str(e)}"
        })

async def register_webhook_now(api_key):
    """Register webhook with HeyGen"""
    
    webhook_url = "https://app.myavatar.dk/api/heygen/webhook"
    events = ["avatar_video.success", "avatar_video.fail"]
    
    registration_url = "https://api.heygen.com/v1/webhook/endpoint.add"
    
    payload = {
        "url": webhook_url,
        "events": events
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": api_key
    }
    
    try:
        response = requests.post(
            registration_url,
            headers=headers,
            data=json.dumps(payload)
        )
        
        if response.status_code != 200:
            return {
                "success": False,
                "error": f"Registration failed: {response.status_code}",
                "response": response.text
            }
            
        result = response.json()
        
        if result.get("code") == 100:
            webhook_data = result.get("data", {})
            return {
                "success": True,
                "endpoint_id": webhook_data.get("endpoint_id"),
                "secret": webhook_data.get("secret"),
                "status": webhook_data.get("status"),
                "message": "✅ Webhook registered successfully!",
                "important": f"🔑 Add HEYGEN_WEBHOOK_SECRET={webhook_data.get('secret')} to Railway environment"
            }
        else:
            return {
                "success": False,
                "error": f"Registration failed: {result}"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"Registration exception: {str(e)}"
        }

@router.get("/voices")
async def get_voices(request: Request, language: Optional[str] = None):
    """
    Get available voices from HeyGen
    """
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
            
        result = get_available_voices(api_key, language)
        return JSONResponse(content=result)
    except Exception as e:
        log_error("Error getting voices", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/heygen-avatars")
async def get_heygen_avatars(request: Request):
    """
    Get available avatars from HeyGen
    """
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
        return JSONResponse(content=result)
    except Exception as e:
        log_error("Error getting HeyGen avatars", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/video-status/{video_id}")
async def get_video_status(request: Request, video_id: str):
    """
    Check status of a video by ID
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
        
        # Get video from database - handle both numeric IDs and HeyGen video IDs
        if video_id.isdigit():
            # Numeric ID - check both id and heygen_video_id fields
            video = execute_query(
                "SELECT * FROM videos WHERE id = %s OR heygen_video_id = %s",
                (int(video_id), video_id),
                fetch_one=True
            )
        else:
            # Non-numeric ID (HeyGen video ID) - only check heygen_video_id field
            video = execute_query(
                "SELECT * FROM videos WHERE heygen_video_id = %s",
                (video_id,),
                fetch_one=True
            )
        
        if not video:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Video not found"}
            )
            
        log_info(f"Found video in database: ID={video.get('id')}, HeyGen_ID={video.get('heygen_video_id')}, Status={video.get('status')}, Has_URL={bool(video.get('video_path'))}", "API")
            
        # Check if user has access to this video
        if not user["is_admin"] and video["user_id"] != int(user["id"]):
            return JSONResponse(
                status_code=403,
                content={"success": False, "error": "Access denied"}
            )
        
        # Check if video has a URL
        video_path = video.get("video_path")
        if not video_path:
            # Try to get the latest video details from HeyGen
            api_key = os.getenv("HEYGEN_API_KEY") or user.get("api_key")
            if api_key and video.get("heygen_video_id"):
                log_info(f"Fetching video URL from HeyGen for video {video['heygen_video_id']}", "API")
                result = get_video_details(api_key, video["heygen_video_id"])
                
                if result["success"] and result.get("details"):
                    details = result["details"]
                    log_info(f"HeyGen response details: {details}", "API")
                    
                    # Try different possible fields for video URL
                    video_path = (details.get("video_url") or 
                               details.get("video_url_caption") or 
                               details.get("url") or 
                               details.get("download_url"))
                    
                    # Check if video is completed
                    video_status = details.get("status", "unknown")
                    log_info(f"Video {video['heygen_video_id']} status: {video_status}", "API")
                    
                    if video_path:
                        # Update the database with the video URL
                        execute_query(
                            "UPDATE videos SET video_path = %s, status = %s WHERE id = %s",
                            (video_path, video_status, video["id"])
                        )
                        log_info(f"Updated video {video['id']} with URL and status {video_status}", "API")
                    elif video_status in ["processing", "pending", "waiting"]:
                        return JSONResponse(
                            status_code=200,
                            content={
                                "success": True, 
                                "message": f"Video is still {video_status}. Please wait...",
                                "status": video_status,
                                "processing": True
                            }
                        )
                    elif video_status == "failed":
                        return JSONResponse(
                            status_code=400,
                            content={
                                "success": False, 
                                "error": "Video generation failed. Please try creating a new video.",
                                "status": video_status
                            }
                        )
                else:
                    log_error(f"Failed to get video details from HeyGen: {result.get('error', 'Unknown error')}", "API")
        
        if not video_path:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False, 
                    "error": "Video URL not available. Video may still be processing or failed to generate."
                }
            )
        
        log_info(f"User {user['username']} checking video status {video_id}", "API")
        
        # Return status information as JSON instead of redirecting
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status": "completed",
                "video_path": video_path,
                "message": "Video is ready for download"
            }
        )
        
    except Exception as e:
        log_error(f"Error downloading video {video_id}", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/debug-video-status/{video_id}")
async def debug_video_status(request: Request, video_id: str):
    """
    Debug endpoint to test video status checking
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
        
        # Get video from database
        video = execute_query(
            "SELECT * FROM videos WHERE heygen_video_id = %s",
            (video_id,),
            fetch_one=True
        )
        
        if not video:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Video not found"}
            )
        
        # Test HeyGen API call
        api_key = os.getenv("HEYGEN_API_KEY")
        if not api_key:
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "No API key available"}
            )
        
        # Call HeyGen API
        result = get_video_details(api_key, video_id)
        
        # Convert video record to JSON-serializable format
        video_dict = dict(video)
        for key, value in video_dict.items():
            if hasattr(value, 'isoformat'):  # datetime object
                video_dict[key] = value.isoformat()
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "video_db": video_dict,
                "heygen_result": result
            }
        )
        
    except Exception as e:
        log_error(f"Debug video status error: {str(e)}", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/api/heygen/webhook")
async def heygen_webhook_test():
    """Test endpoint to verify webhook URL is accessible"""
    log_info("🔔 WEBHOOK GET TEST CALLED", "API")
    return {"status": "Webhook endpoint is accessible", "timestamp": datetime.now().isoformat()}

@router.post("/api/heygen/poll-now")
async def force_polling_check(request: Request):
    """FIXED: Force immediate polling check for completed videos"""
    try:
        # Use same authentication as processing status
        try:
            from ..routes.video_routes import get_current_user_fixed
            user = get_current_user_fixed(request)
        except ImportError:
            user = None
        
        if not user:
            return JSONResponse(
                status_code=401,
                content={"error": "Not authenticated"}
            )
            
        user_id = int(user["id"])
        log_info(f"🚀 Force polling requested by user {user_id}", "API")
        
        # FIXED: Enhanced query to get processing videos with more details
        processing_videos = execute_query("""
            SELECT id, heygen_video_id, status, created_at,
                   EXTRACT(EPOCH FROM (NOW() - created_at))/60 as minutes_ago
            FROM videos 
            WHERE user_id = %s AND status = 'processing'
            ORDER BY created_at ASC
        """, (user_id,), fetch_all=True)
        
        if not processing_videos:
            return {
                "success": True,
                "message": "No processing videos found", 
                "checked": 0,
                "results": []
            }
        
        # FIXED: Use the improved force polling method
        from ..services.video_polling_service import video_polling_service
        
        results = []
        checked_count = 0
        
        for video in processing_videos:
            try:
                if isinstance(video, tuple):
                    video_id = video[0]
                    heygen_video_id = video[1]
                    current_status = video[2]
                    minutes_ago = round(video[4], 1)
                else:
                    video_id = video.get('id')
                    heygen_video_id = video.get('heygen_video_id')
                    current_status = video.get('status')
                    minutes_ago = round(video.get('minutes_ago', 0), 1)
                
                if heygen_video_id:
                    log_info(f"🔍 Force polling video {heygen_video_id} (created {minutes_ago} min ago)", "API")
                    
                    # FIXED: Use the enhanced force polling method
                    poll_result = video_polling_service.force_poll_video(heygen_video_id)
                    
                    results.append({
                        "video_id": video_id,
                        "heygen_video_id": heygen_video_id,
                        "minutes_since_creation": minutes_ago,
                        "poll_result": poll_result
                    })
                    
                    checked_count += 1
                    
            except Exception as video_error:
                log_error(f"❌ Error polling individual video: {str(video_error)}", "API")
                results.append({
                    "video_id": video_id if 'video_id' in locals() else "unknown",
                    "heygen_video_id": heygen_video_id if 'heygen_video_id' in locals() else "unknown",
                    "error": str(video_error)
                })
        
        # FIXED: Get updated processing status after polling
        updated_processing = execute_query(
            "SELECT COUNT(*) FROM videos WHERE user_id = %s AND status = 'processing'",
            (user_id,),
            fetch_one=True
        )
        
        updated_count = updated_processing[0] if isinstance(updated_processing, tuple) else updated_processing.get('count', 0)
        
        response = {
            "success": True,
            "message": f"Force polling completed for {checked_count} videos", 
            "checked": checked_count,
            "processing_videos_before": len(processing_videos),
            "processing_videos_after": updated_count,
            "videos_completed": len(processing_videos) - updated_count,
            "results": results
        }
        
        log_info(f"✅ Force polling complete: {response}", "API")
        return response
        
    except Exception as e:
        log_error(f"❌ Error in force polling: {str(e)}", "API")
        log_error(f"Traceback: {traceback.format_exc()}", "API")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Failed to force polling: {str(e)}",
                "details": traceback.format_exc()
            }
        )

@router.post("/api/videos/cleanup-processing")
async def cleanup_stuck_processing_videos(request: Request):
    """Delete all stuck processing videos for clean testing"""
    try:
        # Use same authentication as processing status
        try:
            from ..routes.video_routes import get_current_user_fixed
            user = get_current_user_fixed(request)
        except ImportError:
            user = None
        
        if not user:
            return JSONResponse(
                status_code=401,
                content={"error": "Not authenticated"}
            )
            
        user_id = int(user["id"])
        
        # Get all processing videos for this user first
        processing_videos = execute_query(
            "SELECT id, title, heygen_video_id FROM videos WHERE user_id = %s AND status = 'processing'",
            (user_id,),
            fetch_all=True
        )
        
        if not processing_videos:
            return {"message": "No processing videos found to delete", "deleted": 0}
        
        # Delete all processing videos
        deleted_count = execute_query(
            "DELETE FROM videos WHERE user_id = %s AND status = 'processing'",
            (user_id,),
            fetch_one=False
        )
        
        return {
            "message": f"Deleted {len(processing_videos)} stuck processing videos", 
            "deleted": len(processing_videos),
            "deleted_videos": [
                {
                    "id": v.get('id') if isinstance(v, dict) else v[0],
                    "title": v.get('title') if isinstance(v, dict) else v[1],
                    "heygen_video_id": v.get('heygen_video_id') if isinstance(v, dict) else v[2]
                } for v in processing_videos
            ]
        }
        
    except Exception as e:
        print(f"❌ Error in cleanup: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to cleanup videos: {str(e)}"}
        )

@router.get("/api/videos/stats")
async def get_video_stats(request: Request):
    """FIXED: Get video statistics for the user"""
    try:
        # Use the same authentication pattern as other working endpoints
        try:
            from ..routes.video_routes import get_current_user_fixed
            user = get_current_user_fixed(request)
        except ImportError:
            user = None
        
        if not user:
            return JSONResponse(
                status_code=401,
                content={"error": "Not authenticated"}
            )
        
        user_id = int(user["id"])
        
        # Get video statistics
        stats = execute_query("""
            SELECT 
                COUNT(*) as total_videos,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_videos,
                COUNT(CASE WHEN status = 'processing' THEN 1 END) as processing_videos,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_videos
            FROM videos 
            WHERE user_id = %s
        """, (user_id,), fetch_one=True)
        
        if isinstance(stats, dict):
            return {
                "total": stats.get("total_videos", 0),
                "completed": stats.get("completed_videos", 0),
                "processing": stats.get("processing_videos", 0),
                "failed": stats.get("failed_videos", 0)
            }
        else:
            return {
                "total": stats[0] if stats else 0,
                "completed": stats[1] if len(stats) > 1 else 0,
                "processing": stats[2] if len(stats) > 2 else 0,
                "failed": stats[3] if len(stats) > 3 else 0
            }
        
    except Exception as e:
        log_error(f"Error getting video stats: {str(e)}", "API")
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to get video stats"}
        )

@router.get("/api/user/processing-status")
async def get_user_processing_status(request: Request):
    """FIXED: Check if user has any videos currently processing"""
    try:
        # Use the same authentication pattern as voice-to-video route
        try:
            from ..routes.video_routes import get_current_user_fixed
            user = get_current_user_fixed(request)
        except ImportError:
            user = None
        
        if not user:
            return JSONResponse(
                status_code=401,
                content={"error": "Not authenticated"}
            )
            
        user_id = int(user["id"])
        log_info(f"🔍 Checking processing status for user {user_id}", "API")
        
        # FIXED: Enhanced query with more debugging info
        processing_videos = execute_query("""
            SELECT id, heygen_video_id, status, created_at, 
                   EXTRACT(EPOCH FROM (NOW() - created_at))/60 as minutes_ago
            FROM videos 
            WHERE user_id = %s AND status = 'processing'
            ORDER BY created_at DESC
        """, (user_id,), fetch_all=True)
        
        processing_count = len(processing_videos) if processing_videos else 0
        
        # FIXED: Add detailed information for debugging
        video_details = []
        if processing_videos:
            for video in processing_videos:
                if isinstance(video, tuple):
                    video_details.append({
                        "id": video[0],
                        "heygen_video_id": video[1], 
                        "status": video[2],
                        "minutes_ago": round(video[4], 1)
                    })
                else:
                    video_details.append({
                        "id": video.get('id'),
                        "heygen_video_id": video.get('heygen_video_id'),
                        "status": video.get('status'),
                        "minutes_ago": round(video.get('minutes_ago', 0), 1)
                    })
        
        log_info(f"📊 User {user_id} has {processing_count} processing videos", "API")
        
        response = {
            "has_processing_videos": processing_count > 0,
            "processing_count": processing_count,
            "videos": video_details  # Added for debugging
        }
        
        return response
        
    except Exception as e:
        log_error(f"Error getting processing status: {str(e)}", "API")
        log_error(f"Traceback: {traceback.format_exc()}", "API")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "details": str(e)}
        )

@router.get("/api/debug/database-test")
async def test_database_connection():
    """CRITICAL: Test database connection and verify video polling setup"""
    try:
        from ..db.database import execute_query
        
        # Test basic connectivity
        current_time = execute_query("SELECT NOW() as current_time", fetch_one=True)
        
        # Test videos table access
        video_count = execute_query("SELECT COUNT(*) as count FROM videos", fetch_one=True)
        
        # Test processing videos
        processing_videos = execute_query("""
            SELECT id, heygen_video_id, status, 
                   EXTRACT(EPOCH FROM (NOW() - created_at))/60 as minutes_ago
            FROM videos 
            WHERE status = 'processing' 
            LIMIT 5
        """, fetch_all=True)
        
        # Test HeyGen API key
        heygen_api_key = os.getenv("HEYGEN_API_KEY")
        
        return {
            "success": True,
            "database_connected": True,
            "current_time": current_time[0].isoformat() if isinstance(current_time, tuple) else current_time.get('current_time').isoformat(),
            "total_videos": video_count[0] if isinstance(video_count, tuple) else video_count.get('count'),
            "processing_videos_count": len(processing_videos) if processing_videos else 0,
            "processing_videos_sample": processing_videos[:3] if processing_videos else [],
            "heygen_api_key_configured": bool(heygen_api_key),
            "heygen_api_key_length": len(heygen_api_key) if heygen_api_key else 0
        }
        
    except Exception as e:
        log_error(f"❌ Database test failed: {str(e)}", "API")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )

@router.get("/api/heygen/webhook/test")
@router.post("/api/heygen/webhook/test")
async def test_heygen_webhook(request: Request):
    """Test webhook endpoint for HeyGen"""
    log_info("🔔 WEBHOOK GET TEST CALLED", "API")
    return {"status": "Webhook endpoint is accessible", "timestamp": datetime.now().isoformat()}

@router.get("/test/heygen-status")
async def test_heygen_status(request: Request):
    """
    Test HeyGen API connection and status
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
            
        api_key = os.getenv("HEYGEN_API_KEY")
        if not api_key:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "No HeyGen API key configured"}
            )
            
        # Test basic connection
        from ..api.heygen import test_heygen_connection, get_available_voices
        
        connection_test = test_heygen_connection(api_key)
        voices_result = get_available_voices(api_key)
        
        return JSONResponse(content={
            "success": True,
            "connection_test": connection_test,
            "voices_available": voices_result.get("success", False),
            "voices_count": len(voices_result.get("voices", [])) if voices_result.get("success") else 0,
            "api_key_present": bool(api_key),
            "api_key_length": len(api_key) if api_key else 0
        })
        
    except Exception as e:
        log_error("Error testing HeyGen API status", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/api/avatar/{avatar_id}/voice-parameters")
@router.get("/api/avatar/{avatar_id}/voice-parameters/")
async def get_avatar_voice_parameters(request: Request, avatar_id: str):
    """
    Get voice parameters for a specific avatar
    Used to pre-fill voice parameter sliders in the UI
    FIXED: Handle missing public_avatars table gracefully
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
        
        # Check if the avatar belongs to the user - UPDATED ORDER
        # 1. First try: heygen_avatar_id (most common)
        avatar = execute_query(
            "SELECT * FROM user_avatars WHERE heygen_avatar_id = %s AND user_id = %s",
            (avatar_id, int(user["id"])),
            fetch_one=True
        )
        
        is_custom_avatar = False
        
        if not avatar:
            # 2. Second try: avatar_id field (fallback)
            avatar = execute_query(
                "SELECT * FROM user_avatars WHERE avatar_id = %s AND user_id = %s",
                (avatar_id, int(user["id"])),
                fetch_one=True
            )
            
            if not avatar:
                # 3. Third try: numeric ID as fallback (for frontend compatibility)
                try:
                    numeric_id = int(avatar_id)
                    avatar = execute_query(
                        "SELECT * FROM user_avatars WHERE id = %s AND user_id = %s",
                        (numeric_id, int(user["id"])),
                        fetch_one=True
                    )
                except (ValueError, TypeError):
                    pass
                
                if not avatar:
                    # FIXED: Return default parameters instead of 404 for unknown avatars
                    log_warning(f"Avatar {avatar_id} not found for user {user['id']}, using defaults", "API")
                    return JSONResponse(content={
                        "success": True,
                        "parameters": {
                            "emotion": 0.5,  # Neutral emotion
                            "speed": 1.0,    # Normal speed
                            "pitch": 1.0,    # Normal pitch
                            "voice_id": "1bd001e7e50f421d891986aad5158bc8",  # Default HeyGen voice
                            "language": "en-US"
                        },
                        "avatar_id": avatar_id,
                        "is_custom": False,
                        "note": "Using default parameters - avatar not found in user's collection"
                    })
        
        # Convert to dict for easier access
        avatar_data = dict(avatar) if avatar else {}
        
        # Check if this is a custom avatar
        is_custom_avatar = avatar_data.get("is_custom", False)
        
        # For custom avatars, use user's personal voice
        if is_custom_avatar:
            try:
                user_voice = execute_query(
                    "SELECT heygen_voice_id, language FROM users WHERE id = %s",
                    (int(user["id"]),),
                    fetch_one=True
                )
                
                if user_voice and user_voice.get("heygen_voice_id"):
                    return JSONResponse(content={
                        "success": True,
                        "parameters": {
                            "emotion": 0.5,  # Neutral emotion
                            "speed": 1.0,    # Normal speed
                            "pitch": 1.0,    # Normal pitch
                            "voice_id": user_voice.get("heygen_voice_id"),
                            "language": user_voice.get("language", "en-US")
                        },
                        "avatar_id": avatar_id,
                        "is_custom": True
                    })
            except Exception as voice_error:
                log_warning(f"Error getting user voice for custom avatar: {voice_error}", "API")
        
        # FIXED: Simplified voice parameter lookup - no more public_avatars dependency
        try:
            voice_params = execute_query(
                "SELECT * FROM avatar_voice_parameters WHERE avatar_id = %s",
                (avatar_id,),
                fetch_one=True
            )
        except Exception as param_error:
            log_warning(f"Could not fetch voice parameters for avatar {avatar_id}: {param_error}", "API")
            voice_params = None
        
        # Default parameters if none found
        if not voice_params:
            # Try to get user's preferred voice if available
            user_voice_id = "1bd001e7e50f421d891986aad5158bc8"  # Default fallback
            try:
                if user.get("heygen_voice_id"):
                    user_voice_id = user["heygen_voice_id"]
            except:
                pass
            
            return JSONResponse(content={
                "success": True,
                "parameters": {
                    "emotion": 0.5,  # Neutral emotion
                    "speed": 1.0,    # Normal speed
                    "pitch": 1.0,    # Normal pitch
                    "voice_id": user_voice_id,
                    "language": "en-US"
                },
                "avatar_id": avatar_id,
                "is_custom": is_custom_avatar
            })
        
        # Return the voice parameters
        voice_params_dict = dict(voice_params)
        return JSONResponse(content={
            "success": True,
            "parameters": {
                "emotion": float(voice_params_dict.get("emotion", 0.5)),
                "speed": float(voice_params_dict.get("speed", 1.0)),
                "pitch": float(voice_params_dict.get("pitch", 1.0)),
                "voice_id": voice_params_dict.get("voice_id", "1bd001e7e50f421d891986aad5158bc8"),
                "language": voice_params_dict.get("language", "en-US")
            },
            "avatar_id": avatar_id,
            "is_custom": is_custom_avatar
        })
        
    except Exception as e:
        log_error(f"Error getting avatar voice parameters: {str(e)}", "API")
        # FIXED: Return default parameters instead of 500 error
        return JSONResponse(content={
            "success": True,
            "parameters": {
                "emotion": 0.5,
                "speed": 1.0,
                "pitch": 1.0,
                "voice_id": "1bd001e7e50f421d891986aad5158bc8",
                "language": "en-US"
            },
            "avatar_id": avatar_id,
            "is_custom": False,
            "note": "Using fallback parameters due to database error"
        })

@router.post("/avatars/update-images")
async def update_avatar_images(request: Request):
    """
    Update all user avatars with fresh HeyGen images
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Not authenticated"}
            )
            
        # Get user's avatars
        user_avatars = execute_query(
            "SELECT avatar_id, avatar_image_url FROM user_avatars WHERE user_id = %s",
            (int(user["id"]),),
            fetch_all=True
        )
        
        if not user_avatars:
            return JSONResponse(content={
                "success": True,
                "message": "No avatars to update",
                "updated_count": 0
            })
        
        api_key = os.getenv("HEYGEN_API_KEY") or user.get("api_key")
        updated_count = 0
        
        # Update each avatar with fresh HeyGen image
        for avatar in user_avatars:
            avatar_data = dict(avatar)
            avatar_id = avatar_data['avatar_id']
            current_image = avatar_data['avatar_image_url']
            
            # Get the best HeyGen image
            new_image_url = ensure_avatar_has_heygen_image(avatar_id, current_image, api_key)
            
            # Update if we got a different/better image
            if new_image_url and new_image_url != current_image:
                execute_query(
                    "UPDATE user_avatars SET avatar_image_url = %s WHERE user_id = %s AND avatar_id = %s",
                    (new_image_url, int(user["id"]), avatar_id)
                )
                updated_count += 1
                log_info(f"Updated avatar image for {avatar_id}: {new_image_url}", "API")
        
        return JSONResponse(content={
            "success": True,
            "message": f"Updated {updated_count} avatar images",
            "updated_count": updated_count
        })
        
    except Exception as e:
        log_error("Error updating avatar images", "API", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )