#!/usr/bin/env python3
"""
Debug script to check production database tables and avatar data
"""
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

def connect_to_production_db():
    """Connect to production PostgreSQL database"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        print("Please set it to your Railway PostgreSQL connection string")
        return None
    
    try:
        conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        print("✅ Connected to production database")
        return conn
    except Exception as e:
        print(f"❌ Failed to connect to production database: {e}")
        return None

def check_tables(conn):
    """Check what tables exist in the database"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT table_name, 
                   (SELECT COUNT(*) FROM information_schema.columns 
                    WHERE table_name = t.table_name) as column_count
            FROM information_schema.tables t
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        
        tables = cursor.fetchall()
        print(f"\n📊 Found {len(tables)} tables in production database:")
        for table in tables:
            print(f"  - {table['table_name']} ({table['column_count']} columns)")
        
        cursor.close()
        return [table['table_name'] for table in tables]
        
    except Exception as e:
        print(f"❌ Error checking tables: {e}")
        return []

def check_user_avatars_table(conn):
    """Check the user_avatars table structure and data"""
    try:
        cursor = conn.cursor()
        
        # Check if user_avatars table exists
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'user_avatars'
            ORDER BY ordinal_position;
        """)
        
        columns = cursor.fetchall()
        if not columns:
            print("❌ user_avatars table does not exist")
            return
            
        print(f"\n🏗️  user_avatars table structure:")
        for col in columns:
            print(f"  - {col['column_name']}: {col['data_type']}")
        
        # Check data in user_avatars table
        cursor.execute("SELECT COUNT(*) as total FROM user_avatars;")
        total = cursor.fetchone()['total']
        print(f"\n📈 Total avatars in user_avatars table: {total}")
        
        if total > 0:
            cursor.execute("""
                SELECT user_id, avatar_name, avatar_id, 
                       CASE WHEN avatar_image_url IS NOT NULL THEN 'HAS_IMAGE' ELSE 'NO_IMAGE' END as image_status,
                       created_at
                FROM user_avatars 
                ORDER BY created_at DESC 
                LIMIT 5;
            """)
            
            sample_avatars = cursor.fetchall()
            print(f"\n🎭 Sample avatars (latest 5):")
            for avatar in sample_avatars:
                print(f"  - User {avatar['user_id']}: {avatar['avatar_name']} (ID: {avatar['avatar_id']}) - {avatar['image_status']}")
        
        cursor.close()
        
    except Exception as e:
        print(f"❌ Error checking user_avatars table: {e}")

def check_avatars_table(conn):
    """Check if there's also an 'avatars' table"""
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'avatars'
            ORDER BY ordinal_position;
        """)
        
        columns = cursor.fetchall()
        if not columns:
            print("ℹ️  No 'avatars' table found (this is expected)")
            return
            
        print(f"\n🏗️  avatars table structure:")
        for col in columns:
            print(f"  - {col['column_name']}: {col['data_type']}")
        
        cursor.execute("SELECT COUNT(*) as total FROM avatars;")
        total = cursor.fetchone()['total']
        print(f"📈 Total records in avatars table: {total}")
        
        cursor.close()
        
    except Exception as e:
        print(f"ℹ️  avatars table check: {e}")

def main():
    print("🔍 MyAvatar Production Database Debug")
    print("=" * 50)
    
    # Connect to database
    conn = connect_to_production_db()
    if not conn:
        return
    
    try:
        # Check all tables
        tables = check_tables(conn)
        
        # Check user_avatars table specifically
        check_user_avatars_table(conn)
        
        # Check if avatars table exists
        check_avatars_table(conn)
        
    finally:
        conn.close()
        print("\n✅ Database connection closed")

if __name__ == "__main__":
    main()
