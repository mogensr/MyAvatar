#!/usr/bin/env python3
"""
Simple diagnostic to find the exact avatar_id issue
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor

def simple_avatar_diagnostic():
    """Find the exact issue with avatar_id saving"""
    try:
        DATABASE_URL = os.getenv('DATABASE_URL')
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        print("🔍 SIMPLE AVATAR_ID DIAGNOSTIC")
        print("=" * 40)
        
        # 1. Check if avatar_id is nullable
        cur.execute("""
            SELECT is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'videos' AND column_name = 'avatar_id'
        """)
        
        result = cur.fetchone()
        if result:
            nullable = result['is_nullable']
            print(f"avatar_id nullable: {nullable}")
        else:
            print("❌ avatar_id column not found")
            return
        
        # 2. Test INSERT with NULL
        print("\n🧪 Testing INSERT with NULL avatar_id...")
        try:
            cur.execute("""
                INSERT INTO videos (user_id, title, video_path, input_url, avatar_id) 
                VALUES (1, 'TEST_NULL', 'test', 'test', NULL) 
                RETURNING id
            """)
            result = cur.fetchone()
            test_id = result['id']
            print(f"✅ SUCCESS: ID {test_id}")
            
            # Clean up
            cur.execute("DELETE FROM videos WHERE id = %s", (test_id,))
            conn.commit()
            
        except Exception as e:
            print(f"❌ FAILED: {e}")
            conn.rollback()
        
        # 3. Test INSERT without avatar_id
        print("\n🧪 Testing INSERT without avatar_id column...")
        try:
            cur.execute("""
                INSERT INTO videos (user_id, title, video_path, input_url) 
                VALUES (1, 'TEST_NO_AVATAR', 'test', 'test') 
                RETURNING id
            """)
            result = cur.fetchone()
            test_id = result['id']
            print(f"✅ SUCCESS: ID {test_id}")
            
            # Clean up
            cur.execute("DELETE FROM videos WHERE id = %s", (test_id,))
            conn.commit()
            
        except Exception as e:
            print(f"❌ FAILED: {e}")
            conn.rollback()
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Diagnostic failed: {e}")

if __name__ == "__main__":
    simple_avatar_diagnostic()
