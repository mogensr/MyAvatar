#!/usr/bin/env python3
"""
COMPLETE Notification Service for MyAvatar
SMS (Twilio) + Email (Resend) - ISOLATED MODULE
Zero changes to existing code!
"""
import os
import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv()

class NotificationService:
    """Complete notification service with SMS and Email"""
    
    def __init__(self):
        # Database
        self.database_url = os.getenv("DATABASE_URL")
        if self.database_url and self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql://", 1)
        
        # Twilio SMS
        self.twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.twilio_phone = os.getenv("TWILIO_PHONE_NUMBER")
        
        # Resend Email
        self.resend_key = os.getenv("RESEND_API_KEY")
        self.email_from = os.getenv("EMAIL_FROM", "noreply@myavatar.dk")
    
    def get_user_and_video_info(self, video_id):
        """Get user and video information from database"""
        try:
            conn = psycopg2.connect(self.database_url)
            cursor = conn.cursor()
            
            query = """
                SELECT v.title, v.id, u.id, u.name, u.email, u.phone_number, 
                       u.country_code, u.sms_notifications, u.is_premium
                FROM videos v
                JOIN users u ON v.user_id = u.id
                WHERE v.id = %s
            """
            
            cursor.execute(query, (video_id,))
            result = cursor.fetchone()
            
            if result:
                return {
                    'video_title': result[0],
                    'video_id': result[1],
                    'user_id': result[2],
                    'user_name': result[3],
                    'user_email': result[4],
                    'phone_number': result[5],
                    'country_code': result[6],
                    'sms_notifications': result[7],
                    'is_premium': result[8]
                }
            
            conn.close()
            return None
            
        except Exception as e:
            print(f"❌ Database error: {e}")
            return None
    
    def send_sms(self, phone_number, message):
        """Send SMS via Twilio"""
        if not all([self.twilio_sid, self.twilio_token, self.twilio_phone]):
            print("❌ Twilio not configured")
            return False
        
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{self.twilio_sid}/Messages.json"
            
            data = {
                'From': self.twilio_phone,
                'To': phone_number,
                'Body': message
            }
            
            response = requests.post(
                url,
                data=data,
                auth=(self.twilio_sid, self.twilio_token)
            )
            
            if response.status_code == 201:
                print(f"✅ SMS sent to {phone_number}")
                return True
            else:
                print(f"❌ SMS failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ SMS error: {e}")
            return False
    
    def send_email(self, to_email, video_title, user_name):
        """Send email via Resend"""
        if not self.resend_key:
            print("❌ Resend not configured")
            return False
        
        greeting = f"Hej {user_name}!" if user_name else "Hej!"
        
        payload = {
            "from": f"MyAvatar <{self.email_from}>",
            "to": [to_email],
            "subject": f"🎬 Din video '{video_title}' er klar!",
            "html": f"""
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
        }
        
        headers = {
            "Authorization": f"Bearer {self.resend_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                "https://api.resend.com/emails",
                json=payload,
                headers=headers
            )
            
            if response.status_code == 200:
                print(f"✅ Email sent to {to_email}")
                return True
            else:
                print(f"❌ Email failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Email error: {e}")
            return False
    
    def notify_video_completion(self, video_id):
        """Main notification function - call this from webhook handler"""
        print(f"🔔 Processing notification for video {video_id}")
        
        # Get user and video info
        info = self.get_user_and_video_info(video_id)
        if not info:
            print("❌ Could not get user/video info")
            return False
        
        video_title = info['video_title']
        user_name = info['user_name']
        user_email = info['user_email']
        is_premium = info['is_premium']
        sms_notifications = info['sms_notifications']
        phone_number = info['phone_number']
        country_code = info['country_code']
        
        print(f"📧 User: {user_name} ({user_email})")
        print(f"🎬 Video: {video_title}")
        print(f"💎 Premium: {is_premium}")
        print(f"📱 SMS Notifications: {sms_notifications}")
        print(f"📞 Phone Number: {phone_number}")
        print(f"🌍 Country Code: {country_code}")
        
        # DEBUG: Check each SMS condition
        print(f"🔍 SMS DEBUG - is_premium: {is_premium} (type: {type(is_premium)})")
        print(f"🔍 SMS DEBUG - sms_notifications: {sms_notifications} (type: {type(sms_notifications)})")
        print(f"🔍 SMS DEBUG - phone_number: {phone_number} (type: {type(phone_number)})")
        print(f"🔍 SMS DEBUG - Combined condition: {is_premium and sms_notifications and phone_number}")
        
        # Premium users with SMS enabled
        if is_premium and sms_notifications and phone_number:
            full_phone = f"{country_code}{phone_number}"
            sms_message = f"🎬 Din MyAvatar video '{video_title}' er klar! Se den på app.myavatar.dk/dashboard"
            
            if self.send_sms(full_phone, sms_message):
                print("✅ SMS notification sent!")
                return True
            else:
                print("⚠️ SMS failed, sending email backup")
        
        # Basic users or SMS backup
        if user_email:
            if self.send_email(user_email, video_title, user_name):
                print("✅ Email notification sent!")
                return True
        
        print("❌ All notification methods failed")
        return False

# Standalone function for webhook integration
def notify_video_completion(video_id):
    """Standalone function to call from webhook handler"""
    service = NotificationService()
    return service.notify_video_completion(video_id)

# Test function
def test_notification_system():
    """Test notification system configuration"""
    service = NotificationService()
    
    print("🧪 Testing Notification System Configuration")
    print("=" * 50)
    
    # Database
    if service.database_url:
        print("✅ Database configured")
    else:
        print("❌ Database not configured")
    
    # Twilio SMS
    if all([service.twilio_sid, service.twilio_token, service.twilio_phone]):
        print("✅ Twilio SMS configured")
    else:
        print("❌ Twilio SMS not configured")
    
    # Resend Email
    if service.resend_key:
        print("✅ Resend Email configured")
    else:
        print("❌ Resend Email not configured")
    
    print("\n🎯 Ready for video completion notifications!")

if __name__ == "__main__":
    test_notification_system()
