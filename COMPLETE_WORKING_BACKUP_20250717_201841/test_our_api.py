#!/usr/bin/env python3
"""
Test our API endpoint logic directly without HTTP
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def simulate_api_call():
    """Simulate what our API endpoint should return"""
    
    user_id = 3  # Your user ID
    
    # Direct SQL query - same as in our API
    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT id, title, thumbnail_url, duration, created_at, heygen_video_id, video_url
        FROM videos 
        WHERE user_id = %s 
        AND status = 'completed' 
        AND video_url IS NOT NULL 
        AND video_url != ''
        ORDER BY created_at DESC
    """, (user_id,))
    
    videos = cur.fetchall()
    conn.close()
    
    print(f"🎬 Found {len(videos)} videos in database")
    
    # Process videos (same logic as API)
    video_list = []
    for video in videos:
        video_dict = dict(video)
        
        # Format date
        if video_dict.get('created_at'):
            video_dict['created_at'] = video_dict['created_at'].strftime('%b %d, %Y')
        
        # Check video URL
        if video_dict.get('video_url'):
            print(f"  ✅ Video '{video_dict.get('title')}' has URL")
        else:
            print(f"  ❌ Video '{video_dict.get('title')}' missing URL")
            
        video_list.append(video_dict)
    
    # Return what API should return
    result = {
        "success": True,
        "count": len(video_list),
        "videos": video_list
    }
    
    print(f"\n📊 API would return:")
    print(f"  Success: {result['success']}")
    print(f"  Count: {result['count']}")
    print(f"  Videos: {len(result['videos'])} items")
    
    if result['videos']:
        first_video = result['videos'][0]
        print(f"\n🎬 First video sample:")
        print(f"  ID: {first_video.get('id')}")
        print(f"  Title: {first_video.get('title')}")
        print(f"  Has URL: {'✅' if first_video.get('video_url') else '❌'}")
        print(f"  URL length: {len(first_video.get('video_url', ''))} chars")
    
    return result

if __name__ == "__main__":
    simulate_api_call()
