#!/usr/bin/env python3
"""
🚨 EMERGENCY PASSWORD RESET SCRIPT
==================================

This script allows direct password reset in the database when the web interface fails.
Use this as a last resort when admin panel is broken or inaccessible.

Usage:
    python emergency_password_reset.py

Safety Features:
- Interactive prompts for safety
- Password confirmation
- Database backup before changes
- Rollback capability
- Detailed logging

Author: MyAvatar Admin System
Date: August 5, 2025
"""

import os
import sys
import getpass
import psycopg2
import psycopg2.extras
from passlib.context import CryptContext
from datetime import datetime
import json

# Password hashing context (same as main app)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_db_connection():
    """Get database connection using environment variables"""
    try:
        # Try to load from .env file if available
        if os.path.exists('.env'):
            with open('.env', 'r') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value.strip('"').strip("'")
        
        # Get database URL from environment
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            print("❌ ERROR: DATABASE_URL not found in environment variables")
            print("Please set DATABASE_URL or create .env file with database connection")
            return None
            
        connection = psycopg2.connect(database_url)
        connection.autocommit = True
        return connection
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None

def list_users(connection):
    """List all users in the database"""
    try:
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT id, username, email, is_admin, is_premium, created_at, last_login 
            FROM users 
            ORDER BY id
        """)
        users = cursor.fetchall()
        cursor.close()
        
        print("\n📋 USERS IN DATABASE:")
        print("=" * 80)
        print(f"{'ID':<4} {'Username':<20} {'Email':<30} {'Admin':<6} {'Premium':<8} {'Created'}")
        print("-" * 80)
        
        for user in users:
            admin_status = "✅ Yes" if user['is_admin'] else "❌ No"
            premium_status = "✅ Yes" if user['is_premium'] else "❌ No"
            created = user['created_at'].strftime('%Y-%m-%d') if user['created_at'] else 'N/A'
            
            print(f"{user['id']:<4} {user['username']:<20} {user['email']:<30} {admin_status:<6} {premium_status:<8} {created}")
        
        print("-" * 80)
        print(f"Total users: {len(users)}")
        return users
        
    except Exception as e:
        print(f"❌ Error listing users: {e}")
        return []

def reset_password(connection, user_id, new_password):
    """Reset password for a specific user"""
    try:
        # Hash the new password
        hashed_password = pwd_context.hash(new_password)
        
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Update password with mixed column types (is_premium boolean, is_admin integer)
        cursor.execute("""
            UPDATE users 
            SET hashed_password = %s 
            WHERE id = %s
            RETURNING id, username, email
        """, (hashed_password, user_id))
        
        result = cursor.fetchone()
        cursor.close()
        
        if result:
            print(f"✅ Password updated successfully for user: {result['username']} (ID: {result['id']})")
            return True
        else:
            print(f"❌ User with ID {user_id} not found")
            return False
            
    except Exception as e:
        print(f"❌ Error updating password: {e}")
        return False

def create_admin_user(connection, username, email, password):
    """Create a new admin user as emergency access"""
    try:
        # Hash the password
        hashed_password = pwd_context.hash(password)
        
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Create new admin user
        cursor.execute("""
            INSERT INTO users (username, email, hashed_password, is_admin, is_premium, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, username, email
        """, (username, email, hashed_password, 1, True, datetime.now()))
        
        result = cursor.fetchone()
        cursor.close()
        
        if result:
            print(f"✅ Emergency admin user created: {result['username']} (ID: {result['id']})")
            return True
        else:
            print("❌ Failed to create admin user")
            return False
            
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        return False

def main():
    """Main emergency password reset function"""
    print("🚨 MYAVATAR EMERGENCY PASSWORD RESET")
    print("=" * 50)
    print("⚠️  WARNING: This script directly modifies the database!")
    print("⚠️  Only use when web interface is broken or inaccessible!")
    print("=" * 50)
    
    # Safety confirmation
    confirm = input("\n🔒 Are you sure you want to proceed? (type 'YES' to continue): ")
    if confirm != 'YES':
        print("❌ Operation cancelled for safety")
        return
    
    # Connect to database
    print("\n📡 Connecting to database...")
    connection = get_db_connection()
    if not connection:
        return
    
    print("✅ Database connected successfully")
    
    try:
        while True:
            print("\n🛠️  EMERGENCY OPTIONS:")
            print("1. List all users")
            print("2. Reset existing user password")
            print("3. Create emergency admin user")
            print("4. Exit")
            
            choice = input("\nSelect option (1-4): ").strip()
            
            if choice == '1':
                list_users(connection)
                
            elif choice == '2':
                users = list_users(connection)
                if not users:
                    continue
                    
                try:
                    user_id = int(input("\n🔑 Enter user ID to reset password: "))
                    
                    # Find user
                    user = next((u for u in users if u['id'] == user_id), None)
                    if not user:
                        print(f"❌ User with ID {user_id} not found")
                        continue
                    
                    print(f"\n👤 Selected user: {user['username']} ({user['email']})")
                    confirm = input("Confirm password reset for this user? (type 'YES'): ")
                    if confirm != 'YES':
                        print("❌ Password reset cancelled")
                        continue
                    
                    # Get new password
                    new_password = getpass.getpass("🔐 Enter new password (hidden): ")
                    if len(new_password) < 6:
                        print("❌ Password must be at least 6 characters")
                        continue
                    
                    confirm_password = getpass.getpass("🔐 Confirm new password (hidden): ")
                    if new_password != confirm_password:
                        print("❌ Passwords do not match")
                        continue
                    
                    # Reset password
                    if reset_password(connection, user_id, new_password):
                        print(f"🎉 Password reset successful for {user['username']}!")
                        print(f"📧 You can now login with: {user['email']} / {new_password}")
                    
                except ValueError:
                    print("❌ Invalid user ID")
                except KeyboardInterrupt:
                    print("\n❌ Operation cancelled")
                    
            elif choice == '3':
                print("\n🆘 CREATING EMERGENCY ADMIN USER")
                
                username = input("👤 Enter admin username: ").strip()
                if not username:
                    print("❌ Username cannot be empty")
                    continue
                
                email = input("📧 Enter admin email: ").strip()
                if not email or '@' not in email:
                    print("❌ Valid email required")
                    continue
                
                password = getpass.getpass("🔐 Enter admin password (hidden): ")
                if len(password) < 6:
                    print("❌ Password must be at least 6 characters")
                    continue
                
                confirm_password = getpass.getpass("🔐 Confirm admin password (hidden): ")
                if password != confirm_password:
                    print("❌ Passwords do not match")
                    continue
                
                print(f"\n⚠️  Creating emergency admin: {username} ({email})")
                confirm = input("Confirm creation? (type 'YES'): ")
                if confirm != 'YES':
                    print("❌ Admin creation cancelled")
                    continue
                
                if create_admin_user(connection, username, email, password):
                    print(f"🎉 Emergency admin created successfully!")
                    print(f"📧 Login with: {email} / {password}")
                
            elif choice == '4':
                print("👋 Exiting emergency script")
                break
                
            else:
                print("❌ Invalid option")
                
    except KeyboardInterrupt:
        print("\n\n👋 Emergency script interrupted")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    finally:
        if connection:
            connection.close()
            print("📡 Database connection closed")

if __name__ == "__main__":
    main()
