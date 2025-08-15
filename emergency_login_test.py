#!/usr/bin/env python3
"""
EMERGENCY LOGIN TEST - Test login functionality directly
"""
import sqlite3
from werkzeug.security import check_password_hash, generate_password_hash
import sys
import os

def test_login_direct():
    """Test login functionality directly"""
    print("🚨 EMERGENCY LOGIN TEST")
    print("=" * 50)
    
    # Test database connection
    try:
        conn = sqlite3.connect('myavatar.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        print("✅ Database connection OK")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False
    
    # Check testuser exists
    cursor.execute('SELECT id, username, password FROM users WHERE username = ?', ('testuser',))
    user = cursor.fetchone()
    
    if not user:
        print("❌ testuser NOT FOUND in database!")
        
        # Create testuser immediately
        print("🚀 Creating testuser now...")
        hashed_password = generate_password_hash('Test123')
        cursor.execute('''
            INSERT INTO users (username, email, password, created_at, is_admin)
            VALUES (?, ?, ?, datetime('now'), ?)
        ''', ('testuser', 'test@example.com', hashed_password, 0))
        conn.commit()
        print("✅ testuser created!")
        
        # Re-fetch user
        cursor.execute('SELECT id, username, password FROM users WHERE username = ?', ('testuser',))
        user = cursor.fetchone()
    
    if user:
        print(f"✅ testuser found: ID={user['id']}, Username={user['username']}")
        
        # Test password
        if check_password_hash(user['password'], 'Test123'):
            print("✅ Password 'Test123' is CORRECT!")
            print("\n🎯 LOGIN SHOULD WORK WITH:")
            print("   Username: testuser")
            print("   Password: Test123")
            return True
        else:
            print("❌ Password 'Test123' is WRONG!")
            
            # Reset password
            print("🔧 Resetting password...")
            new_hash = generate_password_hash('Test123')
            cursor.execute('UPDATE users SET password = ? WHERE id = ?', (new_hash, user['id']))
            conn.commit()
            print("✅ Password reset to 'Test123'")
            return True
    
    conn.close()
    return False

if __name__ == "__main__":
    success = test_login_direct()
    if success:
        print("\n🎉 LOGIN SHOULD NOW WORK!")
        print("🚀 Try: testuser / Test123")
    else:
        print("\n💥 LOGIN STILL BROKEN!")
    
    sys.exit(0 if success else 1)
