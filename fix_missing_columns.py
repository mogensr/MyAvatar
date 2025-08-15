#!/usr/bin/env python3
"""
Fix missing updated_at column in videos table - with proper transaction handling
"""
import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import using absolute imports
from dotenv import load_dotenv
import psycopg2

# Load environment variables
load_dotenv()

def fix_missing_columns():
    """Add missing updated_at column to videos table with proper transaction handling"""
    try:
        # Get database URL
        DATABASE_URL = os.getenv("DATABASE_URL")
        if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
            
        if not DATABASE_URL:
            print("❌ DATABASE_URL not found in environment variables")
            return False
            
        print("🔧 Connecting to PostgreSQL database...")
        
        # Connect to database
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True  # Use autocommit to avoid transaction issues
        cursor = conn.cursor()
        
        print("🔧 Checking current columns in videos table...")
        
        # Check which columns exist
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns 
            WHERE table_name = 'videos' AND column_name IN ('completed_at', 'updated_at')
            ORDER BY column_name;
        """)
        
        existing_columns = [row[0] for row in cursor.fetchall()]
        print(f"📋 Existing timestamp columns: {existing_columns}")
        
        # Add updated_at column if it doesn't exist
        if 'updated_at' not in existing_columns:
            print("🔧 Adding updated_at column...")
            try:
                cursor.execute("ALTER TABLE videos ADD COLUMN updated_at TIMESTAMP DEFAULT NOW();")
                print("✅ Added updated_at column!")
            except Exception as e:
                print(f"❌ Error adding updated_at: {e}")
                return False
        else:
            print("ℹ️ updated_at column already exists")
        
        # Add completed_at column if it doesn't exist
        if 'completed_at' not in existing_columns:
            print("🔧 Adding completed_at column...")
            try:
                cursor.execute("ALTER TABLE videos ADD COLUMN completed_at TIMESTAMP;")
                print("✅ Added completed_at column!")
            except Exception as e:
                print(f"❌ Error adding completed_at: {e}")
                return False
        else:
            print("ℹ️ completed_at column already exists")
        
        # Verify all columns now exist
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'videos' AND column_name IN ('completed_at', 'updated_at')
            ORDER BY column_name;
        """)
        
        columns = cursor.fetchall()
        
        print("\n📋 Final column verification:")
        for col in columns:
            print(f"  - {col[0]} ({col[1]}) {'NULL' if col[2] == 'YES' else 'NOT NULL'} {col[3] or ''}")
            
        # Update existing records to have updated_at timestamp if the column was just added
        if 'updated_at' not in existing_columns:
            print("🔧 Updating existing records with updated_at timestamps...")
            cursor.execute("UPDATE videos SET updated_at = created_at WHERE updated_at IS NULL;")
            updated_rows = cursor.rowcount
            print(f"✅ Updated {updated_rows} existing records")
        
        print(f"\n🎉 Database schema is now ready for webhook updates!")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error fixing columns: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = fix_missing_columns()
    if success:
        print("\n✅ Database schema fix completed successfully!")
        print("🔄 Your webhook should now work properly!")
        print("🧪 Test with: Invoke-RestMethod -Uri 'https://app.myavatar.dk/api/heygen/webhook' -Method POST -ContentType 'application/json' -Body '{\"event_type\":\"video.succeed\",\"video_id\":\"test123\",\"status\":\"completed\",\"video_url\":\"https://test.mp4\"}'")
    else:
        print("\n❌ Database schema fix failed!")
        sys.exit(1)
