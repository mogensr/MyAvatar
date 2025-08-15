#!/usr/bin/env python3
"""
Check password column inconsistency in users table
"""
import sqlite3

def check_password_columns():
    conn = sqlite3.connect('myavatar.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Check database schema first
    cursor.execute('PRAGMA table_info(users)')
    columns = cursor.fetchall()
    print('USERS TABLE COLUMNS:')
    for col in columns:
        print(f'  {col[1]} ({col[2]})')

    print('\n' + '='*70)

    # Check all users and their password fields
    cursor.execute('''
        SELECT id, username, 
               password,
               CASE WHEN password IS NOT NULL THEN length(password) ELSE 0 END as pwd_len
        FROM users ORDER BY id
    ''')
    users = cursor.fetchall()

    print('ALL USERS PASSWORD STATUS:')
    print('ID | Username        | Password Field | Length | Hash Type')
    print('-' * 65)

    for user in users:
        pwd_status = 'YES' if user['password'] else 'NO'
        pwd_len = user['pwd_len'] if user['pwd_len'] else 0
        
        # Detect hash type
        hash_type = 'NONE'
        if user['password']:
            pwd = user['password']
            if pwd.startswith('scrypt:'):
                hash_type = 'SCRYPT'
            elif pwd.startswith('$2b$'):
                hash_type = 'BCRYPT'
            elif pwd.startswith('pbkdf2:'):
                hash_type = 'PBKDF2'
            else:
                hash_type = 'UNKNOWN'
        
        print(f'{user["id"]:2} | {user["username"]:15} | {pwd_status:10} | {pwd_len:6} | {hash_type}')

    print('\n' + '='*70)
    print('ANALYSIS:')
    
    # Count different hash types
    hash_counts = {}
    for user in users:
        if user['password']:
            pwd = user['password']
            if pwd.startswith('scrypt:'):
                hash_counts['SCRYPT'] = hash_counts.get('SCRYPT', 0) + 1
            elif pwd.startswith('$2b$'):
                hash_counts['BCRYPT'] = hash_counts.get('BCRYPT', 0) + 1
            elif pwd.startswith('pbkdf2:'):
                hash_counts['PBKDF2'] = hash_counts.get('PBKDF2', 0) + 1
            else:
                hash_counts['UNKNOWN'] = hash_counts.get('UNKNOWN', 0) + 1
        else:
            hash_counts['NONE'] = hash_counts.get('NONE', 0) + 1
    
    for hash_type, count in hash_counts.items():
        print(f'  {hash_type}: {count} users')

    conn.close()

if __name__ == "__main__":
    check_password_columns()
