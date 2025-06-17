"""
Notifications service for MyAvatar
Uses the libraryFX notifications system for alerts and client notifications
"""
import os
import sys
import logging
from pathlib import Path
import traceback

# Configure logging before anything else
logger = logging.getLogger("myavatar.services.notifications")

# Add libraryFX to Python path for development
# In production, you'd install the package properly
LIBRARY_FX_PATH = os.path.join(Path.home(), "Projects", "Python", "libraryFX")
if os.path.exists(LIBRARY_FX_PATH):
    logger.info(f"Found libraryFX at {LIBRARY_FX_PATH}")
    # Add main package path
    if LIBRARY_FX_PATH not in sys.path:
        sys.path.insert(0, LIBRARY_FX_PATH)
    
    # Add individual module paths for direct importing if needed
    for module in ["core", "notifications", "billing", "media", "distribution"]:
        module_path = os.path.join(LIBRARY_FX_PATH, module)
        if os.path.exists(module_path) and module_path not in sys.path:
            sys.path.insert(0, module_path)
            logger.debug(f"Added {module} module to path: {module_path}")
else:
    logger.warning(f"libraryFX not found at expected path: {LIBRARY_FX_PATH}")

# Import from libraryFX with detailed error handling
try:
    # Try importing from libraryFX
    from libraryFX.notifications.alerts import initialize_default_alert_manager, send_alert
    from libraryFX.notifications.client import initialize_default_client_notification_manager, send_client_notification
    
    # Initialize alert manager for MyAvatar
    try:
        alert_manager = initialize_default_alert_manager("MyAvatar")
        logger.info("Alert manager initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize alert manager: {e}")
        raise
    
    # Initialize client notification manager
    try:
        client_notifier = initialize_default_client_notification_manager("MyAvatar")
        logger.info("Client notification manager initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize client notification manager: {e}")
        raise
    
    USING_LIBRARY_FX = True
    logger.info("Successfully configured libraryFX notifications system")
    
except ImportError as e:
    # Detailed import error handling
    USING_LIBRARY_FX = False
    logger.warning(f"libraryFX import error: {e}")
    logger.warning("Using legacy notifications as fallback")
    
    if LIBRARY_FX_PATH in sys.path:
        logger.debug(f"Current sys.path: {sys.path}")
        # Try to find the specific module causing the import error
        try:
            import libraryFX
            logger.debug(f"libraryFX base package found at {libraryFX.__file__}")
        except ImportError:
            logger.error("Cannot import base libraryFX package")
    
    # Simple legacy notification functions for backward compatibility
    def send_alert(title, message, severity="info"):
        """Legacy alert function"""
        logger.warning(f"[ALERT-{severity.upper()}] {title}: {message}")
    
    def send_client_notification(client_id, title, message, **kwargs):
        """Legacy client notification function"""
        logger.warning(f"[NOTIFICATION] To {client_id}: {title} - {message}")
except Exception as e:
    # Catch any other exceptions during import/initialization
    USING_LIBRARY_FX = False
    logger.error(f"Unexpected error setting up notifications: {e}")
    logger.error(traceback.format_exc())
    
    # Emergency fallback functions
    def send_alert(title, message, severity="info"):
        print(f"[ALERT-{severity.upper()}] {title}: {message}")
        logger.warning(f"[ALERT-{severity.upper()}] {title}: {message}")
    
    def send_client_notification(client_id, title, message, **kwargs):
        print(f"[NOTIFICATION] To {client_id}: {title} - {message}")
        logger.warning(f"[NOTIFICATION] To {client_id}: {title} - {message}")

# Public API - export only stable interface functions
__all__ = ['send_alert', 'send_client_notification', 'notify_admin', 
          'notify_user', 'notify_service_status', 'USING_LIBRARY_FX']


# Helper functions with improved error handling
def notify_admin(title, message, severity="info"):
    """Send notification to administrators"""
    send_alert(title, message, severity)


def notify_user(user_id, title, message, severity="info", **kwargs):
    """Send notification to a user"""
    metadata = kwargs.pop('metadata', {})
    channels = kwargs.pop('channels', ["app", "push"])
    
    send_client_notification(
        client_id=user_id,
        title=title,
        message=message,
        severity=severity,
        channels=channels,
        metadata=metadata
    )


def notify_service_status(service_name, status, details=None):
    """Send service status notification"""
    if status == "up":
        severity = "info"
        message = f"Service {service_name} is up and running"
    elif status == "warning":
        severity = "warning"
        message = f"Service {service_name} is experiencing issues"
    else:
        severity = "critical"
        message = f"Service {service_name} is down"
    
    if details:
        message += f": {details}"
        
    send_alert(f"{service_name} Status", message, severity)
