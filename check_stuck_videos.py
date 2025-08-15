#!/usr/bin/env python3
"""
Check Status of Stuck Videos
Script to check the actual status of videos stuck in "processing" on HeyGen
"""

import os
import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.api.heygen import get_video_details
from app.db.database import execute_query
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VideoStatusChecker")

def check_stuck_videos():
    """Check status of videos stuck in processing"""
    print("🔍 Checking Status of Stuck Videos")
    print("=" * 40)
    
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    
    # Get HeyGen API key
    api_key = os.getenv("HEYGEN_API_KEY")
    if not api_key:
        print("❌ HEYGEN_API_KEY not found in environment")
        return
    
    print(f"✅ HeyGen API Key: {api_key[:10]}...")
    
    # Get videos stuck in processing
    stuck_videos = execute_query("""
        SELECT id, title, heygen_video_id, status, created_at 
        FROM videos 
        WHERE status = 'processing' 
        AND heygen_video_id IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 10
    """)
    
    if not stuck_videos:
        print("✅ No videos stuck in processing")
        return
    
    print(f"\n📊 Found {len(stuck_videos)} videos stuck in processing:")
    
    for video in stuck_videos:
        print(f"\n🎬 Video ID: {video['id']}")
        print(f"   Title: {video['title']}")
        print(f"   HeyGen ID: {video['heygen_video_id']}")
        print(f"   DB Status: {video['status']}")
        print(f"   Created: {video['created_at']}")
        
        # Check actual status on HeyGen
        print("   🔍 Checking HeyGen status...")
        
        try:
            result = get_video_details(api_key, video['heygen_video_id'])
            
            if result.get("success"):
                details = result.get("details", {})
                heygen_status = details.get("status", "unknown")
                video_url = details.get("video_url")
                
                print(f"   ✅ HeyGen Status: {heygen_status}")
                
                if video_url:
                    print(f"   🎥 Video URL: {video_url}")
                
                # If video is completed on HeyGen but not in our DB, update it
                if heygen_status == "completed" and video['status'] == 'processing':
                    print("   🔧 Video is completed on HeyGen but not in our DB - NEEDS UPDATE!")
                    
                    # Update the database
                    try:
                        execute_query("""
                            UPDATE videos 
                            SET status = 'completed', video_path = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (video_url, video['id']))
                        
                        print("   ✅ Database updated successfully!")
                        
                    except Exception as e:
                        print(f"   ❌ Failed to update database: {e}")
                
                elif heygen_status == "failed":
                    print("   ❌ Video failed on HeyGen side")
                    
                    # Update database to reflect failure
                    try:
                        execute_query("""
                            UPDATE videos 
                            SET status = 'failed', error_message = 'Video failed on HeyGen', updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (video['id'],))
                        
                        print("   ✅ Database updated to reflect failure")
                        
                    except Exception as e:
                        print(f"   ❌ Failed to update database: {e}")
                
                else:
                    print(f"   ℹ️ Status is consistent: {heygen_status}")
                    
            else:
                print(f"   ❌ Failed to get HeyGen status: {result.get('error')}")
                
        except Exception as e:
            print(f"   ❌ Error checking HeyGen status: {e}")
    
    print(f"\n🎉 Status check complete!")

def check_specific_videos():
    """Check the specific videos from the log"""
    print("\n🎯 Checking Specific Videos from Log")
    print("-" * 35)
    
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("HEYGEN_API_KEY")
    if not api_key:
        print("❌ HEYGEN_API_KEY not found")
        return
    
    # Specific video IDs from the log
    video_ids = [
        "83eddc286b414b5c8a1ca9b88ec91ceb",  # NeuroGrace Messiah
        "aaa8e159c54743d8a06afd79dafd5a03"   # Welcome to our world
    ]
    
    for video_id in video_ids:
        print(f"\n🔍 Checking HeyGen video: {video_id}")
        
        try:
            result = get_video_details(api_key, video_id)
            
            if result.get("success"):
                details = result.get("details", {})
                status = details.get("status", "unknown")
                video_url = details.get("video_url")
                
                print(f"   Status: {status}")
                if video_url:
                    print(f"   URL: {video_url}")
                    print("   ✅ VIDEO IS READY! Needs database update.")
                else:
                    print("   ⏳ Still processing or no URL available")
                    
            else:
                print(f"   ❌ Error: {result.get('error')}")
                
        except Exception as e:
            print(f"   ❌ Exception: {e}")

if __name__ == "__main__":
    check_stuck_videos()
    check_specific_videos()
