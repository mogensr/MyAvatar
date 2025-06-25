#!/usr/bin/env python3
"""
List all users in the database
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

def list_all_users():
    """List all users in the database"""
    print("👥 All Users in Database")
    print("=" * 50)
    
    try:
        users = execute_query(
            "SELECT id, username, email, is_admin, created_at FROM users ORDER BY id",
            fetch_all=True
        )
        
        if not users:
            print("❌ No users found in database")
            return
        
        print(f"📊 Found {len(users)} users:")
        print()
        
        for user in users:
            user_dict = dict(user) if hasattr(user, 'keys') else {
                'id': user[0],
                'username': user[1], 
                'email': user[2],
                'is_admin': user[3],
                'created_at': user[4]
            }
            
            admin_status = "👑 Admin" if user_dict['is_admin'] else "👤 User"
            print(f"ID: {user_dict['id']}")
            print(f"   Username: {user_dict['username']}")
            print(f"   Email: {user_dict['email']}")
            print(f"   Status: {admin_status}")
            print(f"   Created: {user_dict['created_at']}")
            print()
            
    except Exception as e:
        print(f"❌ Error listing users: {e}")

if __name__ == "__main__":
    list_all_users()
