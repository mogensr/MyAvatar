#!/usr/bin/env python3
"""
Debug Template Data - Check exactly what the dashboard template receives
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    """Main function"""
    print("Template Data Debug")
    print("=" * 30)
    
    try:
        # Connect to database
        conn = psycopg2.connect(
            os.getenv("DATABASE_URL"),
            cursor_factory=RealDictCursor
        )
        
        cur = conn.cursor()
        
        # Get user 3 (MogensR) data exactly like the dashboard does
        user_id = 3
        
        # Simulate db.get_user_videos() call
        cur.execute("SELECT * FROM videos WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
        raw_videos = cur.fetchall()
        
        print(f"Raw videos from db.get_user_videos(): {len(raw_videos)}")
        
        # Simulate the processing in dashboard_page function (lines 1479-1493)
        processed_videos = []
        if raw_videos:
            for video in raw_videos:
                if isinstance(video, dict):
                    processed_video = {
                        'id': video.get('id'),
                        'heygen_video_id': video.get('heygen_video_id'),
                        'title': video.get('title', 'Untitled Video'),
                        'status': video.get('status', 'unknown'),
                        'duration': video.get('duration', ''),
                        'format': video.get('format', '16:9'),
                        'video_url': video.get('video_url'),
                        'thumbnail_url': video.get('thumbnail_url'),
                        'created_at': str(video.get('created_at', 'Unknown'))
                    }
                    processed_videos.append(processed_video)
        
        print(f"Processed videos: {len(processed_videos)}")
        
        # Check the first 3 videos (what template shows)
        print(f"\nFirst 3 videos (what template receives):")
        for i, video in enumerate(processed_videos[:3]):
            print(f"\nVideo {i+1}:")
            print(f"  ID: {video['id']}")
            print(f"  Title: {video['title']}")
            print(f"  Status: {video['status']}")
            print(f"  video_url: {video['video_url']}")
            print(f"  video_url type: {type(video['video_url'])}")
            print(f"  video_url bool: {bool(video['video_url'])}")
            
            # Template condition check
            status_check = video['status'] == 'completed'
            url_check = bool(video['video_url'])
            template_condition = status_check and url_check
            
            print(f"  Template condition breakdown:")
            print(f"    status == 'completed': {status_check}")
            print(f"    bool(video_url): {url_check}")
            print(f"    FINAL CONDITION: {template_condition}")
            
            if template_condition:
                print(f"  ✅ Should show VIDEO PLAYER")
            else:
                print(f"  ❌ Should show PLACEHOLDER")
        
        conn.close()
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
