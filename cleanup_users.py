from app.db.database import execute_query

# List of usernames to DELETE
users_to_delete = ['emergency_admin', 'admin2', 'adminfix', 'admin', 'RyeM', 'MOGENS']

print('🗑️ DELETING UNWANTED USERS:')
print('=' * 50)

for username in users_to_delete:
    user = execute_query('SELECT id, username, email FROM users WHERE username = ?', (username,), fetch_one=True)
    if user:
        user_id = user['id']
        print(f'Deleting user: {username} (ID: {user_id})')
        execute_query('DELETE FROM videos WHERE user_id = ?', (user_id,))
        execute_query('DELETE FROM user_avatars WHERE user_id = ?', (user_id,))
        execute_query('DELETE FROM user_images WHERE user_id = ?', (user_id,))
        execute_query('DELETE FROM user_voices WHERE user_id = ?', (user_id,))
        execute_query('DELETE FROM users WHERE id = ?', (user_id,))
        print(f'✅ Deleted: {username}')
    else:
        print(f'❌ User not found: {username}')

print('\n👤 REMAINING USERS:')
print('=' * 50)
remaining_users = execute_query('SELECT username, email, is_admin FROM users', fetch_all=True)
for user in remaining_users:
    admin_status = '🔑 ADMIN' if user['is_admin'] else '👤 USER'
    print(f'{admin_status} | {user["username"]} | {user["email"]}')