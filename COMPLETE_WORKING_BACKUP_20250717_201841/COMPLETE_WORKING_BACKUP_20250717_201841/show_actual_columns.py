#!/usr/bin/env python3
"""
Just show the actual column names in the users table
"""
import os
import psycopg2
from dotenv import load_dotenv
load_dotenv()

def main():
    try:
        database_url = os.getenv('DATABASE_URL')
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        print("📋 ACTUAL COLUMNS IN USERS TABLE:")
        print("=" * 50)
        
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            ORDER BY ordinal_position;
        """)
        
        columns = cursor.fetchall()
        for i, (col_name,) in enumerate(columns, 1):
            print(f"  {i:2d}. {col_name}")
        
        print("\n📋 ACTUAL COLUMNS IN USER_AVATARS TABLE:")
        print("=" * 50)
        
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'user_avatars' 
            ORDER BY ordinal_position;
        """)
        
        avatar_columns = cursor.fetchall()
        for i, (col_name,) in enumerate(avatar_columns, 1):
            print(f"  {i:2d}. {col_name}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
