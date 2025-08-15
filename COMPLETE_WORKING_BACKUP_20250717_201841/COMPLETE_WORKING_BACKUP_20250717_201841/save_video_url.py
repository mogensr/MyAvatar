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
    # Save URL to file
    with open('video_url.txt', 'w') as f:
        f.write(f"Video ID: {video['id']}\n")
        f.write(f"Title: {video['title']}\n")
        f.write(f"URL: {video['video_url']}\n")
    
    print(f"Video ID: {video['id']}")
    print(f"Title: {video['title']}")
    print(f"URL length: {len(video['video_url'])} characters")
    print("Full URL saved to video_url.txt")
else:
    print("No video found")
