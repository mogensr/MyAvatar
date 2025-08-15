#!/usr/bin/env python3
"""
Script to repopulate missing avatars for users
"""
import os
import sys
from dotenv import load_dotenv

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.db.database import execute_query
from app.api.heygen import get_available_avatars
from app.logger.log_handler import log_info, log_error

# Load environment variables
load_dotenv()

def get_heygen_avatars():
    """Get available avatars from HeyGen API"""
    api_key = os.getenv("HEYGEN_API_KEY")
    if not api_key:
        print("❌ No HeyGen API key found")
        return []
    
    print("🔍 Fetching avatars from HeyGen...")
    result = get_available_avatars(api_key)
    
    if result.get("success"):
        avatars = result.get("avatars", [])
        print(f"✅ Found {len(avatars)} avatars from HeyGen")
        return avatars
    else:
        print(f"❌ Failed to get avatars: {result.get('error')}")
        return []

def get_users():
    """Get all users from database"""
    try:
        users = execute_query("SELECT id, username FROM users", fetch_all=True)
        return [dict(user) if hasattr(user, 'keys') else user for user in users] if users else []
    except Exception as e:
        print(f"❌ Error getting users: {e}")
        return []

def get_user_avatars(user_id):
    """Get avatars for a specific user"""
    try:
        avatars = execute_query(
            "SELECT * FROM user_avatars WHERE user_id = ?", 
            (user_id,), 
            fetch_all=True
        )
        return [dict(avatar) if hasattr(avatar, 'keys') else avatar for avatar in avatars] if avatars else []
    except Exception as e:
        print(f"❌ Error getting avatars for user {user_id}: {e}")
        return []

def add_avatar_to_user(user_id, avatar_id, avatar_name, image_path=None):
    """Add an avatar to a user"""
    try:
        # Check if avatar already exists
        existing = execute_query(
            "SELECT id FROM user_avatars WHERE user_id = ? AND avatar_id = ?",
            (user_id, avatar_id),
            fetch_one=True
        )
        
        if existing:
            print(f"   ⚠️  Avatar {avatar_id} already exists for user {user_id}")
            return False
        
        # Insert new avatar
        execute_query(
            """INSERT INTO user_avatars (user_id, avatar_id, name, image_path, is_default, created_at) 
               VALUES (?, ?, ?, ?, 0, datetime('now'))""",
            (user_id, avatar_id, avatar_name, image_path)
        )
        print(f"   ✅ Added avatar {avatar_id} ({avatar_name}) to user {user_id}")
        return True
    except Exception as e:
        print(f"   ❌ Error adding avatar {avatar_id} to user {user_id}: {e}")
        return False

def main():
    print("🚀 MyAvatar - Avatar Repopulation Script")
    print("=" * 50)
    
    # Get HeyGen avatars
    heygen_avatars = get_heygen_avatars()
    if not heygen_avatars:
        print("❌ No avatars available from HeyGen. Exiting.")
        return
    
    # Get users
    users = get_users()
    if not users:
        print("❌ No users found. Exiting.")
        return
    
    print(f"\n📊 Found {len(users)} users")
    
    # Show some popular avatars
    popular_avatars = [
        "Abigail_expressive_2024112501",  # Adrian in blue suit equivalent
        "Adrian_expressive_2024112501",
        "Anna_expressive_2024112501",
        "Eric_expressive_2024112501",
        "Josh_expressive_2024112501"
    ]
    
    print("\n🎭 Available popular avatars:")
    for avatar in heygen_avatars[:10]:  # Show first 10
        avatar_id = avatar.get('id', avatar.get('avatar_id', 'unknown'))
        avatar_name = avatar.get('name', avatar.get('display_name', 'Unknown'))
        print(f"   • {avatar_id} - {avatar_name}")
    
    print(f"\n👥 Processing users:")
    for user in users:
        user_id = user['id']
        username = user['username']
        
        print(f"\n👤 User: {username} (ID: {user_id})")
        
        # Check current avatars
        current_avatars = get_user_avatars(user_id)
        print(f"   📋 Current avatars: {len(current_avatars)}")
        
        if current_avatars:
            for avatar in current_avatars:
                print(f"      • {avatar.get('avatar_id', 'unknown')} - {avatar.get('name', 'Unknown')}")
        
        # Add some default avatars if user has none
        if len(current_avatars) == 0:
            print(f"   🔧 Adding default avatars for {username}...")
            
            # Add a few popular avatars
            for avatar_data in heygen_avatars[:3]:  # Add first 3 avatars
                avatar_id = avatar_data.get('id', avatar_data.get('avatar_id'))
                avatar_name = avatar_data.get('name', avatar_data.get('display_name', 'Avatar'))
                image_path = avatar_data.get('preview_image_url', avatar_data.get('image_url'))
                
                if avatar_id:
                    add_avatar_to_user(user_id, avatar_id, avatar_name, image_path)
    
    print("\n✅ Avatar repopulation complete!")
    print("\n💡 To add specific avatars manually, use the admin interface or modify this script.")

if __name__ == "__main__":
    main()
