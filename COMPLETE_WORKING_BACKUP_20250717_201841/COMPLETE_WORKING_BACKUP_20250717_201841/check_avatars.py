#!/usr/bin/env python3
"""
Quick script to check avatar data in database
"""
import os
import sys
from dotenv import load_dotenv

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.db.database import execute_query

# Load environment variables
load_dotenv()

def check_avatars():
    """Check what avatars are in the database"""
    try:
        # Get all avatars
        avatars = execute_query(
            "SELECT id, user_id, avatar_id, name, image_path, is_default FROM user_avatars ORDER BY user_id, id", 
            fetch_all=True
        )
        
        if not avatars:
            print("❌ No avatars found in database")
            return
        
        print(f"📊 Found {len(avatars)} avatars in database:")
        print("-" * 80)
        
        for avatar in avatars:
            avatar_dict = dict(avatar) if hasattr(avatar, 'keys') else avatar
            print(f"ID: {avatar_dict.get('id')}")
            print(f"User ID: {avatar_dict.get('user_id')}")
            print(f"Avatar ID: {avatar_dict.get('avatar_id')}")
            print(f"Name: {avatar_dict.get('name')}")
            print(f"Image Path: {avatar_dict.get('image_path')}")
            print(f"Is Default: {avatar_dict.get('is_default')}")
            print("-" * 40)
            
    except Exception as e:
        print(f"❌ Error checking avatars: {e}")

def check_users():
    """Check users and their avatar assignments"""
    try:
        users = execute_query("SELECT id, username FROM users", fetch_all=True)
        
        if not users:
            print("❌ No users found")
            return
            
        print(f"\n👥 Found {len(users)} users:")
        print("-" * 50)
        
        for user in users:
            user_dict = dict(user) if hasattr(user, 'keys') else user
            print(f"User: {user_dict.get('username')} (ID: {user_dict.get('id')})")
            
            # Get user's avatars
            user_avatars = execute_query(
                "SELECT avatar_id, name, image_path FROM user_avatars WHERE user_id = ?",
                (user_dict.get('id'),),
                fetch_all=True
            )
            
            if user_avatars:
                print(f"Available avatars: {len(user_avatars)}")
                for ua in user_avatars:
                    ua_dict = dict(ua) if hasattr(ua, 'keys') else ua
                    print(f"  • {ua_dict.get('avatar_id')} - {ua_dict.get('name')}")
                    print(f"    Image: {ua_dict.get('image_path') or 'NO IMAGE'}")
            else:
                print("Available avatars: 0")
            print("-" * 30)
            
    except Exception as e:
        print(f"❌ Error checking users: {e}")

if __name__ == "__main__":
    print("🔍 MyAvatar Database Check")
    print("=" * 50)
    check_avatars()
    check_users()
