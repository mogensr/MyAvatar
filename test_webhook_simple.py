#!/usr/bin/env python3
"""
Simple test to debug webhook database issue
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

def test_webhook_issue():
    """Test what's causing the webhook database error"""
    try:
        # Get database URL
        DATABASE_URL = os.getenv("DATABASE_URL")
        if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
            
        print("🔧 Connecting to database...")
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Test video ID from webhook
        test_video_id = "47b385f194d14cdbbc155f8f5a3c1c57"
        
        print(f"🔍 Checking if video {test_video_id} exists...")
        cursor.execute("SELECT id, heygen_video_id, status FROM videos WHERE heygen_video_id = %s", (test_video_id,))
        video = cursor.fetchone()
        
        if video:
            print(f"✅ Video exists: ID={video[0]}, Status={video[2]}")
        else:
            print(f"❌ Video {test_video_id} does NOT exist in database")
            print("🔍 Let's see what videos do exist...")
            
            cursor.execute("SELECT heygen_video_id, status FROM videos WHERE status = 'processing' LIMIT 3")
            processing_videos = cursor.fetchall()
            
            if processing_videos:
                print("📋 Processing videos found:")
                for v in processing_videos:
                    print(f"  - {v[0]} (status: {v[1]})")
                    
                # Test with first processing video
                first_video_id = processing_videos[0][0]
                print(f"\n🧪 Testing webhook update with existing video: {first_video_id}")
                
                # Test the exact webhook UPDATE
                update_query = """
                    UPDATE videos 
                    SET status = 'completed', 
                        video_path = %s,
                        duration = %s,
                        completed_at = NOW(),
                        updated_at = NOW()
                    WHERE heygen_video_id = %s
                """
                
                cursor.execute(update_query, ("https://files.heygen.ai/test-video.mp4", 30, first_video_id))
                rows_affected = cursor.rowcount
                
                print(f"✅ UPDATE successful! Rows affected: {rows_affected}")
                conn.commit()
                
                # Verify the update
                cursor.execute("SELECT status, video_path FROM videos WHERE heygen_video_id = %s", (first_video_id,))
                updated = cursor.fetchone()
                print(f"✅ Verified: Status={updated[0]}, Video_Path exists={bool(updated[1])}")
                
            else:
                print("❌ No processing videos found to test with")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_webhook_issue()
