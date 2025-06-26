#!/usr/bin/env python3
"""
Check what tables exist in the database
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.database import execute_query

def check_tables():
    print("🔍 Checking Database Tables")
    print("=" * 40)
    
    try:
        # Get all tables
        result = execute_query("SELECT name FROM sqlite_master WHERE type='table'", fetch_all=True)
        
        if result:
            print(f"📋 Found {len(result)} tables:")
            for row in result:
                table_name = row[0]
                print(f"  - {table_name}")
                
                # Get row count for each table
                try:
                    count_result = execute_query(f"SELECT COUNT(*) FROM {table_name}", fetch_one=True)
                    count = count_result[0] if count_result else 0
                    print(f"    ({count} rows)")
                except Exception as e:
                    print(f"    (Error counting: {e})")
        else:
            print("❌ No tables found!")
            
    except Exception as e:
        print(f"❌ Error checking tables: {e}")

if __name__ == "__main__":
    check_tables()
