#!/usr/bin/env python3
import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect('myavatar.db')
cursor = conn.cursor()

# Reset password for Testuser (with capital T)
new_password = 'Test123'
hashed_password = generate_password_hash(new_password)

cursor.execute('UPDATE users SET password = ? WHERE username = ?', 
               (hashed_password, 'Testuser'))
conn.commit()

print(f"✅ Password reset for 'Testuser' to '{new_password}'")
print("🚀 Try logging in with:")
print("   Username: Testuser")
print("   Password: Test123")

conn.close()
