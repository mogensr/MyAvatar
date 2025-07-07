#!/usr/bin/env python3
"""
Test database connection and avatar data
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add app to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

def test_database():
    """Test database connection and avatar data"""
    print("=== DATABASE CONNECTION TEST ===")
    
    try:
        from app.db.database import execute_query
        
        # Test basic connection
        result = execute_query("SELECT 1 as test", fetch_one=True)
        if result:
            print("✅ Database connection successful")
        else:
            print("❌ Database connection failed")
            return False
            
        # Test users table
        users = execute_query("SELECT COUNT(*) as count FROM users", fetch_one=True)
        print(f"✅ Users table: {users['count']} users found")
        
        # Test user_avatars table
        avatars = execute_query("SELECT COUNT(*) as count FROM user_avatars", fetch_one=True)
        print(f"✅ User avatars table: {avatars['count']} avatars found")
        
        # Get sample avatar data
        sample_avatars = execute_query("""
            SELECT ua.id, ua.user_id, ua.avatar_id, ua.avatar_name, ua.avatar_image_url,
                   u.username
            FROM user_avatars ua
            JOIN users u ON ua.user_id = u.id
            ORDER BY ua.created_at DESC
            LIMIT 5
        """, fetch_all=True)
        
        if sample_avatars:
            print(f"\n=== SAMPLE AVATAR DATA ===")
            for avatar in sample_avatars:
                print(f"\nAvatar ID: {avatar['id']}")
                print(f"User: {avatar['username']}")
                print(f"Avatar Name: {avatar['avatar_name']}")
                print(f"HeyGen ID: {avatar['avatar_id']}")
                print(f"Image URL: {avatar['avatar_image_url']}")
                
                # Check URL format
                url = avatar['avatar_image_url']
                if url:
                    if url.endswith('.jpg') or url.endswith('.png'):
                        print("✅ URL format looks correct")
                    else:
                        print("⚠️  URL might be incomplete")
                else:
                    print("❌ No image URL")
        else:
            print("❌ No avatar data found")
            
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def test_admin_users():
    """Test admin user status"""
    print("\n=== ADMIN USERS TEST ===")
    
    try:
        from app.db.database import execute_query
        
        admin_users = execute_query("""
            SELECT id, username, email, is_admin, created_at, last_login
            FROM users 
            WHERE is_admin = 1
            ORDER BY created_at
        """, fetch_all=True)
        
        if admin_users:
            print(f"✅ Found {len(admin_users)} admin users:")
            for admin in admin_users:
                print(f"  - {admin['username']} ({admin['email']}) - Last login: {admin['last_login']}")
        else:
            print("❌ No admin users found!")
            
        return len(admin_users) > 0
        
    except Exception as e:
        print(f"❌ Admin users check error: {e}")
        return False

if __name__ == "__main__":
    db_ok = test_database()
    admin_ok = test_admin_users()
    
    print(f"\n=== SUMMARY ===")
    print(f"Database Connection: {'✅' if db_ok else '❌'}")
    print(f"Admin Users Found: {'✅' if admin_ok else '❌'}")
