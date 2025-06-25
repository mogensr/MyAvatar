#!/usr/bin/env python3
"""
Populate default avatars for specific users (for testing/fallback)
"""
import os
import sys
from datetime import datetime

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

try:
    from db.database import execute_query
except ImportError:
    try:
        from app.db.database import execute_query
    except ImportError:
        print("❌ Could not import database module")
        sys.exit(1)

def get_default_avatars():
    """Get some default avatars for testing"""
    return [
        {
            "avatar_id": "josh_lite_20230714",
            "name": "Josh in Casual",
            "preview_image_url": "https://resource.heygen.ai/avatar/josh_lite_20230714.jpg"
        },
        {
            "avatar_id": "anna_costume1_canny",
            "name": "Anna in Business Suit",
            "preview_image_url": "https://resource.heygen.ai/avatar/anna_costume1_canny.jpg"
        },
        {
            "avatar_id": "tyler_front_20230714",
            "name": "Tyler Professional",
            "preview_image_url": "https://resource.heygen.ai/avatar/tyler_front_20230714.jpg"
        },
        {
            "avatar_id": "susan_costume1_canny",
            "name": "Susan in Blue Dress",
            "preview_image_url": "https://resource.heygen.ai/avatar/susan_costume1_canny.jpg"
        },
        {
            "avatar_id": "monica_costume1_canny",
            "name": "Monica Professional",
            "preview_image_url": "https://resource.heygen.ai/avatar/monica_costume1_canny.jpg"
        }
    ]

def populate_avatars_for_user_id(user_id: int, username: str):
    """Populate avatars for a specific user ID"""
    print(f"\n🔄 Populating avatars for user: {username} (ID: {user_id})")
    
    try:
        # Get default avatars
        avatars = get_default_avatars()
        print(f"📋 Using {len(avatars)} default avatars")
        
        # Clear existing avatars for this user
        try:
            execute_query(
                "DELETE FROM user_avatars WHERE user_id = ?",
                (user_id,)
            )
            print(f"🗑️ Cleared existing avatars for {username}")
        except Exception as e:
            print(f"⚠️ Warning: Could not clear existing avatars: {e}")
        
        # Add new avatars
        added_count = 0
        for avatar in avatars:
            try:
                avatar_id = avatar.get("avatar_id")
                avatar_name = avatar.get("name", f"Avatar {avatar_id}")
                preview_url = avatar.get("preview_image_url")
                
                if not avatar_id:
                    continue
                
                # Insert avatar
                execute_query(
                    """INSERT INTO user_avatars 
                       (user_id, avatar_id, avatar_name, avatar_image_url, is_default, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (user_id, avatar_id, avatar_name, preview_url, 0, datetime.now())
                )
                added_count += 1
                print(f"✅ Added avatar: {avatar_name} ({avatar_id})")
                
            except Exception as e:
                print(f"❌ Error adding avatar {avatar.get('avatar_id', 'unknown')}: {e}")
        
        print(f"🎉 Successfully added {added_count} avatars for {username}")
        return True
        
    except Exception as e:
        print(f"❌ Error populating avatars for {username}: {e}")
        return False

def main():
    print("🔄 Avatar Population Tool - Default Avatars")
    print("=" * 50)
    
    # Target users with their IDs (from the database screenshot)
    target_users = [
        {"id": 3, "username": "MogensR"},
        {"id": 4, "username": "Lars-Christian"}
    ]
    
    print(f"🎯 Target users: {', '.join([u['username'] for u in target_users])}")
    
    # Populate avatars for each user
    success_count = 0
    for user in target_users:
        if populate_avatars_for_user_id(user["id"], user["username"]):
            success_count += 1
    
    print(f"\n📊 Summary:")
    print(f"   Total users: {len(target_users)}")
    print(f"   Successful: {success_count}")
    print(f"   Failed: {len(target_users) - success_count}")
    
    if success_count == len(target_users):
        print("🎉 All users' avatars populated successfully!")
        print("\n💡 Note: These are default avatars. For full HeyGen avatar list,")
        print("   run the rebuild script on Railway where HEYGEN_API_KEY is available.")
    else:
        print("⚠️ Some users had issues - check the logs above")

if __name__ == "__main__":
    main()
