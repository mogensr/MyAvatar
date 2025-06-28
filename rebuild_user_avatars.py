#!/usr/bin/env python3
"""
Rebuild avatars for specific users
"""
import os
import sys
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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
    print("🔍 Starting HeyGen API call...")
    api_key = os.getenv("HEYGEN_API_KEY")
    if not api_key:
        print("❌ HEYGEN_API_KEY not found in environment variables")
        return []
    
    try:
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }
        
        print("🌐 Making API request to HeyGen...")
        response = requests.get(
            "https://api.heygen.com/v2/avatars",
            headers=headers,
            timeout=30
        )
        print(f"📊 API response status: {response.status_code}")
        
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
        print(f"🔑 API key found: {'Yes' if api_key else 'No'}")
        if not api_key:
            print("❌ HEYGEN_API_KEY not found in environment variables")
            return False
        
        # Get HeyGen avatars
        print("🔍 Fetching avatars from HeyGen API...")
        heygen_avatars = get_heygen_avatars()
        print(f"🎭 Found {len(heygen_avatars) if heygen_avatars else 0} avatars from HeyGen")
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
                raw_name = (
                    avatar.get("name") or 
                    avatar.get("display_name") or 
                    avatar.get("title") or 
                    avatar.get("avatar_name")
                )
                
                # Check if the name is just a technical ID (long hex string)
                if not raw_name or len(raw_name) > 20 or all(c in '0123456789abcdef-' for c in raw_name.lower()):
                    print(f"  🔍 Technical ID detected, getting detailed info for avatar {avatar_id}...")
                    
                    # Try to get detailed info first
                    details_result = get_avatar_details(api_key, avatar_id)
                    if details_result.get('success'):
                        details = details_result.get('details', {})
                        
                        # Generate better name based on avatar characteristics
                        avatar_type = details.get("type", "")
                        gender = details.get("gender", "")
                        
                        if avatar_type and gender:
                            avatar_name = f"{gender.title()} {avatar_type.title()} Avatar"
                        elif gender:
                            avatar_name = f"{gender.title()} Avatar"
                        elif avatar_type:
                            avatar_name = f"{avatar_type.title()} Avatar"
                        else:
                            # Use a more descriptive fallback
                            avatar_name = f"Professional Avatar {avatar_id[:8]}"
                        
                        print(f"    ✅ Generated name: {avatar_name}")
                    else:
                        print(f"    ❌ Could not get details: {details_result.get('error')}")
                        avatar_name = f"Professional Avatar {avatar_id[:8]}"
                else:
                    avatar_name = raw_name
                    print(f"  ✅ Using existing name: {avatar_name}")
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
