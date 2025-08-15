"""
Avatar Refresh Service Startup Integration
Automatically starts the avatar refresh service when the application starts
"""
import asyncio
import logging
from ..services.avatar_refresh_service import avatar_refresh_service
from ..logger.log_handler import log_info, log_error

logger = logging.getLogger(__name__)

async def initialize_avatar_refresh_service():
    """Initialize and start the avatar refresh service"""
    try:
        log_info("🚀 Initializing Avatar Refresh Service...", "Startup")
        
        # Start the service
        await avatar_refresh_service.start_service()
        
        # Get service status for logging
        status = avatar_refresh_service.get_service_status()
        
        if status['running']:
            log_info(f"✅ Avatar Refresh Service started successfully", "Startup")
            log_info(f"   - Refresh interval: {status['refresh_interval_minutes']} minutes", "Startup")
            log_info(f"   - Batch size: {status['batch_size']} avatars", "Startup")
            log_info(f"   - API configured: {status['api_key_configured']}", "Startup")
        else:
            log_error("❌ Avatar Refresh Service failed to start", "Startup")
            
    except Exception as e:
        log_error(f"Error initializing Avatar Refresh Service: {str(e)}", "Startup", e)

def get_avatar_refresh_status():
    """Get current avatar refresh service status"""
    try:
        return avatar_refresh_service.get_service_status()
    except Exception as e:
        log_error(f"Error getting avatar refresh status: {str(e)}", "Startup", e)
        return {
            "running": False,
            "error": str(e)
        }
