
"""
HeyGen API integration module
Enhanced with Text-to-Speech and proper video format support (16:9, 9:16, 1:1)
Premium features: Templates, Interactive Avatars, Custom Backgrounds
"""
import requests
import json
from ..logger.log_handler import log_info, log_error, log_warning

#####################################################################
# HEYGEN API HANDLER - ENHANCED WITH TEXT SUPPORT & PREMIUM FEATURES
#####################################################################

def create_video_from_audio_file(api_key: str, avatar_id: str, audio_url: str, video_format: str = "16:9"):
    """
    Create a video using an audio file URL
    
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
    
    data = {
        "background": {
            "color": "#ffffff"
        },
        "clips": [{
            "avatar_id": avatar_id,
            "avatar_style": "normal",
            "input_text": "",
            "offset": {"x": 0, "y": 0},
            "scale": 1,
            "voice_url": audio_url
        }],
        "ratio": video_format,
        "test": False,
        "version": "v1",
        "height": height, 
        "width": width
    }
    
    try:
        log_info(f"Creating video with avatar {avatar_id}, format: {video_format}", "HeyGen API")
        response = requests.post(
            "https://api.heygen.com/v1/video/generate",
            headers=headers,
            data=json.dumps(data)
        )
        response_data = response.json()
        
        if response.status_code == 200 and "data" in response_data:
            log_info(f"Video creation initiated, video_id: {response_data['data'].get('video_id')}", "HeyGen API")
            return {
                "success": True, 
                "video_id": response_data['data'].get('video_id')
            }
        else:
            error_msg = f"Video creation failed: {response_data.get('message', 'Unknown error')}"
            log_error(error_msg, "HeyGen API")
            return {
                "success": False,
                "error": error_msg
            }
    except Exception as e:
        error_msg = f"Exception in video creation: {str(e)}"
        log_error(error_msg, "HeyGen API", e)
        return {
            "success": False,
            "error": error_msg
        }

def create_video_from_text(api_key: str, avatar_id: str, text: str, video_format: str = "16:9", voice_id: str = None):
    """
    Create video using text-to-speech instead of audio file
    
    Args:
        api_key: HeyGen API key
        avatar_id: ID of the avatar to use
        text: Text to convert to speech
        video_format: Video format (16:9, 9:16, 1:1)
        voice_id: ID of the voice to use. If None or 'cloned', will use avatar's cloned voice
        
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
    
    # Create the clip data
    clip_data = {
        "avatar_id": avatar_id,
        "avatar_style": "normal",
        "input_text": text,
        "offset": {"x": 0, "y": 0},
        "scale": 1
    }
    
    # Only add voice_id if specified and not 'cloned'
    if voice_id and voice_id.lower() != 'cloned':
        clip_data["voice_id"] = voice_id
        log_info(f"Using specified voice_id: {voice_id}", "HeyGen API")
    else:
        log_info(f"Using avatar's cloned voice for avatar_id: {avatar_id}", "HeyGen API")
    
    # Build the full request data
    data = {
        "background": {
            "color": "#ffffff"
        },
        "clips": [clip_data],
        "ratio": video_format,
        "test": False,
        "version": "v1",
        "height": height,
        "width": width
    }
    
    try:
        log_info(f"Creating TTS video with avatar {avatar_id}, format: {video_format}", "HeyGen API")
        
        # Log the exact request being sent for debugging
        log_info(f"HeyGen API request data: {json.dumps(data)}", "HeyGen API")
        
        response = requests.post(
            "https://api.heygen.com/v1/video/generate",
            headers=headers,
            data=json.dumps(data)
        )
        response_data = response.json()
        
        # Log full response for debugging
        log_info(f"HeyGen API response: {json.dumps(response_data)}", "HeyGen API")
        
        if response.status_code == 200 and "data" in response_data:
            log_info(f"TTS Video creation initiated, video_id: {response_data['data'].get('video_id')}", "HeyGen API")
            return {
                "success": True, 
                "video_id": response_data['data'].get('video_id')
            }
        else:
            error_msg = f"TTS Video creation failed: {response_data.get('message', 'Unknown error')}"
            log_error(error_msg, "HeyGen API")
            return {
                "success": False,
                "error": error_msg,
                "details": response_data  # Include full error details
            }
    except Exception as e:
        error_msg = f"Exception in TTS video creation: {str(e)}"
        log_error(error_msg, "HeyGen API", e)
        return {
            "success": False,
            "error": error_msg
        }

# PREMIUM FEATURES
def get_available_avatars(api_key: str):
    """
    Get list of available avatars from HeyGen
    
    Args:
        api_key: HeyGen API key
        
    Returns:
        List of avatars or error information
    """
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    try:
        log_info("Fetching available avatars", "HeyGen API")
        response = requests.get(
            "https://api.heygen.com/v1/avatar",
            headers=headers
        )
        response_data = response.json()
        
        if response.status_code == 200 and "data" in response_data:
            avatars = response_data["data"].get("avatars", [])
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
    Get list of available voices from HeyGen
    
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
        log_info("Fetching available voices", "HeyGen API")
        response = requests.get(
            "https://api.heygen.com/v1/voice",
            headers=headers
        )
        response_data = response.json()
        
        if response.status_code == 200 and "data" in response_data:
            voices = response_data["data"].get("voices", [])
            
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
        response_data = response.json()
        
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
    Create video with custom background
    
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
    
    data = {
        "background": background,
        "clips": [{
            "avatar_id": avatar_id,
            "avatar_style": "normal",
            "input_text": "",
            "offset": {"x": 0, "y": 0},
            "scale": 1,
            "voice_url": audio_url
        }],
        "ratio": video_format,
        "test": False,
        "version": "v1",
        "height": height,
        "width": width
    }
    
    try:
        log_info(f"Creating video with custom background, avatar {avatar_id}, format: {video_format}", "HeyGen API")
        response = requests.post(
            "https://api.heygen.com/v1/video/generate",
            headers=headers,
            data=json.dumps(data)
        )
        response_data = response.json()
        
        if response.status_code == 200 and "data" in response_data:
            log_info(f"Custom background video creation initiated, video_id: {response_data['data'].get('video_id')}", "HeyGen API")
            return {
                "success": True, 
                "video_id": response_data['data'].get('video_id')
            }
        else:
            error_msg = f"Custom background video creation failed: {response_data.get('message', 'Unknown error')}"
            log_error(error_msg, "HeyGen API")
            return {
                "success": False,
                "error": error_msg
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
    Get detailed information about a video
    
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
        log_info(f"Fetching details for video {video_id}", "HeyGen API")
        response = requests.get(
            f"https://api.heygen.com/v1/video_status/{video_id}",
            headers=headers
        )
        response_data = response.json()
        
        if response.status_code == 200 and "data" in response_data:
            log_info(f"Retrieved details for video {video_id}, status: {response_data['data'].get('status')}", "HeyGen API")
            return {
                "success": True, 
                "details": response_data["data"]
            }
        else:
            error_msg = f"Failed to fetch video details: {response_data.get('message', 'Unknown error')}"
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
