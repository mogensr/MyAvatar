"""
SMS App Monitoring Service
Monitors app.myavatar.dk and sends SMS alerts when down
"""
import os
import time
import requests
import threading
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SMSMonitor:
    def __init__(self):
        self.app_url = "https://app.myavatar.dk"
        self.check_interval = 300  # 5 minutes
        self.phone_number = "+4530604639"  # Replace with your Danish phone number
        self.is_app_down = False
        self.last_alert_time = None
        self.alert_cooldown = 1800  # 30 minutes between alerts
        
        # SMS Service Configuration (using TextBelt - free option)
        self.sms_service = "textbelt"  # or "twilio"
        
        # TextBelt (Free SMS service)
        self.textbelt_key = os.getenv("TEXTBELT_API_KEY", "textbelt")  # "textbelt" for free tier
        
        # Twilio (Premium SMS service - uncomment if you prefer)
        # self.twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        # self.twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        # self.twilio_phone_number = os.getenv("TWILIO_PHONE_NUMBER")
        
    def send_sms_textbelt(self, message):
        """Send SMS using TextBelt service"""
        try:
            response = requests.post(
                'https://textbelt.com/text',
                data={
                    'phone': self.phone_number,
                    'message': message,
                    'key': self.textbelt_key
                },
                timeout=10
            )
            
            result = response.json()
            if result.get('success'):
                logger.info(f"SMS sent successfully to {self.phone_number}")
                return True
            else:
                logger.error(f"SMS failed: {result.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            logger.error(f"SMS sending error: {str(e)}")
            return False
    
    def send_sms_twilio(self, message):
        """Send SMS using Twilio service (premium option)"""
        try:
            from twilio.rest import Client
            
            client = Client(self.twilio_account_sid, self.twilio_auth_token)
            
            message = client.messages.create(
                body=message,
                from_=self.twilio_phone_number,
                to=self.phone_number
            )
            
            logger.info(f"Twilio SMS sent successfully: {message.sid}")
            return True
            
        except Exception as e:
            logger.error(f"Twilio SMS error: {str(e)}")
            return False
    
    def send_sms(self, message):
        """Send SMS using configured service"""
        if self.sms_service == "textbelt":
            return self.send_sms_textbelt(message)
        elif self.sms_service == "twilio":
            return self.send_sms_twilio(message)
        else:
            logger.error(f"Unknown SMS service: {self.sms_service}")
            return False
    
    def check_app_status(self):
        """Check if MyAvatar app is accessible"""
        try:
            # Check multiple endpoints
            endpoints = [
                f"{self.app_url}/health",
                f"{self.app_url}/simple-health",
                f"{self.app_url}/"
            ]
            
            for endpoint in endpoints:
                try:
                    response = requests.get(endpoint, timeout=10)
                    if response.status_code == 200:
                        logger.info(f"✅ App is UP - {endpoint} responded with 200")
                        return True
                except requests.exceptions.RequestException:
                    continue
            
            logger.error("❌ App is DOWN - All endpoints failed")
            return False
            
        except Exception as e:
            logger.error(f"Error checking app status: {str(e)}")
            return False
    
    def should_send_alert(self):
        """Check if we should send an alert (respects cooldown)"""
        if self.last_alert_time is None:
            return True
        
        time_since_last_alert = time.time() - self.last_alert_time
        return time_since_last_alert >= self.alert_cooldown
    
    def send_down_alert(self):
        """Send SMS alert when app goes down"""
        if not self.should_send_alert():
            logger.info("Skipping alert - still in cooldown period")
            return
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"🚨 MyAvatar ALERT: Your app (app.myavatar.dk) is DOWN as of {timestamp}. Please check Railway dashboard."
        
        if self.send_sms(message):
            self.last_alert_time = time.time()
            logger.info("Down alert sent successfully")
        else:
            logger.error("Failed to send down alert")
    
    def send_recovery_alert(self):
        """Send SMS alert when app recovers"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"✅ MyAvatar RECOVERY: Your app (app.myavatar.dk) is back UP as of {timestamp}. All systems operational."
        
        if self.send_sms(message):
            logger.info("Recovery alert sent successfully")
        else:
            logger.error("Failed to send recovery alert")
    
    def monitor_loop(self):
        """Main monitoring loop"""
        logger.info(f"🚀 Starting SMS monitoring for {self.app_url}")
        logger.info(f"📱 SMS alerts will be sent to: {self.phone_number}")
        logger.info(f"⏰ Check interval: {self.check_interval} seconds")
        logger.info(f"🔔 Alert cooldown: {self.alert_cooldown} seconds")
        
        while True:
            try:
                app_is_up = self.check_app_status()
                
                if app_is_up and self.is_app_down:
                    # App recovered
                    logger.info("🎉 App recovered!")
                    self.send_recovery_alert()
                    self.is_app_down = False
                    
                elif not app_is_up and not self.is_app_down:
                    # App went down
                    logger.error("🚨 App went down!")
                    self.send_down_alert()
                    self.is_app_down = True
                
                # Wait before next check
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logger.info("🛑 Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    def start_monitoring(self):
        """Start monitoring in a background thread"""
        monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        monitor_thread.start()
        logger.info("📡 SMS monitoring started in background")
        return monitor_thread
    
    def test_sms(self):
        """Test SMS functionality"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"📱 MyAvatar SMS Test: This is a test message sent at {timestamp}. SMS monitoring is working!"
        
        logger.info("Testing SMS functionality...")
        if self.send_sms(message):
            logger.info("✅ SMS test successful!")
            return True
        else:
            logger.error("❌ SMS test failed!")
            return False

# Standalone script for testing
def main():
    """Main function for standalone testing"""
    monitor = SMSMonitor()
    
    print("MyAvatar SMS Monitoring Service")
    print("=" * 35)
    print(f"Monitoring: {monitor.app_url}")
    print(f"Phone: {monitor.phone_number}")
    print(f"Service: {monitor.sms_service}")
    print()
    
    # Test SMS first
    print("Testing SMS functionality...")
    if monitor.test_sms():
        print("✅ SMS test passed!")
        
        # Start monitoring
        print("\nStarting continuous monitoring...")
        monitor.monitor_loop()
    else:
        print("❌ SMS test failed! Check your configuration.")
        print("\nConfiguration checklist:")
        print("1. Update phone_number in the script")
        print("2. Set TEXTBELT_API_KEY environment variable (or use 'textbelt' for free)")
        print("3. Make sure your phone number includes country code (+45 for Denmark)")

if __name__ == "__main__":
    main()
