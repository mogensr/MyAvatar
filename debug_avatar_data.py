#!/usr/bin/env python3
"""
Debug script to check what avatar data is actually being returned from the database
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.user_manager import Database

def debug_avatar_data():
    db = Database()
    
    # Test with a user ID - you'll need to replace this with an actual user ID
    user_id = 1  # Change this to your actual user ID
    
    print(f"🔍 Debugging avatar data for user_id: {user_id}")
    print("=" * 50)
    
    # Get avatars using the same method as the route
    avatars = db.get_user_avatars(user_id)
    
    print(f"📊 Raw avatars returned: {len(avatars) if avatars else 0}")
    print(f"📊 Avatars type: {type(avatars)}")
    
    if avatars:
        for i, avatar in enumerate(avatars):
            print(f"\n🎭 Avatar {i+1}:")
            print(f"   Type: {type(avatar)}")
            print(f"   Keys: {list(avatar.keys()) if isinstance(avatar, dict) else 'Not a dict'}")
            
            if isinstance(avatar, dict):
                print(f"   ID: {avatar.get('id')}")
                print(f"   Name: {avatar.get('name')}")
                print(f"   Avatar Name: {avatar.get('avatar_name')}")
                print(f"   Image URL: {avatar.get('image_url')}")
                print(f"   Avatar Image URL: {avatar.get('avatar_image_url')}")
                print(f"   HeyGen Avatar ID: {avatar.get('heygen_avatar_id')}")
                print(f"   Full data: {avatar}")
    else:
        print("❌ No avatars found!")
    
    print("\n" + "=" * 50)
    print("🔍 Now testing the route processing logic...")
    
    # Simulate the route processing
    user_avatars = []
    if avatars:
        for avatar in avatars:
            if isinstance(avatar, dict):
                avatar_image = avatar.get('avatar_image_url', '')
                avatar_name = avatar.get('avatar_name', 'Unnamed Avatar')
                
                print(f"🖼️ Processing Avatar {avatar_name}:")
                print(f"   Image URL: {avatar_image}")
                print(f"   Image URL length: {len(avatar_image) if avatar_image else 0}")
                print(f"   Image URL starts with http: {avatar_image.startswith('http') if avatar_image else False}")
                
                processed_avatar = {
                    'id': avatar.get('id'),
                    'name': avatar_name,
                    'image_path': avatar_image,
                    'heygen_avatar_id': avatar.get('heygen_avatar_id', ''),
                    'avatar_id': avatar.get('heygen_avatar_id', '')
                }
                user_avatars.append(processed_avatar)
                print(f"   Processed: {processed_avatar}")
    
    print(f"\n📋 Final processed avatars: {len(user_avatars)}")
    for avatar in user_avatars:
        print(f"   - {avatar['name']}: {avatar['image_path'][:50] if avatar['image_path'] else 'NO IMAGE'}...")

if __name__ == "__main__":
    debug_avatar_data()
