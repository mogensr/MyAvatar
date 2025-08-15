"""
HeyGen API integration module
ENHANCED VERSION - Updated to v2 API with correct endpoints
Enhanced with Text-to-Speech and proper video format support (16:9, 9:16, 1:1)
Premium features: Templates, Interactive Avatars, Custom Backgrounds
UPDATED: Now supports ALL avatar types automatically - Photo Avatars, Stock Avatars, Custom Avatars, Instant Avatars
NEW: Universal avatar detection with proper API formatting for each type
"""
import requests
import json
from typing import Dict, Any, Optional
from ..logger.log_handler import log_info, log_error, log_warning

#####################################################################
# CHAPTER 1: UNIVERSAL AVATAR DETECTION AND CONFIGURATION
#####################################################################

def get_avatar_from_any_endpoint(api_key: str, avatar_id: str) -> Dict[str, Any]:
    """
    Get avatar information from HeyGen API by checking multiple endpoints
    
    This function tries different HeyGen API endpoints to get comprehensive
    avatar information including type, which is crucial for voice assignment.
    
    Args:
        api_key: HeyGen API key
        avatar_id: The avatar ID to look up
        
    Returns:
        Dict containing avatar information including type, or error info
    """
    headers = {
        "X-Api-Key": api_key,
        "Accept": "application/json"
    }
    
    try:
        log_info(f"🔍 Searching for avatar {avatar_id} across all HeyGen endpoints", "HeyGen API")
        
        # 1. TRY PHOTO AVATAR ENDPOINT FIRST (most likely for your use case)
        log_info(f"📸 Checking photo avatar endpoint for {avatar_id}", "HeyGen API")
        
        response = requests.get(
            f"https://api.heygen.com/v2/photo_avatar/{avatar_id}",
            headers=headers,
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            if not data.get("error"):
                log_info(f"✅ Found photo avatar {avatar_id}", "HeyGen API")
                return {
                    "type": "photo",
                    "data": data.get("data", data),
                    "config": {
                        "type": "talking_photo",       # ✅ Correct API format
                        "talking_photo_id": avatar_id  # ✅ Use talking_photo_id for photo avatars
                    }
                }
        
        # 2. TRY MAIN V2 AVATARS ENDPOINT (stock + custom avatars)
        log_info(f"🎬 Checking v2/avatars endpoint for {avatar_id}", "HeyGen API")
        
        response = requests.get(
            "https://api.heygen.com/v2/avatars",
            headers=headers,
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if not data.get("error"):
                # Check regular avatars section
                avatars = data.get("data", {}).get("avatars", [])
                for avatar in avatars:
                    if avatar.get("avatar_id") == avatar_id:
                        log_info(f"✅ Found regular avatar {avatar_id}", "HeyGen API")
                        
                        # Determine if it's custom or stock
                        avatar_type = "custom" if len(avatar_id) == 32 or "-" not in avatar_id else "stock"
                        
                        return {
                            "type": avatar_type,
                            "data": avatar,
                            "config": {
                                "type": "avatar",           # ✅ Standard avatar type
                                "avatar_id": avatar_id,     # ✅ Use avatar_id for regular avatars
                                "avatar_style": "normal"    # ✅ Required for regular avatars
                            }
                        }
                
                # Check talking photos section within v2/avatars
                talking_photos = data.get("data", {}).get("talking_photos", [])
                for photo in talking_photos:
                    photo_id = photo.get("talking_photo_id") or photo.get("id") or photo.get("avatar_id")
                    if photo_id == avatar_id:
                        log_info(f"✅ Found talking photo {avatar_id} in v2/avatars", "HeyGen API")
                        return {
                            "type": "talking_photo",
                            "data": photo,
                            "config": {
                                "type": "talking_photo",       # ✅ Talking photo type
                                "talking_photo_id": avatar_id  # ✅ Use talking_photo_id
                            }
                        }
        
        # 3. TRY AVATAR GROUP ENDPOINTS (new photo avatar system)
        log_info(f"👥 Checking avatar groups for {avatar_id}", "HeyGen API")
        
        try:
            # Get avatar groups
            response = requests.get(
                "https://api.heygen.com/v2/avatar_group.list",
                headers=headers,
                timeout=15
            )
            
            if response.status_code == 200:
                groups_data = response.json()
                if not groups_data.get("error"):
                    groups = groups_data.get("data", {}).get("avatar_group_list", [])
                    
                    # Search through each group for the avatar
                    for group in groups:
                        group_id = group.get("id")
                        if group_id:
                            group_response = requests.get(
                                f"https://api.heygen.com/v2/avatar_group/{group_id}/avatars",
                                headers=headers,
                                timeout=10
                            )
                            
                            if group_response.status_code == 200:
                                group_avatars_data = group_response.json()
                                if not group_avatars_data.get("error"):
                                    avatars = group_avatars_data.get("data", {}).get("avatar_list", [])
                                    
                                    for avatar in avatars:
                                        if avatar.get("id") == avatar_id:
                                            log_info(f"✅ Found group photo avatar {avatar_id}", "HeyGen API")
                                            return {
                                                "type": "group_photo",
                                                "data": avatar,
                                                "config": {
                                                    "type": "talking_photo",       # ✅ Group photos use talking_photo
                                                    "talking_photo_id": avatar_id  # ✅ Use talking_photo_id
                                                }
                                            }
        
        except Exception as e:
            log_warning(f"Avatar groups search failed: {e}", "HeyGen API")
        
        # 4. TRY LEGACY V1 AVATAR ENDPOINT (older avatars)
        log_info(f"🔧 Checking legacy v1 endpoint for {avatar_id}", "HeyGen API")
        
        response = requests.get(
            "https://api.heygen.com/v1/avatar.list",
            headers=headers,
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            if not data.get("error"):
                avatars = data.get("data", {}).get("avatars", [])
                for avatar in avatars:
                    if avatar.get("avatar_id") == avatar_id:
                        log_info(f"✅ Found legacy avatar {avatar_id}", "HeyGen API")
                        return {
                            "type": "legacy",
                            "data": avatar,
                            "config": {
                                "type": "avatar",           # ✅ Legacy avatars use standard format
                                "avatar_id": avatar_id,     # ✅ Use avatar_id
                                "avatar_style": "normal"    # ✅ Standard style
                            }
                        }
        
        # 5. TRY INSTANT AVATAR ENDPOINT (user-created avatars)
        log_info(f"⚡ Checking instant avatars for {avatar_id}", "HeyGen API")
        
        try:
            response = requests.get(
                "https://api.heygen.com/v1/instant_avatar.list",
                headers=headers,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                if not data.get("error"):
                    avatars = data.get("data", {}).get("avatars", [])
                    for avatar in avatars:
                        if avatar.get("avatar_id") == avatar_id:
                            log_info(f"✅ Found instant avatar {avatar_id}", "HeyGen API")
                            return {
                                "type": "instant",
                                "data": avatar,
                                "config": {
                                    "type": "avatar",           # ✅ Instant avatars use standard format
                                    "avatar_id": avatar_id,     # ✅ Use avatar_id
                                    "avatar_style": "normal"    # ✅ Standard style
                                }
                            }
        except Exception as e:
            log_warning(f"Instant avatars search failed: {e}", "HeyGen API")
        
        # 6. FALLBACK - Avatar not found, but provide working config
        log_warning(f"⚠️ Avatar {avatar_id} not found in any endpoint - using fallback", "HeyGen API")
        
        # Make educated guess based on avatar_id format
        if len(avatar_id) == 32 and "-" not in avatar_id:
            # Looks like a photo avatar ID
            log_info(f"🤔 ID format suggests photo avatar - using talking_photo config", "HeyGen API")
            return {
                "type": "unknown_photo",
                "data": {"avatar_id": avatar_id},
                "config": {
                    "type": "talking_photo",
                    "talking_photo_id": avatar_id
                }
            }
        else:
            # Looks like a regular avatar
            log_info(f"🤔 ID format suggests regular avatar - using avatar config", "HeyGen API")
            return {
                "type": "unknown_regular",
                "data": {"avatar_id": avatar_id},
                "config": {
                    "type": "avatar",
                    "avatar_id": avatar_id,
                    "avatar_style": "normal"
                }
            }
        
    except requests.exceptions.Timeout:
        log_error(f"⏰ Timeout while searching for avatar {avatar_id}", "HeyGen API")
        # Return fallback config
        return {
            "type": "timeout_fallback",
            "data": {"avatar_id": avatar_id},
            "config": {
                "type": "avatar",
                "avatar_id": avatar_id,
                "avatar_style": "normal"
            }
        }
    except requests.exceptions.RequestException as e:
        log_error(f"🌐 Request error while searching for avatar {avatar_id}: {e}", "HeyGen API")
        return {
            "type": "error_fallback",
            "data": {"avatar_id": avatar_id},
            "config": {
                "type": "avatar",
                "avatar_id": avatar_id,
                "avatar_style": "normal"
            }
        }
    except Exception as e:
        log_error(f"💥 Unexpected error while searching for avatar {avatar_id}: {e}", "HeyGen API")
        return {
            "type": "exception_fallback",
            "data": {"avatar_id": avatar_id},
            "config": {
                "type": "avatar",
                "avatar_id": avatar_id,
                "avatar_style": "normal"
            }
        }

def get_character_config(api_key: str, avatar_id: str):
    """
    UNIVERSAL: Auto-detect avatar type and return appropriate character config for ANY avatar type
    
    Args:
        api_key: HeyGen API key
        avatar_id: Avatar ID to test
        
    Returns:
        Dictionary with appropriate character configuration for HeyGen API
    """
    try:
        log_info(f"🔍 Detecting avatar type for {avatar_id}", "HeyGen API")
        
        # Use universal avatar detection
        avatar_info = get_avatar_from_any_endpoint(api_key, avatar_id)
        
        if avatar_info and avatar_info.get("config"):
            avatar_type = avatar_info.get("type", "unknown")
            config = avatar_info["config"]
            log_info(f"✅ Detected {avatar_type} avatar: {avatar_id} → {config}", "HeyGen API")
            return config
        
        # Ultimate fallback: assume regular avatar
        log_warning(f"⚠️ Avatar detection failed for {avatar_id}, using regular avatar fallback", "HeyGen API")
        return {
            "type": "avatar",
            "avatar_id": avatar_id,
            "avatar_style": "normal"
        }
        
    except Exception as e:
        log_error(f"💥 Exception in avatar detection for {avatar_id}: {e}", "HeyGen API")
        # Return safe fallback
        return {
            "type": "avatar",
            "avatar_id": avatar_id,
            "avatar_style": "normal"
        }

#####################################################################
# CHAPTER 2: VIDEO CREATION WITH AUDIO FILES
#####################################################################

def create_video_from_audio_file(api_key: str, avatar_id: str, audio_url: str, video_format: str = "16:9", speed: float = 1.0, pitch: float = 1.0, emotion: str = "Friendly"):
    """
    Create a video using an audio file URL - UNIVERSAL VERSION supporting ALL avatar types
    
    Args:
        api_key: HeyGen API key
        avatar_id: ID of the avatar to use (works with ALL avatar types)
        audio_url: URL of the audio file
        video_format: Video format (16:9, 9:16, 1:1)
        speed: Speech speed multiplier (0.5 to 2.0)
        pitch: Voice pitch multiplier (0.5 to 2.0)
        emotion: Voice emotion (Friendly, Sad, Excited, etc.)
        
    Returns:
        Dictionary with video details or error information
    """
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    # Properly set dimensions based on format
    if video_format == "9:16":
        width = 540
        height = 960
    elif video_format == "1:1":
        width = 720
        height = 720
    else:  # Default to 16:9
        width = 1280
        height = 720
    
    # UNIVERSAL: Auto-detect avatar type and get correct config
    character_config = get_character_config(api_key, avatar_id)
    
    # Use v2 API format with proper audio voice type
    data = {
        "video_inputs": [
            {
                "character": character_config,
                "voice": {
                    "type": "audio",
                    "audio_url": audio_url,
                    "speed": speed,
                    "pitch": pitch,
                    "emotion": emotion
                },
                "background": {
                    "type": "color",
                    "value": "#ffffff"
                }
            }
        ],
        "dimension": {
            "width": width,
            "height": height
        },
        "callback_id": f"myavatar_audio_{avatar_id}",
        "callback_url": "https://app.myavatar.dk/api/heygen/webhook"
    }
    
    try:
        log_info(f"🎵 Creating audio video with avatar {avatar_id}, format: {video_format}, speed: {speed}, pitch: {pitch}, emotion: {emotion}", "HeyGen API")
        log_info(f"📋 HeyGen API v2 request data: {json.dumps(data)}", "HeyGen API")
        
        response = requests.post(
            "https://api.heygen.com/v2/video/generate",
            headers=headers,
            data=json.dumps(data),
            timeout=30
        )
        
        # Log raw response for debugging
        log_info(f"📊 HeyGen API response status: {response.status_code}", "HeyGen API")
        log_info(f"📋 HeyGen API response text: {response.text[:1000]}{'...' if len(response.text) > 1000 else ''}", "HeyGen API")
        
        # Check if response is actually JSON before parsing
        content_type = response.headers.get('content-type', '').lower()
        if 'application/json' in content_type:
            try:
                response_data = response.json()
                log_info(f"📋 HeyGen API v2 response JSON: {json.dumps(response_data)}", "HeyGen API")
            except json.JSONDecodeError as e:
                log_error(f"❌ Failed to parse JSON despite content-type header: {e}", "HeyGen API")
                return {
                    "success": False,
                    "error": f"Invalid JSON response from HeyGen API: {response.text[:200]}"
                }
        else:
            log_error(f"❌ HeyGen API returned non-JSON response (content-type: {content_type})", "HeyGen API")
            return {
                "success": False,
                "error": f"HeyGen API returned non-JSON response (status: {response.status_code}, content-type: {content_type}): {response.text[:200]}"
            }
        
        # Handle v2 API response format
        if response.status_code == 200:
            if "error" in response_data and response_data["error"] is None:
                # v2 success format: {"error": null, "data": {"video_id": "..."}}
                video_id = response_data.get("data", {}).get("video_id")
                if video_id:
                    log_info(f"✅ Audio video creation initiated (v2), video_id: {video_id}", "HeyGen API")
                    return {
                        "success": True, 
                        "video_id": video_id
                    }
            elif "code" in response_data and response_data["code"] == 100:
                # Legacy format support
                video_id = response_data.get("data", {}).get("video_id")
                if video_id:
                    log_info(f"✅ Audio video creation initiated (legacy), video_id: {video_id}", "HeyGen API")
                    return {
                        "success": True, 
                        "video_id": video_id
                    }
            
            # Error case
            error_msg = response_data.get("error", {}).get("message") if response_data.get("error") else "Unknown v2 API error"
            log_error(f"❌ HeyGen v2 API error: {error_msg}", "HeyGen API")
            return {
                "success": False,
                "error": error_msg,
                "details": response_data
            }
        else:
            error_msg = f"Audio video creation failed: HTTP {response.status_code}"
            log_error(error_msg, "HeyGen API")
            return {
                "success": False,
                "error": error_msg,
                "details": response_data if 'response_data' in locals() else None
            }
            
    except requests.exceptions.Timeout:
        error_msg = "HeyGen API request timed out after 30 seconds"
        log_error(error_msg, "HeyGen API")
        return {"success": False, "error": error_msg}
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error calling HeyGen API: {str(e)}"
        log_error(error_msg, "HeyGen API", e)
        return {"success": False, "error": error_msg}
    except Exception as e:
        error_msg = f"Exception in HeyGen API call: {str(e)}"
        log_error(error_msg, "HeyGen API", e)
        return {
            "success": False,
            "error": error_msg
        }


# Convenience function for backward compatibility
def create_heygen_video(script: str, avatar_id: str, voice_id: str, webhook_url: str) -> Dict[str, Any]:
    """
    Create a video using the HeyGen API with proper webhook configuration
    """
    api = HeyGenAPI()
    return api.create_video(script, avatar_id, voice_id, webhook_url)


# Function to test webhook connectivity
def test_webhook_connectivity(webhook_url: str) -> bool:
    """
    Test if the webhook URL is accessible
    """
    try:
        # Try to make a GET request to the webhook endpoint
        response = requests.get(webhook_url.replace('/webhook', '/webhook/test'), timeout=10)
        return response.status_code == 200
    except:
        return False

def create_video_from_text(text: str, avatar_id: str, voice_id: str = None, 
                          user_id: int = None, language: str = "en", 
                          context: Dict[str, Any] = None, api_key: str = None, 
                          video_format: str = "16:9", emotion: str = "Friendly", 
                          speed: float = 1.0, pitch: float = 1.0) -> Dict[str, Any]:  
    """
    Create video using text-to-speech with HeyGen API v2 - UNIVERSAL VERSION supporting ALL avatar types
    
    Args:
        api_key: HeyGen API key
        avatar_id: ID of the avatar to use (works with ALL avatar types)
        text: Text to convert to speech
        video_format: Video format (16:9, 9:16, 1:1)
        voice_id: ID of the voice to use (required for text-to-speech)
        emotion: Voice emotion (Friendly, Excited, Serious, Soothing, Broadcaster)
        speed: Voice speed multiplier (0.5 to 2.0)
        pitch: Voice pitch multiplier (0.5 to 1.5)
        
    Returns:
        Dictionary with video details or error information
    """
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    # Properly set dimensions based on format
    if video_format == "9:16":
        width = 540
        height = 960
    elif video_format == "1:1":
        width = 720
        height = 720
    else:  # Default to 16:9
        width = 1280
        height = 720
    
    # UNIVERSAL: Auto-detect avatar type and get correct config
    character_config = get_character_config(api_key, avatar_id)
    
    # Build the v2 API request format
    data = {
        "video_inputs": [
            {
                "character": character_config,
                "voice": {
                    "type": "text",
                    "input_text": text
                },
                "background": {
                    "type": "color",
                    "value": "#ffffff"
                }
            }
        ],
        "dimension": {
            "width": width,
            "height": height
        },
        "callback_id": f"myavatar_text_{avatar_id}",
        "callback_url": "https://app.myavatar.dk/api/heygen/webhook"
    }
    
    # DISABLED: Broken voice manager that overrides personal voice assignment
    # The voice_id should already be correctly assigned by video_service.py
    if not voice_id and user_id:
        log_warning(f"⚠️ No voice_id provided for user {user_id}, using fallback", "HeyGen API")
        # Simple fallback to default voice for language
        fallback_voices = {
            "en": "1bd001e7e50f421d891986aad5158bc8",
            "da": "1bd001e7e50f421d891986aad5158bc8", 
            "es": "1bd001e7e50f421d891986aad5158bc8",
            "fr": "1bd001e7e50f421d891986aad5158bc8",
            "de": "1bd001e7e50f421d891986aad5158bc8"
        }
        voice_id = fallback_voices.get(language, "1bd001e7e50f421d891986aad5158bc8")
    
    # For text-to-speech, voice_id is REQUIRED per HeyGen documentation
    if not voice_id:
        log_error(f"❌ Avatar {avatar_id} requires a specific voice_id for text-to-speech", "HeyGen API")
        return {
            "success": False,
            "error": f"Text-to-speech requires a specific voice_id. For avatar '{avatar_id}', please provide a valid HeyGen voice ID or user_id for automatic assignment."
        }
    
    # Add voice_id for text-to-speech (required for all avatars)
    data["video_inputs"][0]["voice"]["voice_id"] = voice_id
    log_info(f"🗣️ Using voice_id for text-to-speech: {voice_id}", "HeyGen API")
    
    # Add emotion, speed and pitch parameters for more natural intonation
    if emotion in ["Friendly", "Excited", "Serious", "Soothing", "Broadcaster"]:
        data["video_inputs"][0]["voice"]["emotion"] = emotion
        log_info(f"😀 Using voice emotion: {emotion}", "HeyGen API")
    
    # Add speed parameter (0.5 to 2.0)
    if 0.5 <= speed <= 2.0:
        data["video_inputs"][0]["voice"]["speed"] = speed
        log_info(f"⏩ Using voice speed: {speed}", "HeyGen API")
    
    # Add pitch parameter (0.5 to 1.5)
    if 0.5 <= pitch <= 1.5:
        data["video_inputs"][0]["voice"]["pitch"] = pitch
        log_info(f"🎵 Using voice pitch: {pitch}", "HeyGen API")
    
    try:
        log_info(f"📝 Creating TTS video with avatar {avatar_id}, format: {video_format}", "HeyGen API")
        log_info(f"📋 HeyGen API v2 request data: {json.dumps(data)}", "HeyGen API")
        
        response = requests.post(
            "https://api.heygen.com/v2/video/generate",
            headers=headers,
            data=json.dumps(data),
            timeout=30
        )
        
        # Log raw response for debugging
        log_info(f"📊 HeyGen API response status: {response.status_code}", "HeyGen API")
        log_info(f"📋 HeyGen API response text: {response.text[:500]}{'...' if len(response.text) > 500 else ''}", "HeyGen API")
        
        # Check if response is actually JSON before parsing
        if response.headers.get('content-type', '').startswith('application/json'):
            response_data = response.json()
        else:
            log_error(f"❌ HeyGen API returned non-JSON response: {response.text}", "HeyGen API")
            return {
                "success": False,
                "error": f"HeyGen API returned non-JSON response (status: {response.status_code}): {response.text}"
            }
        
        # Handle v2 API response format
        if response.status_code == 200:
            if "error" in response_data and response_data["error"] is None:
                # v2 success format: {"error": null, "data": {"video_id": "..."}}
                video_id = response_data.get("data", {}).get("video_id")
                if video_id:
                    log_info(f"✅ TTS Video creation initiated (v2), video_id: {video_id}", "HeyGen API")
                    return {
                        "success": True, 
                        "video_id": video_id
                    }
            elif "code" in response_data and response_data["code"] == 100:
                # Legacy format support
                video_id = response_data.get("data", {}).get("video_id")
                if video_id:
                    log_info(f"✅ TTS Video creation initiated (legacy), video_id: {video_id}", "HeyGen API")
                    return {
                        "success": True, 
                        "video_id": video_id
                    }
            
            # Error case
            error_msg = response_data.get("error", {}).get("message") if response_data.get("error") else "Unknown v2 API error"
            log_error(f"❌ HeyGen v2 API error: {error_msg}", "HeyGen API")
            return {
                "success": False,
                "error": error_msg,
                "details": response_data
            }
        else:
            error_msg = f"TTS Video creation failed: HTTP {response.status_code}"
            log_error(error_msg, "HeyGen API")
            return {
                "success": False,
                "error": error_msg,
                "details": response_data if 'response_data' in locals() else None
            }
            
    except requests.exceptions.Timeout:
        error_msg = "HeyGen API request timed out after 30 seconds"
        log_error(error_msg, "HeyGen API")
        return {"success": False, "error": error_msg}
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error calling HeyGen API: {str(e)}"
        log_error(error_msg, "HeyGen API", e)
        return {"success": False, "error": error_msg}
    except Exception as e:
        error_msg = f"Exception in HeyGen API call: {str(e)}"
        log_error(error_msg, "HeyGen API", e)
        return {
            "success": False,
            "error": error_msg
        }

#####################################################################
# CHAPTER 4: AVATAR AND VOICE MANAGEMENT
#####################################################################

def get_available_avatars(api_key: str):
    """
    Get available avatars from HeyGen API - FIXED V2 VERSION
    
    Args:
        api_key: HeyGen API key
        
    Returns:
        Dictionary with avatars list or error information
    """
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    try:
        log_info("Fetching available avatars (v2)", "HeyGen API")
        
        response = requests.get(
            "https://api.heygen.com/v2/avatars",
            headers=headers
        )
        
        # Log raw response for debugging
        log_info(f"HeyGen API response status: {response.status_code}", "HeyGen API")
        log_info(f"HeyGen API response text: {response.text[:500]}{'...' if len(response.text) > 500 else ''}", "HeyGen API")
        
        # Check if response is actually JSON before parsing
        if response.headers.get('content-type', '').startswith('application/json'):
            response_data = response.json()
        else:
            log_error(f"HeyGen API returned non-JSON response: {response.text}", "HeyGen API")
            return {
                "success": False,
                "error": f"HeyGen API returned non-JSON response (status: {response.status_code}): {response.text}"
            }
        
        # Handle both v2 and legacy response formats
        if response.status_code == 200:
            if "error" in response_data and response_data["error"] is None:
                # v2 format
                avatars = response_data.get("data", {}).get("avatars", [])
            elif "data" in response_data:
                # Legacy format
                avatars = response_data["data"].get("avatars", [])
            else:
                avatars = []
                
            log_info(f"Retrieved {len(avatars)} avatars", "HeyGen API")
            
            # Debug: Check for talking photos in the response
            talking_photos = response_data.get("data", {}).get("talking_photos", [])
            log_info(f"Retrieved {len(talking_photos)} talking photos", "HeyGen API")
            
            return {
                "success": True, 
                "avatars": avatars,
                "talking_photos": talking_photos
            }
        else:
            error_msg = f"Failed to fetch avatars: {response_data.get('message', 'Unknown error')}"
            log_error(error_msg, "HeyGen API")
            return {
                "success": False,
                "error": error_msg
            }
    except Exception as e:
        error_msg = f"Exception in avatar fetch: {str(e)}"
        log_error(error_msg, "HeyGen API", e)
        return {
            "success": False,
            "error": error_msg
        }

def get_available_voices(api_key: str, language: str = None):
    """
    Get list of available voices from HeyGen - FIXED V2 VERSION
    
    Args:
        api_key: HeyGen API key
        language: Optional language filter
        
    Returns:
        List of voices or error information
    """
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    try:
        log_info("Fetching available voices (v2)", "HeyGen API")
        
        response = requests.get(
            "https://api.heygen.com/v2/voices",
            headers=headers
        )
        
        # Log raw response for debugging
        log_info(f"HeyGen API response status: {response.status_code}", "HeyGen API")
        log_info(f"HeyGen API response text: {response.text[:500]}{'...' if len(response.text) > 500 else ''}", "HeyGen API")
        
        # Check if response is actually JSON before parsing
        if response.headers.get('content-type', '').startswith('application/json'):
            response_data = response.json()
        else:
            log_error(f"HeyGen API returned non-JSON response: {response.text}", "HeyGen API")
            return {
                "success": False,
                "error": f"HeyGen API returned non-JSON response (status: {response.status_code}): {response.text}"
            }
        
        # Handle both v2 and legacy response formats
        if response.status_code == 200:
            if "error" in response_data and response_data["error"] is None:
                # v2 format
                voices = response_data.get("data", {}).get("voices", [])
            elif "data" in response_data:
                # Legacy format
                voices = response_data["data"].get("voices", [])
            else:
                voices = []
            
            # Filter by language if specified
            if language:
                voices = [v for v in voices if language.lower() in v.get("language", "").lower()]
                
            log_info(f"Retrieved {len(voices)} voices" + (f" for language {language}" if language else ""), "HeyGen API")
            return {
                "success": True, 
                "voices": voices
            }
        else:
            error_msg = f"Failed to fetch voices: {response_data.get('message', 'Unknown error')}"
            log_error(error_msg, "HeyGen API")
            return {
                "success": False,
                "error": error_msg
            }
    except Exception as e:
        error_msg = f"Exception in voice fetch: {str(e)}"
        log_error(error_msg, "HeyGen API", e)
        return {
            "success": False,
            "error": error_msg
        }

#####################################################################
# CHAPTER 5: VIDEO STATUS AND DETAILS
#####################################################################

def get_video_details(api_key: str, video_id: str):
    """
    Get detailed information about a video - FIXED V2 VERSION
    
    Args:
        api_key: HeyGen API key
        video_id: ID of the video to get details for
        
    Returns:
        Dictionary with video details or error information
    """
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    try:
        log_info(f"Fetching details for video {video_id} (v1)", "HeyGen API")
        
        response = requests.get(
            f"https://api.heygen.com/v1/video_status.get?video_id={video_id}",
            headers=headers
        )
        
        # Log raw response for debugging
        log_info(f"HeyGen API response status: {response.status_code}", "HeyGen API")
        log_info(f"HeyGen API response text: {response.text[:500]}{'...' if len(response.text) > 500 else ''}", "HeyGen API")
        
        # Check if response is actually JSON before parsing
        if response.headers.get('content-type', '').startswith('application/json'):
            response_data = response.json()
        else:
            log_error(f"HeyGen API returned non-JSON response: {response.text}", "HeyGen API")
            return {
                "success": False,
                "error": f"HeyGen API returned non-JSON response (status: {response.status_code}): {response.text}"
            }
        
        # Handle response formats
        if response.status_code == 200:
            if "error" in response_data and response_data["error"] is None:
                log_info(f"Retrieved details for video {video_id}, status: {response_data['data'].get('status')}", "HeyGen API")
                return {
                    "success": True, 
                    "details": response_data["data"]
                }
            elif "data" in response_data and response_data.get("code") == 100:
                log_info(f"Retrieved details for video {video_id} (legacy format), status: {response_data['data'].get('status')}", "HeyGen API")
                return {
                    "success": True, 
                    "details": response_data["data"]
                }
            elif "data" in response_data:
                log_info(f"Retrieved details for video {video_id} (legacy format), status: {response_data['data'].get('status')}", "HeyGen API")
                return {
                    "success": True, 
                    "details": response_data["data"]
                }
            else:
                error_msg = f"Unexpected response format from HeyGen API: {response_data}"
                log_error(error_msg, "HeyGen API")
                return {
                    "success": False,
                    "error": error_msg
                }
        else:
            error_msg = f"Failed to fetch video details (HTTP {response.status_code}): {response_data.get('message', 'Unknown error')}"
            log_error(error_msg, "HeyGen API")
            return {
                "success": False,
                "error": error_msg
            }
    except Exception as e:
        error_msg = f"Exception in video details fetch: {str(e)}"
        log_error(error_msg, "HeyGen API", e)
        return {
            "success": False,
            "error": error_msg
        }

#####################################################################
# CHAPTER 6: UTILITY FUNCTIONS
#####################################################################

def test_heygen_connection(api_key: str):
    """
    Test connection to HeyGen API
    
    Args:
        api_key: HeyGen API key
        
    Returns:
        Boolean indicating connection success
    """
    try:
        log_info("Testing connection to HeyGen API", "HeyGen API")
        result = get_available_voices(api_key)
        if result["success"]:
            log_info("Connection to HeyGen API successful", "HeyGen API")
            return True
        else:
            log_error("Connection to HeyGen API failed", "HeyGen API")
            return False
    except Exception as e:
        log_error("Exception in HeyGen API connection test", "HeyGen API", e)
        return False
