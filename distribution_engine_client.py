"""
DistributionEngine API Client for MyAvatar
Handles all communication with DistributionEngine for social media distribution
"""

import os
import requests
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class DistributionEngineClient:
    """Client for communicating with DistributionEngine API"""
    
    def __init__(self):
        self.base_url = os.getenv("DISTRIBUTION_ENGINE_URL", "https://distributionengine.railway.app")
        self.api_key = os.getenv("DISTRIBUTION_ENGINE_API_KEY", "")
        
        # Default headers
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "MyAvatar/1.0"
        }
        
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"
    
    def _make_request(self, method: str, endpoint: str, data: Dict = None, params: Dict = None) -> Dict[str, Any]:
        """Make HTTP request to DistributionEngine"""
        try:
            url = f"{self.base_url}{endpoint}"
            
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json()
                }
            else:
                logger.error(f"❌ DistributionEngine API error: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"API error: {response.status_code}",
                    "details": response.text
                }
                
        except requests.exceptions.Timeout:
            logger.error("❌ DistributionEngine API timeout")
            return {
                "success": False,
                "error": "API timeout"
            }
        except requests.exceptions.ConnectionError:
            logger.error("❌ DistributionEngine API connection error")
            return {
                "success": False,
                "error": "Connection error - DistributionEngine may be down"
            }
        except Exception as e:
            logger.error(f"❌ DistributionEngine API request failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # Social Media Platform Management
    def connect_platform(self, user_id: str, platform: str, redirect_url: str = None) -> Dict[str, Any]:
        """Initiate OAuth connection to a social media platform"""
        data = {
            "platform": platform,
            "user_id": user_id,
            "redirect_url": redirect_url
        }
        
        return self._make_request("POST", "/api/social-media/connect", data)
    
    def get_user_accounts(self, user_id: str, platform: str = None) -> Dict[str, Any]:
        """Get connected social media accounts for a user"""
        params = {}
        if platform:
            params["platform"] = platform
        
        return self._make_request("GET", f"/api/social-media/accounts/{user_id}", params=params)
    
    def disconnect_account(self, user_id: str, platform: str, account_id: str) -> Dict[str, Any]:
        """Disconnect a social media account"""
        return self._make_request("DELETE", f"/api/social-media/accounts/{user_id}/{platform}/{account_id}")
    
    # Content Optimization and Posting
    def optimize_content(self, user_id: str, content_data: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize content for multiple social media platforms"""
        data = {
            "user_id": user_id,
            **content_data
        }
        
        return self._make_request("POST", "/api/social-media/optimize-content", data)
    
    def post_content(self, user_id: str, content_data: Dict[str, Any]) -> Dict[str, Any]:
        """Post content to selected social media platforms"""
        data = {
            "user_id": user_id,
            **content_data
        }
        
        return self._make_request("POST", "/api/social-media/post-content", data)
    
    # Analytics and Insights
    def get_platform_analytics(self, user_id: str, platform: str, days: int = 30) -> Dict[str, Any]:
        """Get analytics for a specific platform"""
        params = {"days": days}
        return self._make_request("GET", f"/api/social-media/analytics/{user_id}/{platform}", params=params)
    
    def get_platform_requirements(self, platform: str) -> Dict[str, Any]:
        """Get technical requirements and best practices for a platform"""
        return self._make_request("GET", f"/api/social-media/platform-requirements/{platform}")
    
    # Convenience methods for common workflows
    def analyze_video_for_social_media(self, user_id: str, video_id: str, video_title: str, 
                                     video_description: str = "", target_platforms: List[str] = None) -> Dict[str, Any]:
        """Analyze video and generate optimized content for social media platforms"""
        if not target_platforms:
            target_platforms = ["linkedin", "facebook", "instagram", "twitter"]
        
        content_data = {
            "content_id": f"video_{video_id}",
            "title": video_title,
            "description": video_description,
            "video_url": f"/api/videos/{video_id}/download",  # MyAvatar video URL
            "target_platforms": target_platforms,
            "industry": "general"  # Could be determined from user profile
        }
        
        return self.optimize_content(user_id, content_data)
    
    def post_video_to_social_media(self, user_id: str, video_id: str, video_title: str,
                                 optimized_content: Dict[str, Any], selected_platforms: List[str]) -> Dict[str, Any]:
        """Post video content to selected social media platforms"""
        # Use optimized content for the first selected platform as base
        base_content = optimized_content.get("variations", {}).get(selected_platforms[0], {})
        
        content_data = {
            "content_id": f"video_{video_id}",
            "title": base_content.get("title", video_title),
            "description": base_content.get("description", ""),
            "video_url": f"/api/videos/{video_id}/download",
            "hashtags": base_content.get("hashtags", []),
            "call_to_action": base_content.get("call_to_action", ""),
            "platforms": selected_platforms
        }
        
        return self.post_content(user_id, content_data)
    
    def get_user_social_media_overview(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive social media overview for a user"""
        try:
            # Get connected accounts
            accounts_result = self.get_user_accounts(user_id)
            
            if not accounts_result["success"]:
                return accounts_result
            
            accounts = accounts_result["data"]["accounts"]
            
            # Get analytics for each connected platform
            analytics_data = {}
            for account in accounts:
                platform = account["platform"]
                analytics_result = self.get_platform_analytics(user_id, platform)
                
                if analytics_result["success"]:
                    analytics_data[platform] = analytics_result["data"]["analytics"]
                else:
                    analytics_data[platform] = {"error": "Failed to fetch analytics"}
            
            return {
                "success": True,
                "data": {
                    "connected_accounts": accounts,
                    "analytics": analytics_data,
                    "total_platforms": len(accounts),
                    "active_platforms": len([acc for acc in accounts if acc["is_active"]])
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Social media overview failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def health_check(self) -> Dict[str, Any]:
        """Check if DistributionEngine is healthy and accessible"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "status": "healthy",
                    "data": response.json()
                }
            else:
                return {
                    "success": False,
                    "status": "unhealthy",
                    "error": f"Health check failed: {response.status_code}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "status": "unreachable",
                "error": str(e)
            }

# Global client instance
distribution_client = DistributionEngineClient()
