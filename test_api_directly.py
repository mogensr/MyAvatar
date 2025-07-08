#!/usr/bin/env python3
"""
Test the /api/completed-videos endpoint directly
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def test_api_logic():
    """Test the same logic as the API endpoint"""
    
    database_url = os.getenv('DATABASE_URL')
    conn = psycopg2.connect(database_url)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Test the exact same query as the API
    print("🔍 Testing API query...")
    
    # Use a known user ID (like user 3 from before)
    user_id = 3
    
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
    
    print(f"📊 Found {len(videos)} completed videos for user {user_id}")
    
    if videos:
        for i, video in enumerate(videos[:3], 1):
            print(f"\n🎬 Video {i}:")
            print(f"  ID: {video['id']}")
            print(f"  Title: {video['title']}")
            print(f"  Has video_url: {'✅ YES' if video['video_url'] else '❌ NO'}")
            if video['video_url']:
                print(f"  URL: {video['video_url'][:80]}...")
    else:
        print("❌ No videos found!")
        
        # Check if there are ANY completed videos
        cur.execute("SELECT COUNT(*) as count FROM videos WHERE status = 'completed'")
        total = cur.fetchone()['count']
        print(f"📊 Total completed videos in database: {total}")
        
        if total > 0:
            cur.execute("SELECT user_id, COUNT(*) as count FROM videos WHERE status = 'completed' GROUP BY user_id ORDER BY count DESC LIMIT 5")
            user_counts = cur.fetchall()
            print("👥 Completed videos by user:")
            for uc in user_counts:
                print(f"  User {uc['user_id']}: {uc['count']} videos")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    test_api_logic()
