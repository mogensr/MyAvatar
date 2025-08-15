#!/usr/bin/env python3
"""
Fix Stuck Videos Script
======================
Manually checks HeyGen status for videos stuck in 'processing' and updates database.
This fixes the webhook issue without changing any existing code.

Usage: python fix_stuck_videos.py
"""

import os
import sys
from datetime import datetime

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from db.database import execute_query
from api.heygen_enhanced import HeyGenAPI
from logger.log_handler import log_info, log_error, log_warning

def fix_stuck_videos():
    """Check and fix videos stuck in processing status"""
    try:
        # Get HeyGen API key
        api_key = os.getenv("HEYGEN_API_KEY")
        if not api_key:
            log_error("No HeyGen API key found", "VideoFix")
            return
        
        # Initialize HeyGen API
        heygen_api = HeyGenAPI(api_key)
        
        # Get all videos stuck in processing status
        stuck_videos = execute_query("""
            SELECT id, heygen_video_id, title, created_at, user_id
            FROM videos 
            WHERE status = 'processing' 
            AND heygen_video_id IS NOT NULL
            ORDER BY created_at DESC
        """)
        
        if not stuck_videos:
            log_info("No stuck videos found", "VideoFix")
            return
        
        log_info(f"Found {len(stuck_videos)} videos stuck in processing", "VideoFix")
        
        fixed_count = 0
        failed_count = 0
        
        for video in stuck_videos:
            video_id = video.get('id')
            heygen_id = video.get('heygen_video_id')
            title = video.get('title', 'Untitled')
            
            log_info(f"Checking video {video_id} ({title}): HeyGen ID {heygen_id}", "VideoFix")
            
            try:
                # Check status in HeyGen
                status_info = heygen_api.get_video_status(heygen_id)
                heygen_status = status_info.get('status')
                video_url = status_info.get('video_url')
                duration = status_info.get('duration')
                error_msg = status_info.get('error')
                
                log_info(f"HeyGen status for {heygen_id}: {heygen_status}, has_url: {bool(video_url)}", "VideoFix")
                
                if heygen_status == 'completed' and video_url:
                    # Video is completed - update database
                    execute_query("""
                        UPDATE videos 
                        SET status = 'completed', 
                            video_path = %s,
                            video_url = %s, 
                            duration = %s,
                            completed_at = NOW(),
                            updated_at = NOW()
                        WHERE id = %s
                    """, (video_url, video_url, duration, video_id))
                    
                    log_info(f"✅ Fixed video {video_id} ({title}): status=completed, url={video_url}", "VideoFix")
                    fixed_count += 1
                    
                elif heygen_status == 'failed' or error_msg:
                    # Video failed - update database
                    error_message = error_msg or "Video processing failed in HeyGen"
                    execute_query("""
                        UPDATE videos 
                        SET status = 'failed', 
                            error_message = %s,
                            updated_at = NOW()
                        WHERE id = %s
                    """, (error_message, video_id))
                    
                    log_warning(f"❌ Video {video_id} ({title}) failed: {error_message}", "VideoFix")
                    failed_count += 1
                    
                elif heygen_status == 'processing':
                    # Still processing - leave as is
                    log_info(f"⏳ Video {video_id} ({title}) still processing in HeyGen", "VideoFix")
                    
                else:
                    log_warning(f"⚠️ Unknown status for video {video_id} ({title}): {heygen_status}", "VideoFix")
                    
            except Exception as e:
                log_error(f"Error checking video {video_id} ({title}): {str(e)}", "VideoFix")
                continue
        
        log_info(f"Video fix complete: {fixed_count} fixed, {failed_count} failed, {len(stuck_videos) - fixed_count - failed_count} still processing", "VideoFix")
        
        if fixed_count > 0:
            print(f"\n✅ SUCCESS: Fixed {fixed_count} videos!")
            print("Your videos should now appear as completed in the dashboard.")
        
        if failed_count > 0:
            print(f"\n❌ {failed_count} videos failed in HeyGen")
            
    except Exception as e:
        log_error(f"Error in fix_stuck_videos: {str(e)}", "VideoFix")
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    print("🔧 Fixing stuck videos...")
    print("Checking HeyGen status for videos stuck in processing...")
    fix_stuck_videos()
    print("Done!")
