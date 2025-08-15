#!/usr/bin/env python3
"""
Check the actual structure of the user_avatars table
"""
import os
import sys
from dotenv import load_dotenv

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.db.database import execute_query

# Load environment variables
load_dotenv()

def check_table_structure():
    """Check what columns exist in user_avatars table"""
    try:
        # Get table structure for PostgreSQL
        columns = execute_query(
            """SELECT column_name, data_type, is_nullable 
               FROM information_schema.columns 
               WHERE table_name = 'user_avatars' 
               ORDER BY ordinal_position""", 
            fetch_all=True
        )
        
        if not columns:
            print("❌ user_avatars table not found or no columns")
            return
        
        print("📋 user_avatars table structure:")
        print("-" * 50)
        for col in columns:
            col_dict = dict(col) if hasattr(col, 'keys') else col
            print(f"• {col_dict.get('column_name')} ({col_dict.get('data_type')}) - Nullable: {col_dict.get('is_nullable')}")
            
    except Exception as e:
        print(f"❌ Error checking table structure: {e}")

def check_sample_data():
    """Get a sample of what's actually in the table"""
    try:
        # Just get all columns with SELECT *
        sample = execute_query("SELECT * FROM user_avatars LIMIT 5", fetch_all=True)
        
        if not sample:
            print("\n❌ No data in user_avatars table")
            return
        
        print(f"\n📊 Sample data ({len(sample)} records):")
        print("-" * 50)
        
        for i, record in enumerate(sample, 1):
            record_dict = dict(record) if hasattr(record, 'keys') else record
            print(f"Record {i}:")
            for key, value in record_dict.items():
                print(f"  {key}: {value}")
            print("-" * 30)
            
    except Exception as e:
        print(f"❌ Error checking sample data: {e}")

if __name__ == "__main__":
    print("🔍 MyAvatar Table Structure Check")
    print("=" * 50)
    check_table_structure()
    check_sample_data()
