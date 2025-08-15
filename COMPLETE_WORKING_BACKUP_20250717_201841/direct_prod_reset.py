#!/usr/bin/env python3
"""
🚂 Direct Production Password Reset
==================================
Reset admin password on Railway PostgreSQL without prompts
"""

import sys
import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def direct_reset():
    """Direct reset without confirmation"""
    
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
        
        print("🔧 Resetting admin password...")
        
        # Update all admin users and ensure at least one admin exists
        cursor.execute(
            "UPDATE users SET password = %s WHERE username = %s OR email LIKE %s OR is_admin = true",
            (hashed_password, "admin", "%admin%")
        )
        
        updated_count = cursor.rowcount
        
        if updated_count > 0:
            print(f"✅ Updated {updated_count} admin user(s)")
        else:
            # Create new admin if none exists
            cursor.execute(
                "INSERT INTO users (username, email, password, is_admin, created_at) VALUES (%s, %s, %s, %s, NOW())",
                ("admin", "admin@myavatar.dk", hashed_password, True)
            )
            print("✅ Created new admin user")
        
        # Ensure at least one admin exists
        cursor.execute("UPDATE users SET is_admin = true WHERE id = (SELECT MIN(id) FROM users)")
        
        print("\n🎉 PRODUCTION PASSWORD RESET COMPLETE!")
        print(f"🔑 Password: {new_password}")
        print("🚀 Try logging in at: https://app.myavatar.dk")
        
        # Show current admin users
        cursor.execute("SELECT id, username, email, is_admin FROM users WHERE is_admin = true ORDER BY id")
        admins = cursor.fetchall()
        
        print(f"\n👑 Admin users in production ({len(admins)}):")
        for admin in admins:
            print(f"  ID {admin[0]}: {admin[1]} ({admin[2]})")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("🚂 Direct Production Password Reset")
    print("=" * 40)
    direct_reset()
