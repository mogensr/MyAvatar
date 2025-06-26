#!/usr/bin/env python3
"""
Check current user avatars
"""
from app.db.database import execute_query

def check_user_avatars():
    try:
        # Get avatars for user ID 3 (MogensR)
        avatars = execute_query(
            "SELECT * FROM user_avatars WHERE user_id = 3", 
            fetch_all=True
        )
        
        print("🔍 Current avatars for user MogensR (ID: 3):")
        print("-" * 60)
        
        if avatars:
            for i, avatar in enumerate(avatars, 1):
                print(f"Avatar {i}:")
                print(f"  Raw data: {avatar}")
                
                # Handle both dict and tuple/list formats
                if isinstance(avatar, dict):
                    print(f"  ID: {avatar.get('avatar_id', 'N/A')}")
                    print(f"  Name: {avatar.get('avatar_name', 'N/A')}")
                    print(f"  Image URL: {avatar.get('avatar_image_url', 'N/A')}")
                    print(f"  Is Default: {avatar.get('is_default', 'N/A')}")
                else:
                    # Assume it's a tuple/list
                    print(f"  Data: {list(avatar) if hasattr(avatar, '__iter__') else avatar}")
                print()
        else:
            print("❌ No avatars found for this user")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_user_avatars()
