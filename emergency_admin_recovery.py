#!/usr/bin/env python3
"""
🚨 EMERGENCY ADMIN RECOVERY TOOL FOR MYAVATAR 🚨
===============================================
Comprehensive admin password recovery for both local SQLite and production PostgreSQL.
This script will help you regain admin access after password lockout incidents.

Usage:
    python emergency_admin_recovery.py --local     # Reset local SQLite admin
    python emergency_admin_recovery.py --prod      # Reset production PostgreSQL admin
    python emergency_admin_recovery.py --both      # Reset both databases
"""

import sys
import os
import argparse
from datetime import datetime
import getpass

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from app.auth.authentication import get_password_hash
    from app.db.database import execute_query, get_db_connection, USE_POSTGRES
    print("✅ Successfully imported MyAvatar modules")
except ImportError as e:
    print(f"❌ Failed to import MyAvatar modules: {e}")
    print("Make sure you're running this from the MyAvatar project directory")
    sys.exit(1)

class AdminRecovery:
    def __init__(self):
        self.recovery_log = []
        
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}"
        print(log_entry)
        self.recovery_log.append(log_entry)
    
    def list_all_users(self, db_type="current"):
        """List all users in the database"""
        try:
            self.log(f"📋 Listing all users in {db_type} database...")
            
            users = execute_query(
                "SELECT id, username, email, is_admin, created_at FROM users ORDER BY id",
                fetch_all=True
            )
            
            if not users:
                self.log("⚠️  No users found in database!", "WARNING")
                return []
            
            print("\n" + "="*80)
            print(f"👥 USERS IN {db_type.upper()} DATABASE")
            print("="*80)
            print(f"{'ID':<4} {'USERNAME':<15} {'EMAIL':<30} {'ADMIN':<8} {'CREATED':<20}")
            print("-"*80)
            
            for user in users:
                admin_status = "👑 YES" if user[3] else "👤 NO"
                created = user[4] if user[4] else "Unknown"
                print(f"{user[0]:<4} {user[1]:<15} {user[2]:<30} {admin_status:<8} {str(created):<20}")
            
            print("="*80)
            self.log(f"Found {len(users)} users total")
            return users
            
        except Exception as e:
            self.log(f"❌ Error listing users: {e}", "ERROR")
            return []
    
    def reset_admin_password(self, new_password=None):
        """Reset admin password with multiple fallback strategies"""
        try:
            if not new_password:
                new_password = "Admin2025!"
                
            self.log(f"🔧 Starting admin password reset...")
            self.log(f"🔑 New password will be: {new_password}")
            
            # Hash the new password
            hashed_password = get_password_hash(new_password)
            self.log("✅ Password hashed successfully")
            
            # Strategy 1: Try common admin emails
            admin_emails = [
                "admin@myavatar.dk",
                "admin@myavatar.com", 
                "admin@example.com",
                "admin@localhost"
            ]
            
            success = False
            
            for email in admin_emails:
                try:
                    # Check if user exists with this email
                    admin_user = execute_query(
                        "SELECT id, username, email FROM users WHERE LOWER(email) = LOWER(?)",
                        (email,),
                        fetch_one=True
                    )
                    
                    if admin_user:
                        # Update password
                        execute_query(
                            "UPDATE users SET password = ?, is_admin = 1 WHERE LOWER(email) = LOWER(?)",
                            (hashed_password, email)
                        )
                        self.log(f"✅ Successfully reset password for: {email}")
                        self.log(f"👤 User ID: {admin_user[0]}, Username: {admin_user[1]}")
                        success = True
                        break
                        
                except Exception as e:
                    self.log(f"⚠️  Failed to reset password for {email}: {e}", "WARNING")
                    continue
            
            # Strategy 2: Try username-based admin accounts
            if not success:
                admin_usernames = ["admin", "administrator", "root"]
                
                for username in admin_usernames:
                    try:
                        admin_user = execute_query(
                            "SELECT id, username, email FROM users WHERE LOWER(username) = LOWER(?)",
                            (username,),
                            fetch_one=True
                        )
                        
                        if admin_user:
                            execute_query(
                                "UPDATE users SET password = ?, is_admin = 1 WHERE LOWER(username) = LOWER(?)",
                                (hashed_password, username)
                            )
                            self.log(f"✅ Successfully reset password for username: {username}")
                            self.log(f"📧 Email: {admin_user[2]}")
                            success = True
                            break
                            
                    except Exception as e:
                        self.log(f"⚠️  Failed to reset password for username {username}: {e}", "WARNING")
                        continue
            
            # Strategy 3: Create new admin user if none found
            if not success:
                self.log("🆕 No existing admin found, creating new admin user...")
                try:
                    execute_query(
                        """INSERT INTO users (username, email, password, is_admin, created_at) 
                           VALUES (?, ?, ?, 1, ?)""",
                        ("admin", "admin@myavatar.dk", hashed_password, datetime.now())
                    )
                    self.log("✅ New admin user created successfully!")
                    self.log("📧 Email: admin@myavatar.dk")
                    self.log("👤 Username: admin")
                    success = True
                    
                except Exception as e:
                    self.log(f"❌ Failed to create new admin user: {e}", "ERROR")
            
            if success:
                print("\n" + "🎉" * 20)
                print("🎉 ADMIN PASSWORD RESET SUCCESSFUL! 🎉")
                print("🎉" * 20)
                print(f"🔑 Password: {new_password}")
                print("🚀 You can now login to your MyAvatar application!")
                print("🎉" * 20 + "\n")
                return True
            else:
                self.log("❌ All password reset strategies failed", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Critical error during password reset: {e}", "ERROR")
            return False
    
    def force_admin_privileges(self):
        """Ensure at least one user has admin privileges"""
        try:
            self.log("🔧 Checking for admin users...")
            
            # Check if any admin users exist
            admin_users = execute_query(
                "SELECT id, username, email FROM users WHERE is_admin = 1",
                fetch_all=True
            )
            
            if admin_users:
                self.log(f"✅ Found {len(admin_users)} admin user(s)")
                for admin in admin_users:
                    self.log(f"   👑 {admin[1]} ({admin[2]})")
                return True
            
            # No admin users found, promote the first user
            self.log("⚠️  No admin users found! Promoting first user to admin...")
            
            first_user = execute_query(
                "SELECT id, username, email FROM users ORDER BY id LIMIT 1",
                fetch_one=True
            )
            
            if first_user:
                execute_query(
                    "UPDATE users SET is_admin = 1 WHERE id = ?",
                    (first_user[0],)
                )
                self.log(f"✅ Promoted user {first_user[1]} ({first_user[2]}) to admin")
                return True
            else:
                self.log("❌ No users found in database!", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Error checking admin privileges: {e}", "ERROR")
            return False
    
    def database_health_check(self):
        """Perform basic database health check"""
        try:
            self.log("🏥 Performing database health check...")
            
            # Test connection
            conn = get_db_connection()
            self.log("✅ Database connection successful")
            
            # Check if users table exists
            if USE_POSTGRES:
                table_check = execute_query(
                    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'users')",
                    fetch_one=True
                )
            else:
                table_check = execute_query(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='users'",
                    fetch_one=True
                )
            
            if table_check:
                self.log("✅ Users table exists")
            else:
                self.log("❌ Users table not found!", "ERROR")
                return False
            
            # Count users
            user_count = execute_query(
                "SELECT COUNT(*) FROM users",
                fetch_one=True
            )
            
            self.log(f"📊 Total users in database: {user_count[0] if user_count else 0}")
            
            return True
            
        except Exception as e:
            self.log(f"❌ Database health check failed: {e}", "ERROR")
            return False
    
    def save_recovery_log(self):
        """Save recovery log to file"""
        try:
            log_filename = f"admin_recovery_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(log_filename, 'w') as f:
                f.write("MyAvatar Admin Recovery Log\n")
                f.write("=" * 50 + "\n")
                for entry in self.recovery_log:
                    f.write(entry + "\n")
            
            self.log(f"📝 Recovery log saved to: {log_filename}")
            
        except Exception as e:
            self.log(f"⚠️  Could not save recovery log: {e}", "WARNING")

def main():
    parser = argparse.ArgumentParser(description="MyAvatar Emergency Admin Recovery Tool")
    parser.add_argument("--local", action="store_true", help="Reset local SQLite database admin")
    parser.add_argument("--prod", action="store_true", help="Reset production PostgreSQL admin")
    parser.add_argument("--both", action="store_true", help="Reset both databases")
    parser.add_argument("--password", type=str, help="Custom admin password (default: Admin2025!)")
    parser.add_argument("--list-users", action="store_true", help="Only list users, don't reset password")
    
    args = parser.parse_args()
    
    if not any([args.local, args.prod, args.both, args.list_users]):
        print("❌ Please specify --local, --prod, --both, or --list-users")
        parser.print_help()
        return
    
    recovery = AdminRecovery()
    
    print("🚨 MyAvatar Emergency Admin Recovery Tool 🚨")
    print("=" * 50)
    print(f"Database type: {'PostgreSQL' if USE_POSTGRES else 'SQLite'}")
    print("=" * 50)
    
    # Perform health check
    if not recovery.database_health_check():
        print("❌ Database health check failed. Cannot proceed.")
        return
    
    # List users if requested
    if args.list_users:
        recovery.list_all_users()
        recovery.save_recovery_log()
        return
    
    # List current users
    recovery.list_all_users()
    
    # Reset password
    if args.local or args.both or (not args.prod):
        password = args.password or "Admin2025!"
        
        print(f"\n🔧 Proceeding with password reset...")
        print(f"🔑 New password will be: {password}")
        
        # Confirm action
        confirm = input("\n⚠️  Are you sure you want to reset the admin password? (yes/no): ")
        if confirm.lower() not in ['yes', 'y']:
            print("❌ Operation cancelled by user")
            return
        
        # Reset password
        success = recovery.reset_admin_password(password)
        
        if success:
            # Ensure admin privileges
            recovery.force_admin_privileges()
            
            # List users again to confirm
            print("\n📋 Updated user list:")
            recovery.list_all_users("updated")
    
    # Save log
    recovery.save_recovery_log()
    
    print("\n🏁 Recovery operation completed!")

if __name__ == "__main__":
    main()
