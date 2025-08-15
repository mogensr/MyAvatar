#!/usr/bin/env python3
"""
Check what columns actually exist in the production videos table
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def check_columns():
    """Check actual column names in videos table"""
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not found in environment")
        return
    
    print(f"🔗 Connecting to database...")
    print(f"   URL: {database_url[:50]}...")
    
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get all columns in videos table
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'videos'
            ORDER BY ordinal_position;
        """)
        
        columns = cur.fetchall()
        
        print(f"\n📊 VIDEOS TABLE COLUMNS ({len(columns)} total):")
        print("-" * 60)
        
        video_related = []
        for col in columns:
            col_name = col['column_name']
            print(f"  {col_name:25} | {col['data_type']:15} | {'NULL' if col['is_nullable'] == 'YES' else 'NOT NULL'}")
            
            # Look for video-related columns
            if 'video' in col_name.lower():
                video_related.append(col_name)
        
        print(f"\n🎬 VIDEO-RELATED COLUMNS:")
        if video_related:
            for col in video_related:
                print(f"  ✅ {col}")
        else:
            print("  ❌ No video-related columns found!")
        
        # Check if we have any data
        cur.execute("SELECT COUNT(*) as count FROM videos WHERE status = 'completed'")
        count = cur.fetchone()['count']
        print(f"\n📈 COMPLETED VIDEOS: {count}")
        
        if count > 0:
            # Show sample data
            cur.execute("SELECT * FROM videos WHERE status = 'completed' LIMIT 1")
            sample = cur.fetchone()
            print(f"\n🔍 SAMPLE VIDEO RECORD:")
            for key, value in sample.items():
                if value is not None:
                    value_str = str(value)[:100] + ('...' if len(str(value)) > 100 else '')
                    print(f"  {key:20}: {value_str}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_columns()
