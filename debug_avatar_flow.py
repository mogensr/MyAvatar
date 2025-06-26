#!/usr/bin/env python3
"""
Debug script to trace the exact avatar display flow
"""
import os
import sys
sys.path.append('.')

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.db.user_manager import Database
from app.utils.heygen_image_utils import get_heygen_avatar_image, ensure_avatar_has_heygen_image
from app.api.heygen import get_available_avatars

def debug_avatar_flow():
    """Debug the complete avatar display flow"""
    
    print("🔍 DEBUGGING AVATAR DISPLAY FLOW")
    print("=" * 50)
    
    # Step 1: Check API key
    api_key = os.getenv("HEYGEN_API_KEY")
    if not api_key:
        print("❌ HEYGEN_API_KEY not found")
        return
    print(f"✅ API Key: {api_key[:10]}...")
    
    # Step 2: Test HeyGen API directly
    print("\n📡 Testing HeyGen API...")
    try:
        result = get_available_avatars(api_key)
        if result.get('success'):
            avatars = result.get('avatars', [])
            print(f"✅ HeyGen API working: {len(avatars)} avatars found")
            
            if avatars:
                test_avatar = avatars[0]
                avatar_id = test_avatar.get('avatar_id')
                preview_url = test_avatar.get('preview_image_url')
                print(f"📸 Sample avatar: {avatar_id} -> {preview_url}")
        else:
            print(f"❌ HeyGen API failed: {result.get('error')}")
            return
    except Exception as e:
        print(f"❌ HeyGen API exception: {e}")
        return
    
    # Step 3: Test database connection
    print("\n💾 Testing database...")
    try:
        db = Database()
        print("✅ Database connected")
        
        # Get a test user ID (you might need to adjust this)
        test_user_id = 1  # Adjust this to your user ID
        
        # Step 4: Test get_user_avatars function
        print(f"\n👤 Testing get_user_avatars for user {test_user_id}...")
        avatars = db.get_user_avatars(test_user_id)
        
        if not avatars:
            print("❌ No avatars found in database")
            return
            
        print(f"✅ Found {len(avatars)} avatars in database")
        
        for i, avatar in enumerate(avatars):
            print(f"\n🎭 Avatar {i+1}:")
            print(f"  ID: {avatar.get('id')}")
            print(f"  Name: {avatar.get('name')}")
            print(f"  HeyGen ID: {avatar.get('heygen_avatar_id')}")
            print(f"  Image URL: {avatar.get('image_url')}")
            
            # Test individual avatar image fetching
            heygen_id = avatar.get('heygen_avatar_id')
            if heygen_id:
                print(f"  🔄 Testing fresh image fetch for {heygen_id}...")
                fresh_image = ensure_avatar_has_heygen_image(heygen_id, avatar.get('image_url'))
                print(f"  📸 Fresh image: {fresh_image}")
                
                if fresh_image != avatar.get('image_url'):
                    print(f"  ⚠️ Image URL changed from cached to fresh!")
                else:
                    print(f"  ℹ️ Image URL unchanged")
            else:
                print(f"  ⚠️ No HeyGen ID - can't fetch fresh image")
                
    except Exception as e:
        print(f"❌ Database error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_avatar_flow()
