#!/usr/bin/env python3
"""
Emergency Admin Password Reset Script for MyAvatar
=================================================
This script resets the admin password when you're locked out.
FIXED VERSION - Uses correct column name 'password_hash'
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.auth.authentication import get_password_hash
from app.db.database import execute_query

def reset_admin_password():
    """Reset admin password to default"""
    try:
        # Default admin credentials
        admin_email = "admin@myavatar.dk"
        admin_username = "admin"
        new_password = "Admin2025!"
        
        # Hash the new password
        hashed_password = get_password_hash(new_password)
        
        # Check if admin user exists by email
        admin_user = execute_query(
            "SELECT id, email, username FROM users WHERE LOWER(email) = LOWER(?)",
            (admin_email,),
            fetch_one=True
        )
        
        if admin_user:
            # Update existing admin password - FIXED: using password_hash column
            execute_query(
                "UPDATE users SET password_hash = ? WHERE LOWER(email) = LOWER(?)",
                (hashed_password, admin_email)
            )
            print(f"✅ Admin password reset successfully!")
            print(f"📧 Email: {admin_email}")
            print(f"👤 Username: {admin_user[2]}")
            print(f"🔑 Password: {new_password}")
        else:
            # Try to find admin by username
            admin_user = execute_query(
                "SELECT id, email, username FROM users WHERE username = ?",
                (admin_username,),
                fetch_one=True
            )
            
            if admin_user:
                # Update existing admin password - FIXED: using password_hash column
                execute_query(
                    "UPDATE users SET password_hash = ? WHERE username = ?",
                    (hashed_password, admin_username)
                )
                print(f"✅ Admin password reset successfully!")
                print(f"👤 Username: {admin_username}")
                print(f"📧 Email: {admin_user[1]}")
                print(f"🔑 Password: {new_password}")
            else:
                # Create new admin user - FIXED: using password_hash column
                execute_query(
                    """INSERT INTO users (username, email, password_hash, is_admin, created_at) 
                       VALUES (?, ?, ?, 1, datetime('now'))""",
                    (admin_username, admin_email, hashed_password)
                )
                print(f"✅ New admin user created!")
                print(f"👤 Username: {admin_username}")
                print(f"📧 Email: {admin_email}")
                print(f"🔑 Password: {new_password}")
        
        print("\n🚀 You can now login with these credentials!")
        
    except Exception as e:
        print(f"❌ Error resetting admin password: {e}")
        print("\nTrying to find existing admin users...")
        
        # Try to find any admin users
        try:
            admin_users = execute_query(
                "SELECT id, username, email FROM users WHERE is_admin = 1",
                fetch_all=True
            )
            
            if admin_users:
                print(f"\n📋 Found {len(admin_users)} admin user(s):")
                for user in admin_users:
                    user_id, username, email = user[0], user[1], user[2]
                    print(f"  - ID: {user_id}, Username: {username}, Email: {email}")
                
                # Reset password for the first admin user found
                first_admin = admin_users[0]
                admin_id, admin_username, admin_email = first_admin[0], first_admin[1], first_admin[2]
                
                hashed_password = get_password_hash(new_password)
                execute_query(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (hashed_password, admin_id)
                )
                print(f"\n✅ Reset password for admin user:")
                print(f"👤 Username: {admin_username}")
                print(f"📧 Email: {admin_email}")
                print(f"🔑 Password: {new_password}")
            else:
                print("❌ No admin users found in database")
                
        except Exception as inner_e:
            print(f"❌ Error finding admin users: {inner_e}")

def list_all_users():
    """List all users in the database for debugging"""
    try:
        users = execute_query(
            "SELECT id, username, email, is_admin FROM users ORDER BY id",
            fetch_all=True
        )
        
        print("\n📋 All users in database:")
        print("-" * 80)
        print(f"{'ID':<4} | {'Username':<15} | {'Email':<25} | {'Role':<10}")
        print("-" * 80)
        
        for user in users:
            user_id, username, email, is_admin = user[0], user[1], user[2], user[3]
            admin_status = "👑 ADMIN" if is_admin else "👤 USER"
            print(f"{user_id:<4} | {username:<15} | {email:<25} | {admin_status}")
        print("-" * 80)
        
    except Exception as e:
        print(f"❌ Error listing users: {e}")

def test_login():
    """Test login with the reset credentials"""
    try:
        from app.auth.authentication import authenticate_user
        
        print("\n🧪 Testing login with reset credentials...")
        
        # Try common admin usernames
        test_credentials = [
            ("admin", "Admin2025!"),
            ("admin", "admin123"),
        ]
        
        for username, password in test_credentials:
            print(f"Testing: {username} / {password}")
            result = authenticate_user(username, password)
            if result:
                print(f"✅ Login successful for {username}!")
                print(f"   User ID: {result.get('id')}")
                print(f"   Email: {result.get('email')}")
                print(f"   Admin: {result.get('is_admin')}")
                return True
            else:
                print(f"❌ Login failed for {username}")
        
        return False
        
    except Exception as e:
        print(f"❌ Error testing login: {e}")
        return False

if __name__ == "__main__":
    print("🔧 MyAvatar Admin Password Reset Tool")
    print("=" * 50)
    
    # List current users
    list_all_users()
    
    # Reset admin password
    reset_admin_password()
    
    # Test the login
    test_login()
    
    print("\n" + "=" * 50)
    print("🏁 Reset complete! Try logging in now.")
