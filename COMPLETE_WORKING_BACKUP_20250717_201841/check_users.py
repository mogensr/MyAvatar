import sqlite3
import os

# Connect to the database
print("Connecting to database...")
db_path = "myavatar.db"  # Use default path
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row  # This enables column access by name
cursor = conn.cursor()

# List all users
print("\nListing all users in the database:")
cursor.execute("SELECT id, username, email FROM users")
users = cursor.fetchall()

if not users:
    print("No users found in the database!")
else:
    print(f"Found {len(users)} users:")
    for user in users:
        print(f"ID: {user['id']}, Username: {user['username']}, Email: {user['email']}")

# List all tables
print("\nListing all tables in the database:")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
for table in tables:
    print(f"Table: {table['name']}")

conn.close()
print("\nDone!")
