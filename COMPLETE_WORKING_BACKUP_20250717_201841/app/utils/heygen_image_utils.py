"""
Utility functions for getting HeyGen avatar images
FIXED VERSION - Now handles incomplete URLs from HeyGen API + TALKING PHOTOS SUPPORT
"""
import os
import requests
from typing import Optional, Dict, Any
from ..api.heygen import get_available_avatars
from ..logger.log_handler import log_info, log_error, log_warning

# ===============================================================================
# CHAPTER 1: URL VALIDATION AND FIXING UTILITIES
# ===============================================================================

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

# ===============================================================================
# CHAPTER 2: SINGLE AVATAR IMAGE RETRIEVAL - FIXED WITH TALKING PHOTOS SUPPORT
# ===============================================================================

def get_heygen_avatar_image(avatar_id: str, api_key: Optional[str] = None) -> Optional[str]:
    """
    Get the preview image URL for a specific HeyGen avatar
    FIXED VERSION - Now handles incomplete URLs + TALKING PHOTOS + PHOTO AVATARS
    
    Args:
        avatar_id: The HeyGen avatar ID (works for regular avatars, talking photos, and photo avatars)
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
            
        # STEP 1: Get all avatars from regular HeyGen API
        response = get_available_avatars(api_key)
        
        if response and response.get('success'):
            # STEP 2: Extract both regular avatars AND talking photos
            avatars = response.get('avatars', [])
            talking_photos = response.get('talking_photos', [])
            
            log_info(f"Searching in {len(avatars)} regular avatars and {len(talking_photos)} talking photos for {avatar_id}", "HeyGen Image Utils")
            
            # STEP 3: Combine both lists to search in all available avatars
            all_avatars = avatars + talking_photos
            
            # STEP 4: Find the specific avatar by ID
            for avatar in all_avatars:
                # Handle both avatar_id (regular avatars) and id (talking photos)
                current_avatar_id = avatar.get('avatar_id') or avatar.get('id')
                
                if current_avatar_id == avatar_id:
                    # STEP 5: Get the preview image URL (try multiple possible field names)
                    preview_url = (
                        avatar.get('preview_image_url') or 
                        avatar.get('image_url') or 
                        avatar.get('preview_image') or
                        avatar.get('thumbnail_image_url')
                    )
                    
                    if preview_url:
                        # STEP 6: Fix incomplete URL if needed and verify accessibility
                        fixed_url = fix_incomplete_avatar_url(preview_url)
                        if fixed_url:
                            log_info(f"Found and verified HeyGen image for {avatar_id}: {fixed_url}", "HeyGen Image Utils")
                            return fixed_url
                        else:
                            log_warning(f"Found but could not verify HeyGen image for {avatar_id}: {preview_url}", "HeyGen Image Utils")
                            # For talking photos, return the URL even if not accessible (auth issues)
                            if 'talking_photo' in preview_url or 'files2.heygen.ai' in preview_url:
                                log_info(f"Returning talking photo URL despite access issues: {preview_url}", "HeyGen Image Utils")
                                return preview_url
                            return None
                    else:
                        log_warning(f"Avatar {avatar_id} found but has no image URL", "HeyGen Image Utils")
                        return None
        
        # STEP 7: If not found in regular API, try photo avatar specific APIs
        log_info(f"Avatar {avatar_id} not found in regular API, trying photo avatar APIs", "HeyGen Image Utils")
        photo_avatar_url = search_photo_avatar_image(avatar_id, api_key)
        
        if photo_avatar_url:
            log_info(f"Found avatar {avatar_id} via photo avatar API: {photo_avatar_url}", "HeyGen Image Utils")
            return photo_avatar_url
                    
        log_error(f"Avatar {avatar_id} not found in any HeyGen API", "HeyGen Image Utils")
        return None
        
    except Exception as e:
        log_error(f"Error getting HeyGen avatar image for {avatar_id}", "HeyGen Image Utils", e)
        return None

# ===============================================================================
# CHAPTER 3: ALL AVATAR IMAGES RETRIEVAL - FIXED WITH TALKING PHOTOS SUPPORT
# ===============================================================================

def get_all_heygen_avatar_images(api_key: Optional[str] = None) -> Dict[str, str]:
    """
    Get a mapping of all HeyGen avatar IDs to their preview image URLs
    FIXED VERSION - Now handles incomplete URLs from HeyGen API + TALKING PHOTOS
    
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
            
        # STEP 1: Get all avatars from HeyGen API
        response = get_available_avatars(api_key)
        
        if not response or not response.get('success'):
            log_error(f"Failed to fetch avatars from HeyGen: {response.get('error', 'Unknown error') if response else 'No response'}", "HeyGen Image Utils")
            return {}
            
        # STEP 2: Extract both regular avatars AND talking photos
        avatars = response.get('avatars', [])
        talking_photos = response.get('talking_photos', [])
        
        log_info(f"Processing {len(avatars)} regular avatars and {len(talking_photos)} talking photos", "HeyGen Image Utils")
        
        # STEP 3: Combine both lists
        all_avatars = avatars + talking_photos
        
        # STEP 4: Create mapping with fixed URLs
        image_map = {}
        fixed_count = 0
        failed_count = 0
        
        for avatar in all_avatars:
            # Handle both avatar_id (regular avatars) and id (talking photos)
            avatar_id = avatar.get('avatar_id') or avatar.get('id')
            
            # Try multiple possible field names for image URL
            preview_url = (
                avatar.get('preview_image_url') or 
                avatar.get('image_url') or 
                avatar.get('preview_image') or
                avatar.get('thumbnail_image_url')
            )
            
            if avatar_id and preview_url:
                # STEP 5: Fix incomplete URL if needed
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

# ===============================================================================
# CHAPTER 4: AVATAR IMAGE ASSURANCE - MAIN FUNCTION WITH TALKING PHOTOS SUPPORT
# ===============================================================================

def ensure_avatar_has_heygen_image(avatar_id: str, current_image_url: Optional[str] = None, api_key: Optional[str] = None) -> str:
    """
    Ensure an avatar has the correct HeyGen image URL
    FIXED VERSION - Now handles incomplete URLs from HeyGen API + TALKING PHOTOS
    
    Args:
        avatar_id: The HeyGen avatar ID (works for both regular avatars and talking photos)
        current_image_url: Current image URL (if any)
        api_key: Optional API key, will use environment variable if not provided
        
    Returns:
        The best available image URL (HeyGen if available, otherwise fixed current, otherwise placeholder)
    """
    
    # STEP 1: Try to get the HeyGen image (this will be fixed automatically and includes talking photos)
    log_info(f"Attempting to get fresh HeyGen image for avatar {avatar_id}", "HeyGen Image Utils")
    heygen_image = get_heygen_avatar_image(avatar_id, api_key)
    
    if heygen_image:
        log_info(f"Successfully retrieved fresh HeyGen image for {avatar_id}: {heygen_image}", "HeyGen Image Utils")
        return heygen_image
    
    # STEP 2: If no HeyGen image found, try to fix the current image URL
    elif current_image_url:
        log_info(f"No fresh HeyGen image found for {avatar_id}, attempting to fix current URL", "HeyGen Image Utils")
        
        # Try to fix the current image URL if it's incomplete
        fixed_current = fix_incomplete_avatar_url(current_image_url)
        if fixed_current:
            log_info(f"Fixed existing image URL for {avatar_id}: {current_image_url} -> {fixed_current}", "HeyGen Image Utils")
            return fixed_current
        else:
            log_warning(f"Could not fix existing image URL for {avatar_id}: {current_image_url}", "HeyGen Image Utils")
            # Return the original URL anyway, might work in some contexts
            return current_image_url
    
    # STEP 3: No image available - return placeholder
    else:
        log_error(f"No image available for avatar {avatar_id} - using placeholder", "HeyGen Image Utils")
        return f"https://via.placeholder.com/150x150?text={avatar_id[:8]}"

# ===============================================================================
# CHAPTER 5: NEW PHOTO AVATAR SPECIFIC UTILITIES
# ===============================================================================

def get_photo_avatar_groups(api_key: str) -> Optional[list]:
    """
    Get all photo avatar groups from HeyGen API
    
    Args:
        api_key: HeyGen API key
        
    Returns:
        List of avatar groups or None if error
    """
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    try:
        log_info("Fetching photo avatar groups", "HeyGen Image Utils")
        
        response = requests.get(
            "https://api.heygen.com/v2/avatar_group.list",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("error") is None:
                groups = data.get("data", {}).get("avatar_group_list", [])
                log_info(f"Found {len(groups)} photo avatar groups", "HeyGen Image Utils")
                return groups
        
        log_error(f"Failed to fetch photo avatar groups: {response.status_code}", "HeyGen Image Utils")
        return None
        
    except Exception as e:
        log_error(f"Error fetching photo avatar groups", "HeyGen Image Utils", e)
        return None

def get_photo_avatars_in_group(api_key: str, group_id: str) -> Optional[list]:
    """
    Get photo avatars within a specific group
    
    Args:
        api_key: HeyGen API key
        group_id: ID of the avatar group
        
    Returns:
        List of avatars in group or None if error
    """
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    try:
        log_info(f"Fetching photo avatars in group {group_id}", "HeyGen Image Utils")
        
        response = requests.get(
            f"https://api.heygen.com/v2/avatar_group/{group_id}/avatars",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("error") is None:
                avatars = data.get("data", {}).get("avatar_list", [])
                log_info(f"Found {len(avatars)} photo avatars in group {group_id}", "HeyGen Image Utils")
                return avatars
        
        log_error(f"Failed to fetch photo avatars in group {group_id}: {response.status_code}", "HeyGen Image Utils")
        return None
        
    except Exception as e:
        log_error(f"Error fetching photo avatars in group {group_id}", "HeyGen Image Utils", e)
        return None

def get_individual_photo_avatar(api_key: str, photo_avatar_id: str) -> Optional[dict]:
    """
    Get individual photo avatar details
    
    Args:
        api_key: HeyGen API key
        photo_avatar_id: ID of the specific photo avatar
        
    Returns:
        Avatar details dict or None if error
    """
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    try:
        log_info(f"Fetching individual photo avatar {photo_avatar_id}", "HeyGen Image Utils")
        
        response = requests.get(
            f"https://api.heygen.com/v2/photo_avatar/{photo_avatar_id}",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("error") is None:
                avatar_data = data.get("data", {})
                log_info(f"Found photo avatar {photo_avatar_id}", "HeyGen Image Utils")
                return avatar_data
        
        log_error(f"Failed to fetch photo avatar {photo_avatar_id}: {response.status_code}", "HeyGen Image Utils")
        return None
        
    except Exception as e:
        log_error(f"Error fetching photo avatar {photo_avatar_id}", "HeyGen Image Utils", e)
        return None

def search_photo_avatar_image(avatar_id: str, api_key: str) -> Optional[str]:
    """
    Search for photo avatar image URL using photo avatar specific APIs
    
    Args:
        avatar_id: The photo avatar ID to search for
        api_key: HeyGen API key
        
    Returns:
        Fresh image URL or None if not found
    """
    try:
        log_info(f"Searching for photo avatar {avatar_id} using photo avatar APIs", "HeyGen Image Utils")
        
        # STEP 1: Try getting individual photo avatar directly
        avatar_data = get_individual_photo_avatar(api_key, avatar_id)
        if avatar_data:
            image_url = avatar_data.get('image_url')
            if image_url:
                log_info(f"Found photo avatar image via direct API: {image_url}", "HeyGen Image Utils")
                return image_url
        
        # STEP 2: Search through all avatar groups
        groups = get_photo_avatar_groups(api_key)
        if not groups:
            log_warning(f"No photo avatar groups found", "HeyGen Image Utils")
            return None
        
        # STEP 3: Search each group for the avatar ID
        for group in groups:
            group_id = group.get('id')
            if not group_id:
                continue
                
            avatars = get_photo_avatars_in_group(api_key, group_id)
            if not avatars:
                continue
                
            # STEP 4: Check each avatar in the group
            for avatar in avatars:
                current_id = avatar.get('id')
                if current_id == avatar_id:
                    image_url = avatar.get('image_url')
                    if image_url:
                        log_info(f"Found photo avatar {avatar_id} in group {group_id}: {image_url}", "HeyGen Image Utils")
                        return image_url
        
        log_warning(f"Photo avatar {avatar_id} not found in any groups", "HeyGen Image Utils")
        return None
        
    except Exception as e:
        log_error(f"Error searching for photo avatar {avatar_id}", "HeyGen Image Utils", e)
        return None

def get_talking_photo_image(talking_photo_id: str, api_key: Optional[str] = None) -> Optional[str]:
    """
    Specifically get image URL for a talking photo avatar
    ENHANCED - Now checks both regular API and photo avatar APIs
    
    Args:
        talking_photo_id: The talking photo ID
        api_key: Optional API key, will use environment variable if not provided
        
    Returns:
        The verified preview image URL or None if not found
    """
    try:
        if not api_key:
            api_key = os.getenv("HEYGEN_API_KEY")
            
        if not api_key:
            log_error("No HeyGen API key available", "HeyGen Image Utils")
            return None
            
        # STEP 1: Try regular avatars API first (for backward compatibility)
        response = get_available_avatars(api_key)
        
        if response and response.get('success'):
            # Check talking photos from regular API
            talking_photos = response.get('talking_photos', [])
            log_info(f"Searching for talking photo {talking_photo_id} in {len(talking_photos)} talking photos from regular API", "HeyGen Image Utils")
            
            for photo in talking_photos:
                photo_id = photo.get('id') or photo.get('avatar_id')
                
                if photo_id == talking_photo_id:
                    preview_url = (
                        photo.get('preview_image_url') or 
                        photo.get('image_url') or 
                        photo.get('preview_image')
                    )
                    
                    if preview_url:
                        log_info(f"Found talking photo image from regular API: {preview_url}", "HeyGen Image Utils")
                        return preview_url
        
        # STEP 2: Try photo avatar specific APIs
        log_info(f"Talking photo {talking_photo_id} not found in regular API, trying photo avatar APIs", "HeyGen Image Utils")
        photo_avatar_url = search_photo_avatar_image(talking_photo_id, api_key)
        
        if photo_avatar_url:
            return photo_avatar_url
            
        log_error(f"Talking photo {talking_photo_id} not found in any API", "HeyGen Image Utils")
        return None
        
    except Exception as e:
        log_error(f"Error getting talking photo image for {talking_photo_id}", "HeyGen Image Utils", e)
        return None

def is_talking_photo_id(avatar_id: str, api_key: Optional[str] = None) -> bool:
    """
    Check if an avatar ID belongs to a talking photo
    ENHANCED - Now checks both regular API and photo avatar APIs
    
    Args:
        avatar_id: The avatar ID to check
        api_key: Optional API key, will use environment variable if not provided
        
    Returns:
        True if it's a talking photo, False otherwise
    """
    try:
        if not api_key:
            api_key = os.getenv("HEYGEN_API_KEY")
            
        if not api_key:
            return False
        
        # Check regular API first
        response = get_available_avatars(api_key)
        
        if response and response.get('success'):
            talking_photos = response.get('talking_photos', [])
            
            for photo in talking_photos:
                photo_id = photo.get('id') or photo.get('avatar_id')
                if photo_id == avatar_id:
                    return True
        
        # Check photo avatar APIs
        photo_avatar_url = search_photo_avatar_image(avatar_id, api_key)
        return photo_avatar_url is not None
        
    except Exception:
        return False
