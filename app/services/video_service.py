import os
import time
import logging
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Import database query function
try:
    from ..db.database import execute_query
except ImportError:
    def execute_query(query, params=(), fetch_one=False, fetch_all=False):
        logger.error("execute_query not available - database import failed")
        return None

class VideoService:
    """Service for managing videos and HeyGen integration"""
    
    def get_video_url_from_heygen(self, heygen_video_id: str) -> Optional[str]:
        """Get video URL from HeyGen API"""
        if not heygen_video_id:
            return None
        
        try:
            heygen_api_key = os.getenv('HEYGEN_API_KEY')
            if not heygen_api_key or heygen_api_key == 'your-heygen-api-key':
                logger.warning("No valid HeyGen API key found")
                return None
                
            headers = {
                'X-API-KEY': heygen_api_key,
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f'https://api.heygen.com/v2/video/{heygen_video_id}',
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 100 and 'data' in data:
                    video_url = data['data'].get('video_url')
                    if video_url:
                        return video_url
                        
            logger.warning(f"Could not get video URL for HeyGen ID: {heygen_video_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting video URL from HeyGen: {e}")
            return None
    
    def get_user_videos_with_urls(self, user_id: int) -> List[Dict]:
        """Get user videos with refreshed URLs - FIXED for video_path"""
        try:
            # Direct SQL query to get videos
            conn = psycopg2.connect(os.getenv('DATABASE_URL'))
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute("""
                SELECT id, title, thumbnail_url, duration, created_at, heygen_video_id, 
                       video_path, status, format
                FROM videos 
                WHERE user_id = %s 
                ORDER BY created_at DESC
            """, (user_id,))
            
            videos = cur.fetchall()
            
            # Process each video and refresh URLs if needed
            video_list = []
            for video in videos:
                video_dict = dict(video)
                
                # Format created_at
                if video_dict.get('created_at'):
                    video_dict['created_at'] = video_dict['created_at'].strftime('%b %d, %Y')
                
                # Check and refresh video_path if needed
                if video_dict.get('status') == 'completed':
                    video_path = video_dict.get('video_path')
                    
                    if video_path:
                        # Check if URL might be expired
                        if 'Expires=' in video_path:
                            try:
                                expires_part = video_path.split('Expires=')[1].split('&')[0]
                                expires_timestamp = int(expires_part)
                                current_timestamp = int(time.time())
                                
                                # If URL expires within 24 hours, refresh it
                                if expires_timestamp - current_timestamp < 86400:  # 24 hours
                                    logger.info(f"🔄 Refreshing expired/expiring URL for '{video_dict.get('title')}'")
                                    fresh_url = self.get_video_url_from_heygen(video_dict.get('heygen_video_id'))
                                    if fresh_url:
                                        video_dict['video_path'] = fresh_url
                                        # Update database with fresh URL
                                        cur.execute(
                                            "UPDATE videos SET video_path = %s WHERE id = %s",
                                            (fresh_url, video_dict['id'])
                                        )
                                        conn.commit()
                                        logger.info(f"✅ Updated video URL in database for '{video_dict.get('title')}'")
                            except (ValueError, IndexError) as e:
                                logger.warning(f"⚠️ Could not parse expiry from URL: {e}")
                    else:
                        # No video_path, try to get one from HeyGen
                        if video_dict.get('heygen_video_id'):
                            logger.info(f"🔄 Getting fresh URL for '{video_dict.get('title')}'")
                            fresh_url = self.get_video_url_from_heygen(video_dict.get('heygen_video_id'))
                            if fresh_url:
                                video_dict['video_path'] = fresh_url
                                # Update database
                                cur.execute(
                                    "UPDATE videos SET video_path = %s WHERE id = %s",
                                    (fresh_url, video_dict['id'])
                                )
                                conn.commit()
                                logger.info(f"✅ Added fresh video URL to database for '{video_dict.get('title')}'")
                
                video_list.append(video_dict)
            
            conn.close()
            return video_list
            
        except Exception as e:
            logger.error(f"Error getting user videos: {e}")
            return []
    
    def get_completed_videos_api(self, user_id: int) -> Dict:
        """Get only completed videos with URLs for API"""
        try:
            conn = psycopg2.connect(os.getenv('DATABASE_URL'))
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute("""
                SELECT id, title, thumbnail_url, duration, created_at, heygen_video_id, video_path
                FROM videos 
                WHERE user_id = %s 
                AND status = 'completed' 
                AND video_path IS NOT NULL 
                AND video_path != ''
                ORDER BY created_at DESC
            """, (user_id,))
            
            videos = cur.fetchall()
            
            # Convert to dict and format dates
            video_list = []
            for video in videos:
                video_dict = dict(video)
                if video_dict.get('created_at'):
                    video_dict['created_at'] = video_dict['created_at'].strftime('%b %d, %Y')
                
                # Refresh URL if needed
                if video_dict.get('video_path'):
                    video_url = video_dict['video_path']
                    if 'Expires=' in video_url:
                        try:
                            expires_part = video_url.split('Expires=')[1].split('&')[0]
                            expires_timestamp = int(expires_part)
                            current_timestamp = int(time.time())
                            
                            if expires_timestamp - current_timestamp < 86400:  # 24 hours
                                fresh_url = self.get_video_url_from_heygen(video_dict.get('heygen_video_id'))
                                if fresh_url:
                                    video_dict['video_path'] = fresh_url
                                    cur.execute(
                                        "UPDATE videos SET video_path = %s WHERE id = %s",
                                        (fresh_url, video_dict['id'])
                                    )
                                    conn.commit()
                        except (ValueError, IndexError):
                            pass
                
                video_list.append(video_dict)
            
            conn.close()
            
            return {
                "videos": video_list,
                "count": len(video_list),
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Error fetching completed videos: {e}")
            return {"videos": [], "count": 0, "error": str(e)}
    
    def update_video_status(self, video_id: int, status: str, video_path: str = None) -> bool:
        """Update video status and optionally the video path"""
        try:
            if video_path:
                result = execute_query(
                    "UPDATE videos SET status = %s, video_path = %s WHERE id = %s",
                    (status, video_path, video_id)
                )
            else:
                result = execute_query(
                    "UPDATE videos SET status = %s WHERE id = %s",
                    (status, video_id)
                )
            
            if result is not None:
                logger.info(f"✅ Updated video {video_id} status to {status}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error updating video status: {e}")
            return False
    
    def create_video_record(self, user_id: int, video_data: Dict) -> Optional[int]:
        """Create a new video record in the database"""
        try:
            insert_query = """
            INSERT INTO videos (user_id, title, heygen_video_id, status, video_path, thumbnail_url, duration, format, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """
            
            result = execute_query(
                insert_query,
                (
                    user_id,
                    video_data.get('title', 'Untitled Video'),
                    video_data.get('heygen_video_id'),
                    video_data.get('status', 'pending'),
                    video_data.get('video_path'),
                    video_data.get('thumbnail_url'),
                    video_data.get('duration'),
                    video_data.get('format', '16:9'),
                    video_data.get('created_at', 'now()')
                ),
                fetch_one=True
            )
            
            if result:
                video_id = result.get('id')
                logger.info(f"✅ Created video record: {video_id}")
                return video_id
            
            return None
            
        except Exception as e:
            logger.error(f"Error creating video record: {e}")
            return None

# Global video service instance
video_service = VideoService()