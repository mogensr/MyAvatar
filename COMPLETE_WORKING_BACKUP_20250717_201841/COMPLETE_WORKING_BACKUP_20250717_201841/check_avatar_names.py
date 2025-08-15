import sqlite3

conn = sqlite3.connect('C:/Users/mogen/Projects/python/CHATGPT/MyAvatar/myavatar.db')
cursor = conn.cursor()

print("=== Avatar names in database ===")
cursor.execute('SELECT avatar_name, avatar_id FROM user_avatars LIMIT 10')
results = cursor.fetchall()

for row in results:
    print(f'Name: "{row[0]}", ID: {row[1]}')

conn.close()
