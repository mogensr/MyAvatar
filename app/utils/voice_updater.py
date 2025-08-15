"""
Voice Updater Module - Automatically updates HeyGen voice IDs
"""
import os
import json
import requests
from datetime import datetime, timedelta
from ..logger.log_handler import log_info, log_error, log_warning
from ..db.database import execute_query

class VoiceUpdater:
    """
    Utility class to automatically update and validate HeyGen voice IDs
    """
    def __init__(self):
        self.api_key = os.getenv("HEYGEN_API_KEY")
        self.voices_cache = {}
        self.last_update = None
        self.language_voice_map = {}
        self.custom_voices = {}
        self.update_interval = timedelta(days=1)  # Check for updates once per day
        
    def fetch_all_voices(self):
        """
        Fetch all available voices from HeyGen API
        """
        if not self.api_key:
            log_error("No HeyGen API key available", "VoiceUpdater")
            return False
            
        headers = {
            "X-Api-Key": self.api_key,
            "Accept": "application/json"
        }
        
        try:
            log_info("Fetching voices from HeyGen API", "VoiceUpdater")
            response = requests.get(
                "https://api.heygen.com/v2/voices",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                voices_data = response.json()
                
                if voices_data.get("error") is None and "data" in voices_data:
                    voices = voices_data["data"].get("voices", [])
                    log_info(f"Found {len(voices)} voices from HeyGen API", "VoiceUpdater")
                    
                    # Cache the voices
                    self.voices_cache = {voice.get("voice_id"): voice for voice in voices}
                    self.last_update = datetime.now()
                    
                    # Process voices by language
                    self._process_voices_by_language(voices)
                    
                    return True
                else:
                    log_error(f"Error in HeyGen API response: {voices_data}", "VoiceUpdater")
            else:
                log_error(f"HeyGen API request failed: {response.status_code}", "VoiceUpdater")
                
        except Exception as e:
            log_error(f"Exception fetching voices: {e}", "VoiceUpdater")
            
        return False
    
    def _process_voices_by_language(self, voices):
        """
        Process voices and organize them by language
        """
        language_voices = {}
        
        # First pass: collect all voices by language
        for voice in voices:
            voice_id = voice.get("voice_id")
            language = voice.get("language")
            name = voice.get("name", "").lower()
            
            # Skip voices without language or ID
            if not language or not voice_id:
                continue
                
            # Check if this is a custom voice
            standard_names = ["sara", "paul", "rex", "angela", "daisy", "monica", "lina", "cheerful", "friendly"]
            is_custom = not any(standard in name for standard in standard_names)
            
            # Special handling for custom voices
            if is_custom:
                if "mogens" in name:
                    self.custom_voices["mogens"] = voice_id
                elif "phønix" in name or "phoenix" in name:
                    self.custom_voices["phoenix"] = voice_id
                    
            # Add to language map
            if language not in language_voices:
                language_voices[language] = []
                
            language_voices[language].append(voice)
        
        # Second pass: select best voice for each language
        for language, voice_list in language_voices.items():
            # Prefer non-custom voices for language mapping
            standard_voices = [v for v in voice_list if not self._is_custom_voice(v)]
            
            if standard_voices:
                # Use first standard voice
                self.language_voice_map[language] = standard_voices[0].get("voice_id")
            elif voice_list:
                # Fall back to any voice if no standard ones
                self.language_voice_map[language] = voice_list[0].get("voice_id")
        
        # Map language codes to standard format
        self._map_language_codes()
        
        log_info(f"Processed {len(self.language_voice_map)} languages", "VoiceUpdater")
        log_info(f"Found {len(self.custom_voices)} custom voices", "VoiceUpdater")
    
    def _is_custom_voice(self, voice):
        """Check if a voice is custom/cloned"""
        name = voice.get("name", "").lower()
        standard_names = ["sara", "paul", "rex", "angela", "daisy", "monica", "lina", "cheerful", "friendly"]
        return not any(standard in name for standard in standard_names)
    
    def _map_language_codes(self):
        """Map language codes to standard format used in the app"""
        # Define mapping of HeyGen language codes to our standard format
        language_code_map = {
            "english": "en-US",
            "british english": "en-GB",
            "danish": "da-DK",
            "german": "de-DE",
            "spanish": "es-ES",
            "french": "fr-FR",
            "italian": "it-IT",
            "japanese": "ja-JP",
            "korean": "ko-KR",
            "dutch": "nl-NL",
            "polish": "pl-PL",
            "portuguese": "pt-BR",
            "russian": "ru-RU",
            "chinese": "zh-CN"
        }
        
        # Create new map with standardized codes
        standardized_map = {}
        
        for lang, voice_id in self.language_voice_map.items():
            lang_lower = lang.lower()
            
            # Try to find a matching standard code
            for heygen_lang, std_code in language_code_map.items():
                if heygen_lang in lang_lower:
                    standardized_map[std_code] = voice_id
                    break
        
        # Special case for Danish - use MogensR's voice ID if available
        if "da-DK" in standardized_map and "mogens" in self.custom_voices:
            standardized_map["da-DK"] = self.custom_voices["mogens"]
            
        self.language_voice_map = standardized_map
    
    def update_language_voice_map_in_service(self):
        """
        Update the language_voice_map in the video_service module
        """
        if not self.language_voice_map:
            log_warning("No language voice map to update", "VoiceUpdater")
            return False
            
        try:
            # Import here to avoid circular imports
            from ..services.video_service import update_language_voice_map
            
            update_language_voice_map(self.language_voice_map)
            log_info("Updated language_voice_map in video_service", "VoiceUpdater")
            return True
        except Exception as e:
            log_error(f"Failed to update language_voice_map in video_service: {e}", "VoiceUpdater")
            return False
    
    def validate_user_voice_ids(self):
        """
        Validate all user voice IDs against HeyGen API
        """
        if not self.voices_cache:
            log_warning("No voices cache available for validation", "VoiceUpdater")
            return False
            
        try:
            # Get all users with voice IDs
            users = execute_query(
                "SELECT id, heygen_voice_id FROM users WHERE heygen_voice_id IS NOT NULL",
                fetch_all=True
            )
            
            if not users:
                log_info("No users with voice IDs found", "VoiceUpdater")
                return True
                
            log_info(f"Validating voice IDs for {len(users)} users", "VoiceUpdater")
            
            # Check each user's voice ID
            for user in users:
                user_id = user.get("id")
                voice_id = user.get("heygen_voice_id")
                
                if not voice_id:
                    continue
                    
                # Check if voice ID exists in HeyGen
                if voice_id not in self.voices_cache:
                    log_warning(f"Invalid voice ID {voice_id} for user {user_id}", "VoiceUpdater")
                    
                    # Try to find a replacement voice
                    replacement_id = self._find_replacement_voice(voice_id)
                    
                    if replacement_id:
                        # Update the user's voice ID
                        execute_query(
                            "UPDATE users SET heygen_voice_id = %s WHERE id = %s",
                            (replacement_id, user_id)
                        )
                        log_info(f"Updated user {user_id} voice ID from {voice_id} to {replacement_id}", "VoiceUpdater")
            
            return True
        except Exception as e:
            log_error(f"Error validating user voice IDs: {e}", "VoiceUpdater")
            return False
    
    def _find_replacement_voice(self, invalid_voice_id):
        """
        Try to find a replacement for an invalid voice ID
        """
        # Special case for MogensR's voice ID
        if invalid_voice_id == "7c47bfa466e24f60a47fce01d2e4ef58":
            if "mogens" in self.custom_voices:
                return self.custom_voices["mogens"]
            elif "da-DK" in self.language_voice_map:
                return self.language_voice_map["da-DK"]
        
        # Default fallback to English
        if "en-US" in self.language_voice_map:
            return self.language_voice_map["en-US"]
            
        # Last resort: use any available voice
        if self.voices_cache:
            return list(self.voices_cache.keys())[0]
            
        return None
    
    def should_update(self):
        """
        Check if we should update the voices based on the update interval
        """
        if not self.last_update:
            return True
            
        return datetime.now() - self.last_update > self.update_interval
    
    def update_if_needed(self):
        """
        Update voices if needed based on the update interval
        """
        if self.should_update():
            success = self.fetch_all_voices()
            
            if success:
                self.update_language_voice_map_in_service()
                self.validate_user_voice_ids()
                
            return success
        
        return False

# Create a singleton instance
voice_updater = VoiceUpdater()

def update_heygen_voices():
    """
    Update HeyGen voices and validate user voice IDs
    """
    return voice_updater.update_if_needed()

def force_update_heygen_voices():
    """
    Force update of HeyGen voices regardless of the update interval
    """
    success = voice_updater.fetch_all_voices()
    
    if success:
        voice_updater.update_language_voice_map_in_service()
        voice_updater.validate_user_voice_ids()
        
    return success
