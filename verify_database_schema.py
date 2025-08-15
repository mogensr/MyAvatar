#!/usr/bin/env python3
"""
Verify database schema and add missing columns with IF NOT EXISTS
"""
import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
import psycopg2

# Load environment variables
load_dotenv()

def verify_and_fix_database_schema():
    """Verify database schema and add missing columns safely"""
    try:
        # Get database URL
        DATABASE_URL = os.getenv("DATABASE_URL")
        if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
            
        if not DATABASE_URL:
            print("❌ DATABASE_URL not found in environment variables")
            return False
            
        print(f"🔧 Connecting to database: {DATABASE_URL[:50]}...")
        
        # Connect to database
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cursor = conn.cursor()
        
        print("🔍 Checking current videos table schema...")
        
        # Get current table structure
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'videos'
            ORDER BY ordinal_position;
        """)
        
        columns = cursor.fetchall()
        column_names = [col[0] for col in columns]
        
        print(f"📋 Current videos table columns ({len(columns)} total):")
        for col in columns:
            print(f"  - {col[0]} ({col[1]}) {'NULL' if col[2] == 'YES' else 'NOT NULL'} {col[3] or ''}")
        
        # Add missing columns with IF NOT EXISTS
        missing_columns = []
        
        if 'completed_at' not in column_names:
            print("🔧 Adding completed_at column...")
            cursor.execute("ALTER TABLE videos ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP;")
            missing_columns.append('completed_at')
            print("✅ Added completed_at column!")
        else:
            print("ℹ️ completed_at column already exists")
        
        if 'updated_at' not in column_names:
            print("🔧 Adding updated_at column...")
            cursor.execute("ALTER TABLE videos ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();")
            missing_columns.append('updated_at')
            print("✅ Added updated_at column!")
        else:
            print("ℹ️ updated_at column already exists")
        
        # Verify final schema
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'videos' AND column_name IN ('completed_at', 'updated_at')
            ORDER BY column_name;
        """)
        
        timestamp_columns = cursor.fetchall()
        
        print(f"\n📋 Timestamp columns verification:")
        for col in timestamp_columns:
            print(f"  - {col[0]} ({col[1]}) {'NULL' if col[2] == 'YES' else 'NOT NULL'} {col[3] or ''}")
        
        # Test a simple UPDATE to verify it works
        print("\n🧪 Testing UPDATE query syntax...")
        
        # Get a sample video to test with
        cursor.execute("SELECT heygen_video_id FROM videos LIMIT 1")
        sample_video = cursor.fetchone()
        
        if sample_video:
            test_video_id = sample_video[0]
            print(f"🔍 Testing with video ID: {test_video_id}")
            
            # Test the exact UPDATE query from webhook
            test_query = """
                UPDATE videos 
                SET status = 'completed', 
                    video_path = %s,
                    duration = %s,
                    completed_at = NOW(),
                    updated_at = NOW()
                WHERE heygen_video_id = %s
            """
            
            test_url = "https://files.heygen.ai/test-video.mp4"
            test_duration = 30
            
            cursor.execute(test_query, (test_url, test_duration, test_video_id))
            rows_affected = cursor.rowcount
            
            print(f"✅ UPDATE query successful! Rows affected: {rows_affected}")
            
            # Rollback the test change
            cursor.execute("UPDATE videos SET status = 'processing' WHERE heygen_video_id = %s", (test_video_id,))
            print("🔄 Rolled back test change")
            
        else:
            print("⚠️ No videos found to test with")
        
        print(f"\n🎉 Database schema verification complete!")
        print(f"📊 Missing columns added: {missing_columns if missing_columns else 'None'}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error verifying database schema: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = verify_and_fix_database_schema()
    if success:
        print("\n✅ Database schema is ready for webhook updates!")
    else:
        print("\n❌ Database schema verification failed!")
        sys.exit(1)
