#!/usr/bin/env python3
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Connect to database
conn = psycopg2.connect(os.getenv('DATABASE_URL'), cursor_factory=RealDictCursor)
cur = conn.cursor()

# Get one completed video for user 3
cur.execute("""
    SELECT id, title, video_url
    FROM videos 
    WHERE user_id = 3 
    AND status = 'completed' 
    AND video_url IS NOT NULL 
    AND video_url != ''
    ORDER BY created_at DESC 
    LIMIT 1
""")

video = cur.fetchone()
conn.close()

if video:
    print(f"Video ID: {video['id']}")
    print(f"Title: {video['title']}")
    print()
    print("FULL URL:")
    print(video['video_url'])
else:
    print("No video found")
