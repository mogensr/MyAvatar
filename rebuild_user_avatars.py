#!/usr/bin/env python3
"""
Rebuild avatars for specific users
"""
import os
import sys
import requests
from datetime import datetime

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

try:
    from db.user_manager import Database
    from logger.log_handler import log_info, log_error
except ImportError:
    # Fallback imports
    try:
        from app.db.user_manager import Database
        from app.logger.log_handler import log_info, log_error
    except ImportError:
        print("❌ Could not import required modules")
        sys.exit(1)

def get_heygen_avatars():
    """Fetch available avatars from HeyGen API"""
    api_key = os.getenv("HEYGEN_API_KEY")
    if not api_key:
        print("❌ HEYGEN_API_KEY not found in environment variables")
        return []
    
    try:
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            "https://api.heygen.com/v2/avatars",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            avatars = data.get("data", {}).get("avatars", [])
            print(f"✅ Found {len(avatars)} avatars from HeyGen API")
            return avatars
        else:
            print(f"❌ HeyGen API error: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        print(f"❌ Error fetching avatars from HeyGen: {e}")
        return []

def rebuild_avatars_for_user(username: str, db: Database):
    """Rebuild avatars for a specific user"""
    print(f"\n🔄 Rebuilding avatars for user: {username}")
    
    # Get user ID
    try:
        user = db.get_user_by_username(username)
        if not user:
            print(f"❌ User '{username}' not found")
            return False
        
        user_id = user['id']
        print(f"📋 Found user ID: {user_id}")
        
        # Get HeyGen avatars
        heygen_avatars = get_heygen_avatars()
        if not heygen_avatars:
            print("❌ No avatars available from HeyGen API")
            return False
        
        # Clear existing avatars for this user
        try:
            from db.database import execute_query
            execute_query(
                "DELETE FROM user_avatars WHERE user_id = ?",
                (user_id,)
            )
            print(f"🗑️ Cleared existing avatars for {username}")
        except Exception as e:
            print(f"⚠️ Warning: Could not clear existing avatars: {e}")
        
        # Add new avatars
        added_count = 0
        for avatar in heygen_avatars:
            try:
                avatar_id = avatar.get("avatar_id")
                avatar_name = avatar.get("name", f"Avatar {avatar_id}")
                preview_url = avatar.get("preview_image_url") or avatar.get("preview_video_url")
                
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
        print(f"❌ Error rebuilding avatars for {username}: {e}")
        return False

def main():
    print("🔄 Avatar Rebuild Tool")
    print("=" * 50)
    
    # Initialize database
    try:
        db = Database()
        print("✅ Database connection established")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return
    
    # Target users
    target_users = ["MogensR", "Lars-Christian"]
    
    print(f"🎯 Target users: {', '.join(target_users)}")
    
    # Rebuild avatars for each user
    success_count = 0
    for username in target_users:
        if rebuild_avatars_for_user(username, db):
            success_count += 1
    
    print(f"\n📊 Summary:")
    print(f"   Total users: {len(target_users)}")
    print(f"   Successful: {success_count}")
    print(f"   Failed: {len(target_users) - success_count}")
    
    if success_count == len(target_users):
        print("🎉 All users' avatars rebuilt successfully!")
    else:
        print("⚠️ Some users had issues - check the logs above")

if __name__ == "__main__":
    main()
