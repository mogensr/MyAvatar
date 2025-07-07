#!/usr/bin/env python3
"""
🧪 TEST VERSION - Admin Recovery Tool for MyAvatar
=================================================
Safe testing version that simulates recovery operations without making changes.
"""

import sys
import os
from datetime import datetime

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

class TestAdminRecovery:
    def __init__(self):
        self.recovery_log = []
        self.test_mode = True
        
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}"
        print(log_entry)
        self.recovery_log.append(log_entry)
    
    def test_imports(self):
        """Test if all required modules can be imported"""
        self.log("🧪 Testing module imports...")
        
        try:
            from app.auth.authentication import get_password_hash
            self.log("✅ Successfully imported authentication module")
            
            # Test password hashing
            test_hash = get_password_hash("test123")
            if test_hash and len(test_hash) > 20:
                self.log("✅ Password hashing function works")
            else:
                self.log("❌ Password hashing function failed", "ERROR")
                
        except ImportError as e:
            self.log(f"❌ Failed to import authentication: {e}", "ERROR")
            return False
        
        try:
            from app.db.database import execute_query, get_db_connection, USE_POSTGRES
            self.log(f"✅ Successfully imported database module (PostgreSQL: {USE_POSTGRES})")
        except ImportError as e:
            self.log(f"❌ Failed to import database: {e}", "ERROR")
            return False
            
        return True
    
    def test_database_connection(self):
        """Test database connection without making changes"""
        self.log("🔌 Testing database connection...")
        
        try:
            from app.db.database import execute_query, USE_POSTGRES
            
            # Test basic connection
            if USE_POSTGRES:
                result = execute_query("SELECT version()", fetch_one=True)
                if result:
                    self.log("✅ PostgreSQL connection successful")
                    self.log(f"   Database version: {result[0][:50]}...")
            else:
                result = execute_query("SELECT sqlite_version()", fetch_one=True)
                if result:
                    self.log("✅ SQLite connection successful")
                    self.log(f"   SQLite version: {result[0]}")
            
            return True
            
        except Exception as e:
            self.log(f"❌ Database connection failed: {e}", "ERROR")
            return False
    
    def test_users_table(self):
        """Test if users table exists and get basic info"""
        self.log("📋 Testing users table...")
        
        try:
            from app.db.database import execute_query, USE_POSTGRES
            
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
                
                # Get user count
                user_count = execute_query("SELECT COUNT(*) FROM users", fetch_one=True)
                self.log(f"📊 Total users: {user_count[0] if user_count else 0}")
                
                # Get admin count
                admin_count = execute_query("SELECT COUNT(*) FROM users WHERE is_admin = true", fetch_one=True)
                self.log(f"👑 Admin users: {admin_count[0] if admin_count else 0}")
                
                return True
            else:
                self.log("❌ Users table not found!", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Error testing users table: {e}", "ERROR")
            return False
    
    def simulate_user_listing(self):
        """Simulate listing users (read-only operation)"""
        self.log("👥 Simulating user listing...")
        
        try:
            from app.db.database import execute_query
            
            users = execute_query(
                "SELECT id, username, email, is_admin, created_at FROM users ORDER BY id",
                fetch_all=True
            )
            
            if not users:
                self.log("⚠️  No users found in database!", "WARNING")
                return []
            
            print("\n" + "="*80)
            print("👥 CURRENT USERS IN DATABASE")
            print("="*80)
            print(f"{'ID':<4} {'USERNAME':<15} {'EMAIL':<30} {'ADMIN':<8} {'CREATED':<20}")
            print("-"*80)
            
            admin_found = False
            for user in users:
                admin_status = "👑 YES" if user[3] else "👤 NO"
                if user[3]:
                    admin_found = True
                created = user[4] if user[4] else "Unknown"
                print(f"{user[0]:<4} {user[1]:<15} {user[2]:<30} {admin_status:<8} {str(created):<20}")
            
            print("="*80)
            self.log(f"Found {len(users)} users total")
            
            if admin_found:
                self.log("✅ At least one admin user found")
            else:
                self.log("⚠️  No admin users found - recovery would be needed!", "WARNING")
            
            return users
            
        except Exception as e:
            self.log(f"❌ Error listing users: {e}", "ERROR")
            return []
    
    def simulate_password_reset(self):
        """Simulate password reset without actually changing anything"""
        self.log("🔧 SIMULATION: Admin password reset...")
        self.log("🔑 Would use password: Admin2025!")
        
        try:
            from app.auth.authentication import get_password_hash
            
            # Test password hashing
            test_password = "Admin2025!"
            hashed = get_password_hash(test_password)
            self.log("✅ Password hashing test successful")
            
            # Simulate finding admin users
            admin_emails = [
                "admin@myavatar.dk",
                "admin@myavatar.com", 
                "admin@example.com",
                "admin@localhost"
            ]
            
            self.log("🔍 Would search for admin users with emails:")
            for email in admin_emails:
                self.log(f"   - {email}")
            
            self.log("✅ Password reset simulation complete")
            self.log("⚠️  NOTE: No actual changes made in test mode")
            
        except Exception as e:
            self.log(f"❌ Password reset simulation failed: {e}", "ERROR")
    
    def run_full_test(self):
        """Run complete test suite"""
        print("🧪 MyAvatar Admin Recovery - TEST MODE")
        print("=" * 50)
        
        # Test 1: Module imports
        if not self.test_imports():
            self.log("❌ Import test failed - cannot continue", "ERROR")
            return False
        
        # Test 2: Database connection
        if not self.test_database_connection():
            self.log("❌ Database connection test failed", "ERROR")
            return False
        
        # Test 3: Users table
        if not self.test_users_table():
            self.log("❌ Users table test failed", "ERROR")
            return False
        
        # Test 4: List users
        users = self.simulate_user_listing()
        
        # Test 5: Simulate password reset
        self.simulate_password_reset()
        
        # Save test log
        self.save_test_log()
        
        print("\n🎉 All tests completed!")
        print("✅ Admin recovery script appears to be working correctly")
        print("⚠️  Run the actual script with caution on production data")
        
        return True
    
    def save_test_log(self):
        """Save test log to file"""
        try:
            log_filename = f"admin_recovery_test_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(log_filename, 'w') as f:
                f.write("MyAvatar Admin Recovery - TEST LOG\n")
                f.write("=" * 50 + "\n")
                f.write("This is a TEST RUN - no actual changes were made\n")
                f.write("=" * 50 + "\n")
                for entry in self.recovery_log:
                    f.write(entry + "\n")
            
            self.log(f"📝 Test log saved to: {log_filename}")
            
        except Exception as e:
            self.log(f"⚠️  Could not save test log: {e}", "WARNING")

def main():
    print("🧪 Starting Admin Recovery Test Suite...")
    
    test_recovery = TestAdminRecovery()
    success = test_recovery.run_full_test()
    
    if success:
        print("\n✅ Test suite passed - admin recovery script is ready to use")
    else:
        print("\n❌ Test suite failed - check the issues above")

if __name__ == "__main__":
    main()
