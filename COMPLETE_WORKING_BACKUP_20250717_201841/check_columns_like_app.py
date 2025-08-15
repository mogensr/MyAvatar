#!/usr/bin/env python3
"""
Check columns using the EXACT same database connection as the running app
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

# Import the app's database connection
from app.db.database import get_db_connection, USE_POSTGRES

def main():
    try:
        print(f"🔍 Using PostgreSQL: {USE_POSTGRES}")
        print(f"🔍 Database URL exists: {bool(os.getenv('DATABASE_URL'))}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        print("\n📋 ACTUAL COLUMNS IN USERS TABLE (using app's connection):")
        print("=" * 60)
        
        if USE_POSTGRES:
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' 
                ORDER BY ordinal_position;
            """)
        else:
            cursor.execute("PRAGMA table_info(users)")
        
        columns = cursor.fetchall()
        
        if USE_POSTGRES:
            for i, (col_name,) in enumerate(columns, 1):
                print(f"  {i:2d}. {col_name}")
        else:
            for i, row in enumerate(columns, 1):
                print(f"  {i:2d}. {row[1]}")  # SQLite PRAGMA returns (cid, name, type, ...)
        
        # Check specifically for heygen_voice_id
        print(f"\n🔍 Checking for heygen_voice_id column...")
        if USE_POSTGRES:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'users' AND column_name = 'heygen_voice_id'
                );
            """)
            exists = cursor.fetchone()[0]
        else:
            cursor.execute("PRAGMA table_info(users)")
            columns = cursor.fetchall()
            exists = any(row[1] == 'heygen_voice_id' for row in columns)
        
        print(f"   heygen_voice_id exists: {exists}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
