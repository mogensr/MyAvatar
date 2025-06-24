"""
Database migration to fix avatar_id column type with foreign key handling
Run this script to change avatar_id from INTEGER to TEXT
"""
import os
import psycopg2
from urllib.parse import urlparse

def run_migration():
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not found in environment variables")
        return
    
    # Parse the database URL
    url = urlparse(database_url)
    
    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=url.hostname,
            database=url.path[1:],  # Remove leading slash
            user=url.username,
            password=url.password,
            port=url.port
        )
        
        cursor = conn.cursor()
        
        print("🔗 Connected to database")
        
        # Step 1: Find and drop the foreign key constraint
        print("🔍 Finding foreign key constraints...")
        cursor.execute("""
            SELECT constraint_name, table_name 
            FROM information_schema.table_constraints 
            WHERE constraint_type = 'FOREIGN KEY' 
            AND table_name = 'videos' 
            AND constraint_name LIKE '%avatar_id%'
        """)
        
        fk_constraints = cursor.fetchall()
        print(f"📋 Found {len(fk_constraints)} foreign key constraints to handle")
        
        # Step 2: Drop foreign key constraints
        for constraint_name, table_name in fk_constraints:
            print(f"🗑️ Dropping constraint: {constraint_name}")
            cursor.execute(f"ALTER TABLE {table_name} DROP CONSTRAINT {constraint_name};")
        
        # Step 3: Change column type
        print("🔄 Changing avatar_id column type to TEXT...")
        cursor.execute("ALTER TABLE videos ALTER COLUMN avatar_id TYPE TEXT;")
        
        # Step 4: Check if we need to also change the referenced table
        print("🔍 Checking if user_avatars table needs updating...")
        cursor.execute("""
            SELECT data_type 
            FROM information_schema.columns 
            WHERE table_name = 'user_avatars' AND column_name = 'avatar_id'
        """)
        
        user_avatars_type = cursor.fetchone()
        if user_avatars_type and user_avatars_type[0] == 'integer':
            print("🔄 Also updating user_avatars.avatar_id to TEXT...")
            cursor.execute("ALTER TABLE user_avatars ALTER COLUMN avatar_id TYPE TEXT;")
        
        # Step 5: We won't recreate the foreign key since avatar_id should reference HeyGen IDs, not our internal IDs
        print("ℹ️ Not recreating foreign key - avatar_id should reference external HeyGen avatar IDs")
        
        # Commit the changes
        conn.commit()
        
        # Verify the change
        cursor.execute("""
            SELECT data_type 
            FROM information_schema.columns 
            WHERE table_name = 'videos' AND column_name = 'avatar_id'
        """)
        
        new_type = cursor.fetchone()
        if new_type:
            print(f"✅ New videos.avatar_id type: {new_type[0]}")
        
        print("🎉 Migration completed successfully!")
        print("📝 Note: Foreign key constraint removed - avatar_id now stores HeyGen avatar IDs directly")
        
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
    
    finally:
        if 'conn' in locals():
            conn.close()
            print("🔌 Database connection closed")

if __name__ == "__main__":
    run_migration()