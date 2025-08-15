#!/usr/bin/env python3
"""
Avatar Display Issue Fix
========================
Targeted fix for the avatar display issue where cloned and public avatars
show placeholder images while photo-to-avatar works fine.

This script will:
1. Identify avatars with broken/inaccessible image URLs
2. Attempt to refresh avatar data from HeyGen API
3. Update avatar_image_url with working URLs
4. Provide fallback placeholder for truly broken avatars
"""

import os
import sys
import requests
import logging
from datetime import datetime
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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# HeyGen API configuration
HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY")
HEYGEN_API_BASE = "https://api.heygen.com/v2"

def test_image_url(url):
    """Test if an image URL is accessible"""
    try:
        if not url or url == "":
            return False
        
        # Skip placeholder URLs
        if 'placeholder' in url.lower():
            return True  # Placeholder URLs are "working" by design
        
        response = requests.head(url, timeout=10, allow_redirects=True)
        return response.status_code == 200
    except Exception as e:
        logger.warning(f"Failed to test URL {url}: {e}")
        return False

def get_heygen_avatar_details(avatar_id):
    """Get avatar details from HeyGen API"""
    try:
        if not HEYGEN_API_KEY:
            logger.error("HeyGen API key not found")
            return None
        
        headers = {
            "X-API-KEY": HEYGEN_API_KEY,
            "Content-Type": "application/json"
        }
        
        # Try the avatar details endpoint
        response = requests.get(
            f"{HEYGEN_API_BASE}/avatars/{avatar_id}",
            headers=headers,
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 100 and data.get('data'):
                return data['data']
        
        logger.warning(f"Failed to get avatar details for {avatar_id}: {response.status_code}")
        return None
        
    except Exception as e:
        logger.error(f"Error getting HeyGen avatar details for {avatar_id}: {e}")
        return None

def get_user_avatars():
    """Get all user avatars from database"""
    try:
        avatars = execute_query(
            """
            SELECT id, user_id, avatar_name, avatar_image_url, heygen_avatar_id, avatar_id, 
                   is_default, created_at
            FROM user_avatars 
            ORDER BY user_id, created_at DESC
            """,
            fetch_all=True
        )
        return avatars or []
    except Exception as e:
        logger.error(f"Error getting user avatars: {e}")
        return []

def update_avatar_image_url(avatar_db_id, new_url):
    """Update avatar image URL in database"""
    try:
        execute_query(
            "UPDATE user_avatars SET avatar_image_url = %s, updated_at = NOW() WHERE id = %s",
            (new_url, avatar_db_id),
            fetch_one=False
        )
        return True
    except Exception as e:
        logger.error(f"Error updating avatar {avatar_db_id}: {e}")
        return False

def fix_avatar_display_issues():
    """Main function to fix avatar display issues"""
    print("🔧 Starting Avatar Display Issue Fix")
    print("=" * 50)
    
    # Get all avatars
    avatars = get_user_avatars()
    print(f"📊 Found {len(avatars)} avatars to check")
    
    broken_avatars = []
    fixed_avatars = []
    working_avatars = []
    
    for avatar in avatars:
        avatar_id = avatar['id']
        avatar_name = avatar['avatar_name']
        current_url = avatar['avatar_image_url']
        heygen_id = avatar['heygen_avatar_id']
        user_id = avatar['user_id']
        
        print(f"\n🔍 Checking avatar: {avatar_name} (ID: {avatar_id}, User: {user_id})")
        print(f"   Current URL: {current_url}")
        
        # Test current URL
        if test_image_url(current_url):
            print(f"   ✅ Current URL is working")
            working_avatars.append(avatar)
            continue
        
        print(f"   ❌ Current URL is broken or inaccessible")
        broken_avatars.append(avatar)
        
        # Try to get fresh data from HeyGen API
        if heygen_id and heygen_id != "":
            print(f"   🔄 Attempting to refresh from HeyGen API (ID: {heygen_id})")
            
            heygen_data = get_heygen_avatar_details(heygen_id)
            if heygen_data and heygen_data.get('preview_image_url'):
                new_url = heygen_data['preview_image_url']
                print(f"   📥 Got new URL from HeyGen: {new_url}")
                
                # Test the new URL
                if test_image_url(new_url):
                    print(f"   ✅ New URL is working, updating database")
                    if update_avatar_image_url(avatar_id, new_url):
                        fixed_avatars.append({
                            'avatar': avatar,
                            'old_url': current_url,
                            'new_url': new_url
                        })
                        print(f"   ✅ Successfully updated avatar {avatar_name}")
                    else:
                        print(f"   ❌ Failed to update database for avatar {avatar_name}")
                else:
                    print(f"   ❌ New URL from HeyGen is also broken")
            else:
                print(f"   ❌ No valid data from HeyGen API")
        
        # If still broken, set a proper placeholder
        if avatar in broken_avatars and not any(fix['avatar']['id'] == avatar_id for fix in fixed_avatars):
            placeholder_url = f"https://via.placeholder.com/150x150/6366f1/ffffff?text={avatar_name.replace(' ', '+')}"
            print(f"   🔄 Setting placeholder URL: {placeholder_url}")
            
            if update_avatar_image_url(avatar_id, placeholder_url):
                fixed_avatars.append({
                    'avatar': avatar,
                    'old_url': current_url,
                    'new_url': placeholder_url,
                    'type': 'placeholder'
                })
                print(f"   ✅ Set placeholder for avatar {avatar_name}")
    
    # Summary
    print("\n" + "=" * 50)
    print("🏁 Avatar Display Fix Summary")
    print("=" * 50)
    print(f"✅ Working avatars: {len(working_avatars)}")
    print(f"🔧 Fixed avatars: {len(fixed_avatars)}")
    print(f"❌ Still broken: {len(broken_avatars) - len([f for f in fixed_avatars if f['avatar'] in broken_avatars])}")
    
    if fixed_avatars:
        print("\n📋 Fixed Avatars Details:")
        for fix in fixed_avatars:
            avatar = fix['avatar']
            fix_type = fix.get('type', 'heygen_refresh')
            print(f"   • {avatar['avatar_name']} (User {avatar['user_id']}) - {fix_type}")
    
    print(f"\n🎯 Total avatars processed: {len(avatars)}")
    print("✅ Avatar display issue fix completed!")
    
    return {
        'total': len(avatars),
        'working': len(working_avatars),
        'fixed': len(fixed_avatars),
        'broken': len(broken_avatars)
    }

if __name__ == "__main__":
    try:
        results = fix_avatar_display_issues()
        print(f"\n🎉 Fix completed successfully!")
        print(f"Results: {results}")
    except Exception as e:
        print(f"❌ Error during fix: {e}")
        import traceback
        traceback.print_exc()
