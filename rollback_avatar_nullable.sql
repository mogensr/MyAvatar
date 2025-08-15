
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
