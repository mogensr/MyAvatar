#!/usr/bin/env python3
"""
🚂 Railway Production Admin Reset
=================================
Reset admin password on Railway PostgreSQL database
"""

import sys
import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def reset_railway_admin():
    """Reset admin password on Railway PostgreSQL"""
    
    # Get DATABASE_URL from environment
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("❌ DATABASE_URL not found in environment variables")
        print("💡 Make sure your .env file contains the Railway DATABASE_URL")
        return False
    
    # Convert postgres:// to postgresql:// if needed
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    print("🚂 Connecting to Railway PostgreSQL database...")
    
    try:
        # Connect to database
        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        cursor = conn.cursor()
        
        print("✅ Connected to Railway database successfully")
        
        # List current users
        print("\n📋 Current users in production database:")
        cursor.execute("SELECT id, username, email, is_admin FROM users ORDER BY id")
        users = cursor.fetchall()
        
        if users:
            for user in users:
                admin_status = "👑 ADMIN" if user[3] else "👤 USER"
                print(f"  {user[0]}: {user[1]} ({user[2]}) - {admin_status}")
        else:
            print("  No users found in production database!")
        
        # Import password hashing (you'll need to ensure this works with your setup)
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from app.auth.authentication import get_password_hash
        
        # Reset admin password
        new_password = "Admin2025!"
        hashed_password = get_password_hash(new_password)
        
        # Try to update existing admin
        cursor.execute(
            "UPDATE users SET password = %s WHERE username = %s OR email LIKE %s",
            (hashed_password, "admin", "%admin%")
        )
        
        if cursor.rowcount > 0:
            print(f"✅ Updated {cursor.rowcount} admin user(s) in production")
        else:
            # Create new admin if none exists
            cursor.execute(
                "INSERT INTO users (username, email, password, is_admin, created_at) VALUES (%s, %s, %s, %s, NOW())",
                ("admin", "admin@myavatar.dk", hashed_password, True)
            )
            print("✅ Created new admin user in production")
        
        # Ensure at least one admin exists
        cursor.execute("UPDATE users SET is_admin = true WHERE id = (SELECT MIN(id) FROM users)")
        
        print("\n🎉 Production admin password reset successful!")
        print(f"🔑 Password: {new_password}")
        print("🚀 You can now login to your Railway-hosted MyAvatar!")
        
        # Show updated users
        print("\n📋 Updated production users:")
        cursor.execute("SELECT id, username, email, is_admin FROM users ORDER BY id")
        users = cursor.fetchall()
        for user in users:
            admin_status = "👑 ADMIN" if user[3] else "👤 USER"
            print(f"  {user[0]}: {user[1]} ({user[2]}) - {admin_status}")
        
        conn.close()
        return True
        
    except psycopg2.Error as e:
        print(f"❌ PostgreSQL error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("🚂 Railway Admin Password Reset Tool")
    print("=" * 40)
    
    confirm = input("⚠️  Reset admin password on PRODUCTION Railway database? (yes/no): ")
    if confirm.lower() in ['yes', 'y']:
        reset_railway_admin()
    else:
        print("❌ Operation cancelled")
