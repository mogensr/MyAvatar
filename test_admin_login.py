#!/usr/bin/env python3
"""
🧪 Test Admin Login
==================
Test if the admin login works after password reset
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_admin_login():
    """Test admin login functionality"""
    print("🧪 Testing Admin Login")
    print("=" * 30)
    
    try:
        from app.auth.authentication import authenticate_user, authenticate_user_by_email
        from app.db.database import execute_query
        
        # Test credentials
        test_password = "Admin2025!"
        
        print("🔍 Testing authentication methods...")
        
        # Test 1: Authenticate by username
        print("\n1️⃣ Testing username authentication...")
        try:
            user = authenticate_user("admin", test_password)
            if user:
                print(f"✅ Username auth SUCCESS: {user.get('username')} ({user.get('email')})")
                print(f"   Admin status: {'Yes' if user.get('is_admin') else 'No'}")
            else:
                print("❌ Username auth FAILED")
        except Exception as e:
            print(f"❌ Username auth ERROR: {e}")
        
        # Test 2: Authenticate by email
        print("\n2️⃣ Testing email authentication...")
        
        # Get admin email from database
        admin_user = execute_query(
            "SELECT email FROM users WHERE username = ? OR is_admin = 1 LIMIT 1",
            ("admin",),
            fetch_one=True
        )
        
        if admin_user:
            admin_email = admin_user[0]
            print(f"Found admin email: {admin_email}")
            
            try:
                user = authenticate_user_by_email(admin_email, test_password)
                if user:
                    print(f"✅ Email auth SUCCESS: {user.get('username')} ({user.get('email')})")
                    print(f"   Admin status: {'Yes' if user.get('is_admin') else 'No'}")
                else:
                    print("❌ Email auth FAILED")
            except Exception as e:
                print(f"❌ Email auth ERROR: {e}")
        else:
            print("❌ Could not find admin email")
        
        # Test 3: Direct password verification
        print("\n3️⃣ Testing direct password verification...")
        try:
            from app.auth.authentication import verify_password
            
            # Get stored password hash
            stored_hash = execute_query(
                "SELECT password FROM users WHERE username = ?",
                ("admin",),
                fetch_one=True
            )
            
            if stored_hash:
                is_valid = verify_password(test_password, stored_hash[0])
                print(f"Password verification: {'✅ VALID' if is_valid else '❌ INVALID'}")
            else:
                print("❌ Could not retrieve stored password hash")
                
        except Exception as e:
            print(f"❌ Password verification ERROR: {e}")
        
        print("\n" + "=" * 50)
        print("📋 SUMMARY")
        print("=" * 50)
        print("If all tests passed, you can login with:")
        print(f"   Username: admin")
        print(f"   Password: {test_password}")
        print("   OR")
        print(f"   Email: {admin_email if 'admin_email' in locals() else 'admin@myavatar.com'}")
        print(f"   Password: {test_password}")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're in the correct directory and dependencies are installed")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    test_admin_login()
