#!/usr/bin/env python3
"""
Debug the exact data flow from database to template
"""
import os, psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def simulate_dashboard_data_processing():
    """Simulate exactly what the dashboard route does"""
    print("=== SIMULATING DASHBOARD DATA FLOW ===")
    
    # Step 1: Connect to database
    conn = psycopg2.connect(os.getenv('DATABASE_URL'), cursor_factory=RealDictCursor)
    cur = conn.cursor()
    
    # Step 2: Simulate db.get_user_videos(3) - the exact query from user_manager.py
    print("\n1. Raw database query (db.get_user_videos):")
    cur.execute("SELECT * FROM videos WHERE user_id = %s ORDER BY created_at DESC", (3,))
    raw_videos = cur.fetchall()
    print(f"   Found {len(raw_videos)} raw videos")
    
    # Step 3: Convert to dict (like user_manager.py does)
    videos = [dict(row) if hasattr(row, 'keys') else row for row in raw_videos] if raw_videos else []
    print(f"   Converted to {len(videos)} video dicts")
    
    # Step 4: Simulate dashboard processing (lines 1479-1493 in web_routes.py)
    print("\n2. Dashboard processing:")
    processed_videos = []
    if videos:
        for video in videos:
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
    
    print(f"   Processed {len(processed_videos)} videos")
    
    # Step 5: Check first 3 videos (what template gets)
    print("\n3. First 3 videos sent to template:")
    for i, video in enumerate(processed_videos[:3]):
        print(f"\n   Video {i+1}:")
        print(f"     ID: {video['id']}")
        print(f"     Title: {video['title']}")
        print(f"     Status: {video['status']}")
        print(f"     video_url: {video['video_url']}")
        print(f"     video_url type: {type(video['video_url'])}")
        print(f"     video_url bool: {bool(video['video_url'])}")
        print(f"     Template condition: {video['status'] == 'completed' and bool(video['video_url'])}")
    
    conn.close()

if __name__ == "__main__":
    simulate_dashboard_data_processing()
