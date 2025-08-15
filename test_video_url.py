#!/usr/bin/env python3
import os
import psycopg2
import requests
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def test_video_url():
    """Fetch a video from user 3 and test if the URL works"""
    
    # Connect to database
    conn = psycopg2.connect(os.getenv('DATABASE_URL'), cursor_factory=RealDictCursor)
    cur = conn.cursor()
    
    # Get one completed video for user 3
    cur.execute("""
        SELECT id, title, status, video_url, heygen_video_id, created_at, duration, thumbnail_url
        FROM videos 
        WHERE user_id = 3 
        AND status = 'completed' 
        AND video_url IS NOT NULL 
        AND video_url != ''
        ORDER BY created_at DESC 
        LIMIT 1
    """)
    
    video = cur.fetchone()
    conn.close()
    
    if not video:
        print("❌ No completed videos found for user 3")
        return
    
    print("🎬 Found video:")
    print(f"  ID: {video['id']}")
    print(f"  Title: {video['title']}")
    print(f"  Status: {video['status']}")
    print(f"  Created: {video['created_at']}")
    print(f"  Duration: {video['duration']}")
    print(f"  HeyGen ID: {video['heygen_video_id']}")
    print(f"  Thumbnail: {video['thumbnail_url']}")
    print(f"  Video URL: {video['video_url']}")
    print()
    print("🔗 FULL VIDEO URL:")
    print(video['video_url'])
    print()
    
    # Test if the video URL is accessible
    print("🔍 Testing video URL...")
    try:
        response = requests.head(video['video_url'], timeout=10)
        print(f"  Status Code: {response.status_code}")
        print(f"  Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
        print(f"  Content-Length: {response.headers.get('Content-Length', 'Unknown')}")
        
        if response.status_code == 200:
            print("  ✅ Video URL is accessible!")
        else:
            print(f"  ❌ Video URL returned status {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Error accessing video URL: {e}")
    
    print()
    print("📋 Summary:")
    print(f"  Video exists in database: ✅")
    print(f"  Has video_url: {'✅' if video['video_url'] else '❌'}")
    print(f"  URL accessible: Testing above...")
    
    return video

if __name__ == "__main__":
    test_video_url()
