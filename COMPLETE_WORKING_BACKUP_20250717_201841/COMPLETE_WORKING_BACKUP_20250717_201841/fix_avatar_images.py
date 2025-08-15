#!/usr/bin/env python3
"""
Fix broken avatar image URLs by updating with fresh HeyGen API data
"""
import os
from dotenv import load_dotenv
from app.db.database import execute_query
from app.api.heygen import get_available_avatars
import requests
import json

def fix_avatar_images():
    try:
        # Load environment variables
        load_dotenv()
        
        print("🔧 Fixing Avatar Images")
        print("=" * 40)
        
        # Get API key
        api_key = os.getenv("HEYGEN_API_KEY")
        if not api_key:
            print("❌ HEYGEN_API_KEY not found in environment")
            return
        
        # Get all avatars from database
        avatars = execute_query("""
            SELECT ua.id, ua.user_id, ua.avatar_id, ua.avatar_name, ua.avatar_image_url,
                   u.username
            FROM user_avatars ua
            JOIN users u ON ua.user_id = u.id
            ORDER BY ua.user_id, ua.id
        """, fetch_all=True)
        
        print(f"📊 Found {len(avatars)} avatars to check")
        
        # Get fresh avatar data from HeyGen API
        print("🌐 Fetching fresh avatar data from HeyGen API...")
        heygen_avatars = get_available_avatars(api_key)
        
        if not heygen_avatars:
            print("❌ Failed to get avatars from HeyGen API")
            return
        
        print(f"✅ Got {len(heygen_avatars)} avatars from HeyGen API")
        
        # Create lookup dictionary for HeyGen avatars
        heygen_lookup = {}
        for avatar in heygen_avatars:
            avatar_id = avatar.get('avatar_id')
            if avatar_id:
                heygen_lookup[avatar_id] = avatar
        
        # Check and update each avatar
        updates_made = 0
        for avatar in avatars:
            avatar_id = avatar['avatar_id']
            current_url = avatar['avatar_image_url']
            avatar_name = avatar['avatar_name']
            user_id = avatar['user_id']
            username = avatar['username']
            
            print(f"\n👤 {username} - {avatar_name} (ID: {avatar_id})")
            
            # Check if current URL is accessible
            url_working = False
            if current_url and current_url.startswith('http'):
                try:
                    response = requests.head(current_url, timeout=5)
                    if response.status_code == 200:
                        url_working = True
                        print(f"  ✅ Current URL working")
                    else:
                        print(f"  ❌ Current URL returns {response.status_code}")
                except Exception as e:
                    print(f"  ❌ Current URL error: {e}")
            else:
                print(f"  ❌ Invalid current URL: {current_url}")
            
            # If URL is broken, try to fix it
            if not url_working:
                if avatar_id in heygen_lookup:
                    heygen_avatar = heygen_lookup[avatar_id]
                    new_url = heygen_avatar.get('preview_image_url') or heygen_avatar.get('image_url')
                    
                    if new_url and new_url != current_url:
                        print(f"  🔄 Updating URL: {new_url}")
                        
                        # Update database
                        execute_query("""
                            UPDATE user_avatars 
                            SET avatar_image_url = %s 
                            WHERE id = %s
                        """, (new_url, avatar['id']))
                        
                        updates_made += 1
                        print(f"  ✅ Updated successfully")
                    else:
                        print(f"  ⚠️  No better URL available from HeyGen")
                else:
                    print(f"  ⚠️  Avatar ID not found in HeyGen API")
        
        print(f"\n🎉 Fixed {updates_made} avatar image URLs")
        
        # Test a few updated URLs
        if updates_made > 0:
            print("\n🧪 Testing updated URLs...")
            updated_avatars = execute_query("""
                SELECT avatar_name, avatar_image_url 
                FROM user_avatars 
                WHERE avatar_image_url LIKE 'https://files%heygen%'
                LIMIT 3
            """, fetch_all=True)
            
            for avatar in updated_avatars:
                name = avatar['avatar_name']
                url = avatar['avatar_image_url']
                try:
                    response = requests.head(url, timeout=5)
                    status = "✅ Working" if response.status_code == 200 else f"❌ {response.status_code}"
                    print(f"  {name}: {status}")
                except Exception as e:
                    print(f"  {name}: ❌ Error - {e}")
        
    except Exception as e:
        print(f"❌ Error fixing avatar images: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_avatar_images()
