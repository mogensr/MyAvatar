# Enhanced HeyGen Voice Manager with API-based avatar type detection
# app/services/claude_voice_manager.py

import logging
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class HeyGenVoiceManager:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('HEYGEN_API_KEY')
        if not self.api_key:
            logger.error("HEYGEN_API_KEY not found in environment variables or parameters")
            raise ValueError("HEYGEN_API_KEY is required")
    
    def get_best_voice_for_user(self, user_id: int, heygen_avatar_id: str) -> str:
        """
        Enhanced voice selection based on actual avatar type from HeyGen API
        
        Args:
            user_id: The user's ID for personal voice lookup
            heygen_avatar_id: The HeyGen avatar ID to check type for
            
        Returns:
            str: The best voice ID to use for this user and avatar combination
        """
        try:
            logger.info(f"Determining best voice for user {user_id} with avatar {heygen_avatar_id}")
            
            # Get avatar type from HeyGen API
            avatar_info = self._get_avatar_type_from_api(heygen_avatar_id)
            avatar_type = avatar_info.get("type", "unknown")
            
            logger.info(f"Avatar {heygen_avatar_id} detected as type: {avatar_type}")
            
            # Cloned avatars (photo/talking photo) should use user's personal voice
            if avatar_type in ["photo", "talking_photo", "group_photo", "instant_avatar"]:
                logger.info(f"Avatar type '{avatar_type}' detected - using personal voice")
                personal_voice = self._get_user_personal_voice(user_id)
                
                if personal_voice:
                    logger.info(f"Found personal voice {personal_voice} for user {user_id}")
                    return "1bd001e7e50f421d891986aad5158bc8"
                else:
                    logger.warning(f"No personal voice found for user {user_id}, falling back to default")
                    return self._get_fallback_voice_for_cloned()
            
            # Pre-built avatars use language mapping
            elif avatar_type in ["avatar", "public_avatar", "studio_avatar"]:
                logger.info(f"Avatar type '{avatar_type}' detected - using language mapping")
                
                # Get user's preferred language or detect from avatar
                user_language = self._get_user_language_preference(user_id)
                avatar_language = avatar_info.get("language", "en")
                
                # Prioritize user language, fall back to avatar language
                target_language = user_language or avatar_language or "en"
                
                language_voice = self._get_voice_for_language(target_language, avatar_info)
                logger.info(f"Selected language voice {language_voice} for language {target_language}")
                
                return language_voice
            
            else:
                logger.warning(f"Unknown avatar type '{avatar_type}' for avatar {heygen_avatar_id}")
                # Default to language mapping for unknown types
                return self._get_voice_for_language("en")
                
        except Exception as e:
            logger.error(f"Error determining voice for user {user_id}, avatar {heygen_avatar_id}: {str(e)}")
            # Fall back to safe default
            return self._get_emergency_fallback_voice()
    
    def _get_avatar_type_from_api(self, heygen_avatar_id: str) -> Dict[str, Any]:
        """
        Get avatar information and type from HeyGen API
        """
        try:
            # Import the API function
            from ..api.heygen import get_avatar_from_any_endpoint
            
            logger.info(f"Fetching avatar info for {heygen_avatar_id} from HeyGen API")
            avatar_info = get_avatar_from_any_endpoint(self.api_key, heygen_avatar_id)
            
            if avatar_info and not avatar_info.get("error"):
                logger.info(f"Successfully retrieved avatar info: {json.dumps(avatar_info, indent=2)}")
                return avatar_info
            else:
                logger.error(f"HeyGen API returned error for avatar {heygen_avatar_id}: {avatar_info}")
                return {"type": "unknown", "error": "api_error"}
                
        except ImportError as e:
            logger.error(f"Could not import HeyGen API function: {e}")
            return {"type": "unknown", "error": "import_error"}
        except Exception as e:
            logger.error(f"Error fetching avatar info from HeyGen API: {e}")
            return {"type": "unknown", "error": str(e)}
    
    def _get_user_personal_voice(self, user_id: int) -> Optional[str]:
        """
        Get user's personal cloned voice from database
        """
        try:
            from ..db.database import execute_query
            
            # Look for user's personal voice
            result = execute_query(
                "SELECT heygen_voice_id FROM users WHERE id = %s",
                (user_id,),
                fetch_one=True
            )
            
            if result and result.get("heygen_voice_id"):
                voice_id = result.get("heygen_voice_id")
                logger.info(f"Found personal voice {voice_id} for user {user_id}")
                return voice_id
            else:
                logger.info(f"No personal voice found for user {user_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting personal voice for user {user_id}: {e}")
            return None
    
    def _get_user_language_preference(self, user_id: int) -> Optional[str]:
        """
        Get user's language preference from database
        """
        try:
            from ..db.database import execute_query
            
            result = execute_query(
                "SELECT language_preference FROM user_preferences WHERE user_id = %s",
                (user_id,),
                fetch_one=True
            )
            
            return result.get("language_preference") if result else None
            
        except Exception as e:
            logger.error(f"Error getting language preference for user {user_id}: {e}")
            return None
    
    def _get_voice_for_language(self, language: str, avatar_info: Dict = None) -> str:
        """
        Get appropriate voice for a given language
        Enhanced with avatar-specific voice matching
        """
        # Language to voice mapping with gender considerations
        language_voice_map = {
            "en": {
                "male": ["4c7b2d9f6e3a5c8b1f4e7a9d2c5f8e1b", "5d8c3e1a7f4b6c9e2f5a8d1c4f7e9b2a", "6e9d4f2b8c5a7d1e3f6b9c2e5a8f1d4c"],
                "female": ["1bd001e7e50f421d891986aad5158bc8", "2d5b0e6c4c8f4f1b9e7a3d2f8c9e1a4b", "3f6a1c8e5d2f4b9c7e8a2d5f1c4e9b7a"],
                "default": "1bd001e7e50f421d891986aad5158bc8"
            },
            "es": {
                "male": ["4c7b2d9f6e3a5c8b1f4e7a9d2c5f8e1b", "5d8c3e1a7f4b6c9e2f5a8d1c4f7e9b2a"],
                "female": ["7f1e5c9b3d6a8f2c4e7b1d5a9c3f6e8b", "8c2f6d1a4e7c9f3b5d8a2f6c1e4b7d9a"], 
                "default": "7f1e5c9b3d6a8f2c4e7b1d5a9c3f6e8b"
            },
            "fr": {
                "male": ["1a4e8c2f6d9b3a7e1c5f8d2b4a7c9e3f", "2b5f9d3a8c1e4f7b2d6a9c4e8f1b5d7a"],
                "female": ["9d3a7f2e5c8b1f4d6a9c3e7f2b5d8a1c", "3c6e1a9f4d7b2e5a8c1f6d9b4e7a3c5f"],
                "default": "9d3a7f2e5c8b1f4d6a9c3e7f2b5d8a1c"
            },
            "de": {
                "male": ["4d7a2e9c5f8b1d4a7c2e6f9b3d5a8c1e", "5e8b3f1a6c9d2e5b8f1a4c7d9e2b5f8a"],
                "female": ["6f9c4a2d7e1b5f8c4a7d2e9b6f3a5c8d", "7a1d5c8f2b6a9d4c7f1e5b8a2d6c9f4a"],
                "default": "6f9c4a2d7e1b5f8c4a7d2e9b6f3a5c8d"
            }
        }
        
        # Try to match avatar gender if available
        if avatar_info:
            avatar_gender = avatar_info.get("gender", "").lower()
            if language in language_voice_map and avatar_gender in ["male", "female"]:
                voices = language_voice_map[language][avatar_gender]
                if voices:
                    selected_voice = voices[0]  # Use first option
                    logger.info(f"Selected {avatar_gender} voice {selected_voice} for language {language}")
                    return selected_voice
        
        # Fall back to default for language
        if language in language_voice_map:
            return language_voice_map[language]["default"]
        
        # Ultimate fallback
        logger.warning(f"No voice mapping found for language {language}, using default")
        return "1bd001e7e50f421d891986aad5158bc8"
    
    def _get_fallback_voice_for_cloned(self) -> str:
        """
        Get fallback voice when user should have personal voice but doesn't
        """
        return "1bd001e7e50f421d891986aad5158bc8"  # Neutral, pleasant default
    
    def _get_emergency_fallback_voice(self) -> str:
        """
        Emergency fallback voice for any error conditions
        """
        return "1bd001e7e50f421d891986aad5158bc8"
