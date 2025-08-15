#!/usr/bin/env python3
"""
Database Migration: Add missing 'description' column to videos table
This fixes the error: column "description" of relation "videos" does not exist
"""
import os
import sys
from datetime import datetime

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

try:
    from db.database import execute_query, get_db_connection, USE_POSTGRES
except ImportError:
    try:
        from app.db.database import execute_query, get_db_connection, USE_POSTGRES
    except ImportError:
        print("❌ Could not import database module")
        sys.exit(1)

def check_column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    try:
        if USE_POSTGRES:
            # PostgreSQL way to check if column exists
            check_query = """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = %s AND column_name = %s
            """
            result = execute_query(check_query, (table_name, column_name), fetch_one=True)
        else:
            # SQLite way to check if column exists
            check_query = f"PRAGMA table_info({table_name})"
            columns = execute_query(check_query, fetch_all=True)
            result = any(col['name'] == column_name for col in columns) if columns else False
            return result
        
        return result is not None
        
    except Exception as e:
        print(f"❌ Error checking if column exists: {e}")
        return False

def add_description_column():
    """Add description column to videos table if it doesn't exist"""
    print("🔄 Database Migration: Adding 'description' column to videos table")
    print("=" * 60)
    
    try:
        # Check if description column already exists
        if check_column_exists('videos', 'description'):
            print("✅ 'description' column already exists in videos table")
            return True
        
        print("📋 Adding 'description' column to videos table...")
        
        # Add the missing column
        alter_query = "ALTER TABLE videos ADD COLUMN description TEXT"
        execute_query(alter_query)
        
        print("✅ Successfully added 'description' column to videos table")
        
        # Verify the column was added
        if check_column_exists('videos', 'description'):
            print("✅ Verified: 'description' column now exists")
            return True
        else:
            print("❌ Warning: Could not verify column was added")
            return False
            
    except Exception as e:
        print(f"❌ Error adding description column: {e}")
        return False

def main():
    print("🔧 MyAvatar Database Migration Tool")
    print("=" * 60)
    print(f"Database Type: {'PostgreSQL' if USE_POSTGRES else 'SQLite'}")
    print(f"Migration: Add 'description' column to videos table")
    print(f"Timestamp: {datetime.now()}")
    print()
    
    try:
        # Test database connection
        conn = get_db_connection()
        conn.close()
        print("✅ Database connection successful")
        
        # Run migration
        success = add_description_column()
        
        if success:
            print("\n🎉 Migration completed successfully!")
            print("   Both voice-to-video and text-to-video should now work properly.")
        else:
            print("\n❌ Migration failed!")
            print("   Please check the error messages above.")
            
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("   Please check your database configuration.")

if __name__ == "__main__":
    main()
