#!/usr/bin/env python3
"""
Simple Video URL Check
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    """Main function"""
    print("Video URL Check Tool")
    print("=" * 30)
    
    try:
        # Connect to database
        conn = psycopg2.connect(
            os.getenv("DATABASE_URL"),
            cursor_factory=RealDictCursor
        )
        
        cur = conn.cursor()
        
        # Check completed videos without URLs
        cur.execute("""
            SELECT id, heygen_video_id, status, video_url, title
            FROM videos 
            WHERE status = 'completed' 
            AND (video_url IS NULL OR video_url = '')
            ORDER BY created_at DESC
            LIMIT 5
        """)
        videos = cur.fetchall()
        
        print(f"Found {len(videos)} completed videos without URLs:")
        for video in videos:
            print(f"  ID: {video['id']}, HeyGen: {video['heygen_video_id']}")
            print(f"  Title: {video['title']}")
            print(f"  video_url: {video['video_url']}")
            print()
        
        # Check if video_path column exists
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'videos' 
            AND column_name = 'video_path'
        """)
        has_video_path = cur.fetchone()
        
        print(f"video_path column exists: {bool(has_video_path)}")
        
        conn.close()
        
        # Check code for bug
        api_file = "app/routes/api_routes.py"
        if os.path.exists(api_file):
            with open(api_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if 'UPDATE videos SET video_path' in content:
                print("BUG FOUND: Code updates video_path instead of video_url")
            else:
                print("No video_path bug found in code")
        else:
            print(f"File not found: {api_file}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
