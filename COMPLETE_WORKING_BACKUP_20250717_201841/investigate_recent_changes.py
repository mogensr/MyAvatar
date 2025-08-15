#!/usr/bin/env python3
"""
Investigate what changed in the last 5 days
"""
import os
import sys
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

def investigate_recent_changes():
    """Check for recent changes that might explain the avatar issue"""
    print("🔍 INVESTIGATING RECENT CHANGES (Last 5 Days)")
    print("=" * 50)
    
    try:
        from app.db.database import execute_query
        
        # Check when avatars were last modified
        print("📅 CHECKING AVATAR MODIFICATION DATES")
        recent_avatars = execute_query("""
            SELECT avatar_name, avatar_image_url, created_at, 
                   CASE 
                       WHEN updated_at IS NOT NULL THEN updated_at 
                       ELSE created_at 
                   END as last_modified
            FROM user_avatars
            WHERE (updated_at >= datetime('now', '-5 days') OR created_at >= datetime('now', '-5 days'))
            ORDER BY last_modified DESC
        """, fetch_all=True)
        
        if recent_avatars:
            print(f"Found {len(recent_avatars)} avatars modified in last 5 days:")
            for avatar in recent_avatars:
                print(f"  - {avatar['avatar_name']}: {avatar['last_modified']}")
                print(f"    URL: {avatar['avatar_image_url'][:60]}...")
        else:
            print("❌ No avatars modified in last 5 days")
        
        # Check all avatar URLs to see the pattern
        print(f"\n📊 CURRENT URL ANALYSIS")
        all_avatars = execute_query("""
            SELECT avatar_image_url, COUNT(*) as count
            FROM user_avatars
            WHERE avatar_image_url IS NOT NULL
            GROUP BY 
                CASE 
                    WHEN avatar_image_url LIKE '%.jpg' OR avatar_image_url LIKE '%.png' THEN 'complete'
                    ELSE 'incomplete'
                END
        """, fetch_all=True)
        
        for result in all_avatars:
            url_type = "Complete URLs" if result['avatar_image_url'] in ['complete'] else "Incomplete URLs"
            print(f"  {url_type}: {result['count']}")
        
        # Sample current URLs
        print(f"\n🔍 SAMPLE CURRENT URLs")
        samples = execute_query("""
            SELECT avatar_name, avatar_image_url
            FROM user_avatars
            WHERE avatar_image_url IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 3
        """, fetch_all=True)
        
        for sample in samples:
            url = sample['avatar_image_url']
            status = "✅ Complete" if url.endswith(('.jpg', '.png')) else "❌ Incomplete"
            print(f"  {sample['avatar_name']}: {status}")
            print(f"    {url}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    investigate_recent_changes()
