#!/usr/bin/env python3
"""
Verify Video URL Fix

Check if the video URL issue has been resolved.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    """Main function"""
    print("Video URL Fix Verification")
    print("=" * 30)
    
    try:
        # Connect to database
        conn = psycopg2.connect(
            os.getenv("DATABASE_URL"),
            cursor_factory=RealDictCursor
        )
        
        cur = conn.cursor()
        
        # Check completed videos WITH URLs now
        cur.execute("""
            SELECT COUNT(*) as count
            FROM videos 
            WHERE status = 'completed' 
            AND video_url IS NOT NULL 
            AND video_url != ''
        """)
        with_urls = cur.fetchone()['count']
        
        # Check completed videos WITHOUT URLs
        cur.execute("""
            SELECT COUNT(*) as count
            FROM videos 
            WHERE status = 'completed' 
            AND (video_url IS NULL OR video_url = '')
        """)
        without_urls = cur.fetchone()['count']
        
        # Get sample of fixed videos
        cur.execute("""
            SELECT id, title, video_url
            FROM videos 
            WHERE status = 'completed' 
            AND video_url IS NOT NULL 
            AND video_url != ''
            ORDER BY id DESC
            LIMIT 3
        """)
        sample_videos = cur.fetchall()
        
        print(f"Completed videos WITH URLs: {with_urls}")
        print(f"Completed videos WITHOUT URLs: {without_urls}")
        print()
        
        if sample_videos:
            print("Sample fixed videos:")
            for video in sample_videos:
                url_preview = video['video_url'][:50] + "..." if len(video['video_url']) > 50 else video['video_url']
                print(f"  ID {video['id']}: {video['title']}")
                print(f"    URL: {url_preview}")
                print()
        
        # Check if code bug still exists
        api_file = "app/routes/api_routes.py"
        if os.path.exists(api_file):
            with open(api_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if 'UPDATE videos SET video_path' in content:
                print("⚠️  CODE BUG STILL EXISTS!")
                print("   Need to fix: UPDATE videos SET video_path -> video_url")
                print("   File: app/routes/api_routes.py")
            else:
                print("✅ Code bug appears to be fixed")
        
        print("\n" + "=" * 30)
        if with_urls > 0 and without_urls == 0:
            print("🎉 SUCCESS: All completed videos now have URLs!")
        elif with_urls > 0:
            print(f"✅ PROGRESS: {with_urls} videos fixed, {without_urls} still need URLs")
        else:
            print("❌ ISSUE: No videos have URLs yet")
        
        conn.close()
        
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    main()
