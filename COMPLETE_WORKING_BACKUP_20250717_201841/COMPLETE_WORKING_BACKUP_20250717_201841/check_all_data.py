#!/usr/bin/env python3
"""
Check all data in the database
"""
import os
import sys

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

def check_all_data():
    """Check all data in the database"""
    print("🔍 Database Content Check")
    print("=" * 50)
    
    # Check users
    print("\n👥 USERS:")
    try:
        users = execute_query("SELECT * FROM users", fetch_all=True)
        for i, user in enumerate(users):
            print(f"User {i+1}: {dict(user) if hasattr(user, 'keys') else user}")
    except Exception as e:
        print(f"❌ Error checking users: {e}")
    
    # Check user_avatars
    print("\n🎭 USER_AVATARS:")
    try:
        avatars = execute_query("SELECT * FROM user_avatars", fetch_all=True)
        for i, avatar in enumerate(avatars):
            print(f"Avatar {i+1}: {dict(avatar) if hasattr(avatar, 'keys') else avatar}")
    except Exception as e:
        print(f"❌ Error checking avatars: {e}")

if __name__ == "__main__":
    check_all_data()
