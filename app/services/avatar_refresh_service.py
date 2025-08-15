"""
Automated Avatar Refresh Service
Keeps all HeyGen avatars active and image URLs up-to-date 24/7
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import os
from ..db.database import execute_query
from ..api.heygen import get_avatar_from_any_endpoint
from ..logger.log_handler import log_info, log_error, log_warning

logger = logging.getLogger(__name__)

class AvatarRefreshService:
    """Service to automatically refresh avatar data from HeyGen API"""
    
    def __init__(self):
        self.api_key = os.getenv("HEYGEN_API_KEY")
        self.refresh_interval = 3600  # 1 hour in seconds
        self.batch_size = 10  # Process avatars in batches
        self.is_running = False
        
    async def start_service(self):
        """Start the automated avatar refresh service"""
        if self.is_running:
            log_warning("Avatar refresh service is already running", "Avatar Service")
            return
            
        if not self.api_key:
            log_error("HEYGEN_API_KEY not found - avatar refresh service disabled", "Avatar Service")
            return
            
        self.is_running = True
        log_info("🔄 Starting automated avatar refresh service", "Avatar Service")
        
        # Start the refresh loop
        asyncio.create_task(self._refresh_loop())
        
    async def stop_service(self):
        """Stop the automated avatar refresh service"""
        self.is_running = False
        log_info("⏹️ Stopped automated avatar refresh service", "Avatar Service")
        
    async def _refresh_loop(self):
        """Main refresh loop that runs continuously"""
        while self.is_running:
            try:
                await self._refresh_all_avatars()
                log_info(f"✅ Avatar refresh completed. Next refresh in {self.refresh_interval/60} minutes", "Avatar Service")
                
                # Wait for next refresh interval
                await asyncio.sleep(self.refresh_interval)
                
            except Exception as e:
                log_error(f"Error in avatar refresh loop: {str(e)}", "Avatar Service", e)
                # Wait 5 minutes before retrying on error
                await asyncio.sleep(300)
                
    async def _refresh_all_avatars(self):
        """Refresh all avatars in the database"""
        try:
            # Get all unique avatar IDs from database
            avatars = execute_query(
                "SELECT DISTINCT avatar_id, COUNT(*) as usage_count FROM user_avatars GROUP BY avatar_id ORDER BY usage_count DESC",
                fetch_all=True
            )
            
            if not avatars:
                log_info("No avatars found to refresh", "Avatar Service")
                return
                
            log_info(f"🔄 Refreshing {len(avatars)} unique avatars", "Avatar Service")
            
            # Process avatars in batches to avoid API rate limits
            for i in range(0, len(avatars), self.batch_size):
                batch = avatars[i:i + self.batch_size]
                await self._refresh_avatar_batch(batch)
                
                # Small delay between batches to be nice to HeyGen API
                if i + self.batch_size < len(avatars):
                    await asyncio.sleep(2)
                    
        except Exception as e:
            log_error(f"Error refreshing avatars: {str(e)}", "Avatar Service", e)
            
    async def _refresh_avatar_batch(self, avatar_batch: List[Dict[str, Any]]):
        """Refresh a batch of avatars"""
        for avatar_row in avatar_batch:
            try:
                avatar_id = avatar_row['avatar_id']
                usage_count = avatar_row['usage_count']
                
                log_info(f"🔄 Refreshing avatar {avatar_id} (used by {usage_count} users)", "Avatar Service")
                
                # Get fresh avatar data from HeyGen
                avatar_data = get_avatar_from_any_endpoint(self.api_key, avatar_id)
                
                if avatar_data and 'data' in avatar_data:
                    # Extract image URL from the response
                    image_url = self._extract_image_url(avatar_data)
                    
                    if image_url:
                        # Update all users who have this avatar
                        updated_count = execute_query(
                            "UPDATE user_avatars SET avatar_image_url = %s WHERE avatar_id = %s",
                            (image_url, avatar_id)
                        )
                        
                        log_info(f"✅ Updated avatar {avatar_id} image URL for {updated_count} users", "Avatar Service")
                    else:
                        log_warning(f"⚠️ No image URL found for avatar {avatar_id}", "Avatar Service")
                else:
                    log_warning(f"⚠️ Failed to fetch data for avatar {avatar_id}", "Avatar Service")
                    
            except Exception as e:
                log_error(f"Error refreshing avatar {avatar_id}: {str(e)}", "Avatar Service", e)
                
    def _extract_image_url(self, avatar_data: Dict[str, Any]) -> str:
        """Extract image URL from HeyGen API response"""
        try:
            data = avatar_data.get('data', {})
            
            # Try different possible image URL fields
            image_fields = [
                'avatar_image',
                'preview_image_url', 
                'image_url',
                'preview_image',
                'thumbnail_url',
                'avatar_image_url'
            ]
            
            for field in image_fields:
                if field in data and data[field]:
                    return data[field]
                    
            # For talking photos, try nested structure
            if 'talking_photo' in data:
                talking_photo = data['talking_photo']
                for field in image_fields:
                    if field in talking_photo and talking_photo[field]:
                        return talking_photo[field]
                        
            log_warning(f"No image URL found in avatar data: {list(data.keys())}", "Avatar Service")
            return None
            
        except Exception as e:
            log_error(f"Error extracting image URL: {str(e)}", "Avatar Service", e)
            return None
            
    async def refresh_single_avatar(self, avatar_id: str) -> bool:
        """Manually refresh a single avatar (for immediate fixes)"""
        try:
            log_info(f"🔄 Manual refresh for avatar {avatar_id}", "Avatar Service")
            
            if not self.api_key:
                log_error("HEYGEN_API_KEY not found", "Avatar Service")
                return False
                
            # Get fresh avatar data
            avatar_data = get_avatar_from_any_endpoint(self.api_key, avatar_id)
            
            if avatar_data and 'data' in avatar_data:
                image_url = self._extract_image_url(avatar_data)
                
                if image_url:
                    # Update database
                    updated_count = execute_query(
                        "UPDATE user_avatars SET avatar_image_url = %s WHERE avatar_id = %s",
                        (image_url, avatar_id)
                    )
                    
                    log_info(f"✅ Manual refresh successful for avatar {avatar_id} ({updated_count} users updated)", "Avatar Service")
                    return True
                    
            log_error(f"❌ Manual refresh failed for avatar {avatar_id}", "Avatar Service")
            return False
            
        except Exception as e:
            log_error(f"Error in manual avatar refresh: {str(e)}", "Avatar Service", e)
            return False
            
    def get_service_status(self) -> Dict[str, Any]:
        """Get current service status"""
        return {
            "running": self.is_running,
            "api_key_configured": bool(self.api_key),
            "refresh_interval_minutes": self.refresh_interval / 60,
            "batch_size": self.batch_size
        }

# Global service instance
avatar_refresh_service = AvatarRefreshService()
