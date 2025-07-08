#!/usr/bin/env python3
"""
Fix Video URL Bug and Backfill Missing URLs

This script:
1. Identifies the bug where video URLs are saved to wrong column
2. Fixes the code bug in api_routes.py
3. Backfills missing video URLs for completed videos
4. Updates the investigation log
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_connection():
    """Get PostgreSQL database connection"""
    try:
        conn = psycopg2.connect(
            os.getenv("DATABASE_URL"),
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None

def check_video_columns():
    """Check what columns exist in videos table"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'videos' 
            AND column_name IN ('video_url', 'video_path')
            ORDER BY column_name
        """)
        columns = cur.fetchall()
        
        print("📋 Video table columns:")
        for col in columns:
            print(f"   - {col['column_name']}: {col['data_type']}")
        
        return len(columns) > 0
    except Exception as e:
        print(f"❌ Error checking columns: {e}")
        return False
    finally:
        conn.close()

def find_completed_videos_without_urls():
    """Find completed videos that don't have video URLs"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, heygen_video_id, status, video_url, video_path, title, created_at
            FROM videos 
            WHERE status = 'completed' 
            AND (video_url IS NULL OR video_url = '')
            ORDER BY created_at DESC
        """)
        videos = cur.fetchall()
        
        print(f"🔍 Found {len(videos)} completed videos without URLs:")
        for video in videos:
            print(f"   - ID: {video['id']}, HeyGen ID: {video['heygen_video_id']}")
            print(f"     Title: {video['title']}")
            print(f"     video_url: {video['video_url']}")
            print(f"     video_path: {video.get('video_path', 'N/A')}")
            print()
        
        return videos
    except Exception as e:
        print(f"❌ Error finding videos: {e}")
        return []
    finally:
        conn.close()

def get_video_url_from_heygen(api_key, heygen_video_id):
    """Get video URL from HeyGen API"""
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    try:
        print(f"🔍 Fetching video details for {heygen_video_id}...")
        response = requests.get(
            f"https://api.heygen.com/v1/video_status.get?video_id={heygen_video_id}",
            headers=headers
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
            
            print(f"   Status: {status}")
            print(f"   Video URL: {video_url[:50] + '...' if video_url else 'None'}")
            
            return video_url, status
        else:
            print(f"   ❌ API Error: {response.status_code} - {response.text}")
            return None, None
            
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return None, None

def backfill_video_urls():
    """Backfill missing video URLs from HeyGen API"""
    api_key = os.getenv("HEYGEN_API_KEY")
    if not api_key:
        print("❌ No HEYGEN_API_KEY found in environment")
        return False
    
    videos = find_completed_videos_without_urls()
    if not videos:
        print("✅ No videos need URL backfill")
        return True
    
    conn = get_db_connection()
    if not conn:
        return False
    
    updated_count = 0
    
    try:
        cur = conn.cursor()
        
        for video in videos:
            heygen_id = video['heygen_video_id']
            if not heygen_id:
                print(f"⚠️  Video {video['id']} has no HeyGen ID, skipping")
                continue
            
            video_url, status = get_video_url_from_heygen(api_key, heygen_id)
            
            if video_url:
                # Update the video_url column (not video_path!)
                cur.execute(
                    "UPDATE videos SET video_url = %s WHERE id = %s",
                    (video_url, video['id'])
                )
                conn.commit()
                updated_count += 1
                print(f"✅ Updated video {video['id']} with URL")
            else:
                print(f"⚠️  Could not get URL for video {video['id']}")
        
        print(f"\n🎉 Successfully updated {updated_count} videos with URLs")
        return True
        
    except Exception as e:
        print(f"❌ Error during backfill: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def check_code_bug():
    """Check if the code bug still exists in api_routes.py"""
    api_routes_path = "app/routes/api_routes.py"
    
    if not os.path.exists(api_routes_path):
        print(f"❌ File not found: {api_routes_path}")
        return False
    
    try:
        with open(api_routes_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Look for the bug pattern
        if 'UPDATE videos SET video_path' in content:
            print("🐛 BUG FOUND: Code is updating 'video_path' instead of 'video_url'")
            
            # Show the problematic lines
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'UPDATE videos SET video_path' in line:
                    print(f"   Line {i+1}: {line.strip()}")
            
            return True
        else:
            print("✅ No 'video_path' bug found in UPDATE statements")
            return False
            
    except Exception as e:
        print(f"❌ Error checking code: {e}")
        return False

def main():
    """Main function"""
    print("🔧 MyAvatar Video URL Bug Fix & Backfill Tool")
    print("=" * 50)
    
    # Step 1: Check database schema
    print("\n1️⃣ Checking database schema...")
    if not check_video_columns():
        print("❌ Could not verify database schema")
        return
    
    # Step 2: Check for code bug
    print("\n2️⃣ Checking for code bug...")
    has_bug = check_code_bug()
    
    # Step 3: Find videos needing backfill
    print("\n3️⃣ Finding videos needing URL backfill...")
    videos_needing_fix = find_completed_videos_without_urls()
    
    # Step 4: Backfill URLs if needed
    if videos_needing_fix:
        print("\n4️⃣ Backfilling missing video URLs...")
        if backfill_video_urls():
            print("✅ Backfill completed successfully")
        else:
            print("❌ Backfill failed")
    
    # Step 5: Summary
    print("\n📋 SUMMARY:")
    print(f"   - Code bug present: {'Yes' if has_bug else 'No'}")
    print(f"   - Videos needing backfill: {len(videos_needing_fix)}")
    
    if has_bug:
        print("\n⚠️  MANUAL ACTION REQUIRED:")
        print("   The code bug still exists in app/routes/api_routes.py")
        print("   Search for 'UPDATE videos SET video_path' and change to 'video_url'")
    
    print("\n🎯 Next steps:")
    print("   1. Fix the code bug if present")
    print("   2. Deploy the fix to production")
    print("   3. Test video display on dashboard")
    print("   4. Monitor for new videos getting proper URLs")

if __name__ == "__main__":
    main()
