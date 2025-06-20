import sqlite3
import os

# Voice ID to set for testuser
VOICE_ID = "0f04c50500bf417396ba2e846d7bd3d7"

# Connect to the database
print("Connecting to database...")
db_path = "myavatar.db"  # Use default path
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check if heygen_voice_id column exists
print("Checking database schema...")
cursor.execute("PRAGMA table_info(users)")
columns = [col[1] for col in cursor.fetchall()]
print(f"Current columns in users table: {columns}")

# Add the column if needed
if "heygen_voice_id" not in columns:
    print("Adding heygen_voice_id column...")
    cursor.execute("ALTER TABLE users ADD COLUMN heygen_voice_id TEXT")
    conn.commit()
    print("Column added successfully")

# Update the testuser record
print("Updating testuser record...")
cursor.execute(
    "UPDATE users SET heygen_voice_id = ? WHERE username = ?", 
    (VOICE_ID, "testuser")
)
rows_affected = cursor.rowcount
conn.commit()
print(f"Updated {rows_affected} rows")

# Verify the update
print("Verifying update...")
cursor.execute("SELECT id, username, heygen_voice_id FROM users WHERE username = ?", ("testuser",))
user = cursor.fetchone()
if user:
    print(f"User {user[1]} (ID: {user[0]}) now has voice ID: {user[2]}")
else:
    print("Failed to find testuser in database")

conn.close()
print("Done!")
