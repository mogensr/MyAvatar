# ===============================================================================
# HEYGEN AVATAR SUPPORT - ALL AVATAR TYPES
# ===============================================================================
# 🎯 Modular support for all HeyGen avatar types
# 📸 Photo Avatars, ⚡ Instant Avatars, 🎬 Studio Avatars, 
# 🎮 Interactive Avatars, 🎭 Video-to-Avatar Clones
# ===============================================================================

import logging
import requests
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class HeyGenAvatarManager:
    """
    Complete HeyGen Avatar Manager supporting all avatar types
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {"X-API-KEY": api_key}
    
    def find_avatar(self, avatar_id: str) -> Optional[Dict[str, Any]]:
        """
        Find avatar across all HeyGen endpoints
        
        Args:
            avatar_id: The HeyGen avatar ID to search for
            
        Returns:
            Dict with avatar data if found, None if not found
        """
        avatar_id = avatar_id.strip()
        logger.info(f"🔍 Searching for avatar: {avatar_id}")
        
        # Try all endpoints in order of likelihood
        search_methods = [
            self._search_photo_avatars,
            self._search_instant_avatars,
            self._search_studio_avatars,
            self._search_interactive_avatars,
            self._search_video_clones,
            self._search_legacy_endpoint
        ]
        
        for search_method in search_methods:
            try:
                result = search_method(avatar_id)
                if result:
                    logger.info(f"✅ Found avatar via {search_method.__name__}")
                    return result
            except Exception as e:
                logger.warning(f"❌ {search_method.__name__} failed: {e}")
                continue
        
        logger.warning(f"❌ Avatar {avatar_id} not found in any endpoint")
        return None
    
    def _search_photo_avatars(self, avatar_id: str) -> Optional[Dict[str, Any]]:
        """Search Photo Avatars (Talking Photos)"""
        logger.info("📸 Searching Photo Avatars...")
        
        url = "https://api.heygen.com/v1/talking_photo.list"
        response = requests.get(url, headers=self.headers, timeout=10)
        
        if response.status_code != 200:
            logger.warning(f"Photo API returned {response.status_code}")
            return None
        
        data = response.json()
        photos = data.get("data", {}).get("talking_photos", [])
        logger.info(f"📸 Found {len(photos)} photo avatars")
        
        for photo in photos:
            if photo.get("id") == avatar_id:
                return {
                    "data": {
                        "name": photo.get("name", f"Photo Avatar {avatar_id[:8]}"),
                        "preview_image_url": photo.get("preview_image_url"),
                        "image_url": photo.get("image_url"),
                        "type": "photo_avatar"
                    },
                    "type": "talking_photo",
                    "source": "photo_avatars"
                }
        
        return None
    
    def _search_instant_avatars(self, avatar_id: str) -> Optional[Dict[str, Any]]:
        """Search Instant Avatars"""
        logger.info("⚡ Searching Instant Avatars...")
        
        url = "https://api.heygen.com/v1/avatar.list"
        response = requests.get(url, headers=self.headers, timeout=10)
        
        if response.status_code != 200:
            logger.warning(f"Instant Avatar API returned {response.status_code}")
            return None
        
        data = response.json()
        avatars = data.get("data", {}).get("avatars", [])
        logger.info(f"⚡ Found {len(avatars)} instant avatars")
        
        for avatar in avatars:
            if avatar.get("avatar_id") == avatar_id:
                return {
                    "data": {
                        "name": avatar.get("avatar_name", f"Instant Avatar {avatar_id[:8]}"),
                        "preview_image_url": avatar.get("preview_image_url"),
                        "image_url": avatar.get("image_url"),
                        "type": "instant_avatar"
                    },
                    "type": "instant_avatar",
                    "source": "instant_avatars"
                }
        
        return None
    
    def _search_studio_avatars(self, avatar_id: str) -> Optional[Dict[str, Any]]:
        """Search Studio Avatars (v2 API)"""
        logger.info("🎬 Searching Studio Avatars...")
        
        url = "https://api.heygen.com/v2/avatars"
        response = requests.get(url, headers=self.headers, timeout=10)
        
        if response.status_code != 200:
            logger.warning(f"Studio Avatar API returned {response.status_code}")
            return None
        
        data = response.json()
        avatars = data.get("data", [])
        logger.info(f"🎬 Found {len(avatars)} studio avatars")
        
        for avatar in avatars:
            if avatar.get("avatar_id") == avatar_id:
                return {
                    "data": {
                        "name": avatar.get("name", f"Studio Avatar {avatar_id[:8]}"),
                        "preview_image_url": avatar.get("preview_image_url"),
                        "image_url": avatar.get("image_url"),
                        "type": "studio_avatar"
                    },
                    "type": "studio_avatar",
                    "source": "studio_avatars"
                }
        
        return None
    
    def _search_interactive_avatars(self, avatar_id: str) -> Optional[Dict[str, Any]]:
        """Search Interactive Avatars (Streaming)"""
        logger.info("🎮 Searching Interactive Avatars...")
        
        url = "https://api.heygen.com/v1/streaming.list"
        response = requests.get(url, headers=self.headers, timeout=10)
        
        if response.status_code != 200:
            logger.warning(f"Interactive Avatar API returned {response.status_code}")
            return None
        
        data = response.json()
        avatars = data.get("data", [])
        logger.info(f"🎮 Found {len(avatars)} interactive avatars")
        
        for avatar in avatars:
            if avatar.get("avatar_id") == avatar_id:
                return {
                    "data": {
                        "name": avatar.get("avatar_name", f"Interactive Avatar {avatar_id[:8]}"),
                        "preview_image_url": avatar.get("preview_image_url"),
                        "image_url": avatar.get("image_url"),
                        "type": "interactive_avatar"
                    },
                    "type": "interactive_avatar",
                    "source": "interactive_avatars"
                }
        
        return None
    
    def _search_video_clones(self, avatar_id: str) -> Optional[Dict[str, Any]]:
        """Search Video-to-Avatar Clones"""
        logger.info("🎭 Searching Video Clones...")
        
        # Try with custom type filter first
        url = "https://api.heygen.com/v1/avatar.list"
        params = {"type": "custom"}
        response = requests.get(url, headers=self.headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            avatars = data.get("data", {}).get("avatars", [])
            logger.info(f"🎭 Found {len(avatars)} custom avatars")
            
            for avatar in avatars:
                if avatar.get("avatar_id") == avatar_id:
                    return {
                        "data": {
                            "name": avatar.get("avatar_name", f"Video Clone {avatar_id[:8]}"),
                            "preview_image_url": avatar.get("preview_image_url"),
                            "image_url": avatar.get("image_url"),
                            "type": "video_clone"
                        },
                        "type": "video_to_avatar",
                        "source": "video_clones"
                    }
        
        # Try without type filter (get all and check for custom types)
        response = requests.get(url, headers=self.headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            avatars = data.get("data", {}).get("avatars", [])
            
            for avatar in avatars:
                if (avatar.get("avatar_id") == avatar_id and 
                    avatar.get("type") in ["custom", "clone", "personal"]):
                    return {
                        "data": {
                            "name": avatar.get("avatar_name", f"Custom Avatar {avatar_id[:8]}"),
                            "preview_image_url": avatar.get("preview_image_url"),
                            "image_url": avatar.get("image_url"),
                            "type": "custom_avatar"
                        },
                        "type": "custom_avatar",
                        "source": "video_clones"
                    }
        
        return None
    
    def _search_legacy_endpoint(self, avatar_id: str) -> Optional[Dict[str, Any]]:
        """Search using legacy/existing endpoint"""
        logger.info("🔧 Trying legacy endpoint...")
        
        try:
            # This would use your existing get_avatar_from_any_endpoint function
            # Import it here to avoid circular imports
            from ..api.heygen import get_avatar_from_any_endpoint
            result = get_avatar_from_any_endpoint(self.api_key, avatar_id)
            
            if result:
                return {
                    "data": result.get("data", {}),
                    "type": "legacy",
                    "source": "legacy_endpoint"
                }
        except ImportError:
            logger.warning("Legacy endpoint function not available")
        except Exception as e:
            logger.warning(f"Legacy endpoint failed: {e}")
        
        return None
    
    def get_avatar_name_and_image(self, avatar_id: str) -> tuple[str, str]:
        """
        Get avatar name and image URL, with fallbacks
        
        Returns:
            tuple: (avatar_name, avatar_image_url)
        """
        result = self.find_avatar(avatar_id)
        
        if result and result.get("data"):
            data = result["data"]
            avatar_type = result.get("type", "unknown")
            
            # Get name
            name = (data.get("name") or 
                   data.get("avatar_name") or 
                   f"HeyGen {avatar_type.title()} {avatar_id[:8]}")
            
            # Get image URL
            image_url = (data.get("preview_image_url") or 
                        data.get("image_url") or 
                        data.get("preview_image") or
                        f"https://files2.heygen.ai/avatar/v3/{avatar_id}/{avatar_id}.jpg")
            
            logger.info(f"✅ Resolved: {name} ({avatar_type})")
            return name, image_url
        else:
            # Fallback for unknown avatar
            logger.warning(f"⚠️ Using fallback for unknown avatar: {avatar_id}")
            fallback_name = f"Unknown Avatar {avatar_id[:8]}"
            fallback_image = f"https://files2.heygen.ai/avatar/v3/{avatar_id}/{avatar_id}.jpg"
            return fallback_name, fallback_image


# ===============================================================================
# CONVENIENCE FUNCTIONS
# ===============================================================================

def find_heygen_avatar(api_key: str, avatar_id: str) -> Optional[Dict[str, Any]]:
    """
    Convenience function to find a HeyGen avatar
    
    Args:
        api_key: HeyGen API key
        avatar_id: Avatar ID to search for
        
    Returns:
        Avatar data if found, None otherwise
    """
    if not api_key:
        logger.warning("No HeyGen API key provided")
        return None
    
    manager = HeyGenAvatarManager(api_key)
    return manager.find_avatar(avatar_id)


def get_heygen_avatar_details(api_key: str, avatar_id: str) -> tuple[str, str]:
    """
    Convenience function to get avatar name and image URL
    
    Args:
        api_key: HeyGen API key
        avatar_id: Avatar ID to search for
        
    Returns:
        tuple: (avatar_name, avatar_image_url)
    """
    if not api_key:
        logger.warning("No HeyGen API key provided - using fallback")
        return f"Avatar {avatar_id[:8]}", f"https://files2.heygen.ai/avatar/v3/{avatar_id}/{avatar_id}.jpg"
    
    manager = HeyGenAvatarManager(api_key)
    return manager.get_avatar_name_and_image(avatar_id)


# ===============================================================================
# USAGE EXAMPLE
# ===============================================================================

if __name__ == "__main__":
    # Example usage
    api_key = "your_heygen_api_key"
    avatar_id = "7e07203217034961a2bafa14c1cf141e"  # Your Photo Avatar
    
    # Find avatar
    result = find_heygen_avatar(api_key, avatar_id)
    if result:
        print(f"Found: {result}")
    
    # Get name and image
    name, image_url = get_heygen_avatar_details(api_key, avatar_id)
    print(f"Name: {name}")
    print(f"Image: {image_url}")
