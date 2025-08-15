#!/usr/bin/env python3
import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect('myavatar.db')
cursor = conn.cursor()

# Change "Testuser" to "testuser" and reset password
new_username = 'testuser'
new_password = 'Test123'
hashed_password = generate_password_hash(new_password)

cursor.execute('UPDATE users SET username = ?, password = ? WHERE id = 2', 
               (new_username, hashed_password))
conn.commit()

print(f"✅ User updated:")
print(f"   Username: {new_username}")
print(f"   Password: {new_password}")
print("🚀 Try logging in now!")

conn.close()
