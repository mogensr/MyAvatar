"""
Example showing how to use the libraryFX integrations in MyAvatar
"""
import logging
from app.services.notifications import send_alert, send_client_notification, notify_service_status

# Set up logging
logging.basicConfig(level=logging.INFO)

# Example 1: System alerts for administrators
def example_system_alerts():
    """Examples of system alerts for admins/operators"""
    print("Example 1: System Alerts")
    
    # Info level alert - for general information
    send_alert(
        title="Database Backup Completed",
        message="Daily backup of user data completed successfully",
        severity="info"
    )
    
    # Warning level alert - for potential issues
    send_alert(
        title="High Server Load",
        message="Server load above 80% for past 15 minutes",
        severity="warning" 
    )
    
    # Error level alert - for critical issues
    send_alert(
        title="Payment Gateway Error",
        message="Stripe payment processing failed for 3 consecutive attempts",
        severity="error"
    )
    
    print("Alerts sent - check logs or SMS/email if configured")
    print()

# Example 2: Client notifications
def example_client_notifications():
    """Examples of client notifications"""
    print("Example 2: Client Notifications")
    
    client_id = "user_12345"
    
    # App notification (appears in the MyAvatar UI)
    send_client_notification(
        client_id=client_id,
        title="Welcome to MyAvatar",
        message="Your account has been successfully created",
        channels=["app"]
    )
    
    # Push notification (mobile or browser)
    send_client_notification(
        client_id=client_id,
        title="Avatar Ready",
        message="Your new avatar has been generated and is ready to view",
        channels=["push"],
        metadata={
            "avatar_id": "av_789",
            "redirect_url": "/avatars/av_789"
        }
    )
    
    # Multi-channel notification with action buttons
    send_client_notification(
        client_id=client_id,
        title="Subscription Expiring",
        message="Your premium subscription will expire in 3 days",
        channels=["app", "push", "email"],
        metadata={
            "subscription_id": "sub_456",
            "actions": [
                {
                    "label": "Renew Now",
                    "url": "/billing/renew/sub_456"
                },
                {
                    "label": "Change Plan",
                    "url": "/billing/plans"
                }
            ]
        }
    )
    
    print("Client notifications sent - check logs or notification endpoints")
    print()

# Example 3: Service status tracking
def example_service_status():
    """Examples of service status notifications"""
    print("Example 3: Service Status Updates")
    
    # Normal operation
    notify_service_status(
        service_name="BackgroundFX",
        status="up",
        details="Service running normally with optimal performance"
    )
    
    # Warning status
    notify_service_status(
        service_name="VideoFX",
        status="warning",
        details="Service experiencing higher than normal latency"
    )
    
    # Error status
    notify_service_status(
        service_name="Database",
        status="error",
        details="Connection pool exhausted, retry operations failing"
    )
    
    print("Service status notifications sent")
    print()

if __name__ == "__main__":
    print("LibraryFX Integration Examples\n")
    example_system_alerts()
    example_client_notifications()
    example_service_status()
