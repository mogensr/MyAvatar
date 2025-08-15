"""
Migration: Add missing output_url column
"""

import psycopg2
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def run_migration():
    """Add missing output_url column"""
    
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable not found")
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        print(f"🔧 Adding output_url column at {datetime.now()}")
        
        # Add output_url column if it doesn't exist
        cursor.execute("""
            ALTER TABLE video_processing_jobs 
            ADD COLUMN IF NOT EXISTS output_url TEXT;
        """)
        
        # Also add estimated_completion if missing
        cursor.execute("""
            ALTER TABLE video_processing_jobs 
            ADD COLUMN IF NOT EXISTS estimated_completion TIMESTAMP;
        """)
        
        conn.commit()
        print("✅ Added output_url and estimated_completion columns")
        
        # Verify columns exist
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'video_processing_jobs' 
            AND column_name IN ('output_url', 'estimated_completion')
        """)
        
        columns = [row[0] for row in cursor.fetchall()]
        print(f"📋 Verified columns: {columns}")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration error: {e}")
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
        print("🎊 output_url column added successfully!")
    else:
        print("💥 Migration failed.")
