#!/usr/bin/env python3
"""
Check what's actually in the Railway database
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def check_railway_videos():
    """Check videos in Railway database"""
    print("=== CHECKING RAILWAY DATABASE ===")
    
    DATABASE_URL = os.getenv('DATABASE_URL')
    print(f"Database URL: {DATABASE_URL[:50]}...")
    
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        cur = conn.cursor()
        
        # Check user 3's videos (MogensR)
        print("\n1. Checking user 3 (MogensR) videos:")
        cur.execute("""
            SELECT id, title, status, 
                   CASE WHEN video_url IS NOT NULL AND video_url != '' 
                        THEN 'YES' ELSE 'NO' END as has_url,
                   LENGTH(video_url) as url_length
            FROM videos 
            WHERE user_id = 3 
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        
        videos = cur.fetchall()
        print(f"Found {len(videos)} videos for user 3:")
        
        for video in videos:
            print(f"  ID {video['id']}: {video['title']}")
            print(f"    Status: {video['status']}")
            print(f"    Has URL: {video['has_url']}")
            print(f"    URL Length: {video['url_length']}")
            print()
        
        # Check all users with completed videos
        print("2. All users with completed videos:")
        cur.execute("""
            SELECT u.username, COUNT(v.id) as video_count,
                   COUNT(CASE WHEN v.video_url IS NOT NULL AND v.video_url != '' THEN 1 END) as with_urls
            FROM users u
            JOIN videos v ON u.id = v.user_id
            WHERE v.status = 'completed'
            GROUP BY u.id, u.username
            ORDER BY video_count DESC
        """)
        
        users = cur.fetchall()
        for user in users:
            print(f"  {user['username']}: {user['video_count']} videos, {user['with_urls']} with URLs")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_railway_videos()
