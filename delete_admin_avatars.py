import sqlite3

# Path to your database file (adjust if needed)
db_path = 'myavatar.db'  # Use 'myavatar.db' instead of 'portal.db'

admin_user_id = 1  # Change if your admin has a different ID

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Delete avatars for admin user
cur.execute("DELETE FROM avatars WHERE user_id = ?", (admin_user_id,))
conn.commit()

print("Deleted all avatars for admin user (user_id = {})".format(admin_user_id))

conn.close()