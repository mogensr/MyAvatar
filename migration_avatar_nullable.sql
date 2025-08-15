
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
