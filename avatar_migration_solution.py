#!/usr/bin/env python3
"""
COMPREHENSIVE AVATAR_ID MIGRATION SOLUTION
Based on deep-dive research for safely handling NULL avatar_id values
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor

class AvatarMigrationSolution:
    """Complete solution for avatar_id nullable migration"""
    
    def __init__(self):
        self.DATABASE_URL = os.getenv('DATABASE_URL')
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL not found")
    
    def phase_1_verify_current_state(self):
        """Phase 1: Verify current database state and constraints"""
        print("🔍 PHASE 1: VERIFYING CURRENT STATE")
        print("=" * 50)
        
        conn = psycopg2.connect(self.DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check current nullability
        cur.execute("""
            SELECT column_name, is_nullable, data_type
            FROM information_schema.columns 
            WHERE table_name = 'videos' AND column_name = 'avatar_id'
        """)
        
        result = cur.fetchone()
        if result:
            print(f"✅ avatar_id column found: {result['data_type']}, nullable: {result['is_nullable']}")
            is_currently_nullable = result['is_nullable'] == 'YES'
        else:
            print("❌ avatar_id column not found!")
            return False
        
        # Check for existing NULL values
        cur.execute("SELECT COUNT(*) as null_count FROM videos WHERE avatar_id IS NULL")
        null_count = cur.fetchone()['null_count']
        print(f"📊 Current NULL avatar_id count: {null_count}")
        
        # Check for constraints
        cur.execute("""
            SELECT constraint_name, constraint_type 
            FROM information_schema.table_constraints 
            WHERE table_name = 'videos' AND constraint_type = 'CHECK'
        """)
        
        constraints = cur.fetchall()
        if constraints:
            print("⚠️  CHECK constraints found:")
            for constraint in constraints:
                print(f"   {constraint['constraint_name']}: {constraint['constraint_type']}")
        else:
            print("✅ No CHECK constraints on videos table")
        
        conn.close()
        return is_currently_nullable, null_count
    
    def phase_2_create_migration_scripts(self):
        """Phase 2: Create safe migration and rollback scripts"""
        print("\n🛠️  PHASE 2: CREATING MIGRATION SCRIPTS")
        print("=" * 50)
        
        # Migration script
        migration_sql = """
-- AVATAR_ID NULLABLE MIGRATION SCRIPT
-- Execute this in production with monitoring

BEGIN;

-- Set timeout to prevent long lock waits
SET lock_timeout = '5s';

-- Check current state
SELECT 
    COUNT(*) as total_videos,
    COUNT(avatar_id) as non_null_avatars,
    COUNT(*) - COUNT(avatar_id) as null_avatars
FROM videos;

-- Make avatar_id nullable (if not already)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'videos' 
        AND column_name = 'avatar_id' 
        AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE videos ALTER COLUMN avatar_id DROP NOT NULL;
        RAISE NOTICE 'avatar_id constraint dropped successfully';
    ELSE
        RAISE NOTICE 'avatar_id is already nullable';
    END IF;
END $$;

-- Verify the change
SELECT column_name, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'videos' AND column_name = 'avatar_id';

-- Test NULL insertion
INSERT INTO videos (user_id, title, video_path, input_url, avatar_id) 
VALUES (1, 'MIGRATION_TEST_BackgroundFX', 'test_url', 'test_job', NULL) 
RETURNING id;

-- Clean up test record
DELETE FROM videos WHERE title = 'MIGRATION_TEST_BackgroundFX';

COMMIT;
"""
        
        # Rollback script
        rollback_sql = """
-- AVATAR_ID NULLABLE ROLLBACK SCRIPT
-- Use if migration needs to be reverted

BEGIN;

-- Check for NULL values that would prevent rollback
SELECT COUNT(*) as null_avatar_count 
FROM videos 
WHERE avatar_id IS NULL;

-- Option 1: Assign default avatar to BackgroundFX videos
-- UPDATE videos 
-- SET avatar_id = (SELECT id FROM user_avatars WHERE is_default = true LIMIT 1)
-- WHERE avatar_id IS NULL;

-- Option 2: Delete BackgroundFX videos (if acceptable)
-- DELETE FROM videos WHERE avatar_id IS NULL;

-- Restore NOT NULL constraint (uncomment after handling NULLs)
-- ALTER TABLE videos ALTER COLUMN avatar_id SET NOT NULL;

-- Verify rollback
-- SELECT column_name, is_nullable 
-- FROM information_schema.columns 
-- WHERE table_name = 'videos' AND column_name = 'avatar_id';

ROLLBACK; -- Remove this line when ready to execute
"""
        
        # Write scripts to files
        with open('migration_avatar_nullable.sql', 'w') as f:
            f.write(migration_sql)
        print("✅ Created: migration_avatar_nullable.sql")
        
        with open('rollback_avatar_nullable.sql', 'w') as f:
            f.write(rollback_sql)
        print("✅ Created: rollback_avatar_nullable.sql")
    
    def phase_3_update_application_code(self):
        """Phase 3: Generate application code updates"""
        print("\n💻 PHASE 3: APPLICATION CODE UPDATES NEEDED")
        print("=" * 50)
        
        print("📝 1. UPDATE BACKGROUNDFX SAVE FUNCTION:")
        print("""
def save_processed_video_to_database(user_id, cloudinary_url, job_id):
    \"\"\"Save BackgroundFX video with explicit NULL avatar_id\"\"\"
    try:
        # SOLUTION: Explicitly set avatar_id to NULL for BackgroundFX videos
        video_id = execute_query(
            \"\"\"INSERT INTO videos (user_id, title, video_path, input_url, avatar_id, video_type) 
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING id\"\"\",
            (user_id, "BackgroundFX Cinema-Quality Video", cloudinary_url, job_id, None, 'backgroundfx'),
            fetch_one=True
        )
        
        if video_id:
            logger.info(f"✅ BackgroundFX video saved: ID={video_id['id']}")
            return video_id['id']
        return None
        
    except Exception as e:
        logger.error(f"BackgroundFX save error: {e}")
        return None
""")
        
        print("\n📝 2. UPDATE VIDEO QUERIES (INNER → LEFT JOIN):")
        print("""
# BEFORE (excludes BackgroundFX videos):
SELECT v.*, a.name as avatar_name
FROM videos v
INNER JOIN user_avatars a ON v.avatar_id = a.id

# AFTER (includes BackgroundFX videos):
SELECT v.*, a.name as avatar_name, 
       CASE WHEN v.avatar_id IS NULL THEN 'BackgroundFX' ELSE a.name END as display_name
FROM videos v
LEFT JOIN user_avatars a ON v.avatar_id = a.id
""")
        
        print("\n📝 3. ADD VIDEO TYPE DISCRIMINATION:")
        print("""
# Add computed column for video type
ALTER TABLE videos ADD COLUMN video_type VARCHAR(20) 
  GENERATED ALWAYS AS (
    CASE 
      WHEN avatar_id IS NULL THEN 'backgroundfx'
      ELSE 'avatar'
    END
  ) STORED;

CREATE INDEX idx_videos_type ON videos(video_type);
""")
    
    def phase_4_test_migration(self):
        """Phase 4: Test the migration safely"""
        print("\n🧪 PHASE 4: TESTING MIGRATION")
        print("=" * 50)
        
        conn = psycopg2.connect(self.DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Test 1: Current save function behavior
            print("Test 1: Current BackgroundFX save behavior")
            try:
                cur.execute("""
                    INSERT INTO videos (user_id, title, video_path, input_url, avatar_id) 
                    VALUES (1, 'TEST_BackgroundFX', 'test_url', 'test_job', NULL) 
                    RETURNING id
                """)
                result = cur.fetchone()
                test_id = result['id']
                print(f"✅ SUCCESS: BackgroundFX video saved with ID {test_id}")
                
                # Clean up
                cur.execute("DELETE FROM videos WHERE id = %s", (test_id,))
                conn.commit()
                
            except Exception as e:
                print(f"❌ FAILED: {e}")
                conn.rollback()
            
            # Test 2: JOIN query behavior
            print("\nTest 2: JOIN query behavior with NULL avatar_id")
            cur.execute("""
                SELECT COUNT(*) as total_videos,
                       COUNT(v.avatar_id) as videos_with_avatar
                FROM videos v
                LEFT JOIN user_avatars a ON v.avatar_id = a.id
            """)
            
            result = cur.fetchone()
            print(f"✅ Total videos: {result['total_videos']}")
            print(f"✅ Videos with avatars: {result['videos_with_avatar']}")
            print(f"✅ BackgroundFX videos: {result['total_videos'] - result['videos_with_avatar']}")
            
        finally:
            conn.close()
    
    def execute_full_solution(self):
        """Execute the complete migration solution"""
        print("🚀 EXECUTING COMPREHENSIVE AVATAR_ID MIGRATION SOLUTION")
        print("=" * 60)
        
        # Phase 1: Verify current state
        is_nullable, null_count = self.phase_1_verify_current_state()
        
        # Phase 2: Create migration scripts
        self.phase_2_create_migration_scripts()
        
        # Phase 3: Show application code updates needed
        self.phase_3_update_application_code()
        
        # Phase 4: Test current behavior
        self.phase_4_test_migration()
        
        print("\n" + "=" * 60)
        print("🎯 MIGRATION SOLUTION COMPLETE")
        print("\nNEXT STEPS:")
        print("1. Review generated migration scripts")
        print("2. Update application code as shown above")
        print("3. Deploy application changes first")
        print("4. Execute migration_avatar_nullable.sql in production")
        print("5. Monitor performance and error rates")

if __name__ == "__main__":
    solution = AvatarMigrationSolution()
    solution.execute_full_solution()
