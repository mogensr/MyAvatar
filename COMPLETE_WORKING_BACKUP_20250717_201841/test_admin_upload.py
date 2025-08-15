#!/usr/bin/env python3
"""
Test the exact admin upload process to see where it fails
"""
import os
import sys
sys.path.append('.')

from dotenv import load_dotenv
from app.api.heygen import get_avatar_from_any_endpoint
from app.database.db_utils import execute_query

load_dotenv()

def test_admin_upload_process():
    """Test the exact admin upload process"""
    api_key = os.getenv("HEYGEN_API_KEY")
    heygen_avatar_id = "7e07203217034961a2bafa14c1cf141e"
    user_id = 1  # Test with user ID 1
    
    print(f"🔍 Testing admin upload process for avatar: {heygen_avatar_id}")
    print(f"👤 User ID: {user_id}")
    
    try:
        # Step 1: Clean up avatar ID (like admin route does)
        heygen_avatar_id = heygen_avatar_id.strip()
        print(f"✅ Step 1: Avatar ID cleaned: {heygen_avatar_id}")
        
        # Step 2: Check if avatar already exists
        existing = execute_query(
            "SELECT id FROM user_avatars WHERE user_id = %s AND heygen_avatar_id = %s",
            (user_id, heygen_avatar_id)
        )
        
        if existing:
            print(f"⚠️ Step 2: Avatar already exists for user {user_id}")
            return
        else:
            print(f"✅ Step 2: Avatar doesn't exist yet - can proceed")
        
        # Step 3: Get HeyGen API key
        if not api_key:
            print("❌ Step 3: HeyGen API key not found")
            return
        else:
            print(f"✅ Step 3: HeyGen API key found")
        
        # Step 4: Validate avatar with HeyGen API
        print(f"🔍 Step 4: Validating avatar with HeyGen API...")
        avatar_result = get_avatar_from_any_endpoint(api_key, heygen_avatar_id)
        
        if not avatar_result:
            print(f"❌ Step 4: Avatar validation failed - avatar_result is None")
            return
        
        print(f"✅ Step 4: Avatar validation succeeded")
        print(f"   - Type: {avatar_result.get('type')}")
        print(f"   - Has data: {bool(avatar_result.get('data'))}")
        print(f"   - Has error: {bool(avatar_result.get('error'))}")
        
        # Step 5: Check for error field (like admin route does)
        if avatar_result.get("error"):
            print(f"⚠️ Step 5: Avatar has error field: {avatar_result.get('error')}")
            avatar_name = f"Legacy Avatar {heygen_avatar_id[:8]}"
            avatar_image_url = f"https://files2.heygen.ai/avatar/v3/{heygen_avatar_id}/{heygen_avatar_id}.jpg"
        else:
            print(f"✅ Step 5: No error field - proceeding with normal flow")
            
            # Extract avatar details
            avatar_data = avatar_result.get("data", {})
            avatar_type = avatar_result.get("type", "unknown")
            
            # Generate avatar name
            heygen_name = avatar_data.get("name") or avatar_data.get("avatar_name")
            if heygen_name:
                avatar_name = heygen_name
            else:
                avatar_name = f"HeyGen Avatar {heygen_avatar_id[:8]}"
            
            # Get avatar image URL
            avatar_image_url = None
            if avatar_data.get("preview_image_url"):
                avatar_image_url = avatar_data["preview_image_url"]
            elif avatar_data.get("image_url"):
                avatar_image_url = avatar_data["image_url"]
            elif avatar_data.get("preview_image"):
                avatar_image_url = avatar_data["preview_image"]
            else:
                avatar_image_url = f"https://files2.heygen.ai/avatar/v3/{heygen_avatar_id}/{heygen_avatar_id}.jpg"
        
        print(f"✅ Step 6: Avatar details prepared:")
        print(f"   - Name: {avatar_name}")
        print(f"   - Image URL: {avatar_image_url}")
        
        # Step 7: Add avatar to database
        print(f"🔍 Step 7: Adding avatar to database...")
        
        result = execute_query(
            """
            INSERT INTO user_avatars (user_id, heygen_avatar_id, avatar_name, avatar_image_url, is_default, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            """,
            (user_id, heygen_avatar_id, avatar_name, avatar_image_url, False)
        )
        
        print(f"✅ Step 7: Database insert result: {result}")
        
        # Step 8: Verify insertion
        verify = execute_query(
            "SELECT id, avatar_name, avatar_image_url FROM user_avatars WHERE user_id = %s AND heygen_avatar_id = %s",
            (user_id, heygen_avatar_id)
        )
        
        if verify:
            print(f"✅ Step 8: SUCCESS! Avatar added to database:")
            print(f"   - Database ID: {verify[0]['id']}")
            print(f"   - Name: {verify[0]['avatar_name']}")
            print(f"   - Image URL: {verify[0]['avatar_image_url']}")
        else:
            print(f"❌ Step 8: FAILED! Avatar not found in database after insert")
            
    except Exception as e:
        print(f"💥 Exception during upload process: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_admin_upload_process()
