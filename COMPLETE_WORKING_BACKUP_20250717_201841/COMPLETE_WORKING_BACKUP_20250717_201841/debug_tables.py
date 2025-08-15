#!/usr/bin/env python3
"""
Debug script to check database tables and avatar data
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor

def debug_tables():
    """Debug database tables and avatar data"""
    
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        print("❌ DATABASE_URL not found in environment variables")
        return
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check what tables exist
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE '%avatar%'
            ORDER BY table_name
        """)
        tables = cursor.fetchall()
        
        print("🗃️ AVATAR-RELATED TABLES:")
        print("=" * 40)
        for table in tables:
            print(f"   📋 {table['table_name']}")
        
        # Check avatars table structure
        print("\n🔍 AVATARS TABLE STRUCTURE:")
        print("=" * 40)
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'avatars'
            ORDER BY ordinal_position
        """)
        columns = cursor.fetchall()
        for col in columns:
            print(f"   📝 {col['column_name']} ({col['data_type']}) - Nullable: {col['is_nullable']}")
        
        # Check user_avatars table structure if it exists
        print("\n🔍 USER_AVATARS TABLE STRUCTURE:")
        print("=" * 40)
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'user_avatars'
            ORDER BY ordinal_position
        """)
        columns = cursor.fetchall()
        if columns:
            for col in columns:
                print(f"   📝 {col['column_name']} ({col['data_type']}) - Nullable: {col['is_nullable']}")
        else:
            print("   ❌ user_avatars table does not exist")
        
        # Check actual avatar data
        print("\n🎭 SAMPLE AVATAR DATA:")
        print("=" * 40)
        cursor.execute("SELECT * FROM avatars LIMIT 3")
        avatars = cursor.fetchall()
        
        for i, avatar in enumerate(avatars, 1):
            print(f"\n📋 Avatar #{i}:")
            for key, value in avatar.items():
                if key == 'heygen_data' and value:
                    print(f"   {key}: {str(value)[:100]}...")
                else:
                    print(f"   {key}: {value}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_tables()
