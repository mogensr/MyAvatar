"""
Database Migration: Add missing columns to video_processing_jobs table
Run this to fix the schema mismatch
"""

import psycopg2
import os
from datetime import datetime

def run_migration():
    """Add missing columns to video_processing_jobs table"""
    
    # Database connection
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable not found")
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        print(f"🔧 Starting migration at {datetime.now()}")
        
        # First, let's check what columns currently exist
        print("📋 Checking current table structure...")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'video_processing_jobs'
            ORDER BY ordinal_position;
        """)
        
        existing_columns = cursor.fetchall()
        print("Current columns:")
        for col in existing_columns:
            print(f"  - {col[0]} ({col[1]}) {'NULL' if col[2] == 'YES' else 'NOT NULL'}")
        
        # Check if input_url already exists
        column_names = [col[0] for col in existing_columns]
        
        migrations_to_run = []
        
        if 'input_url' not in column_names:
            migrations_to_run.append(("input_url", "ALTER TABLE video_processing_jobs ADD COLUMN input_url TEXT;"))
        
        if 'input_type' not in column_names:
            migrations_to_run.append(("input_type", "ALTER TABLE video_processing_jobs ADD COLUMN input_type VARCHAR(50) DEFAULT 'file';"))
        
        if 'original_filename' not in column_names:
            migrations_to_run.append(("original_filename", "ALTER TABLE video_processing_jobs ADD COLUMN original_filename TEXT;"))
        
        if 'output_url' not in column_names:
            migrations_to_run.append(("output_url", "ALTER TABLE video_processing_jobs ADD COLUMN output_url TEXT;"))
            
        if 'file_size' not in column_names:
            migrations_to_run.append(("file_size", "ALTER TABLE video_processing_jobs ADD COLUMN file_size BIGINT;"))
        
        if not migrations_to_run:
            print("✅ All columns already exist! No migration needed.")
            return True
        
        # Run migrations
        print(f"\n🚀 Running {len(migrations_to_run)} migrations...")
        
        for col_name, sql in migrations_to_run:
            print(f"  Adding column: {col_name}")
            cursor.execute(sql)
            print(f"  ✅ {col_name} added successfully")
        
        # Commit all changes
        conn.commit()
        print(f"\n🎉 Migration completed successfully at {datetime.now()}")
        
        # Verify the changes
        print("\n📋 Updated table structure:")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'video_processing_jobs'
            ORDER BY ordinal_position;
        """)
        
        updated_columns = cursor.fetchall()
        for col in updated_columns:
            default_val = f" DEFAULT {col[3]}" if col[3] else ""
            print(f"  - {col[0]} ({col[1]}) {'NULL' if col[2] == 'YES' else 'NOT NULL'}{default_val}")
        
        return True
        
    except psycopg2.Error as e:
        print(f"❌ Database error: {e}")
        if conn:
            conn.rollback()
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        if conn:
            conn.rollback()
        return False
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    success = run_migration()
    if success:
        print("\n🎊 Ready to deploy! Your video processing should work now.")
    else:
        print("\n💥 Migration failed. Check the errors above.")
