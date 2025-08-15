"""
Notification service for MyAvatar
Handles email and SMS notifications for support interactions
"""
import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        # Email configuration
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.email_user = os.getenv('EMAIL_USER')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        self.admin_email = os.getenv('ADMIN_EMAIL', 'mogensr@gmail.com')
        
        # SMS configuration (using email-to-SMS gateway)
        self.admin_phone = os.getenv('ADMIN_PHONE')  # Format: 1234567890
        self.sms_gateway = os.getenv('SMS_GATEWAY', 'txt.att.net')  # AT&T gateway
        
    def send_support_notification(self, user_email: str, user_message: str, 
                                conversation_id: str, message_type: str = 'general') -> bool:
        """
        Send notification when user interacts with support avatar
        
        Args:
            user_email: User's email address
            user_message: The message from the user
            conversation_id: Unique conversation identifier
            message_type: Type of message (bug_report, feature_request, help_request, etc.)
        """
        try:
            # Send email notification
            email_sent = self._send_email_notification(
                user_email, user_message, conversation_id, message_type
            )
            
            # Send SMS notification for urgent messages
            sms_sent = False
            if message_type in ['bug_report', 'urgent_help']:
                sms_sent = self._send_sms_notification(
                    user_email, user_message, message_type
                )
            
            logger.info(f"📧 Support notification sent - Email: {email_sent}, SMS: {sms_sent}")
            return email_sent or sms_sent
            
        except Exception as e:
            logger.error(f"❌ Failed to send support notification: {str(e)}")
            return False
    
    def _send_email_notification(self, user_email: str, user_message: str, 
                               conversation_id: str, message_type: str) -> bool:
        """Send email notification to admin"""
        try:
            if not self.email_user or not self.email_password:
                logger.warning("Email credentials not configured")
                return False
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.email_user
            msg['To'] = self.admin_email
            msg['Subject'] = f"🤖 MyAvatar Support: {message_type.replace('_', ' ').title()}"
            
            # Email body
            body = f"""
New support interaction on MyAvatar platform:

📧 User: {user_email}
🔗 Conversation ID: {conversation_id}
📝 Message Type: {message_type.replace('_', ' ').title()}
⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

💬 User Message:
{user_message}

---
This is an automated notification from MyAvatar Support System.
Reply to this email or check the admin dashboard for more details.
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_user, self.email_password)
            text = msg.as_string()
            server.sendmail(self.email_user, self.admin_email, text)
            server.quit()
            
            logger.info(f"✅ Email notification sent to {self.admin_email}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send email notification: {str(e)}")
            return False
    
    def _send_sms_notification(self, user_email: str, user_message: str, message_type: str) -> bool:
        """Send SMS notification via email-to-SMS gateway"""
        try:
            if not self.admin_phone or not self.email_user or not self.email_password:
                logger.warning("SMS credentials not configured")
                return False
            
            # Create SMS message
            sms_address = f"{self.admin_phone}@{self.sms_gateway}"
            
            msg = MIMEText(f"🚨 MyAvatar {message_type.replace('_', ' ').title()}\n"
                          f"From: {user_email}\n"
                          f"Msg: {user_message[:100]}{'...' if len(user_message) > 100 else ''}")
            
            msg['From'] = self.email_user
            msg['To'] = sms_address
            msg['Subject'] = "MyAvatar Support Alert"
            
            # Send SMS
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_user, self.email_password)
            server.sendmail(self.email_user, sms_address, msg.as_string())
            server.quit()
            
            logger.info(f"📱 SMS notification sent to {self.admin_phone}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send SMS notification: {str(e)}")
            return False

# Global instance
notification_service = NotificationService()

def send_support_notification(user_email: str, user_message: str, 
                            conversation_id: str, message_type: str = 'general') -> bool:
    """Convenience function to send support notifications"""
    return notification_service.send_support_notification(
        user_email, user_message, conversation_id, message_type
    )
