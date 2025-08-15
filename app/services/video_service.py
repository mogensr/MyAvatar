"""
Video service module - handles video operations
"""
import os
import time
from datetime import datetime
from ..db.database import execute_query
from ..api.heygen import get_video_details, create_video_from_text, create_video_from_audio_file
from ..logger.log_handler import log_info, log_error, log_warning
from ..storage.file_storage import upload_audio_to_cloudinary

# Global language voice map - WORKING HEYGEN VOICE IDS (not Azure TTS IDs)
language_voice_map = {
    "en-US": "1bd001e7e50f421d891986aad5158bc8",  # English (US) - Default - WORKING HEYGEN ID
    "en-GB": "1bd001e7e50f421d891986aad5158bc8",  # English (UK) - Use same working ID
    "da-DK": "1bd001e7e50f421d891986aad5158bc8",  # Danish - Use working ID as fallback
    "de-DE": "1bd001e7e50f421d891986aad5158bc8",  # German - Use working ID as fallback
    "es-ES": "1bd001e7e50f421d891986aad5158bc8",  # Spanish - Use working ID as fallback
    "fr-FR": "1bd001e7e50f421d891986aad5158bc8",  # French - Use working ID as fallback
    "it-IT": "1bd001e7e50f421d891986aad5158bc8",  # Italian - Use working ID as fallback
    "ja-JP": "1bd001e7e50f421d891986aad5158bc8",  # Japanese - Use working ID as fallback
    "ko-KR": "1bd001e7e50f421d891986aad5158bc8",  # Korean - Use working ID as fallback
    "nl-NL": "1bd001e7e50f421d891986aad5158bc8",  # Dutch - Use working ID as fallback
    "pl-PL": "1bd001e7e50f421d891986aad5158bc8",  # Polish - Use working ID as fallback
    "pt-BR": "1bd001e7e50f421d891986aad5158bc8",  # Portuguese - Use working ID as fallback
    "ru-RU": "1bd001e7e50f421d891986aad5158bc8",  # Russian - Use working ID as fallback
    "zh-CN": "1bd001e7e50f421d891986aad5158bc8",  # Chinese - Use working ID as fallback
}

def update_language_voice_map(new_map):
    """
    Update the global language_voice_map with new values
    """
    global language_voice_map
    
    if not new_map or not isinstance(new_map, dict):
        log_warning("Invalid language voice map provided", "VideoService")
        return False
        
    # Update only existing keys to prevent adding invalid languages
    for lang, voice_id in new_map.items():
        if lang in language_voice_map:
            language_voice_map[lang] = voice_id
            log_info(f"Updated voice ID for {lang} to {voice_id}", "VideoService")
    
    return True

class VideoService:
    def __init__(self):
        pass
    
    def get_video_by_id(self, video_id: str, user_id: int):
        """Get video from database by ID or HeyGen ID"""
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
            return None
            
        # Check if user has access to this video
        if video["user_id"] != user_id:
            return None
            
        return video
    
    def get_fresh_video_url(self, video: dict, user: dict):
        """Get fresh video URL, refreshing if expired"""
        
        # Add these debug lines
        log_info(f"DEBUG: Video data: {video}", "VideoService")
        log_info(f"DEBUG: User data: {user}", "VideoService")
        log_info(f"DEBUG: Current video_path: {video.get('video_path')}", "VideoService")
        
        video_url = video.get("video_path")
        
        if not video_url:
            return self._fetch_url_from_heygen(video, user)
        
        # Check if URL is expired
        if 'Expires=' in video_url:
            try:
                expires_part = video_url.split('Expires=')[1].split('&')[0]
                expires_timestamp = int(expires_part)
                current_timestamp = int(time.time())
                
                log_info(f"DEBUG: URL expires at {expires_timestamp}, current time {current_timestamp}", "VideoService")
                
                if expires_timestamp <= current_timestamp:
                    log_info(f"Video URL expired, refreshing for video {video['id']}", "VideoService")
                    return self._fetch_url_from_heygen(video, user)
                else:
                    log_info(f"Video URL still valid for video {video['id']}", "VideoService")
                    return video_url
            except Exception as e:
                log_error(f"Error checking URL expiry: {e}", "VideoService")
                return self._fetch_url_from_heygen(video, user)
        
        return video_url
    
    def _fetch_url_from_heygen(self, video: dict, user: dict):
        """Fetch fresh URL from HeyGen API"""
        log_info(f"DEBUG: Fetching from HeyGen for video {video.get('heygen_video_id')}", "VideoService")
        
        api_key = os.getenv("HEYGEN_API_KEY") or user.get("api_key")
        if not api_key or not video.get("heygen_video_id"):
            log_error(f"DEBUG: Missing api_key or heygen_video_id", "VideoService")
            return None
        
        log_info(f"Fetching fresh URL from HeyGen for video {video['heygen_video_id']}", "VideoService")
        result = get_video_details(api_key, video["heygen_video_id"])
        
        log_info(f"DEBUG: HeyGen result: {result}", "VideoService")
        
        if result["success"] and result.get("details"):
            details = result["details"]
            fresh_url = (details.get("video_url") or 
                        details.get("video_url_caption") or 
                        details.get("url") or 
                        details.get("download_url"))
            
            video_status = details.get("status", "unknown")
            
            if fresh_url:
                # Update database with fresh URL
                execute_query(
                    "UPDATE videos SET video_path = %s, status = %s WHERE id = %s",
                    (fresh_url, video_status, video["id"])
                )
                log_info(f"Updated video {video['id']} with fresh URL", "VideoService")
                return fresh_url
        
        log_error(f"Failed to get fresh URL for video {video['id']}", "VideoService")
        return None

    # =============================================================================
    # NEW METHODS - VIDEO CREATION
    # =============================================================================
    
    def add_speech_pauses(self, text: str) -> str:
        """
        Add SSML pauses to text based on punctuation:
        - Comma: 250ms pause
        - Period/question mark/exclamation mark: 700ms pause
        - New paragraph (double newline): 1200ms pause
        
        Returns text with SSML break tags inserted
        """
        if not text:
            return text
            
        # Replace periods, question marks, and exclamation marks with pauses
        text = text.replace('. ', '.<break time="700ms"/> ')
        text = text.replace('? ', '?<break time="700ms"/> ')
        text = text.replace('! ', '!<break time="700ms"/> ')
        
        # Replace commas with shorter pauses
        text = text.replace(', ', ',<break time="250ms"/> ')
        
        # Replace paragraph breaks (double newlines) with longer pauses
        text = text.replace('\n\n', '<break time="1200ms"/>\n\n')
        
        # Add a pause after colon
        text = text.replace(': ', ':<break time="400ms"/> ')
        
        # Add a pause for semicolon
        text = text.replace('; ', ';<break time="500ms"/> ')
        
        log_info(f"Added speech pauses to text", "VideoService")
        return text
    
    async def create_text_video(self, user_id: int, text: str, avatar_id: str, title: str, voice_id: str = None, language: str = "en-US", emotion: str = "Friendly", speed: float = 1.0, pitch: float = 1.0):
        """Create video from text using HeyGen API"""
        try:
            log_info(f"Creating text video for user {user_id}: {title}", "VideoService")
            
            # Get API key
            api_key = os.getenv("HEYGEN_API_KEY")
            if not api_key:
                log_error("No HeyGen API key available", "VideoService")
                return {"success": False, "error": "No API key available"}
            
            # Get avatar details including whether it's custom or not
            avatar_result = execute_query(
                """
                SELECT COALESCE(heygen_avatar_id, avatar_id) as heygen_id, is_custom
                FROM user_avatars 
                WHERE id = %s AND user_id = %s
                """,
                (avatar_id, user_id),
                fetch_one=True
            )
            
            if not avatar_result:
                log_error(f"Avatar {avatar_id} not found for user {user_id}", "VideoService")
                return {"success": False, "error": f"Avatar {avatar_id} not found"}
            
            heygen_avatar_id = avatar_result.get("heygen_id") if isinstance(avatar_result, dict) else avatar_result[0]
            is_custom_avatar = avatar_result.get("is_custom") if isinstance(avatar_result, dict) else avatar_result[1]
            
            log_info(f"Avatar details - ID: {heygen_avatar_id}, Is Custom: {is_custom_avatar}", "VideoService")
            
            # Get user data (subscription + voice) in one query - COPY OF WORKING LOGIC FROM api_routes.py
            user = execute_query(
                "SELECT subscription_type, heygen_voice_id FROM users WHERE id = %s",
                (user_id,),
                fetch_one=True
            )
            
            is_trial_user = False
            if user:
                subscription_type = user.get("subscription_type") if isinstance(user, dict) else user[0]
                is_trial_user = subscription_type == "trial" or subscription_type == "free"
                log_info(f"User {user_id} is a trial user: {is_trial_user}", "VideoService")
            
            # SIMPLE VOICE ASSIGNMENT - EXACT COPY OF WORKING LOGIC FROM api_routes.py
            voice_id = None
            
            # Always try to find user's preferred voice ID (WORKING LOGIC FROM api_routes.py)
            if not voice_id:
                try:
                    if user and user.get("heygen_voice_id"):
                        voice_id = user["heygen_voice_id"]
                        log_info(f"✅ Using user's heygen_voice_id: {voice_id}", "VideoService")
                except Exception as e:
                    log_warning(f"Error retrieving user heygen_voice_id: {str(e)}", "VideoService")
            
            # If still no voice_id, use a valid HeyGen voice ID as fallback (WORKING LOGIC FROM api_routes.py)
            if not voice_id:
                voice_id = "1bd001e7e50f421d891986aad5158bc8"  # Valid HeyGen voice ID
                log_warning(f"Using fallback HeyGen voice_id: {voice_id}", "VideoService")
            
            # Get voice analysis parameters for better text-to-video generation
            voice_params = {
                "speed": speed,  # Use provided speed or default
                "pitch": pitch,  # Use provided pitch or default
                "emotion": emotion  # Use provided emotion or default
            }
            
            # If we have analyzed voice parameters for this avatar, use them for better results
            if is_custom_avatar:
                try:
                    avatar_voice_params = execute_query(
                        """
                        SELECT voice_parameters_speed, voice_parameters_pitch, voice_parameters_emotion, voice_parameters_analyzed
                        FROM user_avatars 
                        WHERE id = %s AND user_id = %s AND voice_parameters_analyzed = TRUE
                        """,
                        (avatar_id, user_id),
                        fetch_one=True
                    )
                    
                    if avatar_voice_params:
                        # Use analyzed parameters for more natural speech
                        voice_params["speed"] = avatar_voice_params.get("voice_parameters_speed", speed)
                        voice_params["pitch"] = avatar_voice_params.get("voice_parameters_pitch", pitch) 
                        voice_params["emotion"] = avatar_voice_params.get("voice_parameters_emotion", emotion)
                        log_info(f"✅ Using analyzed voice parameters: {voice_params}", "VideoService")
                    else:
                        log_info(f"No analyzed voice parameters found, using defaults: {voice_params}", "VideoService")
                except Exception as e:
                    log_warning(f"Error retrieving voice parameters: {e}, using defaults", "VideoService")
            
            # We already have heygen_avatar_id from earlier query
            log_info(f"Using HeyGen avatar ID: {heygen_avatar_id} for database avatar {avatar_id}", "VideoService")
            
            # Add speech pauses to text
            text_with_pauses = self.add_speech_pauses(text)
            log_info(f"Text with pauses: {text_with_pauses[:100]}...", "VideoService")
            
            # Create video with HeyGen API - Enhanced with voice analysis parameters
            result = create_video_from_text(
                text=text_with_pauses,
                avatar_id=heygen_avatar_id, 
                voice_id=voice_id, 
                user_id=user_id,
                language=language.split('-')[0] if language else "en",  # Extract language code (en from en-US)
                context={"use_cloned_voice": is_custom_avatar},
                api_key=api_key,
                video_format="16:9",
                emotion=voice_params["emotion"],  # Use analyzed emotion parameters
                speed=voice_params["speed"],      # Use analyzed speed parameters  
                pitch=voice_params["pitch"]       # Use analyzed pitch parameters
            )
            
            if not result.get("success"):
                log_error(f"HeyGen API error: {result.get('error')}", "VideoService")
                return {"success": False, "error": result.get("error", "Video creation failed")}
            
            heygen_video_id = result.get("video_id")
            
            # Save video to database
            video_db_id = execute_query(
                """
                INSERT INTO videos (user_id, avatar_id, heygen_video_id, status, format, title, description, audio_path, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (user_id, avatar_id, heygen_video_id, "processing", "16:9", title, text[:500], "", datetime.now()),
                fetch_one=True
            )
            
            if video_db_id:
                db_id = video_db_id.get("id") if isinstance(video_db_id, dict) else video_db_id[0]
                log_info(f"Text video saved to database with ID {db_id}", "VideoService")
                
                # START POLLING: Add video to polling queue for status checking every 5 minutes
                if heygen_video_id:
                    try:
                        from .video_polling_service import video_polling_service
                        video_polling_service.add_video_to_poll(heygen_video_id)
                        log_info(f"🔄 Started polling for video {heygen_video_id} every 5 minutes", "VideoService")
                    except Exception as e:
                        log_warning(f"Could not start polling for video {heygen_video_id}: {str(e)}", "VideoService")
                
                return {
                    "success": True,
                    "video_id": db_id,
                    "heygen_video_id": heygen_video_id,
                    "status": "processing"
                }
            else:
                log_error("Failed to save video to database", "VideoService")
                return {"success": False, "error": "Failed to save video to database"}
            
        except Exception as e:
            log_error(f"Error creating text video: {str(e)}", "VideoService")
            return {"success": False, "error": str(e)}
    
    async def create_voice_video(self, user_id: int, audio_file, avatar_id: str, title: str):
        """Create video from audio file using HeyGen API"""
        try:
            log_info(f"Creating voice video for user {user_id}: {title}", "VideoService")
            
            # Get API key
            api_key = os.getenv("HEYGEN_API_KEY")
            if not api_key:
                log_error("No HeyGen API key available", "VideoService")
                return {"success": False, "error": "No API key available"}
            
            # Upload audio file to Cloudinary
            try:
                audio_url = upload_audio_to_cloudinary(audio_file, user_id)
                if not audio_url:
                    log_error("Failed to upload audio file", "VideoService")
                    return {"success": False, "error": "Failed to upload audio file"}
            except Exception as e:
                log_error(f"Error uploading audio: {str(e)}", "VideoService")
                return {"success": False, "error": f"Error uploading audio: {str(e)}"}
            
            # Create video with HeyGen API
            result = create_video_from_audio_file(api_key, avatar_id, audio_url, "16:9")
            
            if not result.get("success"):
                log_error(f"HeyGen API error: {result.get('error')}", "VideoService")
                return {"success": False, "error": result.get("error", "Video creation failed")}
            
            heygen_video_id = result.get("video_id")
            
            # Save video to database
            video_db_id = execute_query(
                """
                INSERT INTO videos (user_id, avatar_id, heygen_video_id, status, format, title, audio_path, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (user_id, avatar_id, heygen_video_id, "processing", "16:9", title, audio_url, datetime.now()),
                fetch_one=True
            )
            
            if video_db_id:
                db_id = video_db_id.get("id") if isinstance(video_db_id, dict) else video_db_id[0]
                log_info(f"Voice video saved to database with ID {db_id}", "VideoService")
                
                return {
                    "success": True,
                    "video_id": db_id,
                    "heygen_video_id": heygen_video_id,
                    "status": "processing"
                }
            else:
                log_error("Failed to save video to database", "VideoService")
                return {"success": False, "error": "Failed to save video to database"}
                
        except Exception as e:
            log_error(f"Error creating voice video: {str(e)}", "VideoService")
            return {"success": False, "error": str(e)}
    
    async def check_video_status(self, video_id: str, user_id: int):
        """Check video processing status with comprehensive field mapping support"""
        try:
            log_info(f"Checking status for video {video_id}", "VideoService")
            
            # Get video from database
            video = self.get_video_by_id(video_id, user_id)
            if not video:
                log_error(f"Video {video_id} not found or access denied", "VideoService")
                return {"success": False, "error": "Video not found"}
            
            # If video is already completed and has a URL, return it
            if video.get("status") == "completed" and video.get("video_path"):
                return {
                    "success": True,
                    "status": "completed",
                    "video_url": video.get("video_path"),
                    "progress": 100
                }
            
            # Get HeyGen video ID - handle both old and new field mappings
            heygen_id = video.get("heygen_video_id")
            
            # LEGACY SUPPORT: If heygen_video_id is None but video_path looks like a HeyGen ID
            if not heygen_id and video.get("video_path"):
                video_path = video.get("video_path")
                # Check if video_path looks like a HeyGen video ID (32 char hex string)
                if len(video_path) == 32 and all(c in '0123456789abcdef' for c in video_path.lower()):
                    log_info(f"🔄 Legacy video {video_id}: Moving HeyGen ID from video_path to heygen_video_id", "VideoService")
                    heygen_id = video_path
                    # Fix the database record
                    execute_query(
                        "UPDATE videos SET heygen_video_id = %s, video_path = NULL WHERE id = %s",
                        (heygen_id, video["id"])
                    )
                    log_info(f"✅ Fixed video {video_id} field mapping", "VideoService")
            
            # Check with HeyGen API for latest status
            api_key = os.getenv("HEYGEN_API_KEY")
            if not api_key or not heygen_id:
                log_error(f"No API key or HeyGen video ID available for video {video_id}", "VideoService")
                return {"success": False, "error": "Cannot check status"}
            
            result = get_video_details(api_key, video["heygen_video_id"])
            
            if result.get("success") and result.get("details"):
                details = result["details"]
                status = details.get("status", "unknown")
                
                # DEBUG: Log the full HeyGen response to see what fields are available
                log_info(f"🔍 HeyGen API response for video {video['id']}: {details}", "VideoService")
                
                # Get video URL if available
                video_url = (details.get("video_url") or 
                            details.get("video_url_caption") or 
                            details.get("url") or 
                            details.get("download_url"))
                
                # DEBUG: Log what video URL we found (or didn't find)
                log_info(f"🎬 Video URL found for video {video['id']}: {video_url}", "VideoService")
                
                # Update database with new status
                if status != video.get("status") or (video_url and not video.get("video_path")):
                    execute_query(
                        "UPDATE videos SET status = %s, video_path = %s WHERE id = %s",
                        (status, video_url, video["id"])
                    )
                    log_info(f"Updated video {video['id']} status to {status}", "VideoService")
                
                # Map status to progress
                progress = 0
                if status == "completed":
                    progress = 100
                elif status == "processing":
                    progress = 50
                elif status == "pending":
                    progress = 25
                elif status == "failed":
                    progress = 0
                
                return {
                    "success": True,
                    "status": status,
                    "video_url": video_url,
                    "progress": progress,
                    "duration": details.get("duration"),
                    "thumbnail_url": details.get("thumbnail_url")
                }
            else:
                log_error(f"Failed to get video status from HeyGen: {result.get('error')}", "VideoService")
                return {"success": False, "error": "Failed to check status"}
                
        except Exception as e:
            log_error(f"Error checking video status: {str(e)}", "VideoService")
            return {"success": False, "error": str(e)}
