import sqlite3

conn = sqlite3.connect("myavatar.db")
cur = conn.cursor()

# Check users table
print("USERS TABLE SCHEMA:")
cur.execute("PRAGMA table_info(users)")
for col in cur.fetchall():
    print(f"  {col}")

# Check avatars table  
print("\nAVATARS TABLE SCHEMA:")
cur.execute("PRAGMA table_info(avatars)")
for col in cur.fetchall():
    print(f"  {col}")

# Check videos table
print("\nVIDEOS TABLE SCHEMA:")
cur.execute("PRAGMA table_info(videos)")
for col in cur.fetchall():
    print(f"  {col}")

# Check if there are any users
print("\nUSERS IN DATABASE:")
cur.execute("SELECT id, username, email, is_admin FROM users")
for user in cur.fetchall():
    print(f"  {user}")

conn.close()
