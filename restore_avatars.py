import sqlite3 
from app.db.database import execute_query 
conn = sqlite3.connect('myavatar_backup.db') 
conn.row_factory = sqlite3.Row 
avatars = conn.execute('SELECT * FROM user_avatars WHERE user_id = 2').fetchall() 
conn.close() 
for avatar in avatars: 
    execute_query('INSERT INTO user_avatars (user_id, avatar_id, avatar_name, avatar_image_url, is_default) VALUES (?, ?, ?, ?, ?)', (avatar['user_id'], avatar['avatar_id'], avatar['avatar_name'], avatar['avatar_image_url'], avatar['is_default'])) 
print(f'Restored {len(avatars)} avatars!') 
