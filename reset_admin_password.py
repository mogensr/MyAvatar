#!/usr/bin/env python3
"""
Emergency Admin Password Reset Script for MyAvatar
=================================================
This script resets the admin password when you're locked out.
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
        new_password = "Admin2025!"
        
        # Hash the new password
        hashed_password = get_password_hash(new_password)
        
        # Check if admin user exists
        admin_user = execute_query(
            "SELECT id, email FROM users WHERE LOWER(email) = LOWER(?)",
            (admin_email,),
            fetch_one=True
        )
        
        if admin_user:
            # Update existing admin password
            execute_query(
                "UPDATE users SET password = ? WHERE LOWER(email) = LOWER(?)",
                (hashed_password, admin_email)
            )
            print(f"✅ Admin password reset successfully!")
            print(f"📧 Email: {admin_email}")
            print(f"🔑 Password: {new_password}")
        else:
            # Create new admin user
            execute_query(
                """INSERT INTO users (username, email, password, is_admin, created_at) 
                   VALUES (?, ?, ?, 1, datetime('now'))""",
                ("admin", admin_email, hashed_password)
            )
            print(f"✅ New admin user created!")
            print(f"📧 Email: {admin_email}")
            print(f"🔑 Password: {new_password}")
        
        print("\n🚀 You can now login with these credentials!")
        
    except Exception as e:
        print(f"❌ Error resetting admin password: {e}")
        print("\nTrying alternative admin emails...")
        
        # Try common admin emails
        alternative_emails = [
            "admin@example.com",
            "admin@localhost",
            "admin@myavatar.com"
        ]
        
        for email in alternative_emails:
            try:
                admin_user = execute_query(
                    "SELECT id, email FROM users WHERE LOWER(email) = LOWER(?)",
                    (email,),
                    fetch_one=True
                )
                
                if admin_user:
                    hashed_password = get_password_hash(new_password)
                    execute_query(
                        "UPDATE users SET password = ? WHERE LOWER(email) = LOWER(?)",
                        (hashed_password, email)
                    )
                    print(f"✅ Found and reset password for: {email}")
                    print(f"🔑 New password: {new_password}")
                    return
            except:
                continue
        
        print("❌ Could not find any admin users to reset")

def list_all_users():
    """List all users in the database for debugging"""
    try:
        users = execute_query(
            "SELECT id, username, email, is_admin FROM users ORDER BY id",
            fetch_all=True
        )
        
        print("\n📋 All users in database:")
        print("-" * 60)
        for user in users:
            admin_status = "👑 ADMIN" if user[3] else "👤 USER"
            print(f"ID: {user[0]} | {user[1]} | {user[2]} | {admin_status}")
        print("-" * 60)
        
    except Exception as e:
        print(f"❌ Error listing users: {e}")

if __name__ == "__main__":
    print("🔧 MyAvatar Admin Password Reset Tool")
    print("=" * 40)
    
    # List current users
    list_all_users()
    
    # Reset admin password
    reset_admin_password()
