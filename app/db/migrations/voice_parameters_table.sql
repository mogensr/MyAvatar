-- Migration: Create voice_parameters table
-- This table stores extracted voice parameters from user audio uploads

CREATE TABLE IF NOT EXISTS voice_parameters (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    avatar_id VARCHAR(255),
    speed FLOAT DEFAULT 1.0,
    pitch FLOAT DEFAULT 1.0,
    emotion VARCHAR(50) DEFAULT 'Friendly',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_voice_parameters_user_id ON voice_parameters(user_id);
CREATE INDEX IF NOT EXISTS idx_voice_parameters_avatar_id ON voice_parameters(avatar_id);

-- Add comment to table
COMMENT ON TABLE voice_parameters IS 'Stores extracted voice parameters from user audio uploads for natural TTS';
