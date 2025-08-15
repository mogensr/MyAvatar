#!/usr/bin/env python3
"""
Add missing completed_at and updated_at columns to videos table
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

def add_missing_columns():
    """Add missing completed_at and updated_at columns to videos table"""
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
        cursor = conn.cursor()
        
        print("🔧 Adding missing columns to videos table...")
        
        # Add completed_at column
        try:
            cursor.execute("ALTER TABLE videos ADD COLUMN completed_at TIMESTAMP;")
            print("✅ Added completed_at column!")
        except psycopg2.errors.DuplicateColumn:
            print("ℹ️ completed_at column already exists")
        except Exception as e:
            print(f"⚠️ Error adding completed_at: {e}")
        
        # Add updated_at column with default
        try:
            cursor.execute("ALTER TABLE videos ADD COLUMN updated_at TIMESTAMP DEFAULT NOW();")
            print("✅ Added updated_at column!")
        except psycopg2.errors.DuplicateColumn:
            print("ℹ️ updated_at column already exists")
        except Exception as e:
            print(f"⚠️ Error adding updated_at: {e}")
        
        # Commit changes
        conn.commit()
        
        # Verify columns were added
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'videos' AND column_name IN ('completed_at', 'updated_at')
            ORDER BY column_name;
        """)
        
        columns = cursor.fetchall()
        
        print("\n📋 Verified new columns:")
        for col in columns:
            print(f"  - {col[0]} ({col[1]}) {'NULL' if col[2] == 'YES' else 'NOT NULL'} {col[3] or ''}")
            
        # Update existing records to have updated_at timestamp
        cursor.execute("UPDATE videos SET updated_at = created_at WHERE updated_at IS NULL;")
        updated_rows = cursor.rowcount
        print(f"✅ Updated {updated_rows} existing records with updated_at timestamps")
        
        conn.commit()
        
        print(f"\n🎉 Missing columns added successfully!")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error adding columns: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = add_missing_columns()
    if success:
        print("\n✅ Database schema update completed successfully!")
        print("🔄 Now restart your server and test the webhook again!")
    else:
        print("\n❌ Database schema update failed!")
        sys.exit(1)
