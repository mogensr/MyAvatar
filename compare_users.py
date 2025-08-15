#!/usr/bin/env python3
"""
Compare Lars-Christian vs testuser passwords
"""
import sqlite3
from werkzeug.security import check_password_hash

def compare_users():
    conn = sqlite3.connect('myavatar.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get both users
    cursor.execute('''
        SELECT id, username, password 
        FROM users 
        WHERE username IN (?, ?) 
        ORDER BY username
    ''', ('Lars-Christian', 'testuser'))
    
    users = cursor.fetchall()
    
    print('USER COMPARISON:')
    print('=' * 80)
    
    for user in users:
        print(f'\n👤 {user["username"]} (ID: {user["id"]})')
        
        if user['password']:
            pwd = user['password']
            print(f'   Password length: {len(pwd)}')
            print(f'   Hash type: {pwd[:20]}...')
            
            # Test common passwords
            test_passwords = ['Test123', 'test123', 'password', '123456', 'admin']
            
            for test_pwd in test_passwords:
                try:
                    if check_password_hash(pwd, test_pwd):
                        print(f'   ✅ WORKS WITH: "{test_pwd}"')
                        break
                except Exception as e:
                    print(f'   ⚠️ Hash check error with "{test_pwd}": {e}')
            else:
                print(f'   ❌ None of the test passwords work')
                
        else:
            print(f'   ❌ NO PASSWORD SET!')
    
    conn.close()

if __name__ == "__main__":
    compare_users()
