#!/usr/bin/env python3
"""
Test script to verify HeyGen image fetching is working
"""
import os
import sys
sys.path.append('.')

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Loaded .env file")
except ImportError:
    print("⚠️ python-dotenv not installed, trying without .env loading")

from app.utils.heygen_image_utils import get_heygen_avatar_image, ensure_avatar_has_heygen_image
from app.api.heygen import get_available_avatars

def test_heygen_images():
    """Test HeyGen image fetching functionality"""
    
    # Check if API key is available
    api_key = os.getenv("HEYGEN_API_KEY")
    if not api_key:
        print("❌ HEYGEN_API_KEY environment variable not set")
        return False
    
    print(f"✅ HeyGen API key found: {api_key[:10]}...")
    
    # Test 1: Get all available avatars
    print("\n🔍 Testing get_available_avatars...")
    try:
        result = get_available_avatars(api_key)
        if result.get('success'):
            avatars = result.get('avatars', [])
            print(f"✅ Found {len(avatars)} avatars")
            
            # Show first few avatars
            for i, avatar in enumerate(avatars[:3]):
                avatar_id = avatar.get('avatar_id', 'Unknown')
                preview_url = avatar.get('preview_image_url', 'No preview')
                print(f"  Avatar {i+1}: {avatar_id} -> {preview_url}")
                
            # Test 2: Get specific avatar image
            if avatars:
                test_avatar_id = avatars[0].get('avatar_id')
                print(f"\n🖼️ Testing get_heygen_avatar_image for {test_avatar_id}...")
                
                image_url = get_heygen_avatar_image(test_avatar_id, api_key)
                if image_url:
                    print(f"✅ Got image URL: {image_url}")
                else:
                    print("❌ Failed to get image URL")
                
                # Test 3: Test ensure_avatar_has_heygen_image
                print(f"\n🔄 Testing ensure_avatar_has_heygen_image for {test_avatar_id}...")
                
                fresh_image = ensure_avatar_has_heygen_image(test_avatar_id, None, api_key)
                if fresh_image:
                    print(f"✅ Got fresh image URL: {fresh_image}")
                    return True
                else:
                    print("❌ Failed to get fresh image URL")
                    return False
            else:
                print("❌ No avatars found to test with")
                return False
        else:
            print(f"❌ Failed to get avatars: {result.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Exception during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 Testing HeyGen Image Fetching...")
    success = test_heygen_images()
    
    if success:
        print("\n✅ All tests passed! HeyGen image fetching is working.")
    else:
        print("\n❌ Tests failed! Check the errors above.")
