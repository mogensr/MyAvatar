-- Migration: Add voice parameters columns to user_avatars table
-- This adds columns for storing extracted voice parameters from user audio uploads

-- Add voice parameter columns to user_avatars table
ALTER TABLE user_avatars ADD COLUMN IF NOT EXISTS voice_parameters_speed FLOAT DEFAULT 1.0;
ALTER TABLE user_avatars ADD COLUMN IF NOT EXISTS voice_parameters_pitch FLOAT DEFAULT 1.0;
ALTER TABLE user_avatars ADD COLUMN IF NOT EXISTS voice_parameters_emotion VARCHAR(50) DEFAULT 'Friendly';
ALTER TABLE user_avatars ADD COLUMN IF NOT EXISTS voice_parameters_analyzed BOOLEAN DEFAULT FALSE;

-- Add comment to columns
COMMENT ON COLUMN user_avatars.voice_parameters_speed IS 'Extracted speech rate from user voice (1.0 is average)';
COMMENT ON COLUMN user_avatars.voice_parameters_pitch IS 'Extracted pitch from user voice (1.0 is average)';
COMMENT ON COLUMN user_avatars.voice_parameters_emotion IS 'Detected emotional tone from user voice';
COMMENT ON COLUMN user_avatars.voice_parameters_analyzed IS 'Whether voice analysis has been performed';
