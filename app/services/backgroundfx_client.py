"""
Client for BackgroundFX microservice
Handles communication with the background replacement service
"""
import os
import io
import logging
import base64
import requests
from typing import Dict, Any, Optional, List, Union
from urllib.parse import urljoin
from fastapi import HTTPException

# Import notifications system - using try/except to handle potential import issues
try:
    from app.services.notifications import send_alert, notify_service_status
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False
    logging.warning("Notification system not available")
    
    # Dummy functions if notifications not available
    def send_alert(title, message, severity="info"):
        logging.warning(f"[ALERT-{severity.upper()}] {title}: {message}")
        
    def notify_service_status(service, status, details=None):
        logging.info(f"[SERVICE-{service}] Status: {status} - {details}")

# Configure logging
logger = logging.getLogger("myavatar.backgroundfx_client")

class BackgroundFXClient:
    """Client for communicating with the BackgroundFX microservice"""
    
    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize the BackgroundFX client
        
        Args:
            base_url: Base URL for the BackgroundFX service
        """
        # Get service URL from environment or use default
        self.base_url = base_url or os.environ.get(
            "BACKGROUNDFX_URL", 
            "http://localhost:8001"  # Default to local development
        )
        logger.info(f"BackgroundFX client initialized with URL: {self.base_url}")
    
    def health_check(self) -> bool:
        """
        Check if the BackgroundFX service is healthy
        
        Returns:
            True if service is healthy, False otherwise
        """
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logging.error(f"BackgroundFX health check error: {str(e)}")
            send_alert(
                title="BackgroundFX Connection Error",
                message=f"Failed to connect to BackgroundFX service: {str(e)}",
                severity="error"
            )
            return False
    
    def get_available_backgrounds(self) -> List[Dict[str, str]]:
        """
        Get list of available backgrounds
        
        Returns:
            List of background objects with id, name and description
        
        Raises:
            HTTPException: If service is unavailable
        """
        try:
            response = requests.get(f"{self.base_url}/api/available-backgrounds", timeout=5)
            response.raise_for_status()
            return response.json().get("backgrounds", [])
        except requests.RequestException as e:
            logging.error(f"Error fetching backgrounds: {str(e)}")
            send_alert(
                title="BackgroundFX Error",
                message=f"Failed to fetch backgrounds: {str(e)}",
                severity="error"
            )
            raise HTTPException(
                status_code=503, 
                detail="Background service is currently unavailable"
            )
    
    def replace_background(
        self, 
        image_data: bytes, 
        background_id: str,
        strength: float = 0.8,
        return_raw: bool = False
    ) -> Union[bytes, str]:
        """
        Replace background in image
        
        Args:
            image_data: Image as bytes
            background_id: ID of background to use
            strength: Effect strength (0.0-1.0)
            return_raw: If True, return raw bytes, otherwise base64 string
            
        Returns:
            Processed image as bytes or base64 string
            
        Raises:
            HTTPException: For service errors
        """
        try:
            # Determine endpoint based on return format
            endpoint = (
                "/api/replace-background-raw" if return_raw 
                else "/api/replace-background"
            )
            
            # Prepare files and form data
            files = {"image": ("image.jpg", image_data, "image/jpeg")}
            data = {"background_id": background_id, "strength": str(strength)}
            
            # Make request to service
            response = requests.post(
                f"{self.base_url}{endpoint}", 
                files=files, 
                data=data,
                timeout=30  # Longer timeout for image processing
            )
            response.raise_for_status()
            
            # Return appropriate format
            if return_raw:
                return response.content
            else:
                return response.json().get("image", "")
                
        except requests.RequestException as e:
            logging.error(f"Background replacement error: {str(e)}")
            send_alert(
                title="BackgroundFX Error",
                message=f"Failed to replace background: {str(e)}",
                severity="error"
            )
            if hasattr(e, "response") and e.response is not None:
                status_code = e.response.status_code
                try:
                    detail = e.response.json().get("detail", str(e))
                except:
                    detail = str(e)
            else:
                status_code = 503
                detail = "Background service is currently unavailable"
                
            raise HTTPException(status_code=status_code, detail=detail)

# Create a singleton instance
backgroundfx_client = BackgroundFXClient()
