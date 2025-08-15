"""
Video service module - handles video operations
"""
import os
import time
from ..db.database import execute_query
from ..api.heygen import get_video_details
from ..logger.log_handler import log_info, log_error

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
        
        # Add debug logging
        log_info(f"DEBUG: Video data: {video}", "VideoService")
        log_info(f"DEBUG: User data: {user}", "VideoService")
        log_info(f"DEBUG: Current video_path: {video.get('video_path')}", "VideoService")
        
        video_url = video.get("video_path")
        
        if not video_url:
            log_info(f"DEBUG: No video_path found, fetching from HeyGen", "VideoService")
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
        
        log_info(f"DEBUG: Returning current video_path: {video_url}", "VideoService")
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
