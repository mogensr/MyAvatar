#!/usr/bin/env python3
"""
Check avatar_id column schema and constraints in videos table
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor

def check_avatar_id_schema():
    """Check the current schema for avatar_id column"""
    try:
        DATABASE_URL = os.getenv('DATABASE_URL')
        if not DATABASE_URL:
            print("❌ DATABASE_URL not found in environment")
            return
        
        print("🔍 Checking avatar_id column schema...")
        
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Check avatar_id column details
        print("\n📋 AVATAR_ID COLUMN DETAILS:")
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'videos' AND column_name = 'avatar_id'
        """)
        
        result = cur.fetchone()
        if result:
            print(f"   Column: {result['column_name']}")
            print(f"   Type: {result['data_type']}")
            print(f"   Nullable: {result['is_nullable']}")
            print(f"   Default: {result['column_default']}")
        else:
            print("   ❌ avatar_id column not found")
            return
        
        # 2. Check for foreign key constraints
        print("\n🔗 FOREIGN KEY CONSTRAINTS:")
        cur.execute("""
            SELECT tc.constraint_name, tc.table_name, kcu.column_name, 
                   ccu.table_name AS foreign_table_name,
                   ccu.column_name AS foreign_column_name 
            FROM information_schema.table_constraints AS tc 
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
              AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' 
              AND tc.table_name='videos' 
              AND kcu.column_name='avatar_id'
        """)
        
        fk_result = cur.fetchone()
        if fk_result:
            print(f"   Foreign Key: {fk_result['constraint_name']}")
            print(f"   References: {fk_result['foreign_table_name']}.{fk_result['foreign_column_name']}")
        else:
            print("   ✅ No foreign key constraints on avatar_id")
        
        # 3. Check how many videos currently have NULL or empty avatar_id
        print("\n📊 CURRENT DATA ANALYSIS:")
        cur.execute("SELECT COUNT(*) as total_videos FROM videos")
        total = cur.fetchone()['total_videos']
        print(f"   Total videos: {total}")
        
        cur.execute("SELECT COUNT(*) as null_avatar_id FROM videos WHERE avatar_id IS NULL")
        null_count = cur.fetchone()['null_avatar_id']
        print(f"   Videos with NULL avatar_id: {null_count}")
        
        cur.execute("SELECT COUNT(*) as empty_avatar_id FROM videos WHERE avatar_id = ''")
        empty_count = cur.fetchone()['empty_avatar_id']
        print(f"   Videos with empty avatar_id: {empty_count}")
        
        # 4. Check what avatar_id values are being used
        print("\n🎭 AVATAR_ID VALUES IN USE:")
        cur.execute("""
            SELECT avatar_id, COUNT(*) as count 
            FROM videos 
            WHERE avatar_id IS NOT NULL AND avatar_id != ''
            GROUP BY avatar_id 
            ORDER BY count DESC 
            LIMIT 10
        """)
        
        avatar_usage = cur.fetchall()
        if avatar_usage:
            for row in avatar_usage:
                print(f"   '{row['avatar_id']}': {row['count']} videos")
        else:
            print("   No avatar_id values found")
        
        # 5. Check if there are any background replacement videos
        print("\n🎬 BACKGROUND REPLACEMENT VIDEOS:")
        cur.execute("""
            SELECT COUNT(*) as bg_videos 
            FROM videos 
            WHERE title ILIKE '%background%' OR title ILIKE '%backgroundfx%'
        """)
        
        bg_count = cur.fetchone()['bg_videos']
        print(f"   Background replacement videos: {bg_count}")
        
        conn.close()
        
        # 6. Assessment and recommendation
        print("\n💡 ASSESSMENT:")
        if result['is_nullable'] == 'NO':
            print("   ❌ avatar_id is currently NOT NULL")
            print("   🔧 RECOMMENDATION: Make avatar_id nullable for background replacement videos")
            
            if fk_result:
                print("   ⚠️  WARNING: Foreign key constraint exists - need to check impact")
            else:
                print("   ✅ No foreign key constraints - safe to make nullable")
                
        else:
            print("   ✅ avatar_id is already nullable")
        
        return result, fk_result
        
    except Exception as e:
        print(f"❌ Error checking schema: {e}")
        return None, None

if __name__ == "__main__":
    check_avatar_id_schema()
