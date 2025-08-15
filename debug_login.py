#!/usr/bin/env python3
"""
Debug script to test login functionality
"""
import sys
sys.path.append('.')

from app.db.user_manager import Database
from app.auth.authentication import verify_password

def test_login(username, password):
    """Test the exact login flow"""
    print(f"=== Testing login for: {username} ===")
    
    db = Database()
    
    # Step 1: Get user by username
    print("Step 1: Looking up user...")
    user = db.get_user_by_username(username)
    if not user:
        print("❌ User not found!")
        return False
    
    print(f"✅ User found: {user['username']}")
    print(f"   Email: {user['email']}")
    print(f"   Is Admin: {user.get('is_admin', 'Unknown')}")
    print(f"   Available fields: {list(user.keys())}")
    
    # Step 2: Check password field
    password_field = user.get("password", "")
    if not password_field:
        print("❌ No password field found!")
        return False
    
    print(f"✅ Password field exists (length: {len(password_field)})")
    
    # Step 3: Verify password
    print("Step 3: Verifying password...")
    try:
        is_valid = verify_password(password, password_field)
        if is_valid:
            print("✅ Password verification PASSED")
            return True
        else:
            print("❌ Password verification FAILED")
            return False
    except Exception as e:
        print(f"❌ Password verification ERROR: {e}")
        return False

if __name__ == "__main__":
    # Test with admin credentials
    success = test_login("admin", "admin123")
    
    if success:
        print("\n🎉 LOGIN TEST PASSED - Authentication should work!")
    else:
        print("\n💥 LOGIN TEST FAILED - There's still an issue!")
