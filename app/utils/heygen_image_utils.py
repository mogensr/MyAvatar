"""
Utility functions for getting HeyGen avatar images
"""
import os
from typing import Optional, Dict, Any
from ..api.heygen import get_available_avatars
from ..logger.log_handler import log_info, log_error

def get_heygen_avatar_image(avatar_id: str, api_key: Optional[str] = None) -> Optional[str]:
    """
    Get the preview image URL for a specific HeyGen avatar
    
    Args:
        avatar_id: The HeyGen avatar ID
        api_key: Optional API key, will use environment variable if not provided
        
    Returns:
        The preview image URL or None if not found
    """
    try:
        if not api_key:
            api_key = os.getenv("HEYGEN_API_KEY")
            
        if not api_key:
            log_error("No HeyGen API key available", "HeyGen Image Utils")
            return None
            
        # Get all avatars from HeyGen
        response = get_available_avatars(api_key)
        
        if not response or not response.get('success'):
            log_error(f"Failed to fetch avatars from HeyGen: {response.get('error', 'Unknown error') if response else 'No response'}", "HeyGen Image Utils")
            return None
            
        avatars = response.get('avatars', [])
        
        # Find the specific avatar
        for avatar in avatars:
            if avatar.get('avatar_id') == avatar_id:
                preview_url = avatar.get('preview_image_url')
                if preview_url:
                    log_info(f"Found HeyGen image for {avatar_id}: {preview_url}", "HeyGen Image Utils")
                    return preview_url
                    
        log_error(f"Avatar {avatar_id} not found in HeyGen response", "HeyGen Image Utils")
        return None
        
    except Exception as e:
        log_error(f"Error getting HeyGen avatar image for {avatar_id}", "HeyGen Image Utils", e)
        return None

def get_all_heygen_avatar_images(api_key: Optional[str] = None) -> Dict[str, str]:
    """
    Get a mapping of all HeyGen avatar IDs to their preview image URLs
    
    Args:
        api_key: Optional API key, will use environment variable if not provided
        
    Returns:
        Dictionary mapping avatar_id -> preview_image_url
    """
    try:
        if not api_key:
            api_key = os.getenv("HEYGEN_API_KEY")
            
        if not api_key:
            log_error("No HeyGen API key available", "HeyGen Image Utils")
            return {}
            
        # Get all avatars from HeyGen
        response = get_available_avatars(api_key)
        
        if not response or not response.get('success'):
            log_error(f"Failed to fetch avatars from HeyGen: {response.get('error', 'Unknown error') if response else 'No response'}", "HeyGen Image Utils")
            return {}
            
        avatars = response.get('avatars', [])
        
        # Create mapping
        image_map = {}
        for avatar in avatars:
            avatar_id = avatar.get('avatar_id')
            preview_url = avatar.get('preview_image_url')
            
            if avatar_id and preview_url:
                image_map[avatar_id] = preview_url
                
        log_info(f"Retrieved {len(image_map)} avatar images from HeyGen", "HeyGen Image Utils")
        return image_map
        
    except Exception as e:
        log_error("Error getting all HeyGen avatar images", "HeyGen Image Utils", e)
        return {}

def ensure_avatar_has_heygen_image(avatar_id: str, current_image_url: Optional[str] = None, api_key: Optional[str] = None) -> str:
    """
    Ensure an avatar has the correct HeyGen image URL
    
    Args:
        avatar_id: The HeyGen avatar ID
        current_image_url: Current image URL (if any)
        api_key: Optional API key, will use environment variable if not provided
        
    Returns:
        The best available image URL (HeyGen if available, otherwise current)
    """
    # Try to get the HeyGen image
    heygen_image = get_heygen_avatar_image(avatar_id, api_key)
    
    if heygen_image:
        return heygen_image
    elif current_image_url:
        log_info(f"Using existing image for {avatar_id}: {current_image_url}", "HeyGen Image Utils")
        return current_image_url
    else:
        # Fallback to a default or placeholder
        log_error(f"No image available for avatar {avatar_id}", "HeyGen Image Utils")
        return f"https://via.placeholder.com/150x150?text={avatar_id}"
