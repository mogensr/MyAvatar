"""
HF Space Warming Service - Proactive Wake-up for BackgroundFX
============================================================
Automatically warms up the HF Space when users log in to reduce first-use latency
"""

import asyncio
import logging
import os
import time
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class HFSpaceWarmer:
    """Service to proactively warm up HF Space to reduce latency"""
    
    def __init__(self):
        self.hf_space_url = os.getenv("HF_SPACE_URL", "https://MogensR-VideoBackgroundReplacer.hf.space")
        self.last_warm_time = None
        self.warm_interval = 300  # 5 minutes between warm attempts
        self.is_warming = False
        
    async def warm_hf_space_async(self) -> bool:
        """Asynchronously warm up the HF Space"""
        if self.is_warming:
            logger.info("🔥 HF Space warming already in progress, skipping")
            return True
            
        # Check if we warmed recently
        if self.last_warm_time:
            time_since_last = (datetime.now() - self.last_warm_time).total_seconds()
            if time_since_last < self.warm_interval:
                logger.info(f"🔥 HF Space warmed recently ({time_since_last:.0f}s ago), skipping")
                return True
        
        self.is_warming = True
        try:
            logger.info(f"🔥 Starting HF Space warm-up: {self.hf_space_url}")
            
            # Import gradio client
            from gradio_client import Client
            
            # Create client (timeout handled internally by gradio)
            client = Client(self.hf_space_url)
            
            # Try to get the API info (lightweight operation to wake the space)
            try:
                api_info = client.view_api()
                logger.info(f"✅ HF Space warmed successfully - API endpoints: {len(api_info.named_endpoints) if hasattr(api_info, 'named_endpoints') else 'unknown'}")
                self.last_warm_time = datetime.now()
                return True
            except Exception as api_error:
                logger.warning(f"⚠️ HF Space warming partial success (connected but API error): {api_error}")
                self.last_warm_time = datetime.now()
                return True  # Still consider it warmed since we connected
                
        except Exception as e:
            logger.warning(f"⚠️ HF Space warming failed: {e}")
            return False
        finally:
            self.is_warming = False
    
    def warm_hf_space_background(self) -> None:
        """Start HF Space warming in background thread"""
        try:
            # Create new event loop for background task
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Run the warming task
            result = loop.run_until_complete(self.warm_hf_space_async())
            
            # Clean up
            loop.close()
            
            if result:
                logger.info("🎉 Background HF Space warming completed successfully")
            else:
                logger.warning("⚠️ Background HF Space warming failed")
                
        except Exception as e:
            logger.error(f"💥 Background HF Space warming error: {e}")
    
    def trigger_warm_on_login(self, user_id: int) -> None:
        """Trigger HF Space warming when a user logs in"""
        try:
            import threading
            
            logger.info(f"🔥 Triggering HF Space warm-up for user {user_id}")
            
            # Start warming in background thread
            warm_thread = threading.Thread(
                target=self.warm_hf_space_background,
                name=f"HFSpaceWarmer-User{user_id}",
                daemon=True
            )
            warm_thread.start()
            
            logger.info(f"🚀 HF Space warming started in background for user {user_id}")
            
        except Exception as e:
            logger.error(f"💥 Failed to start HF Space warming for user {user_id}: {e}")

# Global instance
hf_warmer = HFSpaceWarmer()

# Convenience functions
def warm_hf_space_on_login(user_id: int) -> None:
    """Convenience function to warm HF Space on user login"""
    hf_warmer.trigger_warm_on_login(user_id)

def get_last_warm_time() -> Optional[datetime]:
    """Get the last time HF Space was warmed"""
    return hf_warmer.last_warm_time

def is_hf_space_warm() -> bool:
    """Check if HF Space was warmed recently"""
    if not hf_warmer.last_warm_time:
        return False
    
    time_since_warm = (datetime.now() - hf_warmer.last_warm_time).total_seconds()
    return time_since_warm < 600  # Consider warm if warmed within 10 minutes
