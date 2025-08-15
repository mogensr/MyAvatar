-- Create avatar_voice_parameters table for storing voice emotion, speed, and pitch settings
CREATE TABLE IF NOT EXISTS avatar_voice_parameters (
    id SERIAL PRIMARY KEY,
    avatar_id VARCHAR(255) NOT NULL,
    emotion FLOAT DEFAULT 0.5,  -- Emotion value (0.0 to 1.0)
    speed FLOAT DEFAULT 1.0,    -- Speed multiplier (0.5 to 2.0)
    pitch FLOAT DEFAULT 1.0,    -- Pitch multiplier (0.5 to 2.0)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(avatar_id)
);

-- Add indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_avatar_voice_params_avatar_id ON avatar_voice_parameters(avatar_id);

-- Insert default values for testing
INSERT INTO avatar_voice_parameters (avatar_id, emotion, speed, pitch)
VALUES 
    ('065ec9e82e904bebbe50d283af9a5ab7', 0.7, 1.1, 1.0)  -- MogensR's Danish avatar
ON CONFLICT (avatar_id) DO UPDATE 
SET emotion = EXCLUDED.emotion,
    speed = EXCLUDED.speed,
    pitch = EXCLUDED.pitch,
    updated_at = CURRENT_TIMESTAMP;

-- Add comment for documentation
COMMENT ON TABLE avatar_voice_parameters IS 'Stores voice parameter settings (emotion, speed, pitch) for each avatar';
