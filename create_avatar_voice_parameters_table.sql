-- Create avatar_voice_parameters table for storing voice settings per avatar/user
CREATE TABLE avatar_voice_parameters (
    id SERIAL PRIMARY KEY,
    avatar_id VARCHAR(255) NOT NULL,
    user_id INTEGER,
    emotion FLOAT DEFAULT 0.5,
    speed FLOAT DEFAULT 1.0, 
    pitch FLOAT DEFAULT 1.0,
    voice_id VARCHAR(255),
    language VARCHAR(10) DEFAULT 'en-US',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(avatar_id, user_id)
);

-- Create indexes for better query performance
CREATE INDEX idx_avatar_voice_params_avatar ON avatar_voice_parameters(avatar_id);
CREATE INDEX idx_avatar_voice_params_user ON avatar_voice_parameters(user_id);

-- Verify table creation
SELECT 'Table avatar_voice_parameters created successfully!' as status;
