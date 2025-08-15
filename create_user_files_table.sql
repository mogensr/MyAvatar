-- Create user_files table for BackgroundFX file management
-- This table stores user-uploaded files (videos, images, backgrounds)

CREATE TABLE IF NOT EXISTS user_files (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    file_type VARCHAR(50) NOT NULL, -- 'video', 'image', 'background'
    file_size BIGINT NOT NULL,
    mime_type VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'active', -- 'active', 'deleted', 'processing'
    metadata JSONB DEFAULT '{}', -- Additional file metadata
    
    -- Indexes for performance
    INDEX idx_user_files_user_id (user_id),
    INDEX idx_user_files_type (file_type),
    INDEX idx_user_files_status (status),
    INDEX idx_user_files_created (created_at)
);

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_user_files_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_user_files_updated_at
    BEFORE UPDATE ON user_files
    FOR EACH ROW
    EXECUTE FUNCTION update_user_files_updated_at();

-- Grant necessary permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON user_files TO PUBLIC;
GRANT USAGE, SELECT ON SEQUENCE user_files_id_seq TO PUBLIC;

-- Add some sample data structure comments
COMMENT ON TABLE user_files IS 'Stores user-uploaded files for BackgroundFX and other features';
COMMENT ON COLUMN user_files.file_type IS 'Type of file: video, image, background, etc.';
COMMENT ON COLUMN user_files.metadata IS 'JSON metadata: dimensions, duration, processing_info, etc.';
