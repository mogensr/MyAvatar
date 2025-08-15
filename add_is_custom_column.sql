-- Script to add is_custom column to user_avatars table
-- This fixes the "column is_custom does not exist" error

-- Add the column if it doesn't exist
ALTER TABLE user_avatars ADD COLUMN IF NOT EXISTS is_custom BOOLEAN DEFAULT FALSE;

-- Set existing avatars as custom (assuming all existing avatars are custom)
-- Comment this out if you want to set specific values manually
UPDATE user_avatars SET is_custom = TRUE;

-- Verify the column was added
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'user_avatars' AND column_name = 'is_custom';
