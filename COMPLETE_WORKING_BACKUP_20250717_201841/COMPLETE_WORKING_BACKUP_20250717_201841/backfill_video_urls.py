#!/usr/bin/env python3
"""
Backfill Missing Video URLs

This script fetches video URLs from HeyGen API for completed videos
that don't have URLs in the database and updates them.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_video_url_from_heygen(api_key, heygen_video_id):
    """Get video URL from HeyGen API"""
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    try:
        print(f"  Fetching details for {heygen_video_id}...")
        response = requests.get(
            f"https://api.heygen.com/v1/video_status.get?video_id={heygen_video_id}",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            details = data.get("data", {})
            
            # Try different possible fields for video URL
            video_url = (details.get("video_url") or 
                        details.get("video_url_caption") or 
                        details.get("url") or 
                        details.get("download_url"))
            
            status = details.get("status", "unknown")
            
            if video_url:
                print(f"    Found URL: {video_url[:50]}...")
                return video_url
            else:
                print(f"    No URL found, status: {status}")
                return None
        else:
            print(f"    API Error: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"    Exception: {e}")
        return None

def main():
    """Main function"""
    print("Backfill Video URLs Tool")
    print("=" * 30)
    
    # Check for API key
    api_key = os.getenv("HEYGEN_API_KEY")
    if not api_key:
        print("ERROR: No HEYGEN_API_KEY found in environment")
        return
    
    try:
        # Connect to database
        conn = psycopg2.connect(
            os.getenv("DATABASE_URL"),
            cursor_factory=RealDictCursor
        )
        
        cur = conn.cursor()
        
        # Find completed videos without URLs
        cur.execute("""
            SELECT id, heygen_video_id, title
            FROM videos 
            WHERE status = 'completed' 
            AND (video_url IS NULL OR video_url = '')
            AND heygen_video_id IS NOT NULL
            ORDER BY created_at DESC
        """)
        videos = cur.fetchall()
        
        print(f"Found {len(videos)} videos needing URL backfill")
        
        if not videos:
            print("No videos need backfill!")
            return
        
        updated_count = 0
        
        for video in videos:
            print(f"\nProcessing video {video['id']}: {video['title']}")
            
            video_url = get_video_url_from_heygen(api_key, video['heygen_video_id'])
            
            if video_url:
                # Update the video_url column
                cur.execute(
                    "UPDATE videos SET video_url = %s WHERE id = %s",
                    (video_url, video['id'])
                )
                conn.commit()
                updated_count += 1
                print(f"    ✓ Updated video {video['id']}")
            else:
                print(f"    ✗ Could not get URL for video {video['id']}")
        
        print(f"\nSUCCESS: Updated {updated_count} out of {len(videos)} videos")
        
        # Verify the updates
        cur.execute("""
            SELECT COUNT(*) as count
            FROM videos 
            WHERE status = 'completed' 
            AND video_url IS NOT NULL 
            AND video_url != ''
        """)
        result = cur.fetchone()
        print(f"Total completed videos with URLs: {result['count']}")
        
        conn.close()
        
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    main()
