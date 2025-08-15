#!/usr/bin/env python3
"""
Debug script to check avatars table and user avatar data
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.user_manager import Database
from app.db.database import execute_query

def debug_avatars():
    print("🔍 Debugging Avatar Data")
    print("=" * 50)
    
    # Initialize database
    db = Database()
    
    # Check if avatars table exists
    try:
        result = execute_query("SELECT name FROM sqlite_master WHERE type='table' AND name='avatars'", fetch_all=True)
        if result:
            print("✅ Avatars table exists")
        else:
            print("❌ Avatars table does not exist!")
            return
    except Exception as e:
        print(f"❌ Error checking table existence: {e}")
        return
    
    # Check table structure
    try:
        result = execute_query("PRAGMA table_info(avatars)", fetch_all=True)
        print("\n📋 Avatars table structure:")
        for row in result:
            print(f"  - {row[1]} ({row[2]})")
    except Exception as e:
        print(f"❌ Error getting table structure: {e}")
    
    # Check total avatar count
    try:
        result = execute_query("SELECT COUNT(*) FROM avatars", fetch_one=True)
        total_avatars = result[0] if result else 0
        print(f"\n📊 Total avatars in database: {total_avatars}")
    except Exception as e:
        print(f"❌ Error counting avatars: {e}")
        return
    
    if total_avatars == 0:
        print("⚠️  No avatars found in database!")
        return
    
    # Check avatars by user
    try:
        result = execute_query("SELECT user_id, COUNT(*) FROM avatars GROUP BY user_id", fetch_all=True)
        print("\n👥 Avatars by user:")
        for row in result:
            user_id, count = row
            print(f"  - User {user_id}: {count} avatars")
    except Exception as e:
        print(f"❌ Error getting avatars by user: {e}")
    
    # Show sample avatar data
    try:
        result = execute_query("SELECT id, user_id, name, image_url, heygen_avatar_id FROM avatars LIMIT 5", fetch_all=True)
        print("\n🎭 Sample avatar data:")
        for row in result:
            print(f"  - ID: {row[0]}, User: {row[1]}, Name: {row[2]}, Image: {row[3][:50]}..., HeyGen: {row[4]}")
    except Exception as e:
        print(f"❌ Error getting sample data: {e}")
    
    # Test get_user_avatars function for user ID 1
    print("\n🧪 Testing get_user_avatars function for user ID 1:")
    try:
        avatars = db.get_user_avatars(1)
        print(f"  - Found {len(avatars)} avatars")
        for avatar in avatars[:3]:  # Show first 3
            print(f"    * {avatar.get('name', 'No name')}: {avatar.get('image_url', 'No image')[:50]}...")
    except Exception as e:
        print(f"❌ Error testing get_user_avatars: {e}")

if __name__ == "__main__":
    debug_avatars()
