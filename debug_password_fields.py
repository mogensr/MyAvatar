#!/usr/bin/env python3
"""
Debug script to check password field names in the database
"""
import os
import psycopg2
from urllib.parse import urlparse

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

def main():
    try:
        # Connect to Railway dev database
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            print("❌ DATABASE_URL not found in environment")
            return
        
        print("🔗 Connecting to database...")
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Get table schema for users table
        print("\n📋 USERS TABLE SCHEMA:")
        print("=" * 50)
        cursor.execute("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            ORDER BY ordinal_position;
        """)
        
        columns = cursor.fetchall()
        for col_name, data_type, nullable in columns:
            print(f"  📝 {col_name:<20} | {data_type:<15} | {'NULL' if nullable == 'YES' else 'NOT NULL'}")
        
        # Check admin user specifically
        print(f"\n👤 ADMIN USER DATA:")
        print("=" * 50)
        cursor.execute("SELECT username, email, password_hash FROM users WHERE is_admin = true LIMIT 1")
        admin = cursor.fetchone()
        
        if admin:
            username, email, password_hash = admin
            print(f"  👤 Username: {username}")
            print(f"  📧 Email: {email}")
            print(f"  🔑 password_hash field: {'SET' if password_hash else 'NULL'}")
            
            # Show first 20 chars of password hash
            if password_hash:
                print(f"  🔍 password_hash preview: {password_hash[:20]}...")
        else:
            print("  ❌ No admin user found")
        
        cursor.close()
        conn.close()
        print("\n✅ Database check complete!")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
