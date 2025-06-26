#!/usr/bin/env python3
"""
Test the exact avatar query that should be working
"""
import sys
import os

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from db.database import execute_query
from logger.log_handler import log_info, log_error

def test_avatar_query():
    """Test the avatar query directly"""
    print("🧪 Testing avatar query...")
    
    try:
        # Test the exact query from get_user_avatars
        result = execute_query(
            """SELECT id, avatar_name as name, avatar_image_url as image_url, 
                      avatar_id as heygen_avatar_id, created_at 
               FROM user_avatars 
               WHERE user_id = ? 
               ORDER BY created_at DESC""", 
            (1,),  # Test with user ID 1
            fetch_all=True
        )
        
        print(f"✅ Query executed successfully")
        print(f"📊 Found {len(result) if result else 0} results")
        
        if result:
            print("\n🎭 Avatar data:")
            for i, row in enumerate(result):
                print(f"  {i+1}. {dict(row) if hasattr(row, 'keys') else row}")
        else:
            print("❌ No avatars found for user ID 1")
            
            # Let's check if there are any avatars at all
            all_avatars = execute_query("SELECT COUNT(*) as total FROM user_avatars", fetch_one=True)
            print(f"📈 Total avatars in database: {all_avatars[0] if all_avatars else 0}")
            
            # Check what user IDs exist
            users = execute_query("SELECT DISTINCT user_id FROM user_avatars LIMIT 5", fetch_all=True)
            if users:
                print(f"👥 User IDs with avatars: {[u[0] for u in users]}")
            
    except Exception as e:
        print(f"❌ Error executing query: {e}")
        log_error(f"Avatar query test failed: {e}", "Test")

def test_user_manager():
    """Test the UserManager get_user_avatars function"""
    print("\n🧪 Testing UserManager.get_user_avatars...")
    
    try:
        from db.user_manager import Database
        db = Database()
        
        # Test with user ID 1
        avatars = db.get_user_avatars(1)
        print(f"✅ UserManager query executed successfully")
        print(f"📊 Found {len(avatars)} avatars")
        
        if avatars:
            print("\n🎭 Avatar data from UserManager:")
            for i, avatar in enumerate(avatars):
                print(f"  {i+1}. {avatar}")
        else:
            print("❌ No avatars returned from UserManager")
            
    except Exception as e:
        print(f"❌ Error testing UserManager: {e}")
        log_error(f"UserManager test failed: {e}", "Test")

if __name__ == "__main__":
    print("🔍 Avatar Query Test")
    print("=" * 40)
    
    test_avatar_query()
    test_user_manager()
    
    print("\n✅ Test completed")
