#!/usr/bin/env python3
import os, psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(os.getenv('DATABASE_URL'), cursor_factory=RealDictCursor)
cur = conn.cursor()

# Check completed videos for user 3
cur.execute('SELECT id, title, status, video_url FROM videos WHERE user_id = 3 AND status = %s ORDER BY created_at DESC LIMIT 3', ('completed',))
videos = cur.fetchall()

print(f'Found {len(videos)} completed videos for user 3:')
for v in videos:
    has_url = bool(v['video_url'])
    print(f'  ID {v["id"]}: {v["title"]} - URL: {"YES" if has_url else "NO"}')
    if has_url:
        print(f'    URL: {v["video_url"][:50]}...')

conn.close()
