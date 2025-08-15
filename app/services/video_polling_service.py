"""
Video Polling Service
====================
Background service to poll HeyGen for video completion status.
Polls every 5 minutes until videos are completed.
"""

import os
import time
import threading
import requests
import psycopg2
from typing import Dict, Set, Optional, Any
from ..db.database import execute_query
from ..utils.logger import log_info, log_error, log_warning

class VideoPollingService:
    def __init__(self):
        self.polling_videos: Set[str] = set()  # Set of heygen_video_ids being polled
        self.polling_active = False
        self.polling_thread = None
        self.api_key = os.getenv("HEYGEN_API_KEY")
        
    def start_polling(self):
        """Start the background polling service"""
        if not self.polling_active:
            self.polling_active = True
            self.polling_thread = threading.Thread(target=self._polling_loop, daemon=True)
            self.polling_thread.start()
            log_info("🔄 Video polling service started", "VideoPolling")
    
    def stop_polling(self):
        """Stop the background polling service"""
        self.polling_active = False
        if self.polling_thread:
            self.polling_thread.join(timeout=5)
        log_info("⏹️ Video polling service stopped", "VideoPolling")
    
    def add_video_to_poll(self, heygen_video_id: str):
        """Add a video to the polling queue"""
        self.polling_videos.add(heygen_video_id)
        log_info(f"➕ Added video {heygen_video_id} to polling queue", "VideoPolling")
        
        # Start polling if not already active
        if not self.polling_active:
            self.start_polling()
    
    def remove_video_from_poll(self, heygen_video_id: str):
        """Remove a video from the polling queue"""
        self.polling_videos.discard(heygen_video_id)
        log_info(f"➖ Removed video {heygen_video_id} from polling queue", "VideoPolling")
    
    def _polling_loop(self):
        """Main polling loop - runs in background thread"""
        log_info("🔄 Polling loop started", "VideoPolling")
        
        while self.polling_active:
            try:
                if not self.polling_videos:
                    # No videos to poll, sleep for 30 seconds
                    time.sleep(30)
                    continue
                
                log_info(f"🔍 Polling {len(self.polling_videos)} videos", "VideoPolling")
                
                # Poll each video
                videos_to_remove = set()
                for heygen_video_id in self.polling_videos.copy():
                    try:
                        if self._poll_video_status(heygen_video_id):
                            # Video completed or failed, remove from polling
                            videos_to_remove.add(heygen_video_id)
                    except Exception as e:
                        log_error(f"Error polling video {heygen_video_id}: {str(e)}", "VideoPolling")
                
                # Remove completed videos from polling queue
                for video_id in videos_to_remove:
                    self.remove_video_from_poll(video_id)
                
                # Sleep for 5 minutes (300 seconds)
                log_info("😴 Polling sleep for 5 minutes", "VideoPolling")
                time.sleep(300)
                
            except Exception as e:
                log_error(f"Error in polling loop: {str(e)}", "VideoPolling")
                time.sleep(60)  # Sleep 1 minute on error
    
    def _poll_video_status(self, heygen_video_id: str) -> bool:
        """
        Poll a single video's status from HeyGen - FIXED VERSION
        Returns True if video is completed/failed (should stop polling)
        Returns False if video is still processing (continue polling)
        """
        try:
            if not self.api_key:
                log_error("No HeyGen API key available for polling", "VideoPolling")
                return True  # Stop polling this video
            
            # FIXED: Use correct HeyGen API endpoint and headers
            headers = {
                "X-API-KEY": self.api_key,  # FIXED: Correct header name
                "Content-Type": "application/json"
            }
            
            # Try both API versions - depends on avatar type
            response = None
            
            # First try v2 endpoint (for newer avatars)
            try:
                response = requests.get(
                    f"https://api.heygen.com/v2/video/{heygen_video_id}",
                    headers=headers,
                    timeout=30
                )
                log_info(f"🌐 HeyGen v2 API Response Status: {response.status_code}", "VideoPolling")
            except Exception as v2_error:
                log_warning(f"v2 API failed: {v2_error}", "VideoPolling")
            
            # If v2 fails with 404, try v1 endpoint (for older avatars)
            if not response or response.status_code == 404:
                log_info(f"🔄 Trying v1 API for video {heygen_video_id}", "VideoPolling")
                try:
                    response = requests.get(
                        f"https://api.heygen.com/v1/video_status.get?video_id={heygen_video_id}",
                        headers=headers,
                        timeout=30
                    )
                    log_info(f"🌐 HeyGen v1 API Response Status: {response.status_code}", "VideoPolling")
                except Exception as v1_error:
                    log_error(f"Both v1 and v2 APIs failed: {v1_error}", "VideoPolling")
                    return False
            
            log_info(f"🌐 HeyGen API Response Status: {response.status_code}", "VideoPolling")
            log_info(f"🔍 HeyGen API Response Body: {response.text[:500]}...", "VideoPolling")
            
            if response.status_code != 200:
                log_error(f"HeyGen API error for video {heygen_video_id}: {response.status_code} - {response.text}", "VideoPolling")
                return False  # Continue polling
            
            response_data = response.json()
            
            # FIXED: Handle HeyGen v2 API response structure
            data = response_data.get('data', {})
            status = data.get('status', '').lower()
            
            # FIXED: More comprehensive video URL extraction
            video_url = self._extract_video_url(data, response_data)
            duration = data.get('duration') or response_data.get('duration') or 0
            error_msg = data.get('error') or response_data.get('error')
            
            log_info(f"📊 Video {heygen_video_id} - Status: '{status}', Has Video URL: {bool(video_url)}", "VideoPolling")
            log_info(f"🔍 DETAILED DEBUG - Video URL: '{video_url}', Duration: {duration}", "VideoPolling")
            
            # FIXED: Handle completion with proper database transaction
            if status == 'completed' and video_url:
                return self._update_video_completed(heygen_video_id, video_url, duration)
                
            elif status == 'completed' and not video_url:
                log_error(f"⚠️ Video {heygen_video_id} completed but NO video_url returned from HeyGen!", "VideoPolling")
                log_error(f"🔍 Full HeyGen response: {response_data}", "VideoPolling")
                return False  # Continue polling
                
            elif status == 'failed' or error_msg:
                return self._update_video_failed(heygen_video_id, error_msg)
                
            elif status in ['processing', 'pending', 'queued']:
                log_info(f"⏳ Video {heygen_video_id} still processing (status: {status})", "VideoPolling")
                return False  # Continue polling
                
            else:
                log_info(f"⚠️ Unknown status for video {heygen_video_id}: '{status}'", "VideoPolling")
                return False  # Continue polling
                
        except Exception as e:
            log_error(f"Error polling video {heygen_video_id}: {str(e)}", "VideoPolling")
            import traceback
            log_error(f"Traceback: {traceback.format_exc()}", "VideoPolling")
            return False  # Continue polling
    
    def _extract_video_url(self, data: dict, response_data: dict) -> Optional[str]:
        """
        FIXED: Extract video URL from HeyGen response with all possible field names
        """
        # Try all possible video URL field names from HeyGen API
        possible_fields = [
            'video_url',
            'url', 
            'download_url',
            'video_path',
            'file_url',
            'result_url'
        ]
        
        # Check in data object first
        for field in possible_fields:
            if data.get(field):
                log_info(f"🔍 Found video URL in data.{field}: {data[field]}", "VideoPolling")
                return data[field]
        
        # Check in root response object
        for field in possible_fields:
            if response_data.get(field):
                log_info(f"🔍 Found video URL in response.{field}: {response_data[field]}", "VideoPolling")
                return response_data[field]
        
        log_error(f"🔍 No video URL found in any expected field. Available fields: {list(data.keys())}", "VideoPolling")
        return None
    
    def _update_video_completed(self, heygen_video_id: str, video_url: str, duration: Optional[int]) -> bool:
        """
        FIXED: Update video as completed with proper error handling and verification
        """
        try:
            log_info(f"🔄 Attempting database update for completed video {heygen_video_id}", "VideoPolling")
            
            # FIXED: First check if video exists in database
            existing_video = execute_query(
                "SELECT id, status FROM videos WHERE heygen_video_id = %s",
                (heygen_video_id,),
                fetch_one=True
            )
            
            if not existing_video:
                log_error(f"❌ Video {heygen_video_id} not found in database!", "VideoPolling")
                return True  # Stop polling since video doesn't exist
            
            video_db_id = existing_video[0] if isinstance(existing_video, tuple) else existing_video.get('id')
            current_status = existing_video[1] if isinstance(existing_video, tuple) else existing_video.get('status')
            
            log_info(f"🔍 Found video in DB - ID: {video_db_id}, Current Status: {current_status}", "VideoPolling")
            
            # FIXED: Update with explicit transaction handling
            update_result = execute_query("""
                UPDATE videos 
                SET status = 'completed', 
                    video_path = %s,
                    duration = %s,
                    completed_at = NOW(),
                    updated_at = NOW()
                WHERE heygen_video_id = %s
                RETURNING id, status, video_path
            """, (video_url, duration, heygen_video_id), fetch_one=True)
            
            if update_result:
                log_info(f"✅ Video {heygen_video_id} successfully updated to completed in database", "VideoPolling")
                log_info(f"🔍 Update result: {update_result}", "VideoPolling")
                
                # FIXED: Verify the update actually worked
                verification = execute_query(
                    "SELECT status, video_path FROM videos WHERE heygen_video_id = %s",
                    (heygen_video_id,),
                    fetch_one=True
                )
                
                if verification:
                    verify_status = verification[0] if isinstance(verification, tuple) else verification.get('status')
                    verify_path = verification[1] if isinstance(verification, tuple) else verification.get('video_path')
                    
                    if verify_status == 'completed' and verify_path:
                        log_info(f"✅ VERIFIED: Video {heygen_video_id} update successful", "VideoPolling")
                        
                        # 🔔 SEND NOTIFICATION - Same logic as webhook handler
                        log_info(f"🚀 ABOUT TO SEND NOTIFICATION for video {heygen_video_id}", "VideoPolling")
                        try:
                            self._send_completion_notification(heygen_video_id)
                        except Exception as notify_error:
                            log_error(f"❌ Notification failed for video {heygen_video_id}: {notify_error}", "VideoPolling")
                        
                        return True  # Stop polling
                    else:
                        log_error(f"❌ VERIFICATION FAILED: Status={verify_status}, Path={verify_path}", "VideoPolling")
                        return False  # Continue polling
                else:
                    log_error(f"❌ Could not verify update for video {heygen_video_id}", "VideoPolling")
                    return False  # Continue polling
            else:
                log_error(f"❌ Database update returned no result for video {heygen_video_id}", "VideoPolling")
                return False  # Continue polling
                
        except Exception as db_error:
            log_error(f"❌ Database update failed for video {heygen_video_id}: {str(db_error)}", "VideoPolling")
            import traceback
            log_error(f"Database error traceback: {traceback.format_exc()}", "VideoPolling")
            return False  # Continue polling
    
    def _update_video_failed(self, heygen_video_id: str, error_msg: Optional[str]) -> bool:
        """
        FIXED: Update video as failed with proper error handling
        """
        try:
            error_message = error_msg or "Video processing failed in HeyGen"
            
            update_result = execute_query("""
                UPDATE videos 
                SET status = 'failed', 
                    error_message = %s,
                    updated_at = NOW()
                WHERE heygen_video_id = %s
                RETURNING id
            """, (error_message, heygen_video_id), fetch_one=True)
            
            if update_result:
                log_info(f"❌ Video {heygen_video_id} marked as failed: {error_message}", "VideoPolling")
                return True  # Stop polling
            else:
                log_error(f"❌ Failed to update video {heygen_video_id} as failed", "VideoPolling")
                return False  # Continue polling
                
        except Exception as e:
            log_error(f"❌ Error updating failed video {heygen_video_id}: {str(e)}", "VideoPolling")
            return False  # Continue polling
    
    def force_poll_video(self, heygen_video_id: str) -> dict:
        """
        FIXED: Force immediate polling of a specific video with detailed response
        """
        try:
            log_info(f"🚀 Force polling video {heygen_video_id}", "VideoPolling")
            
            # Check if video exists in database first
            video_record = execute_query(
                "SELECT id, status, video_path FROM videos WHERE heygen_video_id = %s",
                (heygen_video_id,),
                fetch_one=True
            )
            
            if not video_record:
                return {
                    "success": False,
                    "error": f"Video {heygen_video_id} not found in database"
                }
            
            current_status = video_record[1] if isinstance(video_record, tuple) else video_record.get('status')
            current_path = video_record[2] if isinstance(video_record, tuple) else video_record.get('video_path')
            
            log_info(f"🔍 Current DB status: {current_status}, path: {current_path}", "VideoPolling")
            
            # Perform the polling
            should_stop = self._poll_video_status(heygen_video_id)
            
            # Check status after polling
            updated_record = execute_query(
                "SELECT status, video_path FROM videos WHERE heygen_video_id = %s",
                (heygen_video_id,),
                fetch_one=True
            )
            
            new_status = updated_record[0] if isinstance(updated_record, tuple) else updated_record.get('status')
            new_path = updated_record[1] if isinstance(updated_record, tuple) else updated_record.get('video_path')
            
            return {
                "success": True,
                "heygen_video_id": heygen_video_id,
                "status_changed": current_status != new_status,
                "old_status": current_status,
                "new_status": new_status,
                "has_video_path": bool(new_path),
                "should_stop_polling": should_stop
            }
            
        except Exception as e:
            log_error(f"❌ Error in force polling: {str(e)}", "VideoPolling")
            return {
                "success": False,
                "error": str(e)
            }

    def _send_completion_notification(self, video_id: str):
        """
        Send notification for completed video - INLINE implementation to avoid import issues
        """
        try:
            log_info(f"📧 Sending completion notification for video {video_id}", "VideoPolling")
            
            # Get database connection
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                log_error("❌ DATABASE_URL not found in environment", "VideoPolling")
                return
            
            with psycopg2.connect(database_url) as conn:
                with conn.cursor() as cursor:
                    # Get video and user info
                    cursor.execute("""
                        SELECT v.title, u.username, u.email, u.phone_number, 
                               u.country_code, u.sms_notifications, u.is_premium
                        FROM videos v
                        JOIN users u ON v.user_id = u.id
                        WHERE v.heygen_video_id = %s
                    """, (video_id,))
                    
                    result = cursor.fetchone()
                    if not result:
                        log_error(f"❌ No user/video data found for video {video_id}", "VideoPolling")
                        return
                    
                    title, username, email, phone, country_code, sms_opt_in, is_premium = result
                    
                    log_info(f"📧 Notification for {username}: video \"{title}\" completed", "VideoPolling")
                    
                    # Send SMS for premium users with phone and SMS opt-in
                    if is_premium and phone and sms_opt_in and country_code:
                        try:
                            # Twilio SMS
                            from twilio.rest import Client
                            
                            account_sid = os.getenv('TWILIO_ACCOUNT_SID')
                            auth_token = os.getenv('TWILIO_AUTH_TOKEN')
                            twilio_phone = os.getenv('TWILIO_PHONE_NUMBER')
                            
                            if account_sid and auth_token and twilio_phone:
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
                                
                                log_info(f"📱 SMS sent to {full_phone} - SID: {message.sid}", "VideoPolling")
                            else:
                                log_info(f"📱 Would send SMS to {country_code}{phone} (Twilio credentials missing)", "VideoPolling")
                        except Exception as sms_error:
                            log_error(f"❌ SMS failed: {sms_error}", "VideoPolling")
                    
                    # Send email for all users
                    if email:
                        try:
                            # Resend email
                            import requests
                            
                            resend_api_key = os.getenv('RESEND_API_KEY')
                            email_from = os.getenv('EMAIL_FROM', 'delivered@resend.dev')
                            
                            if resend_api_key:
                                email_data = {
                                    "from": email_from,
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
                                    log_info(f"📧 Email sent to {email}", "VideoPolling")
                                else:
                                    log_error(f"❌ Email failed: {response.status_code} - {response.text}", "VideoPolling")
                            else:
                                log_info(f"📧 Would send email to {email} (Resend API key missing)", "VideoPolling")
                        except Exception as email_error:
                            log_error(f"❌ Email failed: {email_error}", "VideoPolling")
                    
                    log_info(f"✅ Notification processed for video {video_id}", "VideoPolling")
                    
        except Exception as e:
            log_error(f"❌ Notification system error: {str(e)}", "VideoPolling")
            import traceback
            log_error(f"Notification traceback: {traceback.format_exc()}", "VideoPolling")

# Global polling service instance
video_polling_service = VideoPollingService()
