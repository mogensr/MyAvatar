#!/usr/bin/env python3
"""
Debug Dashboard Data

Check exactly what data is being passed to the dashboard template
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    """Main function"""
    print("Dashboard Data Debug")
    print("=" * 30)
    
    try:
        # Connect to database
        conn = psycopg2.connect(
            os.getenv("DATABASE_URL"),
            cursor_factory=RealDictCursor
        )
        
        cur = conn.cursor()
        
        # Simulate the exact query from web_routes.py dashboard
        print("1. Testing dashboard video query...")
        cur.execute("""
            SELECT v.*, ua.avatar_image_url, ua.avatar_name
            FROM videos v
            LEFT JOIN user_avatars ua ON v.avatar_id = ua.avatar_id AND v.user_id = ua.user_id
            WHERE v.user_id = %s
            ORDER BY v.created_at DESC
        """, (1,))  # Using user_id = 1 as example
        
        videos = cur.fetchall()
        print(f"Found {len(videos)} videos for user_id=1")
        
        if videos:
            print("\n2. Sample video data structure:")
            video = videos[0]
            print(f"Video ID: {video.get('id')}")
            print(f"Title: {video.get('title')}")
            print(f"Status: {video.get('status')}")
            print(f"video_url: {video.get('video_url')}")
            print(f"heygen_video_id: {video.get('heygen_video_id')}")
            print(f"thumbnail_url: {video.get('thumbnail_url')}")
            print(f"avatar_image_url: {video.get('avatar_image_url')}")
            print(f"avatar_name: {video.get('avatar_name')}")
            
            print(f"\nAll fields in video record:")
            for key, value in video.items():
                print(f"  {key}: {value}")
        
        # Check what the template processing would look like
        print("\n3. Template condition check:")
        for video in videos[:3]:  # Check first 3 videos
            video_dict = dict(video)
            status = video_dict.get('status')
            video_url = video_dict.get('video_url')
            
            print(f"\nVideo {video_dict.get('id')}:")
            print(f"  status == 'completed': {status == 'completed'}")
            print(f"  video_url exists: {bool(video_url)}")
            print(f"  video_url value: {video_url}")
            print(f"  Template condition (status == 'completed' and video_url): {status == 'completed' and bool(video_url)}")
        
        conn.close()
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
