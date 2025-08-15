#!/usr/bin/env python3
"""
Refresh Avatar Images - Quick Fix
=================================
Refresh avatar image URLs from HeyGen API to fix the display issue
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

# HeyGen API configuration
HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY")
HEYGEN_API_BASE = "https://api.heygen.com/v2"

def get_heygen_avatars():
    """Get all avatars from HeyGen API"""
    try:
        if not HEYGEN_API_KEY:
            print("❌ HeyGen API key not found")
            return None
        
        headers = {
            "X-API-KEY": HEYGEN_API_KEY,
            "Content-Type": "application/json"
        }
        
        # Get all avatars
        response = requests.get(
            f"{HEYGEN_API_BASE}/avatars",
            headers=headers,
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 100 and data.get('data'):
                return data['data']['avatars']
        
        print(f"❌ Failed to get avatars from HeyGen: {response.status_code}")
        return None
        
    except Exception as e:
        print(f"❌ Error getting HeyGen avatars: {e}")
        return None

def refresh_avatar_images():
    """Refresh avatar image URLs"""
    print("🔄 Refreshing Avatar Images from HeyGen")
    print("=" * 50)
    
    # Get HeyGen avatars
    heygen_avatars = get_heygen_avatars()
    if not heygen_avatars:
        print("❌ Could not fetch avatars from HeyGen API")
        return
    
    print(f"📥 Got {len(heygen_avatars)} avatars from HeyGen API")
    
    # Create lookup dict by avatar_id
    heygen_lookup = {}
    for avatar in heygen_avatars:
        avatar_id = avatar.get('avatar_id')
        if avatar_id:
            heygen_lookup[avatar_id] = avatar
    
    # Get our database avatars
    db_avatars = execute_query(
        "SELECT id, avatar_name, heygen_avatar_id, avatar_image_url FROM user_avatars WHERE heygen_avatar_id IS NOT NULL AND heygen_avatar_id != ''",
        fetch_all=True
    )
    
    if not db_avatars:
        print("❌ No avatars with HeyGen IDs found in database")
        return
    
    print(f"📊 Found {len(db_avatars)} avatars in database with HeyGen IDs")
    
    updated_count = 0
    
    for db_avatar in db_avatars:
        db_id = db_avatar['id']
        avatar_name = db_avatar['avatar_name']
        heygen_id = db_avatar['heygen_avatar_id']
        current_url = db_avatar['avatar_image_url']
        
        print(f"\n🎭 Processing: {avatar_name} (HeyGen ID: {heygen_id})")
        
        # Find matching HeyGen avatar
        heygen_avatar = heygen_lookup.get(heygen_id)
        if not heygen_avatar:
            print(f"   ❌ Not found in HeyGen API")
            continue
        
        # Get new image URL
        new_url = heygen_avatar.get('preview_image_url')
        if not new_url:
            print(f"   ❌ No preview image URL in HeyGen data")
            continue
        
        if new_url == current_url:
            print(f"   ✅ URL already up to date")
            continue
        
        # Update database
        try:
            execute_query(
                "UPDATE user_avatars SET avatar_image_url = %s WHERE id = %s",
                (new_url, db_id),
                fetch_one=False
            )
            print(f"   ✅ Updated image URL")
            print(f"      Old: {current_url}")
            print(f"      New: {new_url}")
            updated_count += 1
        except Exception as e:
            print(f"   ❌ Failed to update database: {e}")
    
    print("\n" + "=" * 50)
    print("📋 Refresh Complete")
    print("=" * 50)
    print(f"✅ Updated {updated_count} avatar image URLs")
    print(f"📊 Total processed: {len(db_avatars)}")
    
    if updated_count > 0:
        print(f"\n🎉 Avatar images refreshed! Try reloading your text-to-video page.")
    else:
        print(f"\n💡 No updates needed - all URLs were already current.")

if __name__ == "__main__":
    try:
        refresh_avatar_images()
    except Exception as e:
        print(f"❌ Error during refresh: {e}")
        import traceback
        traceback.print_exc()
