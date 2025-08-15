#!/usr/bin/env python3
"""
ISOLATED Notification Service for MyAvatar
Handles SMS and Email notifications WITHOUT touching any existing code
"""
import os
import sys
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
from twilio.rest import Client

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv()

class IsolatedNotificationService:
    """
    Completely isolated notification service
    Does NOT import or modify any existing MyAvatar code
    """
    
    def __init__(self):
        # Twilio configuration
        self.twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.twilio_phone_number = os.getenv("TWILIO_PHONE_NUMBER")
        
        # Email configuration
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.email_user = os.getenv("EMAIL_USER")
        self.email_password = os.getenv("EMAIL_PASSWORD")
        self.email_from = os.getenv("EMAIL_FROM", "noreply@myavatar.dk")
        
        # Database configuration
        self.database_url = os.getenv("DATABASE_URL")
        if self.database_url and self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql://", 1)
        
        # Initialize services
        self.twilio_client = None
        if self.twilio_account_sid and self.twilio_auth_token:
            try:
                self.twilio_client = Client(self.twilio_account_sid, self.twilio_auth_token)
                print("✅ Twilio SMS service initialized")
            except Exception as e:
                print(f"❌ Twilio initialization failed: {e}")
        
        if self.email_user and self.email_password:
            print("✅ Email service initialized")
        else:
            print("⚠️ Email not configured")
    
    def get_user_data(self, video_id):
        """Get user data for notification based on video ID"""
        try:
            conn = psycopg2.connect(self.database_url)
            cursor = conn.cursor()
            
            # Get user info from video
            cursor.execute("""
                SELECT u.id, u.name, u.email, u.phone_number, u.sms_notifications, 
                       u.is_premium, v.title
                FROM users u
                JOIN videos v ON u.id = v.user_id
                WHERE v.heygen_video_id = %s
            """, (video_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'user_id': result[0],
                    'name': result[1],
                    'email': result[2],
                    'phone_number': result[3],
                    'sms_notifications': result[4],
                    'is_premium': result[5],
                    'video_title': result[6]
                }
            return None
            
        except Exception as e:
            print(f"❌ Database error: {e}")
            return None
    
    def send_sms_notification(self, phone_number, message):
        """Send SMS via Twilio"""
        if not self.twilio_client:
            print("❌ Twilio not configured")
            return False
        
        try:
            message = self.twilio_client.messages.create(
                body=message,
                from_=self.twilio_phone_number,
                to=phone_number
            )
            print(f"✅ SMS sent to {phone_number}: {message.sid}")
            return True
        except Exception as e:
            print(f"❌ SMS failed to {phone_number}: {e}")
            return False
    
    def send_email_notification(self, email, video_title, user_name):
        """Send HTML email notification"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = email
            msg['Subject'] = f"🎬 Din video '{video_title}' er klar!"
            
            greeting = f"Hej {user_name}!" if user_name else "Hej!"
            
            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; color: white;">
                    <h1 style="margin: 0; font-size: 28px;">🎬 Din video er klar!</h1>
                </div>
                
                <div style="padding: 30px; background-color: #f9f9f9;">
                    <p style="font-size: 18px; color: #333;">{greeting}</p>
                    
                    <p style="font-size: 16px; color: #555;">
                        Din video <strong>"{video_title}"</strong> er nu færdig og klar til visning!
                    </p>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="https://app.myavatar.dk/dashboard" 
                           style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                  color: white; 
                                  padding: 15px 30px; 
                                  text-decoration: none; 
                                  border-radius: 25px; 
                                  font-weight: bold; 
                                  font-size: 16px;
                                  display: inline-block;">
                            🎥 Se din video nu
                        </a>
                    </div>
                    
                    <p style="font-size: 14px; color: #777; margin-top: 30px;">
                        💡 <strong>Tip:</strong> Opgrader til Premium for at få SMS notifikationer direkte på din telefon!
                    </p>
                </div>
                
                <div style="background-color: #333; padding: 20px; text-align: center; color: white;">
                    <p style="margin: 0; font-size: 14px;">
                        Med venlig hilsen,<br>
                        <strong>MyAvatar Team</strong>
                    </p>
                </div>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(html_body, 'html'))
            
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_user, self.email_password)
            text = msg.as_string()
            server.sendmail(self.email_from, email, text)
            server.quit()
            
            print(f"✅ Email sent to {email}")
            return True
            
        except Exception as e:
            print(f"❌ Email failed to {email}: {e}")
            return False
    
    def process_video_completion(self, video_id):
        """Main notification logic for video completion"""
        print(f"🔔 Processing notification for video: {video_id}")
        
        # Get user data
        user_data = self.get_user_data(video_id)
        if not user_data:
            print(f"❌ No user data found for video: {video_id}")
            return False
        
        user_name = user_data['name']
        video_title = user_data['video_title']
        is_premium = user_data['is_premium']
        sms_opt_in = user_data['sms_notifications']
        phone_number = user_data['phone_number']
        email = user_data['email']
        
        print(f"📊 User: {user_name}, Premium: {is_premium}, SMS: {sms_opt_in}")
        
        # Premium users with SMS opt-in get SMS
        if is_premium and sms_opt_in and phone_number:
            message = f"Hej {user_name}! Din video '{video_title}' er nu klar. Se den på MyAvatar.dk"
            print(f"📱 Sending SMS to premium user: {user_name}")
            return self.send_sms_notification(phone_number, message)
        
        # All other users get email
        elif email:
            print(f"📧 Sending email to user: {user_name}")
            return self.send_email_notification(email, video_title, user_name)
        
        else:
            print(f"⚠️ No notification method available for user: {user_name}")
            return False

# Standalone notification function
def notify_video_completion(video_id):
    """
    Standalone function to notify user of video completion
    Can be called from webhook handler without importing anything
    """
    service = IsolatedNotificationService()
    return service.process_video_completion(video_id)

if __name__ == "__main__":
    # Test the notification service
    import sys
    
    if len(sys.argv) > 1:
        video_id = sys.argv[1]
        print(f"🧪 Testing notification for video: {video_id}")
        result = notify_video_completion(video_id)
        print(f"📊 Result: {result}")
    else:
        print("🚀 Isolated Notification Service")
        print("=" * 50)
        print("Usage: python notification_service.py <video_id>")
        print("Example: python notification_service.py d7b74340b6614866a5ffda15a21aff1d")
        
        # Test configuration
        service = IsolatedNotificationService()
        print(f"📱 Twilio configured: {service.twilio_client is not None}")
        print(f"📧 Email configured: {service.email_user is not None}")
        print(f"🗄️ Database configured: {service.database_url is not None}")
