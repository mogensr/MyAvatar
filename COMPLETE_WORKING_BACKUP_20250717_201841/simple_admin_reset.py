#!/usr/bin/env python3
"""
Simple admin password reset for Railway dev database
"""
import os
import psycopg2
import bcrypt
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def hash_password(password):
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def reset_admin():
    """Reset admin user password"""
    try:
        DATABASE_URL = os.getenv('DATABASE_URL')
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # First, let's see what users exist
        print("🔍 Current users:")
        cursor.execute("SELECT id, username, email, is_admin FROM users ORDER BY is_admin DESC")
        users = cursor.fetchall()
        
        for user in users:
            user_id, username, email, is_admin = user
            status = "🔑 ADMIN" if is_admin else "👤 USER"
            print(f"  {status} | {username} | {email}")
        
        # Reset password for username 'admin'
        new_password = "admin123"
        hashed_password = hash_password(new_password)
        
        print(f"\n🔧 Resetting password for 'admin' user...")
        cursor.execute(
            "UPDATE users SET password_hash = %s WHERE username = %s",
            (hashed_password, 'admin')
        )
        
        if cursor.rowcount > 0:
            conn.commit()
            print(f"✅ Password reset successfully!")
            print(f"👤 Username: admin")
            print(f"🔑 Password: {new_password}")
        else:
            print("❌ No 'admin' user found to update")
            
            # Try to find any admin user
            cursor.execute("SELECT username FROM users WHERE is_admin = true LIMIT 1")
            admin_user = cursor.fetchone()
            
            if admin_user:
                admin_username = admin_user[0]
                cursor.execute(
                    "UPDATE users SET password_hash = %s WHERE username = %s",
                    (hashed_password, admin_username)
                )
                conn.commit()
                print(f"✅ Reset password for admin user: {admin_username}")
                print(f"🔑 Password: {new_password}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    reset_admin()
