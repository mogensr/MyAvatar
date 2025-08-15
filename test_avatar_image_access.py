#!/usr/bin/env python3
"""
Avatar Image URL Accessibility Test
===================================
Test if the avatar image URLs that are being passed to the frontend
are actually accessible and loading properly.
"""

import os
import sys
import requests
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add app directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

try:
    from app.db.database import execute_query
    print("✅ Database connection imported successfully")
except ImportError as e:
    print(f"❌ Failed to import database: {e}")
    sys.exit(1)

def test_image_url(url, timeout=10):
    """Test if an image URL is accessible and returns an image"""
    try:
        if not url or url.strip() == "":
            return False, "Empty URL"
        
        # Clean the URL
        url = url.strip()
        
        print(f"   Testing: {url}")
        
        # Make request with proper headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.head(url, timeout=timeout, allow_redirects=True, headers=headers)
        
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '').lower()
            if 'image' in content_type:
                return True, f"✅ OK (200) - {content_type}"
            else:
                return False, f"❌ Not an image - {content_type}"
        else:
            return False, f"❌ HTTP {response.status_code}"
            
    except requests.exceptions.Timeout:
        return False, "❌ Timeout"
    except requests.exceptions.ConnectionError:
        return False, "❌ Connection Error"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def test_all_avatar_urls():
    """Test all avatar URLs for accessibility"""
    print("🔍 Testing Avatar Image URL Accessibility")
    print("=" * 50)
    
    # Get all avatars (same query as your main.py filter)
    avatars = execute_query(
        "SELECT id, user_id, avatar_name, avatar_image_url, heygen_avatar_id FROM user_avatars WHERE avatar_image_url NOT LIKE '%placeholder%' ORDER BY user_id, created_at DESC",
        fetch_all=True
    )
    
    if not avatars:
        print("❌ No avatars found (excluding placeholders)")
        return
    
    print(f"📊 Found {len(avatars)} avatars to test")
    
    working_count = 0
    broken_count = 0
    
    for avatar in avatars:
        avatar_id = avatar['id']
        user_id = avatar['user_id']
        avatar_name = avatar['avatar_name']
        image_url = avatar['avatar_image_url']
        heygen_id = avatar['heygen_avatar_id']
        
        print(f"\n🎭 Avatar: {avatar_name} (ID: {avatar_id}, User: {user_id})")
        print(f"   HeyGen ID: {heygen_id}")
        
        if not image_url:
            print(f"   ❌ No image URL in database")
            broken_count += 1
            continue
        
        is_working, status = test_image_url(image_url)
        
        if is_working:
            print(f"   {status}")
            working_count += 1
        else:
            print(f"   {status}")
            broken_count += 1
    
    print("\n" + "=" * 50)
    print("📋 Summary")
    print("=" * 50)
    print(f"✅ Working images: {working_count}")
    print(f"❌ Broken images: {broken_count}")
    print(f"📊 Total tested: {len(avatars)}")
    
    if broken_count > 0:
        print(f"\n🔧 Recommendation: {broken_count} avatar images need to be refreshed from HeyGen API")
    else:
        print(f"\n✅ All avatar images are accessible!")
    
    return working_count, broken_count

if __name__ == "__main__":
    try:
        working, broken = test_all_avatar_urls()
        
        if broken > 0:
            print(f"\n💡 Next steps:")
            print(f"   1. Run the avatar refresh script to update broken URLs")
            print(f"   2. Check if HeyGen API key is valid")
            print(f"   3. Verify network connectivity to HeyGen servers")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
