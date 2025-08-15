#!/usr/bin/env python3
"""
Check users table schema for missing notification columns
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def check_users_schema():
    """Check if users table has notification columns"""
    
    database_url = os.getenv("DATABASE_URL")
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    try:
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Get users table columns
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'users'
            ORDER BY ordinal_position
        """)
        
        columns = cursor.fetchall()
        
        print("📋 Users table columns:")
        for col in columns:
            print(f"   {col[0]} ({col[1]}) - Nullable: {col[2]}")
        
        # Check for notification columns
        required_cols = ['phone_number', 'country_code', 'sms_notifications', 'is_premium']
        existing_cols = [col[0] for col in columns]
        
        missing_cols = []
        for col in required_cols:
            if col not in existing_cols:
                missing_cols.append(col)
        
        if missing_cols:
            print(f"\n❌ Missing notification columns: {missing_cols}")
            print(f"\n🔧 SQL to add missing columns:")
            
            for col in missing_cols:
                if col == 'phone_number':
                    print(f"ALTER TABLE users ADD COLUMN {col} VARCHAR(20);")
                elif col == 'country_code':
                    print(f"ALTER TABLE users ADD COLUMN {col} VARCHAR(5);")
                elif col == 'sms_notifications':
                    print(f"ALTER TABLE users ADD COLUMN {col} BOOLEAN DEFAULT FALSE;")
                elif col == 'is_premium':
                    print(f"ALTER TABLE users ADD COLUMN {col} BOOLEAN DEFAULT FALSE;")
        else:
            print(f"\n✅ All notification columns exist!")
        
        cursor.close()
        conn.close()
        
        return missing_cols
        
    except Exception as e:
        print(f"❌ Error checking schema: {e}")
        return None

if __name__ == "__main__":
    print("🔍 Checking users table schema for notification columns...")
    missing = check_users_schema()
    
    if missing:
        print(f"\n🚨 Add missing columns to fix notifications!")
    else:
        print(f"\n🎉 Schema is ready for notifications!")
