#!/usr/bin/env python3
"""
Check actual column names in the videos table
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

# Import the app's database connection
from app.db.database import get_db_connection, USE_POSTGRES
import psycopg2.extras

def main():
    try:
        print(f"🔍 Using PostgreSQL: {USE_POSTGRES}")
        print(f"🔍 Database URL exists: {bool(os.getenv('DATABASE_URL'))}")
        
        conn = get_db_connection()
        
        if USE_POSTGRES:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            cursor = conn.cursor()
        
        print("\n📋 ACTUAL COLUMNS IN VIDEOS TABLE:")
        print("=" * 50)
        
        if USE_POSTGRES:
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'videos' 
                ORDER BY ordinal_position;
            """)
            columns = cursor.fetchall()
            
            for i, row in enumerate(columns, 1):
                nullable = "NULL" if row['is_nullable'] == 'YES' else "NOT NULL"
                print(f"  {i:2d}. {row['column_name']:<20} ({row['data_type']}) {nullable}")
        else:
            cursor.execute("PRAGMA table_info(videos)")
            columns = cursor.fetchall()
            for i, row in enumerate(columns, 1):
                print(f"  {i:2d}. {row[1]}")  # SQLite PRAGMA returns (cid, name, type, ...)
        
        print(f"\n🔍 Checking for specific video URL columns...")
        if USE_POSTGRES:
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'videos' 
                AND column_name IN ('video_url', 'video_path')
                ORDER BY column_name;
            """)
            url_columns = cursor.fetchall()
            
            if url_columns:
                print("   Found video URL columns:")
                for col in url_columns:
                    print(f"     ✅ {col['column_name']}")
            else:
                print("   ❌ No video_url or video_path columns found")
        
        # Also check a sample video record to see what data is available
        print(f"\n🎬 Sample video record (first 1):")
        print("=" * 50)
        
        cursor.execute("SELECT * FROM videos LIMIT 1")
        sample = cursor.fetchone()
        
        if sample:
            if USE_POSTGRES:
                for key, value in sample.items():
                    print(f"   {key}: {value}")
            else:
                # For SQLite, we need column names
                cursor.execute("PRAGMA table_info(videos)")
                col_info = cursor.fetchall()
                for i, col in enumerate(col_info):
                    print(f"   {col[1]}: {sample[i] if i < len(sample) else 'N/A'}")
        else:
            print("   No video records found")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
