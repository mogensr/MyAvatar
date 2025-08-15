#!/usr/bin/env python3
"""
Simple check: Do both video_path and video_url columns exist?
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def simple_check():
    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    cur = conn.cursor()
    
    # Check for both columns
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'videos' 
        AND column_name IN ('video_path', 'video_url')
        ORDER BY column_name
    """)
    
    columns = [row[0] for row in cur.fetchall()]
    
    print("VIDEO COLUMNS FOUND:")
    for col in columns:
        print(f"  ✅ {col}")
    
    if len(columns) == 2:
        print("\n🚨 BOTH COLUMNS EXIST!")
        
        # Check which has data
        cur.execute("SELECT COUNT(*) FROM videos WHERE video_path IS NOT NULL")
        path_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM videos WHERE video_url IS NOT NULL") 
        url_count = cur.fetchone()[0]
        
        print(f"Records with video_path: {path_count}")
        print(f"Records with video_url:  {url_count}")
        
    elif len(columns) == 1:
        print(f"\n✅ Only {columns[0]} exists")
    else:
        print("\n❌ No video columns found!")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    simple_check()
