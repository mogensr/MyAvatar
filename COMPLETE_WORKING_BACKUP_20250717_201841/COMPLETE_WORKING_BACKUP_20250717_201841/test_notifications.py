"""
Test script for the new notification system integration
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the libraryFX path to Python path if needed
LIBRARY_FX_PATH = os.path.join(os.path.expanduser("~"), "Projects", "Python", "libraryFX")
if os.path.exists(LIBRARY_FX_PATH) and LIBRARY_FX_PATH not in sys.path:
    sys.path.append(LIBRARY_FX_PATH)

# Import our notification system
from app.services.notifications import send_alert, send_client_notification, notify_service_status

def test_alerts():
    """Test system alerts"""
    print("Testing system alerts...")
    
    # Test various severity levels
    send_alert(
        title="Test Info Alert",
        message="This is a test info alert from MyAvatar",
        severity="info"
    )
    
    send_alert(
        title="Test Warning Alert",
        message="This is a test warning alert from MyAvatar",
        severity="warning"
    )
    
    send_alert(
        title="Test Error Alert",
        message="This is a test error alert from MyAvatar",
        severity="error"
    )
    
    # Test service status notification
    notify_service_status(
        service_name="MyAvatar",
        status="warning",
        details="Testing service status notifications"
    )
    
    print("Alert tests completed. Check your SMS and email if configured.")

def test_client_notifications():
    """Test client notifications"""
    print("Testing client notifications...")
    
    # Test client notification
    client_id = "test_client"
    
    send_client_notification(
        client_id=client_id,
        title="Test Client Notification",
        message="This is a test notification for clients",
        severity="info",
        channels=["app"],
        metadata={
            "test_id": "123",
            "test_type": "integration"
        }
    )
    
    print(f"Client notification test completed for client {client_id}")

if __name__ == "__main__":
    print("Testing MyAvatar notification system integration with libraryFX")
    test_alerts()
    test_client_notifications()
