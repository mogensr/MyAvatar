"""
HeyGen API integration module
FIXED VERSION - Updated to v2 API with correct endpoints
Enhanced with Text-to-Speech and proper video format support (16:9, 9:16, 1:1)
Premium features: Templates, Interactive Avatars, Custom Backgrounds
"""
import requests
import json
from ..logger.log_handler import log_info, log_error, log_warning

#####################################################################
# HEYGEN API HANDLER - FIXED V2 VERSION WITH PROPER AUDIO SUPPORT
#####################################################################

def create_video_from_audio_file(api_key: str, avatar_id: str, audio_url: str, video_format: str = "16:9"):
    """
    Create a video using an audio file URL - FIXED V2 VERSION
    
    Args:
        api_key: HeyGen API key
        avatar_id: ID of the avatar to use
        audio_url: URL of the audio file
        video_format: Video format (16:9, 9:16, 1:1)
        
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
    
    # FIXED: Use v2 API format with proper audio voice type
    data = {
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id,
                    "avatar_style": "normal"
                },
                "voice": {
                    "type": "audio",
                    "audio_url": audio_url  # FIXED: Use audio_url as required by HeyGen
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
        log_info(f"Creating video with avatar {avatar_id}, format: {video_format} (v2)", "HeyGen API")
        log_info(f"HeyGen API v2 request data: {json.dumps(data)}", "HeyGen API")
        
        # FIXED: Use v2 endpoint consistently
        response = requests.post(
            "https://api.heygen.com/v2/video/generate",
            headers=headers,
            data=json.dumps(data),
            timeout=30
        )
        
        # Log raw response for debugging
        log_info(f"HeyGen API response status: {response.status_code}", "HeyGen API")
        log_info(f"HeyGen API response headers: {dict(response.headers)}", "HeyGen API")
        log_info(f"HeyGen API response text: {response.text[:1000]}{'...' if len(response.text) > 1000 else ''}", "HeyGen API")
        
        # Check if response is actually JSON before parsing
        content_type = response.headers.get('content-type', '').lower()
        if 'application/json' in content_type:
            try:
                response_data = response.json()
                log_info(f"HeyGen API v2 response JSON: {json.dumps(response_data)}", "HeyGen API")
            except json.JSONDecodeError as e:
                log_error(f"Failed to parse JSON despite content-type header: {e}", "HeyGen API")
                return {
                    "success": False,
                    "error": f"Invalid JSON response from HeyGen API: {response.text[:200]}"
                }
        else:
            log_error(f"HeyGen API returned non-JSON response (content-type: {content_type})", "HeyGen API")
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
                    log_info(f"Audio video creation initiated (v2), video_id: {video_id}", "HeyGen API")
                    return {
                        "success": True, 
                        "video_id": video_id
                    }
            elif "code" in response_data and response_data["code"] == 100:
                # Legacy format support
                video_id = response_data.get("data", {}).get("video_id")
                if video_id:
                    log_info(f"Audio video creation initiated (legacy), video_id: {video_id}", "HeyGen API")
                    return {
                        "success": True, 
                        "video_id": video_id
                    }
            
            # Error case
            error_msg = response_data.get("error", {}).get("message") if response_data.get("error") else "Unknown v2 API error"
            log_error(f"HeyGen v2 API error: {error_msg}", "HeyGen API")
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

def create_video_from_text(api_key: str, avatar_id: str, text: str, video_format: str = "16:9", voice_id: str = None):
    """
    Create video using text-to-speech with HeyGen API v2
    
    Args:
        api_key: HeyGen API key
        avatar_id: ID of the avatar to use
        text: Text to convert to speech
        video_format: Video format (16:9, 9:16, 1:1)
        voice_id: ID of the voice to use. If None or 'cloned', will use avatar's cloned voice
           For public avatars (not starting with 'custom-'), a voice_id MUST be provided
        
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
    
    # Build the v2 API request format
    data = {
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id,
                    "avatar_style": "normal"
                },
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
    
    # Check if this is a public avatar (not starting with custom-)
    is_public_avatar = not avatar_id.startswith("custom-")
    
    # For ALL avatars using text-to-speech, voice_id is REQUIRED per HeyGen documentation
    if not voice_id or voice_id.lower() == 'cloned':
        log_error(f"Avatar {avatar_id} requires a specific voice_id for text-to-speech", "HeyGen API")
        return {
            "success": False,
            "error": f"Text-to-speech requires a specific voice_id. For avatar '{avatar_id}', please provide a valid HeyGen voice ID."
        }
    
    # Add voice_id for text-to-speech (required for all avatars)
    data["video_inputs"][0]["voice"]["voice_id"] = voice_id
    log_info(f"Using voice_id for text-to-speech: {voice_id}", "HeyGen API")
    
    try:
        log_info(f"Creating TTS video with avatar {avatar_id}, format: {video_format}", "HeyGen API")
        log_info(f"HeyGen API v2 request data: {json.dumps(data)}", "HeyGen API")
        
        # Use v2 endpoint
        response = requests.post(
            "https://api.heygen.com/v2/video/generate",
            headers=headers,
            data=json.dumps(data)
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
        
        # Handle v2 API response format
        if response.status_code == 200:
            if "error" in response_data and response_data["error"] is None:
                # v2 success format: {"error": null, "data": {"video_id": "..."}}
                video_id = response_data.get("data", {}).get("video_id")
                if video_id:
                    log_info(f"TTS Video creation initiated (v2), video_id: {video_id}", "HeyGen API")
                    return {
                        "success": True, 
                        "video_id": video_id
                    }
            elif "code" in response_data and response_data["code"] == 100:
                # Legacy format support
                video_id = response_data.get("data", {}).get("video_id")
                if video_id:
                    log_info(f"TTS Video creation initiated (legacy), video_id: {video_id}", "HeyGen API")
                    return {
                        "success": True, 
                        "video_id": video_id
                    }
            
            # Error case
            error_msg = response_data.get("error", {}).get("message") if response_data.get("error") else "Unknown v2 API error"
            log_error(f"HeyGen v2 API error: {error_msg}", "HeyGen API")
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
        
        # FIXED: Use v2 endpoint
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
            return {
                "success": True, 
                "avatars": avatars
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
        
        # FIXED: Use v2 endpoint
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

def create_video_with_template(api_key: str, template_id: str, variables: dict, avatar_id: str = None):
    """
    Create video using HeyGen templates (Premium feature)
    
    Args:
        api_key: HeyGen API key
        template_id: ID of the template to use
        variables: Dictionary of variables to populate the template
        avatar_id: Optional avatar ID override
        
    Returns:
        Dictionary with video details or error information
    """
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    data = {
        "template_id": template_id,
        "variables": variables
    }
    
    # Override avatar if specified
    if avatar_id:
        data["avatar_id"] = avatar_id
    
    try:
        log_info(f"Creating template video with template {template_id}", "HeyGen API")
        response = requests.post(
            "https://api.heygen.com/v1/template/generate",
            headers=headers,
            data=json.dumps(data)
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
        
        if response.status_code == 200 and "data" in response_data:
            log_info(f"Template video creation initiated, video_id: {response_data['data'].get('video_id')}", "HeyGen API")
            return {
                "success": True, 
                "video_id": response_data['data'].get('video_id')
            }
        else:
            error_msg = f"Template video creation failed: {response_data.get('message', 'Unknown error')}"
            log_error(error_msg, "HeyGen API")
            return {
                "success": False,
                "error": error_msg
            }
    except Exception as e:
        error_msg = f"Exception in template video creation: {str(e)}"
        log_error(error_msg, "HeyGen API", e)
        return {
            "success": False,
            "error": error_msg
        }

def create_video_with_background(api_key: str, avatar_id: str, audio_url: str, background: dict, video_format: str = "16:9"):
    """
    Create video with custom background - FIXED V2 VERSION
    
    Args:
        api_key: HeyGen API key
        avatar_id: ID of the avatar to use
        audio_url: URL of the audio file
        background: Background configuration dictionary
        video_format: Video format (16:9, 9:16, 1:1)
        
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
    
    # FIXED: Use v2 API format
    data = {
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id,
                    "avatar_style": "normal"
                },
                "voice": {
                    "type": "audio",
                    "audio_url": audio_url
                },
                "background": background
            }
        ],
        "dimension": {
            "width": width,
            "height": height
        }
    }
    
    try:
        log_info(f"Creating video with custom background, avatar {avatar_id}, format: {video_format}", "HeyGen API")
        
        # FIXED: Use v2 endpoint
        response = requests.post(
            "https://api.heygen.com/v2/video/generate",
            headers=headers,
            data=json.dumps(data)
        )
        
        # Log raw response for debugging
        log_info(f"HeyGen API response status: {response.status_code}", "HeyGen API")
        log_info(f"HeyGen API response text: {response.text[:500]}{'...' if len(response.text) > 500 else ''}", "HeyGen API")
        
        # Check if response is actually JSON before parsing
        content_type = response.headers.get('content-type', '').lower()
        if 'application/json' in content_type:
            response_data = response.json()
        else:
            log_error(f"HeyGen API returned non-JSON response (content-type: {content_type})", "HeyGen API")
            return {
                "success": False,
                "error": f"HeyGen API returned non-JSON response (status: {response.status_code}, content-type: {content_type}): {response.text[:200]}"
            }
        
        # Handle v2 API response format
        if response.status_code == 200:
            if "error" in response_data and response_data["error"] is None:
                # v2 success format
                video_id = response_data.get("data", {}).get("video_id")
                if video_id:
                    log_info(f"Custom background video creation initiated (v2), video_id: {video_id}", "HeyGen API")
                    return {
                        "success": True, 
                        "video_id": video_id
                    }
            elif "code" in response_data and response_data["code"] == 100:
                # Legacy format support
                video_id = response_data.get("data", {}).get("video_id")
                if video_id:
                    log_info(f"Custom background video creation initiated (legacy), video_id: {video_id}", "HeyGen API")
                    return {
                        "success": True, 
                        "video_id": video_id
                    }
            
            # Error case
            error_msg = response_data.get("error", {}).get("message") if response_data.get("error") else "Unknown v2 API error"
            log_error(f"HeyGen v2 API error: {error_msg}", "HeyGen API")
            return {
                "success": False,
                "error": error_msg,
                "details": response_data
            }
        else:
            error_msg = f"Custom background video creation failed: HTTP {response.status_code}"
            log_error(error_msg, "HeyGen API")
            return {
                "success": False,
                "error": error_msg,
                "details": response_data if 'response_data' in locals() else None
            }
    except Exception as e:
        error_msg = f"Exception in custom background video creation: {str(e)}"
        log_error(error_msg, "HeyGen API", e)
        return {
            "success": False,
            "error": error_msg
        }

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
        
        # FIXED: Use the correct v1 API endpoint for video status
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
        
        # Handle both v2 and v1 response formats for compatibility
        if response.status_code == 200:
            # v2 API format: {"error": null, "data": {...}}
            if "error" in response_data and response_data["error"] is None:
                log_info(f"Retrieved details for video {video_id}, status: {response_data['data'].get('status')}", "HeyGen API")
                return {
                    "success": True, 
                    "details": response_data["data"]
                }
            # v2 API format: {"code": 100, "data": {...}, "message": "Success"}
            elif "data" in response_data and response_data.get("code") == 100:
                log_info(f"Retrieved details for video {video_id} (legacy format), status: {response_data['data'].get('status')}", "HeyGen API")
                return {
                    "success": True, 
                    "details": response_data["data"]
                }
            # Legacy v1 format fallback
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