import sqlite3

conn = sqlite3.connect('C:/Users/mogen/Projects/python/CHATGPT/MyAvatar/myavatar.db')
cursor = conn.cursor()

print("=== All users ===")
cursor.execute('SELECT id, username FROM users')
users = cursor.fetchall()
for user in users:
    print(f'User ID: {user[0]}, Username: {user[1]}')

print("\n=== Avatar data for each user ===")
for user in users:
    user_id = user[0]
    username = user[1]
    print(f'\n--- User: {username} (ID: {user_id}) ---')
    
    cursor.execute('SELECT avatar_name, avatar_id, avatar_image_url FROM user_avatars WHERE user_id = ?', (user_id,))
    avatars = cursor.fetchall()
    
    if avatars:
        for avatar in avatars:
            print(f'  Name: "{avatar[0]}"')
            print(f'  ID: {avatar[1]}')
            print(f'  Image: {avatar[2][:50]}...' if avatar[2] else '  Image: None')
            print()
    else:
        print('  No avatars found')

conn.close()
