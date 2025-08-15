"""
Video Completion Notifier Service
=================================
Simple service that monitors database for completed videos and sends notifications.
Runs as a background thread and checks for newly completed videos every 30 seconds.

When video status = 'completed':
A) Basic user => Send email
B) Premium user => Send email + SMS
"""

import os
import time
import threading
import psycopg2
import requests
from typing import Set
from ..utils.logger import log_info, log_error

class VideoCompletionNotifier:
    def __init__(self):
        self.processed_videos: Set[str] = set()  # Track processed video IDs
        self.running = False
        self.thread = None
        
    def start(self):
        """Start the notification monitoring service"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.thread.start()
            log_info("🔔 Video completion notifier started", "NotificationService")
    
    def stop(self):
        """Stop the notification monitoring service"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        log_info("⏹️ Video completion notifier stopped", "NotificationService")
    
    def _monitor_loop(self):
        """Main monitoring loop - checks for completed videos every 30 seconds"""
        while self.running:
            try:
                self._check_for_completed_videos()
                time.sleep(30)  # Check every 30 seconds
            except Exception as e:
                log_error(f"❌ Error in notification monitor loop: {e}", "NotificationService")
                time.sleep(60)  # Wait longer on error
    
    def _check_for_completed_videos(self):
        """Check database for newly completed videos and send notifications"""
        try:
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                return
            
            with psycopg2.connect(database_url) as conn:
                with conn.cursor() as cursor:
                    # Find completed videos from last hour that haven't been processed
                    cursor.execute("""
                        SELECT v.heygen_video_id, v.title, v.completed_at,
                               u.username, u.email, u.phone_number, u.country_code,
                               u.sms_notifications, u.is_premium
                        FROM videos v
                        JOIN users u ON v.user_id = u.id
                        WHERE v.status = 'completed' 
                        AND v.completed_at IS NOT NULL
                        AND v.completed_at > NOW() - INTERVAL '1 hour'
                        ORDER BY v.completed_at DESC
                    """)
                    
                    results = cursor.fetchall()
                    
                    for result in results:
                        video_id, title, completed_at, username, email, phone, country_code, sms_opt_in, is_premium = result
                        
                        # Skip if already processed
                        if video_id in self.processed_videos:
                            continue
                        
                        log_info(f"🔔 NEW COMPLETED VIDEO: {video_id} for {username} - {title}", "NotificationService")
                        
                        # Send notifications based on user type
                        if is_premium:
                            log_info(f"💎 Premium user - sending EMAIL + SMS", "NotificationService")
                            self._send_email(username, email, title)
                            if phone and country_code and sms_opt_in:
                                self._send_sms(username, phone, country_code, title)
                        else:
                            log_info(f"📧 Basic user - sending EMAIL only", "NotificationService")
                            self._send_email(username, email, title)
                        
                        # Mark as processed
                        self.processed_videos.add(video_id)
                        log_info(f"✅ Notification processed for video {video_id}", "NotificationService")
                        
                        # Keep processed set manageable
                        if len(self.processed_videos) > 100:
                            self.processed_videos = set(list(self.processed_videos)[-50:])
                        
        except Exception as e:
            log_error(f"❌ Error checking completed videos: {e}", "NotificationService")
    
    def _send_email(self, username: str, email: str, title: str):
        """Send email notification using Resend"""
        try:
            resend_api_key = os.getenv('RESEND_API_KEY')
            if not resend_api_key:
                log_info(f"📧 Would send email to {email} (Resend API key missing)", "NotificationService")
                return
            
            email_data = {
                "from": "delivered@resend.dev",
                "to": [email],
                "subject": f"🎬 Your video '{title}' is ready!",
                "html": f"""
                <h2>🎬 Your video is ready!</h2>
                <p>Hi {username},</p>
                <p>Your video <strong>"{title}"</strong> has been successfully generated and is ready for download.</p>
                <p><a href="https://myavatar.live/dashboard" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Your Video</a></p>
                <p>Best regards,<br>MyAvatar Team</p>
                """
            }
            
            response = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {resend_api_key}",
                    "Content-Type": "application/json"
                },
                json=email_data,
                timeout=10
            )
            
            if response.status_code == 200:
                log_info(f"📧 Email sent to {email}", "NotificationService")
            else:
                log_error(f"❌ Email failed: {response.status_code} - {response.text}", "NotificationService")
                
        except Exception as e:
            log_error(f"❌ Email error: {e}", "NotificationService")
    
    def _send_sms(self, username: str, phone: str, country_code: str, title: str):
        """Send SMS notification using Twilio"""
        try:
            from twilio.rest import Client
            
            account_sid = os.getenv('TWILIO_ACCOUNT_SID')
            auth_token = os.getenv('TWILIO_AUTH_TOKEN')
            twilio_phone = os.getenv('TWILIO_PHONE_NUMBER')
            
            if not (account_sid and auth_token and twilio_phone):
                log_info(f"📱 Would send SMS to {country_code}{phone} (Twilio credentials missing)", "NotificationService")
                return
            
            client = Client(account_sid, auth_token)
            
            # Format phone number
            full_phone = f"{country_code}{phone}"
            if not full_phone.startswith('+'):
                full_phone = f"+{full_phone}"
            
            message = client.messages.create(
                body=f"🎬 Your video '{title}' is ready! Check your MyAvatar dashboard to view and download.",
                from_=twilio_phone,
                to=full_phone
            )
            
            log_info(f"📱 SMS sent to {full_phone} - SID: {message.sid}", "NotificationService")
            
        except Exception as e:
            log_error(f"❌ SMS error: {e}", "NotificationService")

# Global notifier instance
video_completion_notifier = VideoCompletionNotifier()
