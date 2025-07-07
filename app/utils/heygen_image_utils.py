"""
Utility functions for getting HeyGen avatar images
FIXED VERSION - Now handles incomplete URLs from HeyGen API
"""
import os
import requests
from typing import Optional, Dict, Any
from ..api.heygen import get_available_avatars
from ..logger.log_handler import log_info, log_error, log_warning

def fix_incomplete_avatar_url(url: str) -> Optional[str]:
    """
    Fix incomplete avatar URLs from HeyGen API by appending .jpg if needed
    and verify the URL is accessible
    
    Args:
        url: The potentially incomplete URL
        
    Returns:
        Fixed and verified URL or None if not accessible
    """
    if not url:
        return None
        
    # Check if URL already has an extension
    if url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
        # URL already has extension, test if it works
        if test_url_accessibility(url):
            return url
        else:
            log_warning(f"Complete URL not accessible: {url}", "HeyGen Image Utils")
            return None
    
    # Try appending .jpg to incomplete URL
    fixed_url = url + '.jpg'
    if test_url_accessibility(fixed_url):
        log_info(f"Fixed incomplete URL: {url} -> {fixed_url}", "HeyGen Image Utils")
        return fixed_url
    
    # Try appending .png as fallback
    fixed_url_png = url + '.png'
    if test_url_accessibility(fixed_url_png):
        log_info(f"Fixed incomplete URL with PNG: {url} -> {fixed_url_png}", "HeyGen Image Utils")
        return fixed_url_png
    
    log_error(f"Could not fix incomplete URL: {url}", "HeyGen Image Utils")
    return None

def test_url_accessibility(url: str, timeout: int = 10) -> bool:
    """
    Test if a URL is accessible via HTTP HEAD request
    
    Args:
        url: URL to test
        timeout: Request timeout in seconds
        
    Returns:
        True if URL is accessible, False otherwise
    """
    try:
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        is_accessible = response.status_code == 200
        if not is_accessible:
            log_warning(f"URL returned status {response.status_code}: {url}", "HeyGen Image Utils")
        return is_accessible
    except requests.exceptions.RequestException as e:
        log_warning(f"URL not accessible: {url} - {str(e)}", "HeyGen Image Utils")
        return False
    except Exception as e:
        log_error(f"Error testing URL accessibility: {url}", "HeyGen Image Utils", e)
        return False

def get_heygen_avatar_image(avatar_id: str, api_key: Optional[str] = None) -> Optional[str]:
    """
    Get the preview image URL for a specific HeyGen avatar
    FIXED VERSION - Now handles incomplete URLs from HeyGen API
    
    Args:
        avatar_id: The HeyGen avatar ID
        api_key: Optional API key, will use environment variable if not provided
        
    Returns:
        The fixed and verified preview image URL or None if not found
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
                    # Fix incomplete URL if needed
                    fixed_url = fix_incomplete_avatar_url(preview_url)
                    if fixed_url:
                        log_info(f"Found and verified HeyGen image for {avatar_id}: {fixed_url}", "HeyGen Image Utils")
                        return fixed_url
                    else:
                        log_warning(f"Found but could not verify HeyGen image for {avatar_id}: {preview_url}", "HeyGen Image Utils")
                        return None
                    
        log_error(f"Avatar {avatar_id} not found in HeyGen response", "HeyGen Image Utils")
        return None
        
    except Exception as e:
        log_error(f"Error getting HeyGen avatar image for {avatar_id}", "HeyGen Image Utils", e)
        return None

def get_all_heygen_avatar_images(api_key: Optional[str] = None) -> Dict[str, str]:
    """
    Get a mapping of all HeyGen avatar IDs to their preview image URLs
    FIXED VERSION - Now handles incomplete URLs from HeyGen API
    
    Args:
        api_key: Optional API key, will use environment variable if not provided
        
    Returns:
        Dictionary mapping avatar_id -> fixed_and_verified_preview_image_url
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
        
        # Create mapping with fixed URLs
        image_map = {}
        fixed_count = 0
        failed_count = 0
        
        for avatar in avatars:
            avatar_id = avatar.get('avatar_id')
            preview_url = avatar.get('preview_image_url')
            
            if avatar_id and preview_url:
                # Fix incomplete URL if needed
                fixed_url = fix_incomplete_avatar_url(preview_url)
                if fixed_url:
                    image_map[avatar_id] = fixed_url
                    if fixed_url != preview_url:
                        fixed_count += 1
                else:
                    failed_count += 1
                    log_warning(f"Could not fix URL for avatar {avatar_id}: {preview_url}", "HeyGen Image Utils")
                
        log_info(f"Retrieved {len(image_map)} avatar images from HeyGen ({fixed_count} fixed, {failed_count} failed)", "HeyGen Image Utils")
        return image_map
        
    except Exception as e:
        log_error("Error getting all HeyGen avatar images", "HeyGen Image Utils", e)
        return {}

def ensure_avatar_has_heygen_image(avatar_id: str, current_image_url: Optional[str] = None, api_key: Optional[str] = None) -> str:
    """
    Ensure an avatar has the correct HeyGen image URL
    FIXED VERSION - Now handles incomplete URLs from HeyGen API
    
    Args:
        avatar_id: The HeyGen avatar ID
        current_image_url: Current image URL (if any)
        api_key: Optional API key, will use environment variable if not provided
        
    Returns:
        The best available image URL (HeyGen if available, otherwise fixed current, otherwise placeholder)
    """
    # Try to get the HeyGen image (this will be fixed automatically)
    heygen_image = get_heygen_avatar_image(avatar_id, api_key)
    
    if heygen_image:
        return heygen_image
    elif current_image_url:
        # Try to fix the current image URL if it's incomplete
        fixed_current = fix_incomplete_avatar_url(current_image_url)
        if fixed_current:
            log_info(f"Fixed existing image URL for {avatar_id}: {current_image_url} -> {fixed_current}", "HeyGen Image Utils")
            return fixed_current
        else:
            log_warning(f"Could not fix existing image URL for {avatar_id}: {current_image_url}", "HeyGen Image Utils")
            # Return the original URL anyway, might work in some contexts
            return current_image_url
    else:
        # Fallback to a default or placeholder
        log_error(f"No image available for avatar {avatar_id}", "HeyGen Image Utils")
        return f"https://via.placeholder.com/150x150?text={avatar_id}"
