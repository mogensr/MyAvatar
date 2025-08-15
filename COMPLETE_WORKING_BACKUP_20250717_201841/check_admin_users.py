#!/usr/bin/env python3
"""
Check admin users in Railway dev database
"""
import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_admin_users():
    """Check admin users and their details"""
    try:
        # Connect to database
        DATABASE_URL = os.getenv('DATABASE_URL')
        print(f"🔗 Connecting to database...")
        
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Check all users with admin privileges
        print("\n👥 CHECKING ALL USERS:")
        print("=" * 50)
        cursor.execute("""
            SELECT id, username, email, is_admin, password_hash, created_at 
            FROM users 
            ORDER BY is_admin DESC, created_at ASC
        """)
        
        users = cursor.fetchall()
        for user in users:
            user_id, username, email, is_admin, password_hash, created_at = user
            admin_status = "🔑 ADMIN" if is_admin else "👤 USER"
            has_password = "✅ HAS PASSWORD" if password_hash else "❌ NO PASSWORD"
            
            print(f"{admin_status} | {username} | {email} | {has_password}")
            if is_admin:
                print(f"   ID: {user_id}")
                print(f"   Created: {created_at}")
                if password_hash:
                    print(f"   Password Hash: {password_hash[:20]}...")
                print()
        
        # Check specifically for 'admin' user
        print("\n🔍 CHECKING 'admin' USER SPECIFICALLY:")
        print("=" * 50)
        cursor.execute("SELECT * FROM users WHERE username = %s", ('admin',))
        admin_user = cursor.fetchone()
        
        if admin_user:
            print("✅ Admin user found!")
            print(f"   Username: {admin_user[1]}")
            print(f"   Email: {admin_user[2]}")
            print(f"   Is Admin: {admin_user[4]}")
            print(f"   Password Hash: {admin_user[3][:30] if admin_user[3] else 'None'}...")
        else:
            print("❌ No 'admin' user found!")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_admin_users()
