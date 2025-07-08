#!/usr/bin/env python3
"""
Find which users have videos
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    """Main function"""
    print("Find Users with Videos")
    print("=" * 30)
    
    try:
        # Connect to database
        conn = psycopg2.connect(
            os.getenv("DATABASE_URL"),
            cursor_factory=RealDictCursor
        )
        
        cur = conn.cursor()
        
        # Find users with videos
        cur.execute("""
            SELECT v.user_id, u.username, u.email, COUNT(v.id) as video_count,
                   COUNT(CASE WHEN v.status = 'completed' THEN 1 END) as completed_count,
                   COUNT(CASE WHEN v.status = 'completed' AND v.video_url IS NOT NULL THEN 1 END) as with_urls
            FROM videos v
            LEFT JOIN users u ON v.user_id = u.id
            GROUP BY v.user_id, u.username, u.email
            ORDER BY video_count DESC
        """)
        
        users = cur.fetchall()
        
        print(f"Found {len(users)} users with videos:")
        for user in users:
            print(f"\nUser ID: {user['user_id']}")
            print(f"  Username: {user['username']}")
            print(f"  Email: {user['email']}")
            print(f"  Total videos: {user['video_count']}")
            print(f"  Completed: {user['completed_count']}")
            print(f"  With URLs: {user['with_urls']}")
        
        # Test dashboard query with the actual user who has videos
        if users:
            test_user_id = users[0]['user_id']
            print(f"\n" + "="*30)
            print(f"Testing dashboard query for user {test_user_id}:")
            
            cur.execute("""
                SELECT v.*, ua.avatar_image_url, ua.avatar_name
                FROM videos v
                LEFT JOIN user_avatars ua ON v.avatar_id = ua.avatar_id AND v.user_id = ua.user_id
                WHERE v.user_id = %s
                ORDER BY v.created_at DESC
            """, (test_user_id,))
            
            videos = cur.fetchall()
            print(f"Dashboard query returned {len(videos)} videos")
            
            if videos:
                print("\nFirst video details:")
                video = videos[0]
                print(f"  ID: {video.get('id')}")
                print(f"  Title: {video.get('title')}")
                print(f"  Status: {video.get('status')}")
                print(f"  video_url: {video.get('video_url')}")
                print(f"  Template condition: {video.get('status') == 'completed' and bool(video.get('video_url'))}")
        
        conn.close()
        
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    main()
