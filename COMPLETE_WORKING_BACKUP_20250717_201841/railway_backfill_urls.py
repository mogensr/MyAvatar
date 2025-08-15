#!/usr/bin/env python3
"""
Backfill video URLs for Railway database
This script connects to Railway PostgreSQL and populates missing video_url values
"""
import os
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# Railway database URL (should be different from local)
RAILWAY_DATABASE_URL = os.getenv('DATABASE_URL')  # This should be Railway's URL
HEYGEN_API_KEY = os.getenv('HEYGEN_API_KEY')

def get_video_url_from_heygen(heygen_video_id):
    """Get video URL from HeyGen API"""
    if not heygen_video_id:
        return None
    
    try:
        headers = {
            'X-API-KEY': HEYGEN_API_KEY,
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f'https://api.heygen.com/v2/video/{heygen_video_id}',
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 100 and 'data' in data:
                video_url = data['data'].get('video_url')
                if video_url:
                    print(f"  ✅ Got URL for {heygen_video_id}: {video_url[:50]}...")
                    return video_url
                else:
                    print(f"  ❌ No video_url in response for {heygen_video_id}")
            else:
                print(f"  ❌ API error for {heygen_video_id}: {data}")
        else:
            print(f"  ❌ HTTP {response.status_code} for {heygen_video_id}")
            
    except Exception as e:
        print(f"  ❌ Exception getting URL for {heygen_video_id}: {e}")
    
    return None

def backfill_railway_video_urls():
    """Backfill missing video URLs in Railway database"""
    print("=== BACKFILLING VIDEO URLs IN RAILWAY DATABASE ===")
    print(f"Database URL: {RAILWAY_DATABASE_URL[:50]}...")
    
    if not RAILWAY_DATABASE_URL:
        print("❌ No DATABASE_URL found in environment")
        return
    
    if not HEYGEN_API_KEY:
        print("❌ No HEYGEN_API_KEY found in environment")
        return
    
    try:
        # Connect to Railway database
        conn = psycopg2.connect(RAILWAY_DATABASE_URL, cursor_factory=RealDictCursor)
        cur = conn.cursor()
        
        # Find completed videos without URLs
        print("\n1. Finding completed videos without URLs...")
        cur.execute("""
            SELECT id, heygen_video_id, title, user_id 
            FROM videos 
            WHERE status = 'completed' 
            AND (video_url IS NULL OR video_url = '')
            ORDER BY created_at DESC
        """)
        
        videos_to_fix = cur.fetchall()
        print(f"Found {len(videos_to_fix)} completed videos without URLs")
        
        if not videos_to_fix:
            print("✅ All completed videos already have URLs!")
            return
        
        # Backfill each video
        print("\n2. Backfilling video URLs...")
        updated_count = 0
        
        for video in videos_to_fix:
            print(f"\nProcessing video {video['id']}: {video['title']}")
            
            if not video['heygen_video_id']:
                print("  ❌ No heygen_video_id, skipping")
                continue
            
            # Get URL from HeyGen
            video_url = get_video_url_from_heygen(video['heygen_video_id'])
            
            if video_url:
                # Update database
                cur.execute("""
                    UPDATE videos 
                    SET video_url = %s 
                    WHERE id = %s
                """, (video_url, video['id']))
                
                updated_count += 1
                print(f"  ✅ Updated video {video['id']}")
            else:
                print(f"  ❌ Could not get URL for video {video['id']}")
            
            # Rate limiting
            time.sleep(0.5)
        
        # Commit changes
        conn.commit()
        print(f"\n✅ Successfully updated {updated_count} videos")
        
        # Verify results
        print("\n3. Verification:")
        cur.execute("""
            SELECT COUNT(*) as total_completed,
                   COUNT(video_url) as with_urls
            FROM videos 
            WHERE status = 'completed'
        """)
        
        result = cur.fetchone()
        print(f"Completed videos: {result['total_completed']}")
        print(f"With URLs: {result['with_urls']}")
        print(f"Missing URLs: {result['total_completed'] - result['with_urls']}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()

if __name__ == "__main__":
    backfill_railway_video_urls()
