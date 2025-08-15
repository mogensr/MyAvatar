"""
Migration: Fix input_url column and job_type constraint
Run this to properly add the missing column and fix constraints
"""

import psycopg2
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def run_migration():
    """Fix input_url column and job_type constraint"""
    
    # Database connection
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable not found")
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        print(f"🔧 Starting fix migration at {datetime.now()}")
        
        # Check current table structure
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
        
        column_names = [col[0] for col in existing_columns]
        
        # Check if input_url column exists
        if 'input_url' not in column_names:
            print("➕ Adding input_url column...")
            cursor.execute("ALTER TABLE video_processing_jobs ADD COLUMN input_url TEXT;")
            print("✅ input_url column added")
        else:
            print("✅ input_url column already exists")
        
        # Check for job_type constraint
        print("🔍 Checking job_type constraint...")
        cursor.execute("""
            SELECT constraint_name, check_clause
            FROM information_schema.check_constraints 
            WHERE constraint_schema = 'public' 
            AND constraint_name LIKE '%job_type%'
        """)
        
        constraints = cursor.fetchall()
        print("Current job_type constraints:")
        for constraint in constraints:
            print(f"  - {constraint[0]}: {constraint[1]}")
        
        # If there's a restrictive job_type constraint, drop it
        if constraints:
            for constraint_name, _ in constraints:
                print(f"🗑️ Dropping restrictive constraint: {constraint_name}")
                cursor.execute(f"ALTER TABLE video_processing_jobs DROP CONSTRAINT IF EXISTS {constraint_name};")
                print(f"✅ Dropped constraint: {constraint_name}")
        
        # Add a more flexible job_type constraint
        print("➕ Adding flexible job_type constraint...")
        cursor.execute("""
            ALTER TABLE video_processing_jobs 
            ADD CONSTRAINT flexible_job_type 
            CHECK (job_type IN (
                'background_replacement', 
                'local_background_replacement',
                'video_enhancement',
                'audio_processing',
                'format_conversion'
            ));
        """)
        print("✅ Added flexible job_type constraint")
        
        # Commit all changes
        conn.commit()
        print(f"\n🎉 Fix migration completed successfully at {datetime.now()}")
        
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
        print("\n🎊 Ready to test! Your video processing should work now.")
    else:
        print("\n💥 Migration failed. Check the errors above.")
