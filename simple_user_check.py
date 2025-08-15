#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('myavatar.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check all users
cursor.execute('SELECT id, username FROM users ORDER BY id')
users = cursor.fetchall()

print("ALL USERS IN DATABASE:")
for user in users:
    print(f"ID: {user['id']}, Username: {user['username']}")

# Specifically check testuser
cursor.execute('SELECT id, username, password FROM users WHERE username = ?', ('testuser',))
testuser = cursor.fetchone()

if testuser:
    print(f"\n✅ TESTUSER FOUND: ID={testuser['id']}, Username={testuser['username']}")
    print(f"Password hash exists: {'YES' if testuser['password'] else 'NO'}")
else:
    print("\n❌ TESTUSER NOT FOUND!")

conn.close()
