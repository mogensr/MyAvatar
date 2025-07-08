#!/usr/bin/env python3
"""
Database Migration: Rename video_path column to video_url
Step 1 of the cleanup process
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def migrate_column_name():
    """Rename video_path column to video_url in the videos table"""
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not found in environment")
        return False
    
    print("🔄 Starting database migration...")
    print("   Renaming: video_path → video_url")
    
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Step 1: Check if video_path column exists
        print("\n🔍 Step 1: Checking current column...")
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'videos' 
            AND column_name IN ('video_path', 'video_url')
        """)
        
        existing_columns = [row['column_name'] for row in cur.fetchall()]
        print(f"   Found columns: {existing_columns}")
        
        if 'video_url' in existing_columns:
            print("✅ Column 'video_url' already exists! Migration not needed.")
            return True
            
        if 'video_path' not in existing_columns:
            print("❌ Column 'video_path' not found! Cannot migrate.")
            return False
        
        # Step 2: Count records that will be affected
        print("\n📊 Step 2: Checking data...")
        cur.execute("SELECT COUNT(*) as total FROM videos")
        total_videos = cur.fetchone()['total']
        
        cur.execute("SELECT COUNT(*) as with_path FROM videos WHERE video_path IS NOT NULL")
        videos_with_path = cur.fetchone()['with_path']
        
        print(f"   Total videos: {total_videos}")
        print(f"   Videos with video_path: {videos_with_path}")
        
        # Step 3: Perform the migration
        print("\n🔄 Step 3: Renaming column...")
        cur.execute("ALTER TABLE videos RENAME COLUMN video_path TO video_url;")
        
        # Step 4: Verify the migration
        print("\n✅ Step 4: Verifying migration...")
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'videos' 
            AND column_name = 'video_url'
        """)
        
        if cur.fetchone():
            print("   ✅ Column successfully renamed to 'video_url'")
            
            # Check data integrity
            cur.execute("SELECT COUNT(*) as with_url FROM videos WHERE video_url IS NOT NULL")
            videos_with_url = cur.fetchone()['with_url']
            
            if videos_with_url == videos_with_path:
                print(f"   ✅ Data integrity verified: {videos_with_url} records preserved")
                conn.commit()
                print("\n🎉 MIGRATION SUCCESSFUL!")
                return True
            else:
                print(f"   ❌ Data mismatch: expected {videos_with_path}, got {videos_with_url}")
                conn.rollback()
                return False
        else:
            print("   ❌ Column rename failed")
            conn.rollback()
            return False
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        if 'conn' in locals():
            conn.rollback()
        return False
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def main():
    print("🚀 DATABASE MIGRATION: video_path → video_url")
    print("=" * 50)
    
    success = migrate_column_name()
    
    if success:
        print("\n✅ NEXT STEPS:")
        print("   1. Update application code to use 'video_url' consistently")
        print("   2. Remove column aliases from SQL queries")
        print("   3. Test the application")
        print("   4. Deploy the updated code")
    else:
        print("\n❌ MIGRATION FAILED")
        print("   Please check the error messages above")
        print("   The database has been rolled back to its original state")

if __name__ == "__main__":
    main()
