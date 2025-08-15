#!/usr/bin/env python3
"""
Simple Video Status Update Script
================================
Manually updates videos that are completed in HeyGen but stuck in processing status.
Uses direct database connection without complex imports.
"""

import os
import sys
import requests
from datetime import datetime
import mysql.connector
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_connection():
    """Get database connection"""
    return mysql.connector.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_NAME', 'myavatar'),
        charset='utf8mb4'
    )

def check_heygen_video_status(video_id, api_key):
    """Check video status directly from HeyGen API"""
    try:
        headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"https://api.heygen.com/v1/video_status.get?video_id={video_id}",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get('data', {})
        else:
            print(f"Error checking video {video_id}: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Error checking video {video_id}: {str(e)}")
        return None

def update_completed_videos():
    """Update videos that are completed in HeyGen"""
    try:
        # Get API key
        api_key = os.getenv("HEYGEN_API_KEY")
        if not api_key:
            print("❌ No HeyGen API key found")
            return
        
        # Connect to database
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get stuck videos
        cursor.execute("""
            SELECT id, heygen_video_id, title, created_at
            FROM videos 
            WHERE status = 'processing' 
            AND heygen_video_id IS NOT NULL
            ORDER BY created_at DESC
        """)
        
        stuck_videos = cursor.fetchall()
        
        if not stuck_videos:
            print("✅ No stuck videos found")
            return
        
        print(f"🔍 Found {len(stuck_videos)} videos stuck in processing")
        
        fixed_count = 0
        
        for video in stuck_videos:
            video_id = video['id']
            heygen_id = video['heygen_video_id']
            title = video['title'] or 'Untitled'
            
            print(f"\n🔍 Checking video {video_id} ({title})")
            print(f"   HeyGen ID: {heygen_id}")
            
            # Check status in HeyGen
            status_data = check_heygen_video_status(heygen_id, api_key)
            
            if status_data:
                heygen_status = status_data.get('status')
                video_url = status_data.get('video_url')
                duration = status_data.get('duration')
                error_msg = status_data.get('error')
                
                print(f"   HeyGen Status: {heygen_status}")
                print(f"   Has Video URL: {bool(video_url)}")
                
                if heygen_status == 'completed' and video_url:
                    # Update database
                    cursor.execute("""
                        UPDATE videos 
                        SET status = 'completed', 
                            video_path = %s,
                            video_url = %s, 
                            duration = %s,
                            completed_at = NOW(),
                            updated_at = NOW()
                        WHERE id = %s
                    """, (video_url, video_url, duration, video_id))
                    
                    conn.commit()
                    print(f"   ✅ FIXED: Updated to completed with video URL")
                    fixed_count += 1
                    
                elif heygen_status == 'failed' or error_msg:
                    # Update as failed
                    error_message = error_msg or "Video processing failed in HeyGen"
                    cursor.execute("""
                        UPDATE videos 
                        SET status = 'failed', 
                            error_message = %s,
                            updated_at = NOW()
                        WHERE id = %s
                    """, (error_message, video_id))
                    
                    conn.commit()
                    print(f"   ❌ FAILED: {error_message}")
                    
                elif heygen_status == 'processing':
                    print(f"   ⏳ Still processing in HeyGen")
                    
                else:
                    print(f"   ⚠️ Unknown status: {heygen_status}")
            else:
                print(f"   ❌ Could not check status in HeyGen")
        
        cursor.close()
        conn.close()
        
        print(f"\n🎉 SUMMARY: Fixed {fixed_count} videos!")
        if fixed_count > 0:
            print("✅ Your videos should now appear as completed in the dashboard!")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    print("🔧 Updating completed videos from HeyGen...")
    update_completed_videos()
    print("✅ Done!")
