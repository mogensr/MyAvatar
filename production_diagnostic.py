#!/usr/bin/env python3
"""
PRODUCTION DIAGNOSTIC: Find the REAL cause of avatar_id save issue
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor

def comprehensive_production_diagnostic():
    """Complete diagnostic of production database and environment"""
    try:
        DATABASE_URL = os.getenv('DATABASE_URL')
        if not DATABASE_URL:
            print("❌ No DATABASE_URL found")
            return
        
        print("🔍 COMPREHENSIVE PRODUCTION DIAGNOSTIC")
        print("=" * 50)
        
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. EXACT TABLE SCHEMA
        print("\n📋 EXACT VIDEOS TABLE SCHEMA:")
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default, character_maximum_length
            FROM information_schema.columns 
            WHERE table_name = 'videos'
            ORDER BY ordinal_position
        """)
        
        columns = cur.fetchall()
        for col in columns:
            nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
            default = f" DEFAULT {col['column_default']}" if col['column_default'] else ""
            length = f"({col['character_maximum_length']})" if col['character_maximum_length'] else ""
            print(f"   {col['column_name']} {col['data_type']}{length} {nullable}{default}")
        
        # 2. CHECK FOR CONSTRAINTS
        print("\n🔒 TABLE CONSTRAINTS:")
        cur.execute("""
            SELECT tc.constraint_name, tc.constraint_type, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name
            WHERE tc.table_name = 'videos'
            ORDER BY tc.constraint_type, kcu.column_name
        """)
        
        constraints = cur.fetchall()
        if constraints:
            for constraint in constraints:
                print(f"   {constraint['constraint_type']}: {constraint['constraint_name']} on {constraint['column_name']}")
        else:
            print("   No constraints found")
        
        # 3. CHECK FOR TRIGGERS
        print("\n⚡ TRIGGERS:")
        cur.execute("""
            SELECT trigger_name, event_manipulation, action_timing, action_statement
            FROM information_schema.triggers 
            WHERE event_object_table = 'videos'
        """)
        
        triggers = cur.fetchall()
        if triggers:
            for trigger in triggers:
                print(f"   {trigger['trigger_name']}: {trigger['event_manipulation']} {trigger['action_timing']}")
                print(f"      Action: {trigger['action_statement'][:100]}...")
        else:
            print("   No triggers found")
        
        # 4. TEST ACTUAL INSERT
        print("\n🧪 TESTING ACTUAL INSERT OPERATIONS:")
        
        # Test 1: Insert with explicit NULL avatar_id
        print("\n   Test 1: INSERT with explicit NULL avatar_id")
        try:
            cur.execute("""
                INSERT INTO videos (user_id, title, video_path, input_url, avatar_id) 
                VALUES (1, 'TEST: Explicit NULL', 'test_url_1', 'test_job_1', NULL) 
                RETURNING id, avatar_id
            """)
            result = cur.fetchone()
            print(f"   ✅ SUCCESS: ID={result['id']}, avatar_id={result['avatar_id']}")
            test1_id = result['id']
        except Exception as e:
            print(f"   ❌ FAILED: {e}")
            test1_id = None
        
        # Test 2: Insert without avatar_id column
        print("\n   Test 2: INSERT without avatar_id column")
        try:
            cur.execute("""
                INSERT INTO videos (user_id, title, video_path, input_url) 
                VALUES (1, 'TEST: No avatar_id column', 'test_url_2', 'test_job_2') 
                RETURNING id, avatar_id
            """)
            result = cur.fetchone()
            print(f"   ✅ SUCCESS: ID={result['id']}, avatar_id={result['avatar_id']}")
            test2_id = result['id']
        except Exception as e:
            print(f"   ❌ FAILED: {e}")
            test2_id = None
        
        # Test 3: Insert with empty string avatar_id
        print("\n   Test 3: INSERT with empty string avatar_id")
        try:
            cur.execute("""
                INSERT INTO videos (user_id, title, video_path, input_url, avatar_id) 
                VALUES (1, 'TEST: Empty string', 'test_url_3', 'test_job_3', '') 
                RETURNING id, avatar_id
            """)
            result = cur.fetchone()
            print(f"   ✅ SUCCESS: ID={result['id']}, avatar_id='{result['avatar_id']}'")
            test3_id = result['id']
        except Exception as e:
            print(f"   ❌ FAILED: {e}")
            test3_id = None
        
        # 5. CHECK CURRENT DATA
        print("\n📊 CURRENT AVATAR_ID DATA:")
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(avatar_id) as non_null_avatar_id,
                COUNT(*) - COUNT(avatar_id) as null_avatar_id
            FROM videos
        """)
        
        stats = cur.fetchone()
        print(f"   Total videos: {stats['total']}")
        print(f"   Non-NULL avatar_id: {stats['non_null_avatar_id']}")
        print(f"   NULL avatar_id: {stats['null_avatar_id']}")
        
        # 6. SAMPLE DATA
        print("\n📝 SAMPLE AVATAR_ID VALUES:")
        cur.execute("""
            SELECT avatar_id, COUNT(*) as count
            FROM videos 
            GROUP BY avatar_id 
            ORDER BY count DESC 
            LIMIT 5
        """)
        
        samples = cur.fetchall()
        for sample in samples:
            avatar_val = sample['avatar_id'] if sample['avatar_id'] is not None else "NULL"
            print(f"   '{avatar_val}': {sample['count']} videos")
        
        # Clean up test records
        print("\n🧹 CLEANING UP TEST RECORDS...")
        for test_id in [test1_id, test2_id, test3_id]:
            if test_id:
                cur.execute("DELETE FROM videos WHERE id = %s", (test_id,))
                print(f"   Deleted test record ID: {test_id}")
        
        conn.commit()
        conn.close()
        
        print("\n" + "=" * 50)
        print("🎯 DIAGNOSTIC COMPLETE")
        
    except Exception as e:
        print(f"❌ Diagnostic failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    comprehensive_production_diagnostic()
