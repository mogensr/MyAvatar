#!/usr/bin/env python3
"""
Clean up videos that return 404 from HeyGen API
"""
import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
import psycopg2

# Load environment variables
load_dotenv()

def cleanup_404_videos():
    """Clean up videos that no longer exist at HeyGen"""
    try:
        # Get database URL
        DATABASE_URL = os.getenv("DATABASE_URL")
        if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
            
        print("🔧 Connecting to database...")
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Video IDs that are returning 404 from HeyGen
        video_ids_404 = [
            "1b05592ce8cb4c4d9e8d1a27977acf53",
            "f98dc11094f44a30944a99a343f4ed79", 
            "672dcb92ba1b45c9aabdc7aa2c6dd5ab"
        ]
        
        print(f"🔍 Checking {len(video_ids_404)} videos that return 404 from HeyGen...")
        
        for video_id in video_ids_404:
            # Check if video exists in database
            cursor.execute("SELECT id, title, status FROM videos WHERE heygen_video_id = %s", (video_id,))
            video = cursor.fetchone()
            
            if video:
                print(f"📋 Found video: ID={video[0]}, Title={video[1]}, Status={video[2]}")
                
                # Update status to failed since it doesn't exist at HeyGen
                cursor.execute("""
                    UPDATE videos 
                    SET status = 'failed', 
                        error_message = 'Video not found at HeyGen (404)',
                        updated_at = NOW()
                    WHERE heygen_video_id = %s
                """, (video_id,))
                
                print(f"✅ Updated video {video_id} status to 'failed'")
            else:
                print(f"❌ Video {video_id} not found in database")
        
        conn.commit()
        
        # Show current processing videos
        cursor.execute("SELECT heygen_video_id, status FROM videos WHERE status = 'processing'")
        processing_videos = cursor.fetchall()
        
        print(f"\n📊 Current processing videos: {len(processing_videos)}")
        for video in processing_videos:
            print(f"  - {video[0]} (status: {video[1]})")
        
        cursor.close()
        conn.close()
        
        print(f"\n🎉 Cleanup complete! 404 videos marked as failed.")
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    cleanup_404_videos()
