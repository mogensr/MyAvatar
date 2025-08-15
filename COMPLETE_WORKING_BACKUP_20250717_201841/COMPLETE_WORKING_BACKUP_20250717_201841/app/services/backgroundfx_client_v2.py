"""
BackgroundFX Client for MyAvatar
Interface for interacting with the BackgroundFX microservice
"""
import os
import sys
import time
import base64
import logging
import requests
import json
from typing import Optional, Dict, Any, Tuple, Union
import cv2
import numpy as np
from pathlib import Path

# Setup paths for importing from libraryFX
LIBRARY_FX_PATH = os.path.join(Path.home(), "Projects", "Python", "libraryFX")
if os.path.exists(LIBRARY_FX_PATH):
    sys.path.insert(0, LIBRARY_FX_PATH)
    
    # Try to import from libraryFX
    try:
        from libraryFX.notifications.alerts import send_alert
        from libraryFX.core.config import load_config
        USING_LIBRARY_FX = True
        logger = logging.getLogger(__name__)
        logger.info("Using libraryFX for BackgroundFX client")
    except ImportError:
        USING_LIBRARY_FX = False
        logger = logging.getLogger(__name__)
        logger.warning("libraryFX not found, using legacy implementation")
        
        # Fallback dummy functions
        def send_alert(title, message, severity="info"):
            logger.warning(f"[ALERT-{severity.upper()}] {title}: {message}")
            
        def load_config(key, default=None):
            return os.environ.get(key, default)
else:
    USING_LIBRARY_FX = False
    logger = logging.getLogger(__name__)
    logger.warning("libraryFX not found, using legacy implementation")
    
    # Fallback dummy functions
    def send_alert(title, message, severity="info"):
        logger.warning(f"[ALERT-{severity.upper()}] {title}: {message}")
        
    def load_config(key, default=None):
        return os.environ.get(key, default)
    
class BackgroundFXClient:
    """Client for interacting with the BackgroundFX microservice"""
    
    def __init__(self, service_url=None):
        """
        Initialize the BackgroundFX client
        
        Args:
            service_url: URL of the BackgroundFX service
        """
        # Get service URL from environment or use default
        self.service_url = service_url or load_config("BACKGROUNDFX_SERVICE_URL", "http://localhost:5000")
        self.session = requests.Session()
        self.logger = logging.getLogger(__name__)
        
        # Track performance
        self.processing_times = []
        
        # Test connection to service
        try:
            self.check_connection()
            self.logger.info(f"BackgroundFX client initialized with service at {self.service_url}")
        except Exception as e:
            self.logger.error(f"Could not connect to BackgroundFX service: {e}")
            # We'll still initialize the client - maybe the service will be available later
        
    def check_connection(self) -> Dict[str, Any]:
        """
        Check if the BackgroundFX service is available
        
        Returns:
            Service health status
        
        Raises:
            ConnectionError: If the service is not available
        """
        try:
            response = self.session.get(f"{self.service_url}/health", timeout=5.0)
            response.raise_for_status()
            health_info = response.json()
            
            # Log service health info
            self.logger.info(f"BackgroundFX service health: {health_info}")
            
            # Send alert if GPU is not available
            if USING_LIBRARY_FX and not health_info.get("gpu_available", False):
                send_alert(
                    title="BackgroundFX Performance Warning",
                    message="BackgroundFX service is running without GPU acceleration. Performance may be degraded.",
                    severity="warning"
                )
                
            return health_info
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to connect to BackgroundFX service: {e}"
            self.logger.error(error_msg)
            if USING_LIBRARY_FX:
                send_alert(
                    title="BackgroundFX Connection Failed",
                    message=error_msg,
                    severity="error"
                )
            raise ConnectionError(error_msg)
    
    def replace_background(self, 
                          image: Union[np.ndarray, str, Path], 
                          background_id: Optional[int] = None,
                          background_image: Optional[Union[np.ndarray, str, Path]] = None,
                          quality: str = "medium") -> Tuple[np.ndarray, float]:
        """
        Replace the background in an image
        
        Args:
            image: Input image (numpy array) or path to image file
            background_id: ID of background to use
            background_image: Custom background image or path to image file
            quality: Quality level ("low", "medium", "high")
            
        Returns:
            Tuple of (processed image, processing time)
            
        Raises:
            ValueError: For invalid input
            ConnectionError: If the service is not available
            RuntimeError: If processing fails
        """
        start_time = time.time()
        
        # Convert image to base64
        if isinstance(image, (str, Path)):
            # Load image from file path
            image_path = str(image)
            if not os.path.exists(image_path):
                raise ValueError(f"Image file not found: {image_path}")
            with open(image_path, "rb") as f:
                image_base64 = base64.b64encode(f.read()).decode("utf-8")
        elif isinstance(image, np.ndarray):
            # Convert numpy array to base64
            _, buffer = cv2.imencode(".jpg", image)
            image_base64 = base64.b64encode(buffer).decode("utf-8")
        else:
            raise ValueError("Image must be a numpy array or a file path")
            
        # Prepare background if provided
        background_base64 = None
        if background_image is not None:
            if isinstance(background_image, (str, Path)):
                # Load background from file path
                bg_path = str(background_image)
                if not os.path.exists(bg_path):
                    raise ValueError(f"Background image file not found: {bg_path}")
                with open(bg_path, "rb") as f:
                    background_base64 = base64.b64encode(f.read()).decode("utf-8")
            elif isinstance(background_image, np.ndarray):
                # Convert numpy array to base64
                _, buffer = cv2.imencode(".jpg", background_image)
                background_base64 = base64.b64encode(buffer).decode("utf-8")
            else:
                raise ValueError("Background image must be a numpy array or a file path")
        
        # Prepare request data
        request_data = {
            "image_base64": image_base64,
            "quality": quality
        }
        
        if background_id is not None:
            request_data["background_id"] = background_id
        elif background_base64 is not None:
            request_data["background_base64"] = background_base64
        
        # Make API request
        try:
            response = self.session.post(
                f"{self.service_url}/replace-background",
                json=request_data,
                timeout=30.0  # Longer timeout for image processing
            )
            response.raise_for_status()
            result = response.json()
            
            if not result.get("success", False):
                error_msg = result.get("message", "Unknown error")
                self.logger.error(f"BackgroundFX processing failed: {error_msg}")
                if USING_LIBRARY_FX:
                    send_alert(
                        title="BackgroundFX Processing Failed",
                        message=f"Error: {error_msg}",
                        severity="error"
                    )
                raise RuntimeError(f"BackgroundFX processing failed: {error_msg}")
            
            # Decode the processed image
            processed_image_base64 = result.get("image_base64")
            if not processed_image_base64:
                raise RuntimeError("No processed image returned")
                
            image_data = base64.b64decode(processed_image_base64)
            nparr = np.frombuffer(image_data, np.uint8)
            processed_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            # Get processing time
            processing_time = result.get("processing_time", time.time() - start_time)
            self.processing_times.append(processing_time)
            
            # Log success
            self.logger.info(f"Background replacement completed in {processing_time:.2f} seconds")
            
            return processed_image, processing_time
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to connect to BackgroundFX service: {e}"
            self.logger.error(error_msg)
            if USING_LIBRARY_FX:
                send_alert(
                    title="BackgroundFX Connection Failed",
                    message=error_msg,
                    severity="error"
                )
            raise ConnectionError(error_msg)
    
    def upload_and_replace(self, 
                          image_path: Union[str, Path], 
                          background_id: Optional[int] = None,
                          quality: str = "medium") -> Tuple[np.ndarray, float]:
        """
        Upload an image file and replace the background
        
        Args:
            image_path: Path to image file
            background_id: ID of background to use
            quality: Quality level ("low", "medium", "high")
            
        Returns:
            Tuple of (processed image, processing time)
            
        Raises:
            ValueError: For invalid input
            ConnectionError: If the service is not available
            RuntimeError: If processing fails
        """
        start_time = time.time()
        
        # Validate image path
        if not os.path.exists(image_path):
            raise ValueError(f"Image file not found: {image_path}")
        
        # Prepare form data
        files = {
            "file": open(image_path, "rb")
        }
        
        form_data = {
            "quality": quality
        }
        
        if background_id is not None:
            form_data["background_id"] = str(background_id)
        
        # Make API request
        try:
            response = self.session.post(
                f"{self.service_url}/upload-and-replace",
                files=files,
                data=form_data,
                timeout=30.0  # Longer timeout for image processing
            )
            response.raise_for_status()
            
            # Get processing time from headers
            processing_time = float(response.headers.get("X-Processing-Time", "0"))
            self.processing_times.append(processing_time)
            
            # Read image from response
            image_data = response.content
            nparr = np.frombuffer(image_data, np.uint8)
            processed_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            # Log success
            self.logger.info(f"Background replacement completed in {processing_time:.2f} seconds")
            
            return processed_image, processing_time
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to connect to BackgroundFX service: {e}"
            self.logger.error(error_msg)
            if USING_LIBRARY_FX:
                send_alert(
                    title="BackgroundFX Connection Failed",
                    message=error_msg,
                    severity="error"
                )
            raise ConnectionError(error_msg)
        finally:
            # Make sure to close the file
            files["file"].close()
    
    def list_backgrounds(self) -> Dict[str, Any]:
        """
        List available backgrounds from the service
        
        Returns:
            Dict with background information
            
        Raises:
            ConnectionError: If the service is not available
        """
        try:
            response = self.session.get(f"{self.service_url}/backgrounds", timeout=5.0)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to connect to BackgroundFX service: {e}"
            self.logger.error(error_msg)
            if USING_LIBRARY_FX:
                send_alert(
                    title="BackgroundFX Connection Failed",
                    message=error_msg,
                    severity="error"
                )
            raise ConnectionError(error_msg)
    
    def upload_background(self, 
                         image_path: Union[str, Path], 
                         name: str,
                         description: str = "") -> Dict[str, Any]:
        """
        Upload a new background image to the service
        
        Args:
            image_path: Path to image file
            name: Name for the background
            description: Optional description
            
        Returns:
            Dict with upload information
            
        Raises:
            ValueError: For invalid input
            ConnectionError: If the service is not available
        """
        # Validate image path
        if not os.path.exists(image_path):
            raise ValueError(f"Image file not found: {image_path}")
        
        # Prepare form data
        files = {
            "file": open(image_path, "rb")
        }
        
        form_data = {
            "name": name,
            "description": description
        }
        
        # Make API request
        try:
            response = self.session.post(
                f"{self.service_url}/backgrounds/upload",
                files=files,
                data=form_data,
                timeout=10.0
            )
            response.raise_for_status()
            
            # Log success
            result = response.json()
            background_id = result.get("background_id")
            self.logger.info(f"Background '{name}' uploaded with ID {background_id}")
            
            return result
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to connect to BackgroundFX service: {e}"
            self.logger.error(error_msg)
            if USING_LIBRARY_FX:
                send_alert(
                    title="BackgroundFX Connection Failed",
                    message=error_msg,
                    severity="error"
                )
            raise ConnectionError(error_msg)
        finally:
            # Make sure to close the file
            files["file"].close()
    
    def get_average_processing_time(self) -> float:
        """Get the average processing time in seconds"""
        if not self.processing_times:
            return 0.0
        return sum(self.processing_times) / len(self.processing_times)

# Create a default client instance for easy import
try:
    default_client = BackgroundFXClient()
except Exception as e:
    logger.warning(f"Could not initialize default BackgroundFX client: {e}")
    default_client = None
