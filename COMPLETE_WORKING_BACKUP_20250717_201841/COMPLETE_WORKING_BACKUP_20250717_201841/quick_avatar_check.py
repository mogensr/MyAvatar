#!/usr/bin/env python3
"""
Quick check of current avatar status
"""
import os
import sys
from dotenv import load_dotenv

# Load environment
load_dotenv()
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

def quick_check():
    """Quick avatar status check"""
    try:
        from app.db.database import execute_query
        
        print("=== QUICK AVATAR STATUS CHECK ===")
        
        # Count total avatars
        total = execute_query("SELECT COUNT(*) as count FROM user_avatars", fetch_one=True)
        print(f"Total avatars in database: {total['count']}")
        
        # Count avatars with image URLs
        with_urls = execute_query("""
            SELECT COUNT(*) as count FROM user_avatars 
            WHERE avatar_image_url IS NOT NULL AND avatar_image_url != ''
        """, fetch_one=True)
        print(f"Avatars with image URLs: {with_urls['count']}")
        
        # Count avatars with complete URLs (ending in .jpg/.png)
        complete_urls = execute_query("""
            SELECT COUNT(*) as count FROM user_avatars 
            WHERE avatar_image_url LIKE '%.jpg' OR avatar_image_url LIKE '%.png'
        """, fetch_one=True)
        print(f"Avatars with complete URLs: {complete_urls['count']}")
        
        # Show sample of recent avatars
        recent = execute_query("""
            SELECT ua.avatar_name, ua.avatar_image_url, u.username
            FROM user_avatars ua
            JOIN users u ON ua.user_id = u.id
            ORDER BY ua.created_at DESC
            LIMIT 3
        """, fetch_all=True)
        
        print(f"\n=== RECENT AVATARS SAMPLE ===")
        for avatar in recent:
            url = avatar['avatar_image_url'] or 'No URL'
            url_status = "✅ Complete" if url.endswith(('.jpg', '.png')) else "❌ Incomplete"
            print(f"User: {avatar['username']}")
            print(f"Avatar: {avatar['avatar_name']}")
            print(f"URL: {url[:50]}{'...' if len(url) > 50 else ''}")
            print(f"Status: {url_status}\n")
            
        # Check admin users
        admins = execute_query("SELECT COUNT(*) as count FROM users WHERE is_admin = 1", fetch_one=True)
        print(f"Admin users: {admins['count']}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    quick_check()
