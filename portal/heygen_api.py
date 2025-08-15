# portal/heygen_api.py
"""
HeyGen API Integration for MyAvatar
Handles communication with HeyGen API for avatar management
"""

import os
import requests
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()

class HeyGenAPI:
    """HeyGen API client for avatar management"""
    
    def __init__(self):
        self.api_key = os.getenv("HEYGEN_API_KEY", "")
        self.base_url = "https://api.heygen.com/v2"
        self.headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json"
        }
    
    def get_avatar_groups(self) -> Dict[str, Any]:
        """
        Get all available avatar groups
        
        Returns:
            Dict with avatar groups data or error
        """
        try:
            url = f"{self.base_url}/avatar_groups"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return {"success": True, "data": response.json().get("data", {})}
        except Exception as e:
            logger.error(f"❌ Failed to get avatar groups: {e}")
            return {"success": False, "error": str(e)}
    
    def get_avatars_in_group(self, group_id: str) -> Dict[str, Any]:
        """
        Get all avatars in a specific group
        
        Args:
            group_id: HeyGen avatar group ID
            
        Returns:
            Dict with avatars data or error
        """
        try:
            url = f"{self.base_url}/avatar_group/{group_id}/avatars"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return {"success": True, "data": response.json().get("data", {})}
        except Exception as e:
            logger.error(f"❌ Failed to get avatars in group {group_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def get_all_public_avatars(self) -> Dict[str, Any]:
        """
        Get all public avatars from all groups
        
        Returns:
            Dict with all public avatars or error
        """
        try:
            # First get all avatar groups
            groups_result = self.get_avatar_groups()
            if not groups_result.get("success"):
                return groups_result
            
            # Find public avatar groups
            public_groups = []
            for group in groups_result.get("data", {}).get("avatar_group_list", []):
                if group.get("is_public", False):
                    public_groups.append(group)
            
            # Get avatars from each public group
            all_avatars = []
            for group in public_groups:
                group_id = group.get("id")
                group_name = group.get("name", "Unknown Group")
                
                avatars_result = self.get_avatars_in_group(group_id)
                if avatars_result.get("success"):
                    avatars = avatars_result.get("data", {}).get("avatar_list", [])
                    # Add group info to each avatar
                    for avatar in avatars:
                        avatar["group_id"] = group_id
                        avatar["group_name"] = group_name
                    
                    all_avatars.extend(avatars)
            
            return {
                "success": True,
                "data": {
                    "avatar_count": len(all_avatars),
                    "avatar_list": all_avatars
                }
            }
        except Exception as e:
            logger.error(f"❌ Failed to get all public avatars: {e}")
            return {"success": False, "error": str(e)}

# Global instance
heygen_api = HeyGenAPI()
