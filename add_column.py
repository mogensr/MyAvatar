"""
Script to add input_url column to PostgreSQL database
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor

def add_input_url_column():
    """Add input_url column to videos table"""
    
    # Check DATABASE_URL
    DATABASE_URL = os.getenv("DATABASE_URL")
    print(f"🔍 DATABASE_URL found: {bool(DATABASE_URL)}")
    if DATABASE_URL:
        print(f"🔍 DATABASE_URL starts with: {DATABASE_URL[:20]}...")
    
    try:
        # Connect to database
        if DATABASE_URL:
            print("🔌 Connecting with DATABASE_URL...")
            conn = psycopg2.connect(DATABASE_URL)
        else:
            print("❌ No DATABASE_URL found in environment variables")
            print("💡 Make sure it's set in your system environment variables")
            return
            
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        print("✅ Connected to database successfully")
        
        # Check if column already exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'videos' AND column_name = 'input_url'
        """)
        
        if cursor.fetchone():
            print("✅ Column 'input_url' already exists in videos table")
        else:
            # Add the column
            cursor.execute("ALTER TABLE videos ADD COLUMN input_url TEXT")
            conn.commit()
            print("✅ Successfully added 'input_url' column to videos table")
        
        # Also add to video_processing_jobs if needed
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'video_processing_jobs' AND column_name = 'input_url'
        """)
        
        if cursor.fetchone():
            print("✅ Column 'input_url' already exists in video_processing_jobs table")
        else:
            cursor.execute("ALTER TABLE video_processing_jobs ADD COLUMN input_url TEXT")
            conn.commit()
            print("✅ Successfully added 'input_url' column to video_processing_jobs table")
            
    except psycopg2.Error as e:
        print(f"❌ Database error: {e}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        
    finally:
        if 'conn' in locals():
            conn.close()
            print("🔌 Database connection closed")

if __name__ == "__main__":
    print("🚀 Adding input_url column to database...")
    add_input_url_column()
    print("✅ Done!")
