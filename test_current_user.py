#!/usr/bin/env python3
"""
Test what user is currently logged in and what videos they should see
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    """Main function"""
    print("Current User and Video Test")
    print("=" * 30)
    
    try:
        # Connect to database
        conn = psycopg2.connect(
            os.getenv("DATABASE_URL"),
            cursor_factory=RealDictCursor
        )
        
        cur = conn.cursor()
        
        # Show all users
        cur.execute("SELECT id, username, email FROM users ORDER BY id")
        users = cur.fetchall()
        
        print("All users in system:")
        for user in users:
            print(f"  ID {user['id']}: {user['username']} ({user['email']})")
        
        print("\nUser video counts:")
        cur.execute("""
            SELECT u.id, u.username, COUNT(v.id) as video_count
            FROM users u
            LEFT JOIN videos v ON u.id = v.user_id
            GROUP BY u.id, u.username
            ORDER BY u.id
        """)
        user_videos = cur.fetchall()
        
        for uv in user_videos:
            print(f"  User {uv['id']} ({uv['username']}): {uv['video_count']} videos")
        
        # Test the exact query from dashboard for each user
        print("\nTesting dashboard query for each user:")
        for user in users:
            user_id = user['id']
            cur.execute("""
                SELECT v.*, ua.avatar_image_url, ua.avatar_name
                FROM videos v
                LEFT JOIN user_avatars ua ON v.avatar_id = ua.avatar_id AND v.user_id = ua.user_id
                WHERE v.user_id = %s
                ORDER BY v.created_at DESC
            """, (user_id,))
            
            videos = cur.fetchall()
            print(f"\n  User {user_id} ({user['username']}):")
            print(f"    Dashboard query returns: {len(videos)} videos")
            
            if videos:
                completed_with_urls = 0
                for video in videos:
                    if video.get('status') == 'completed' and video.get('video_url'):
                        completed_with_urls += 1
                        print(f"      ✅ Video {video['id']}: {video['title']} - HAS URL")
                    elif video.get('status') == 'completed':
                        print(f"      ❌ Video {video['id']}: {video['title']} - NO URL")
                    else:
                        print(f"      ⏳ Video {video['id']}: {video['title']} - Status: {video['status']}")
                
                print(f"    Videos that should display: {completed_with_urls}")
        
        conn.close()
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
