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
    from api.heygen import get_available_avatars, get_avatar_details
except ImportError:
    # Fallback imports
    try:
        from app.db.user_manager import Database
        from app.logger.log_handler import log_info, log_error
        from app.api.heygen import get_available_avatars, get_avatar_details
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

def rebuild_avatars_for_user_id(user_id: int, db: Database):
    """Rebuild avatars for a specific user by ID"""
    print(f"\n🔄 Rebuilding avatars for user ID: {user_id}")
    
    # Get user info
    try:
        user = db.get_user_by_id(user_id)
        if not user:
            print(f"❌ User with ID '{user_id}' not found")
            return False
        
        username = user.get('username', f'User_{user_id}')
        print(f"📋 Found user: {username} (ID: {user_id})")
        
        # Get HeyGen API key
        api_key = os.getenv("HEYGEN_API_KEY")
        if not api_key:
            print("❌ HEYGEN_API_KEY not found in environment variables")
            return False
        
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
                # Try multiple possible name fields from HeyGen API
                avatar_name = (
                    avatar.get("name") or 
                    avatar.get("display_name") or 
                    avatar.get("title") or 
                    avatar.get("avatar_name")
                )
                
                # If no proper name found, try to get detailed info
                if not avatar_name or avatar_name.startswith('Avatar '):
                    print(f"  🔍 Getting detailed info for avatar {avatar_id}...")
                    details_result = get_avatar_details(api_key, avatar_id)
                    if details_result.get('success'):
                        details = details_result.get('details', {})
                        avatar_name = (
                            details.get("name") or 
                            details.get("display_name") or 
                            details.get("title") or
                            details.get("avatar_name")
                        )
                        print(f"    ✅ Found name: {avatar_name}")
                    else:
                        print(f"    ❌ Could not get details: {details_result.get('error')}")
                
                # Final fallback to a readable name
                if not avatar_name or avatar_name.startswith('Avatar '):
                    if avatar_id:
                        # Create a more readable name from avatar_id
                        clean_id = avatar_id.replace('_', ' ').replace('-', ' ')
                        clean_id = ' '.join(word.capitalize() for word in clean_id.split())
                        avatar_name = f"Avatar {clean_id[:20]}"  # Limit length
                    else:
                        avatar_name = "Unknown Avatar"
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
    
    # Target user IDs - using exact IDs from PostgreSQL
    target_user_ids = [3]  # MogensR has ID 3
    
    print(f"🎯 Target user IDs: {target_user_ids}")
    
    # Rebuild avatars for each user
    success_count = 0
    for user_id in target_user_ids:
        if rebuild_avatars_for_user_id(user_id, db):
            success_count += 1
    
    print(f"\n📁 Summary:")
    print(f"   Total users: {len(target_user_ids)}")
    print(f"   Successful: {success_count}")
    print(f"   Failed: {len(target_user_ids) - success_count}")
    
    if success_count == len(target_user_ids):
        print("🎉 All users' avatars rebuilt successfully!")
    else:
        print("⚠️ Some users had issues - check the logs above")

if __name__ == "__main__":
    main()
