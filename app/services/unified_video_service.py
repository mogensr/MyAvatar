"""
Unified Video Creation Service for MyAvatar
==========================================
Single source of truth for all video creation functionality
Handles both text-to-video and voice-to-video with consistent avatar management
"""

import logging
import os
import json
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

# Import database and logging
from ..db.database import execute_query
from ..logger.log_handler import log_info, log_error, log_warning

logger = logging.getLogger("UnifiedVideoService")

class UnifiedVideoService:
    """
    Unified service for all MyAvatar video creation functionality
    
    Features:
    - Consistent avatar management across all video types
    - Unified authentication and validation
    - Single HeyGen integration point
    - Standardized error handling and logging
    """
    
    def __init__(self):
        self.heygen_api_key = os.getenv("HEYGEN_API_KEY")
        self.heygen_base_url = "https://api.heygen.com/v2"
        
        # Fallback avatar for when no avatars are available
        self.fallback_avatar = {
            'id': 'fallback',
            'name': 'Default Avatar',
            'avatar_name': 'Default Avatar',
            'avatar_image_url': '/static/images/default-avatar.jpg',
            'heygen_avatar_id': 'default',
            'avatar_id': 'default',
            'is_default': True,
            'status': 'active'
        }
    
    def get_user_avatars_unified(self, user_id: int) -> List[Dict]:
        """
        Get user avatars with unified, consistent field mapping
        This is the single source of truth for avatar data across the entire system
        """
        try:
            log_info(f"Getting avatars for user {user_id} (unified method)", "UnifiedVideoService")
            
            # Use the EXACT same query that works in admin panel
            avatars_query = """
            SELECT id, avatar_name, avatar_image_url, avatar_id, heygen_avatar_id, is_default, created_at 
            FROM user_avatars 
            WHERE user_id = %s 
            ORDER BY created_at DESC
            """
            
            raw_avatars = execute_query(avatars_query, (user_id,), fetch_all=True)
            log_info(f"Found {len(raw_avatars) if raw_avatars else 0} raw avatars for user {user_id}", "UnifiedVideoService")
            
            processed_avatars = []
            
            if raw_avatars:
                for i, avatar in enumerate(raw_avatars):
                    try:
                        # Handle different data formats (dict vs named tuple)
                        if hasattr(avatar, '_asdict'):
                            avatar_dict = avatar._asdict()
                        else:
                            avatar_dict = dict(avatar)
                        
                        # UNIFIED field mapping - consistent across entire system
                        processed_avatar = {
                            'id': avatar_dict.get('id'),
                            'name': avatar_dict.get('avatar_name', f'Avatar {i+1}'),  # For templates
                            'avatar_name': avatar_dict.get('avatar_name', f'Avatar {i+1}'),  # For admin consistency
                            'avatar_image_url': avatar_dict.get('avatar_image_url', '/static/images/default-avatar.jpg'),
                            'heygen_avatar_id': avatar_dict.get('heygen_avatar_id', ''),  # Critical for HeyGen API
                            'avatar_id': avatar_dict.get('avatar_id', ''),  # Additional ID field
                            'is_default': bool(avatar_dict.get('is_default', False)),
                            'created_at': avatar_dict.get('created_at', ''),
                            'status': 'active'  # Always active for video creation
                        }
                        
                        # Only include avatars with valid data
                        if processed_avatar['id'] and processed_avatar['avatar_name']:
                            processed_avatars.append(processed_avatar)
                            
                    except Exception as process_error:
                        log_warning(f"Failed to process avatar {i} for user {user_id}: {process_error}", "UnifiedVideoService")
                        continue
            
            # Always provide at least one avatar (fallback)
            if not processed_avatars:
                log_info(f"No avatars found for user {user_id}, providing fallback avatar", "UnifiedVideoService")
                processed_avatars = [self.fallback_avatar.copy()]
            
            log_info(f"Returning {len(processed_avatars)} processed avatars for user {user_id}", "UnifiedVideoService")
            return processed_avatars
            
        except Exception as e:
            log_error(f"Avatar query failed for user {user_id}: {e}", "UnifiedVideoService")
            # Always return fallback to prevent system failure
            return [self.fallback_avatar.copy()]
    
    def validate_avatar_selection(self, user_id: int, avatar_id: str, heygen_avatar_id: str = None) -> Optional[Dict]:
        """
        Validate that the selected avatar belongs to the user and return avatar data
        """
        try:
            user_avatars = self.get_user_avatars_unified(user_id)
            
            for avatar in user_avatars:
                # Match by either avatar ID or HeyGen avatar ID
                if (str(avatar['id']) == str(avatar_id) or 
                    str(avatar.get('heygen_avatar_id', '')) == str(heygen_avatar_id) or
                    str(avatar.get('avatar_id', '')) == str(avatar_id)):
                    
                    log_info(f"Avatar validation successful for user {user_id}: {avatar['avatar_name']}", "UnifiedVideoService")
                    return avatar
            
            log_error(f"Avatar validation failed for user {user_id} - ID: {avatar_id}, HeyGen: {heygen_avatar_id}", "UnifiedVideoService")
            return None
            
        except Exception as e:
            log_error(f"Avatar validation error for user {user_id}: {e}", "UnifiedVideoService")
            return None
    
    async def create_text_video_unified(self, user_id: int, text: str, avatar_id: str, title: str = None, video_format: str = "16:9") -> Dict:
        """
        Create text-to-video using unified system
        """
        try:
            log_info(f"Creating text video for user {user_id} with avatar {avatar_id}", "UnifiedVideoService")
            
            # Validate avatar
            selected_avatar = self.validate_avatar_selection(user_id, avatar_id)
            if not selected_avatar:
                return {
                    "success": False,
                    "error": "Invalid avatar selection"
                }
            
            # Set default title
            if not title:
                title = f"Text Video - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            
            # Prepare HeyGen API request
            heygen_avatar_id = selected_avatar.get('heygen_avatar_id') or selected_avatar.get('avatar_id')
            
            heygen_request = {
                "video_inputs": [{
                    "character": {
                        "type": "avatar",
                        "avatar_id": heygen_avatar_id
                    },
                    "voice": {
                        "type": "text",
                        "input_text": text
                    }
                }],
                "dimension": {
                    "width": 1920 if video_format == "16:9" else 1080,
                    "height": 1080
                },
                "aspect_ratio": video_format
            }
            
            # Call HeyGen API
            result = await self._call_heygen_api("/video/generate", heygen_request)
            
            if result.get("success"):
                # Save video metadata to database
                video_id = await self._save_video_metadata({
                    "user_id": user_id,
                    "title": title,
                    "description": f"Text-to-video created with {selected_avatar['avatar_name']}",
                    "avatar_id": selected_avatar['id'],
                    "heygen_video_id": result.get("video_id"),
                    "status": "processing",
                    "video_type": "text",
                    "input_text": text,
                    "video_format": video_format
                })
                
                return {
                    "success": True,
                    "video_id": video_id,
                    "heygen_video_id": result.get("video_id"),
                    "status": "processing",
                    "avatar_name": selected_avatar['avatar_name'],
                    "estimated_duration": "2-5 minutes"
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "HeyGen API call failed")
                }
                
        except Exception as e:
            log_error(f"Text video creation failed for user {user_id}: {e}", "UnifiedVideoService")
            return {
                "success": False,
                "error": f"Video creation failed: {str(e)}"
            }
    
    async def create_voice_video_unified(self, user_id: int, audio_file, avatar_id: str, title: str = None) -> Dict:
        """
        Create voice-to-video using unified system
        """
        try:
            log_info(f"Creating voice video for user {user_id} with avatar {avatar_id}", "UnifiedVideoService")
            
            # Validate avatar
            selected_avatar = self.validate_avatar_selection(user_id, avatar_id)
            if not selected_avatar:
                return {
                    "success": False,
                    "error": "Invalid avatar selection"
                }
            
            # Set default title
            if not title:
                title = f"Voice Video - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            
            # Process audio file (save temporarily)
            audio_path = await self._save_temp_audio(audio_file)
            
            # Prepare HeyGen API request
            heygen_avatar_id = selected_avatar.get('heygen_avatar_id') or selected_avatar.get('avatar_id')
            
            heygen_request = {
                "video_inputs": [{
                    "character": {
                        "type": "avatar",
                        "avatar_id": heygen_avatar_id
                    },
                    "voice": {
                        "type": "audio",
                        "audio_url": audio_path  # Or upload to HeyGen
                    }
                }],
                "dimension": {
                    "width": 1920,
                    "height": 1080
                }
            }
            
            # Call HeyGen API
            result = await self._call_heygen_api("/video/generate", heygen_request)
            
            if result.get("success"):
                # Save video metadata to database
                video_id = await self._save_video_metadata({
                    "user_id": user_id,
                    "title": title,
                    "description": f"Voice-to-video created with {selected_avatar['avatar_name']}",
                    "avatar_id": selected_avatar['id'],
                    "heygen_video_id": result.get("video_id"),
                    "status": "processing",
                    "video_type": "voice",
                    "audio_path": audio_path
                })
                
                return {
                    "success": True,
                    "video_id": video_id,
                    "heygen_video_id": result.get("video_id"),
                    "status": "processing",
                    "avatar_name": selected_avatar['avatar_name'],
                    "estimated_duration": "3-7 minutes"
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "HeyGen API call failed")
                }
                
        except Exception as e:
            log_error(f"Voice video creation failed for user {user_id}: {e}", "UnifiedVideoService")
            return {
                "success": False,
                "error": f"Video creation failed: {str(e)}"
            }
    
    async def _call_heygen_api(self, endpoint: str, data: Dict) -> Dict:
        """
        Make API call to HeyGen
        """
        try:
            import aiohttp
            
            headers = {
                "Authorization": f"Bearer {self.heygen_api_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.heygen_base_url}{endpoint}",
                    json=data,
                    headers=headers
                ) as response:
                    result = await response.json()
                    
                    if response.status == 200:
                        return {
                            "success": True,
                            "video_id": result.get("data", {}).get("video_id"),
                            "data": result
                        }
                    else:
                        return {
                            "success": False,
                            "error": result.get("message", f"API error: {response.status}")
                        }
                        
        except Exception as e:
            log_error(f"HeyGen API call failed: {e}", "UnifiedVideoService")
            return {
                "success": False,
                "error": f"API call failed: {str(e)}"
            }
    
    async def _save_video_metadata(self, video_data: Dict) -> int:
        """
        Save video metadata to database
        """
        try:
            query = """
            INSERT INTO videos (
                user_id, title, description, avatar_id, heygen_video_id, 
                status, video_type, input_text, audio_path, video_format, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """
            
            result = execute_query(
                query,
                (
                    video_data.get("user_id"),
                    video_data.get("title"),
                    video_data.get("description"),
                    video_data.get("avatar_id"),
                    video_data.get("heygen_video_id"),
                    video_data.get("status", "processing"),
                    video_data.get("video_type"),
                    video_data.get("input_text"),
                    video_data.get("audio_path"),
                    video_data.get("video_format", "16:9"),
                    datetime.now()
                ),
                fetch_one=True
            )
            
            video_id = result['id'] if result else None
            log_info(f"Video metadata saved with ID: {video_id}", "UnifiedVideoService")
            return video_id
            
        except Exception as e:
            log_error(f"Failed to save video metadata: {e}", "UnifiedVideoService")
            raise
    
    async def _save_temp_audio(self, audio_file) -> str:
        """
        Save uploaded audio file temporarily
        """
        try:
            # Create temp directory
            temp_dir = Path("temp_audio")
            temp_dir.mkdir(exist_ok=True)
            
            # Generate unique filename
            filename = f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
            file_path = temp_dir / filename
            
            # Save file
            with open(file_path, "wb") as f:
                content = await audio_file.read()
                f.write(content)
            
            log_info(f"Audio file saved: {file_path}", "UnifiedVideoService")
            return str(file_path)
            
        except Exception as e:
            log_error(f"Failed to save audio file: {e}", "UnifiedVideoService")
            raise

# Global unified service instance
unified_video_service = UnifiedVideoService()
