#!/usr/bin/env python3
"""
🚂 Fixed Production Password Reset
=================================
Reset admin password with proper PostgreSQL syntax
"""

import sys
import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def fixed_reset():
    """Fixed reset with proper PostgreSQL syntax"""
    
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("❌ DATABASE_URL not found in .env file")
        return False
    
    # Convert postgres:// to postgresql:// if needed
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    print("🚂 Connecting to Railway PostgreSQL...")
    
    try:
        # Connect to database
        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        cursor = conn.cursor()
        
        print("✅ Connected to production database")
        
        # Import password hashing
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from app.auth.authentication import get_password_hash
        
        # Reset admin password
        new_password = "Admin2025!"
        hashed_password = get_password_hash(new_password)
        
        print("🔧 Checking current users...")
        
        # First, let's see what users exist
        cursor.execute("SELECT id, username, email, is_admin FROM users ORDER BY id")
        users = cursor.fetchall()
        
        print(f"Found {len(users)} users:")
        for user in users:
            admin_status = "👑 ADMIN" if user[3] else "👤 USER"
            print(f"  ID {user[0]}: {user[1]} ({user[2]}) - {admin_status}")
        
        print("\n🔧 Resetting admin password...")
        
        # Update admin users with proper casting
        cursor.execute(
            "UPDATE users SET password = %s WHERE username = %s",
            (hashed_password, "admin")
        )
        
        admin_updated = cursor.rowcount
        print(f"Updated {admin_updated} admin user(s) by username")
        
        # Also update by email pattern
        cursor.execute(
            "UPDATE users SET password = %s WHERE email ILIKE %s",
            (hashed_password, "%admin%")
        )
        
        email_updated = cursor.rowcount
        print(f"Updated {email_updated} user(s) by admin email pattern")
        
        # Ensure admin privileges - use CAST for boolean
        cursor.execute(
            "UPDATE users SET is_admin = CAST(1 AS BOOLEAN) WHERE username = %s OR email ILIKE %s",
            ("admin", "%admin%")
        )
        
        # If no admin found, promote first user
        if admin_updated == 0 and email_updated == 0:
            print("No admin users found, promoting first user...")
            cursor.execute(
                "UPDATE users SET password = %s, is_admin = CAST(1 AS BOOLEAN) WHERE id = (SELECT MIN(id) FROM users)",
                (hashed_password,)
            )
            print("✅ Promoted first user to admin with new password")
        
        print("\n🎉 PRODUCTION PASSWORD RESET COMPLETE!")
        print(f"🔑 Password: {new_password}")
        print("🚀 Try logging in at: https://app.myavatar.dk")
        
        # Show updated admin users
        cursor.execute("SELECT id, username, email, is_admin FROM users WHERE is_admin = CAST(1 AS BOOLEAN) ORDER BY id")
        admins = cursor.fetchall()
        
        print(f"\n👑 Admin users in production ({len(admins)}):")
        for admin in admins:
            print(f"  ID {admin[0]}: {admin[1]} ({admin[2]})")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        print(f"Full error: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    print("🚂 Fixed Production Password Reset")
    print("=" * 40)
    fixed_reset()
