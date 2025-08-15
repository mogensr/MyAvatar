#!/usr/bin/env python3
"""
Resend Email Service for MyAvatar
Simple, developer-friendly email delivery
3,000 emails/month FREE - much easier than SendGrid!
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

class ResendEmailService:
    """Simple email service using Resend API"""
    
    def __init__(self):
        self.api_key = os.getenv("RESEND_API_KEY")
        self.from_email = os.getenv("EMAIL_FROM", "noreply@myavatar.dk")
        self.api_url = "https://api.resend.com/emails"
    
    def send_video_completion_email(self, to_email, video_title, user_name):
        """Send video completion email via Resend"""
        if not self.api_key:
            print("❌ Resend API key not configured")
            return False
        
        greeting = f"Hej {user_name}!" if user_name else "Hej!"
        
        # Resend API payload (much simpler than SendGrid!)
        payload = {
            "from": f"MyAvatar <{self.from_email}>",
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
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(self.api_url, json=payload, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                email_id = result.get('id', 'unknown')
                print(f"✅ Resend email sent to {to_email} (ID: {email_id})")
                return True
            else:
                print(f"❌ Resend failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Resend error: {e}")
            return False

# Test function
def test_resend():
    """Test Resend configuration"""
    service = ResendEmailService()
    
    if service.api_key:
        print("✅ Resend API key configured")
        print("🧪 Ready to send emails!")
        print(f"📧 From: {service.from_email}")
    else:
        print("❌ Resend API key missing")
        print("🔑 Add RESEND_API_KEY to environment variables")
        print("📝 Get free API key: https://resend.com/")
        print("🎉 3,000 emails/month FREE!")

if __name__ == "__main__":
    test_resend()
