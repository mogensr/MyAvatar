#!/usr/bin/env python3
"""
Debug script to check avatar data for text-to-video page
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.user_manager import Database

def debug_avatars():
    """Debug avatar data"""
    try:
        db = Database()
        print("🔍 Debugging Avatar Data for Text-to-Video")
        print("=" * 50)
        
        # Get all users first
        users = db.get_all_users()
        print(f"📊 Found {len(users) if users else 0} users")
        
        if users:
            for user in users[:3]:  # Check first 3 users
                user_id = user.get('id')
                username = user.get('username', 'Unknown')
                print(f"\n👤 User: {username} (ID: {user_id})")
                
                # Get avatars for this user
                avatars = db.get_user_avatars(user_id)
                print(f"🎭 Raw avatars from DB: {avatars}")
                
                if avatars:
                    for i, avatar in enumerate(avatars):
                        print(f"   Avatar {i+1}:")
                        print(f"     - ID: {avatar.get('id')}")
                        print(f"     - Name: {avatar.get('avatar_name')}")
                        print(f"     - HeyGen ID: {avatar.get('heygen_avatar_id')}")
                        print(f"     - Image URL: {avatar.get('avatar_image_url')}")
                        print(f"     - Full data: {avatar}")
                else:
                    print("   ❌ No avatars found for this user")
                    
        print("\n" + "=" * 50)
        print("✅ Debug complete")
        
    except Exception as e:
        print(f"❌ Error debugging avatars: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_avatars()
