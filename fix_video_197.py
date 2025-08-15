#!/usr/bin/env python3
"""
Fix existing video 197 (TEST 3) by moving HeyGen video ID to correct database field
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import execute_query

def fix_video_197():
    """Fix video 197 by moving HeyGen ID from video_path to heygen_video_id"""
    
    print("🔧 Fixing video 197 (TEST 3) database record...")
    
    # First, check current state
    current_video = execute_query(
        "SELECT id, title, video_path, heygen_video_id, status FROM videos WHERE id = 197",
        fetch_one=True
    )
    
    if not current_video:
        print("❌ Video 197 not found!")
        return False
    
    print(f"📊 Current state:")
    print(f"   ID: {current_video['id']}")
    print(f"   Title: {current_video['title']}")
    print(f"   video_path: {current_video['video_path']}")
    print(f"   heygen_video_id: {current_video['heygen_video_id']}")
    print(f"   status: {current_video['status']}")
    
    # Check if fix is needed
    if current_video['heygen_video_id'] is not None:
        print("✅ Video 197 already has heygen_video_id set - no fix needed!")
        return True
    
    if not current_video['video_path'] or len(current_video['video_path']) < 10:
        print("❌ Video 197 doesn't have a valid HeyGen ID in video_path!")
        return False
    
    # Apply the fix
    heygen_id = current_video['video_path']
    
    print(f"🔄 Moving HeyGen ID '{heygen_id}' from video_path to heygen_video_id...")
    
    execute_query(
        """
        UPDATE videos 
        SET heygen_video_id = %s, video_path = NULL 
        WHERE id = 197
        """,
        (heygen_id,)
    )
    
    # Verify the fix
    fixed_video = execute_query(
        "SELECT id, title, video_path, heygen_video_id, status FROM videos WHERE id = 197",
        fetch_one=True
    )
    
    print(f"✅ Fixed state:")
    print(f"   ID: {fixed_video['id']}")
    print(f"   Title: {fixed_video['title']}")
    print(f"   video_path: {fixed_video['video_path']}")
    print(f"   heygen_video_id: {fixed_video['heygen_video_id']}")
    print(f"   status: {fixed_video['status']}")
    
    print("🎉 Video 197 fix completed! Background polling should now work.")
    return True

if __name__ == "__main__":
    success = fix_video_197()
    if success:
        print("\n🚀 Next steps:")
        print("1. The background polling system will now be able to find the HeyGen video")
        print("2. It will check HeyGen API for completion status")
        print("3. When complete, it will update the video_path with the actual video URL")
        print("4. The video should then display in the dashboard")
    else:
        print("\n❌ Fix failed - manual intervention may be needed")
