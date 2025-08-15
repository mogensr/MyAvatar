#!/usr/bin/env python3
"""
Quick login test for testuser vs Lars-Christian
"""
import sqlite3
from werkzeug.security import check_password_hash

def test_login():
    conn = sqlite3.connect('myavatar.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get both users
    cursor.execute('SELECT id, username, password FROM users WHERE username IN (?, ?)', 
                   ('Lars-Christian', 'testuser'))
    users = cursor.fetchall()
    
    print("🔍 COMPARING USERS:")
    for user in users:
        print(f"\n👤 {user['username']} (ID: {user['id']})")
        print(f"   Password hash: {user['password'][:50]}...")
        
        # Test common passwords
        test_passwords = ['Test123', 'test123', 'password', '123456']
        for pwd in test_passwords:
            if check_password_hash(user['password'], pwd):
                print(f"   ✅ WORKS WITH: {pwd}")
                break
        else:
            print(f"   ❌ None of the test passwords work")
    
    conn.close()

if __name__ == "__main__":
    test_login()
