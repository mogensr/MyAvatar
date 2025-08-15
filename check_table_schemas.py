#!/usr/bin/env python3
"""
Check the schema of users and user_avatars tables
"""
import os
import psycopg2
from dotenv import load_dotenv
load_dotenv()

def main():
    try:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            print("❌ DATABASE_URL not found")
            return
        
        print("🔗 Connecting to database...")
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Check users table schema
        print("\n📋 USERS TABLE SCHEMA:")
        print("=" * 60)
        cursor.execute("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            ORDER BY ordinal_position;
        """)
        
        users_columns = cursor.fetchall()
        for col_name, data_type, nullable in users_columns:
            print(f"  📝 {col_name:<25} | {data_type:<15} | {'NULL' if nullable == 'YES' else 'NOT NULL'}")
        
        # Check user_avatars table schema
        print(f"\n📋 USER_AVATARS TABLE SCHEMA:")
        print("=" * 60)
        cursor.execute("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'user_avatars' 
            ORDER BY ordinal_position;
        """)
        
        avatars_columns = cursor.fetchall()
        for col_name, data_type, nullable in avatars_columns:
            print(f"  📝 {col_name:<25} | {data_type:<15} | {'NULL' if nullable == 'YES' else 'NOT NULL'}")
        
        # Sample data from users table
        print(f"\n👤 SAMPLE USERS DATA:")
        print("=" * 60)
        cursor.execute("SELECT id, username, email, is_admin FROM users LIMIT 3")
        users = cursor.fetchall()
        for user_id, username, email, is_admin in users:
            admin_status = "ADMIN" if is_admin else "USER"
            print(f"  {user_id:<3} | {username:<15} | {email:<25} | {admin_status}")
        
        # Sample data from user_avatars table
        print(f"\n🎭 SAMPLE USER_AVATARS DATA:")
        print("=" * 60)
        cursor.execute("SELECT id, user_id, avatar_id, avatar_name FROM user_avatars LIMIT 5")
        avatars = cursor.fetchall()
        for avatar_id, user_id, heygen_avatar_id, avatar_name in avatars:
            print(f"  {avatar_id:<3} | User:{user_id:<3} | {heygen_avatar_id:<20} | {avatar_name or 'No Name'}")
        
        cursor.close()
        conn.close()
        print("\n✅ Schema check complete!")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
