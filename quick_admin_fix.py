#!/usr/bin/env python3
"""
🚀 QUICK ADMIN FIX - MyAvatar Password Recovery
==============================================
Simple, direct admin password reset for immediate access recovery.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.auth.authentication import get_password_hash
from app.db.database import execute_query

def quick_admin_fix():
    """Quick and dirty admin password reset"""
    print("🚀 MyAvatar Quick Admin Fix")
    print("=" * 40)
    
    # New admin credentials
    new_password = "Admin2025!"
    admin_email = "admin@myavatar.dk"
    
    try:
        # Hash password
        hashed_password = get_password_hash(new_password)
        print("✅ Password hashed successfully")
        
        # List current users first
        print("\n📋 Current users:")
        users = execute_query("SELECT id, username, email, is_admin FROM users", fetch_all=True)
        
        if users:
            for user in users:
                admin_status = "👑 ADMIN" if user[3] else "👤 USER"
                print(f"  {user[0]}: {user[1]} ({user[2]}) - {admin_status}")
        else:
            print("  No users found!")
        
        # Try to find and update existing admin
        admin_found = False
        
        # Check for admin by email
        admin = execute_query(
            "SELECT id, username FROM users WHERE email = ?", 
            (admin_email,), 
            fetch_one=True
        )
        
        if admin:
            execute_query(
                "UPDATE users SET password = ?, is_admin = 1 WHERE email = ?",
                (hashed_password, admin_email)
            )
            print(f"✅ Updated existing admin: {admin[1]} ({admin_email})")
            admin_found = True
        
        # Check for admin by username
        if not admin_found:
            admin = execute_query(
                "SELECT id, email FROM users WHERE username = ?", 
                ("admin",), 
                fetch_one=True
            )
            
            if admin:
                execute_query(
                    "UPDATE users SET password = ?, is_admin = 1 WHERE username = ?",
                    (hashed_password, "admin")
                )
                print(f"✅ Updated existing admin: admin ({admin[1]})")
                admin_found = True
        
        # Create new admin if none found
        if not admin_found:
            execute_query(
                "INSERT INTO users (username, email, password, is_admin) VALUES (?, ?, ?, 1)",
                ("admin", admin_email, hashed_password)
            )
            print(f"✅ Created new admin user: admin ({admin_email})")
        
        # Ensure at least one admin exists
        execute_query(
            "UPDATE users SET is_admin = 1 WHERE id = (SELECT MIN(id) FROM users)"
        )
        
        print("\n🎉 SUCCESS! Admin access restored!")
        print(f"📧 Email/Username: admin or {admin_email}")
        print(f"🔑 Password: {new_password}")
        print("\n🚀 You can now login to your MyAvatar application!")
        
        # Show updated user list
        print("\n📋 Updated users:")
        users = execute_query("SELECT id, username, email, is_admin FROM users", fetch_all=True)
        for user in users:
            admin_status = "👑 ADMIN" if user[3] else "👤 USER"
            print(f"  {user[0]}: {user[1]} ({user[2]}) - {admin_status}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("💡 Try running the full emergency_admin_recovery.py script instead")

if __name__ == "__main__":
    quick_admin_fix()
