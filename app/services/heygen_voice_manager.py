# Enhanced HeyGen Voice Manager with API-based avatar type detection
# app/services/heygen_voice_manager.py

import logging
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class AvatarType(Enum):
    """Avatar type enumeration"""
    PUBLIC_HEYGEN = "public_heygen"
    IMAGE_TO_AVATAR = "image_to_avatar" 
    CLONED_AVATAR = "cloned_avatar"
    CUSTOM_AVATAR = "custom_avatar"
    TALKING_PHOTO = "talking_photo"

class VoiceType(Enum):
    """Voice type enumeration"""
    CLONED = "cloned"
    PUBLIC_HEYGEN = "public_heygen"
    LANGUAGE_DEFAULT = "language_default"

@dataclass
class VoiceAssignmentResult:
    """Voice assignment result structure"""
    voice_id: str
    voice_type: str
    source: str
    confidence: str
    is_fallback: bool = False
    avatar_type: str = None
    warning: str = None

class HeyGenVoiceManager:
    """
    Comprehensive voice management for all HeyGen avatar types
    Uses existing MyAvatar database schema with users.heygen_voice_id
    """
    
    def __init__(self, db_connection, heygen_api_key: str):
        """
        Initialize the voice manager
        
        Args:
            db_connection: Database connection object
            heygen_api_key: HeyGen API key for validation
        """
        self.db = db_connection
        self.heygen_api_key = heygen_api_key
        self.heygen_base_url = "https://api.heygen.com/v2"
        self.voice_cache = {}
        self.cache_expiry = {}
        
        # Default language-to-voice mapping for public avatars
        self.language_voice_map = {
            "en": "1bd001e7e50f421d891986aad5158bc8",
            "da": "1bd001e7e50f421d891986aad5158bc8", 
            "es": "1bd001e7e50f421d891986aad5158bc8",
            "fr": "1bd001e7e50f421d891986aad5158bc8",
            "de": "1bd001e7e50f421d891986aad5158bc8",
            "it": "1bd001e7e50f421d891986aad5158bc8",
            "pt": "1bd001e7e50f421d891986aad5158bc8",
            "ja": "1bd001e7e50f421d891986aad5158bc8",
            "ko": "1bd001e7e50f421d891986aad5158bc8",
            "zh": "1bd001e7e50f421d891986aad5158bc8"
        }
        
    def get_voice_id_for_avatar(self, user_id: int, avatar_id: str, 
                                language: str = "en", 
                                context: Dict = None) -> VoiceAssignmentResult:
        """
        Main method to get the appropriate voice ID for any avatar type
        
        Args:
            user_id: User identifier
            avatar_id: Avatar identifier
            language: Target language code
            context: Additional context (e.g., use_cloned_voice preference)
            
        Returns:
            VoiceAssignmentResult with voice_id and metadata
        """
        try:
            logger.info(f"🎯 Getting voice ID for user {user_id}, avatar {avatar_id}, language {language}")
            
            # Step 1: Get avatar metadata from database
            avatar_metadata = self._get_avatar_metadata(avatar_id, user_id)
            
            # Step 2: Determine avatar type and voice assignment strategy
            avatar_type = self._classify_avatar_type(avatar_metadata, avatar_id)
            
            # Step 3: Get voice based on avatar type and user preferences
            voice_result = self._determine_voice_for_avatar_type(
                avatar_type, avatar_metadata, user_id, language, context
            )
            
            # Step 4: Validate the selected voice (with caching)
            if voice_result.voice_id:
                is_valid = self._validate_voice_id_cached(voice_result.voice_id)
                if not is_valid:
                    logger.warning(f"Voice {voice_result.voice_id} validation failed, using fallback")
                    voice_result = self._get_fallback_voice(language)
            
            # Step 5: Log the assignment for debugging
            self._log_voice_assignment(user_id, avatar_id, voice_result)
            
            logger.info(f"✅ Voice assignment complete: {voice_result.voice_id} ({voice_result.source})")
            return voice_result
            
        except Exception as e:
            logger.error(f"❌ Error getting voice ID: {str(e)}")
            return self._get_fallback_voice(language)
    
    def _get_avatar_metadata(self, avatar_id: str, user_id: int) -> Optional[Dict]:
        """
        Get avatar metadata from database
        """
        try:
            # Query user_avatars table for avatar metadata
            query = """
            SELECT 
                ua.avatar_id,
                ua.user_id,
                ua.avatar_name,
                ua.avatar_image_url,
                ua.heygen_avatar_id,
                ua.is_custom,
                ua.created_at,
                u.heygen_voice_id as user_voice_id
            FROM user_avatars ua
            LEFT JOIN users u ON ua.user_id = u.id
            WHERE ua.avatar_id = %s
            """
            
            from ..db.database import execute_query
            result = execute_query(query, (avatar_id,))
            
            if result and len(result) > 0:
                return result[0]
            else:
                logger.warning(f"Avatar {avatar_id} not found in database")
                return None
                
        except Exception as e:
            logger.error(f"Error getting avatar metadata: {str(e)}")
            return None
    
    def _classify_avatar_type(self, avatar_metadata: Optional[Dict], avatar_id: str) -> AvatarType:
        """
        Classify the avatar type based on metadata and ID patterns
        """
        if not avatar_metadata:
            # If not in database, assume it's a public HeyGen avatar
            return AvatarType.PUBLIC_HEYGEN
        
        # Check if it's marked as custom in database
        if avatar_metadata.get('is_custom'):
            return AvatarType.CUSTOM_AVATAR
        
        # Check if it has a user_id (user-owned)
        if avatar_metadata.get('user_id'):
            return AvatarType.IMAGE_TO_AVATAR
        
        # Default to public avatar
        return AvatarType.PUBLIC_HEYGEN
    
    def _determine_voice_for_avatar_type(self, avatar_type: AvatarType, 
                                        avatar_metadata: Optional[Dict],
                                        user_id: int, language: str, 
                                        context: Dict = None) -> VoiceAssignmentResult:
        """
        Determine the appropriate voice based on avatar type
        """
        context = context or {}
        
        # Handle custom/cloned avatars - always use user's cloned voice
        if avatar_type in [AvatarType.CUSTOM_AVATAR, AvatarType.CLONED_AVATAR]:
            return self._handle_custom_avatar_voice(user_id)
        
        # Handle image-to-avatar - can use cloned or default based on preference
        elif avatar_type == AvatarType.IMAGE_TO_AVATAR:
            return self._handle_image_to_avatar_voice(user_id, language, context)
        
        # Handle public avatars - use default language mapping
        else:  # PUBLIC_HEYGEN, TALKING_PHOTO
            return self._handle_public_avatar_voice(language, avatar_metadata)
    
    def _handle_custom_avatar_voice(self, user_id: int) -> VoiceAssignmentResult:
        """
        Handle voice for custom/cloned avatars - always use user's cloned voice
        """
        user_voice_id = self._get_user_cloned_voice(user_id)
        
        if user_voice_id:
            return VoiceAssignmentResult(
                voice_id=user_voice_id,
                voice_type=VoiceType.CLONED.value,
                source="user_cloned_voice",
                confidence="high",
                avatar_type=AvatarType.CUSTOM_AVATAR.value
            )
        else:
            logger.warning(f"User {user_id} has custom avatar but no cloned voice")
            return VoiceAssignmentResult(
                voice_id=self.language_voice_map.get("en", "1bd001e7e50f421d891986aad5158bc8"),
                voice_type=VoiceType.LANGUAGE_DEFAULT.value,
                source="fallback_no_cloned_voice",
                confidence="low",
                is_fallback=True,
                warning="Custom avatar but no cloned voice available"
            )
    
    def _handle_image_to_avatar_voice(self, user_id: int, language: str, 
                                     context: Dict) -> VoiceAssignmentResult:
        """
        Handle voice for image-to-avatar - can use cloned or default
        """
        # Check if user explicitly wants to use their cloned voice
        if context.get('use_cloned_voice'):
            user_voice_id = self._get_user_cloned_voice(user_id)
            if user_voice_id:
                return VoiceAssignmentResult(
                    voice_id=user_voice_id,
                    voice_type=VoiceType.CLONED.value,
                    source="user_preference_cloned",
                    confidence="high",
                    avatar_type=AvatarType.IMAGE_TO_AVATAR.value
                )
        
        # Default to language-appropriate voice
        return self._handle_public_avatar_voice(language, None)
    
    def _handle_public_avatar_voice(self, language: str, 
                                   avatar_metadata: Optional[Dict]) -> VoiceAssignmentResult:
        """
        Handle voice for public avatars - use language defaults
        """
        # Try to get language-specific voice
        voice_id = self.language_voice_map.get(language, self.language_voice_map.get("en"))
        
        return VoiceAssignmentResult(
            voice_id=voice_id,
            voice_type=VoiceType.PUBLIC_HEYGEN.value,
            source="language_default",
            confidence="medium",
            avatar_type=AvatarType.PUBLIC_HEYGEN.value
        )
    
    def _get_user_cloned_voice(self, user_id: int) -> Optional[str]:
        """
        Get user's cloned voice ID from users table
        """
        try:
            query = "SELECT heygen_voice_id FROM users WHERE id = %s AND heygen_voice_id IS NOT NULL"
            
            from ..db.database import execute_query
            result = execute_query(query, (user_id,))
            
            if result and len(result) > 0 and result[0].get('heygen_voice_id'):
                voice_id = result[0]['heygen_voice_id']
                logger.info(f"✅ Found user {user_id} cloned voice: {voice_id}")
                return voice_id
            else:
                logger.info(f"No cloned voice found for user {user_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting user cloned voice: {str(e)}")
            return None
    
    def _validate_voice_id_cached(self, voice_id: str) -> bool:
        """
        Validate voice with HeyGen API (with 1-hour caching)
        """
        # Check cache first
        if voice_id in self.voice_cache:
            if datetime.now() < self.cache_expiry.get(voice_id, datetime.now()):
                return self.voice_cache[voice_id]
        
        # Validate with HeyGen API
        is_valid = self._validate_voice_with_heygen(voice_id)
        
        # Cache for 1 hour
        self.voice_cache[voice_id] = is_valid
        self.cache_expiry[voice_id] = datetime.now() + timedelta(hours=1)
        
        return is_valid
    
    def _validate_voice_with_heygen(self, voice_id: str) -> bool:
        """
        Validate voice exists in HeyGen API
        """
        try:
            headers = {
                "X-Api-Key": self.heygen_api_key,
                "Content-Type": "application/json"
            }
            
            # Try to get voice details
            response = requests.get(
                f"{self.heygen_base_url}/voices/{voice_id}",
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Voice {voice_id} validated successfully")
                return True
            else:
                logger.warning(f"⚠️ Voice {voice_id} validation failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error validating voice {voice_id}: {str(e)}")
            return False
    
    def _get_fallback_voice(self, language: str) -> VoiceAssignmentResult:
        """
        Get fallback voice when all else fails
        """
        fallback_voice = self.language_voice_map.get(language, "1bd001e7e50f421d891986aad5158bc8")
        
        return VoiceAssignmentResult(
            voice_id=fallback_voice,
            voice_type=VoiceType.LANGUAGE_DEFAULT.value,
            source="system_fallback",
            confidence="lowest",
            is_fallback=True,
            warning="Using system fallback voice"
        )
    
    def _log_voice_assignment(self, user_id: int, avatar_id: str, 
                             voice_result: VoiceAssignmentResult):
        """
        Log voice assignment for debugging and analytics
        """
        try:
            # Create voice_assignment_log table if it doesn't exist
            create_table_query = """
            CREATE TABLE IF NOT EXISTS voice_assignment_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                avatar_id TEXT,
                assigned_voice_id TEXT,
                voice_type TEXT,
                source TEXT,
                confidence TEXT,
                is_fallback BOOLEAN,
                avatar_type TEXT,
                warning TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            
            from ..db.database import execute_query
            execute_query(create_table_query)
            
            # Insert log entry
            insert_query = """
            INSERT INTO voice_assignment_log 
            (user_id, avatar_id, assigned_voice_id, voice_type, source, confidence, is_fallback, avatar_type, warning)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            execute_query(insert_query, (
                user_id,
                avatar_id,
                voice_result.voice_id,
                voice_result.voice_type,
                voice_result.source,
                voice_result.confidence,
                voice_result.is_fallback,
                voice_result.avatar_type,
                voice_result.warning
            ))
            
        except Exception as e:
            logger.error(f"Error logging voice assignment: {str(e)}")
    
    def diagnose_voice_issue(self, user_id: int, avatar_id: str) -> Dict[str, Any]:
        """
        Diagnostic function to troubleshoot voice assignment issues
        """
        try:
            logger.info(f"🔍 Diagnosing voice issue for user {user_id}, avatar {avatar_id}")
            
            # Get avatar metadata
            avatar_metadata = self._get_avatar_metadata(avatar_id, user_id)
            avatar_type = self._classify_avatar_type(avatar_metadata, avatar_id)
            
            # Get user's cloned voice
            user_voice_id = self._get_user_cloned_voice(user_id)
            
            # Get recent assignments
            recent_assignments = self._get_recent_voice_assignments(avatar_id)
            
            diagnosis = {
                "avatar_id": avatar_id,
                "user_id": user_id,
                "avatar_metadata": avatar_metadata,
                "avatar_type": avatar_type.value if avatar_type else None,
                "user_cloned_voice": user_voice_id,
                "recent_assignments": recent_assignments,
                "timestamp": datetime.now().isoformat()
            }
            
            # Print diagnosis
            print(f"\n🔍 VOICE ASSIGNMENT DIAGNOSIS")
            print(f"Avatar ID: {avatar_id}")
            print(f"User ID: {user_id}")
            print(f"Avatar Type: {avatar_type.value if avatar_type else 'Unknown'}")
            print(f"User Cloned Voice: {user_voice_id or 'None'}")
            print(f"Avatar in Database: {'Yes' if avatar_metadata else 'No'}")
            print(f"Is Custom: {avatar_metadata.get('is_custom') if avatar_metadata else 'N/A'}")
            print(f"Recent Assignments: {len(recent_assignments)}")
            
            for assignment in recent_assignments[:3]:
                print(f"  - {assignment.get('assigned_voice_id')} ({assignment.get('source')}) - {assignment.get('created_at')}")
            
            return diagnosis
            
        except Exception as e:
            logger.error(f"Error in voice diagnosis: {str(e)}")
            return {"error": str(e)}
    
    def _get_recent_voice_assignments(self, avatar_id: str, limit: int = 5) -> list:
        """
        Get recent voice assignments for an avatar
        """
        try:
            query = """
            SELECT * FROM voice_assignment_log 
            WHERE avatar_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
            """
            
            from ..db.database import execute_query
            result = execute_query(query, (avatar_id, limit))
            return result or []
            
        except Exception as e:
            logger.error(f"Error getting recent assignments: {str(e)}")
            return []
