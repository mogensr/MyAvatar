#!/usr/bin/env python3
"""
Check if BOTH video_path and video_url columns exist in the database
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def check_both_columns():
    """Check if both video_path and video_url columns exist"""
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not found in environment")
        return
    
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get ALL columns in videos table
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'videos'
            ORDER BY ordinal_position;
        """)
        
        all_columns = cur.fetchall()
        
        print(f"🔍 ALL COLUMNS in 'videos' table ({len(all_columns)} total):")
        print("-" * 70)
        
        video_path_exists = False
        video_url_exists = False
        
        for col in all_columns:
            col_name = col['column_name']
            print(f"  {col_name:25} | {col['data_type']:15} | {'NULL' if col['is_nullable'] == 'YES' else 'NOT NULL'}")
            
            if col_name == 'video_path':
                video_path_exists = True
            elif col_name == 'video_url':
                video_url_exists = True
        
        print(f"\n🎯 VIDEO COLUMN STATUS:")
        print(f"  video_path exists: {'✅ YES' if video_path_exists else '❌ NO'}")
        print(f"  video_url exists:  {'✅ YES' if video_url_exists else '❌ NO'}")
        
        if video_path_exists and video_url_exists:
            print(f"\n🚨 BOTH COLUMNS EXIST! Let's check their data:")
            
            # Check sample data from both columns
            cur.execute("""
                SELECT id, title, video_path, video_url
                FROM videos 
                WHERE status = 'completed'
                LIMIT 3
            """)
            
            samples = cur.fetchall()
            
            for i, sample in enumerate(samples, 1):
                print(f"\n📄 Sample {i}:")
                print(f"  ID: {sample['id']}")
                print(f"  Title: {sample['title'][:50]}...")
                print(f"  video_path: {'✅ HAS DATA' if sample['video_path'] else '❌ NULL'}")
                print(f"  video_url:  {'✅ HAS DATA' if sample['video_url'] else '❌ NULL'}")
                
                if sample['video_path']:
                    print(f"    video_path: {sample['video_path'][:80]}...")
                if sample['video_url']:
                    print(f"    video_url:  {sample['video_url'][:80]}...")
        
        elif video_path_exists:
            print(f"\n✅ Only video_path exists (as we thought originally)")
        elif video_url_exists:
            print(f"\n✅ Only video_url exists (after your migration)")
        else:
            print(f"\n❌ Neither column exists! Something is wrong.")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_both_columns()
