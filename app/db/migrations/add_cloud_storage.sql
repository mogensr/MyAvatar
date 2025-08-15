-- Migration: Add Cloud Storage Support to MyAvatar (Updated for BackgroundFX)
-- Run this after backing up your database

-- Add cloud storage columns to users table (if not already present)
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS cloud_storage_provider VARCHAR(50),
ADD COLUMN IF NOT EXISTS cloud_storage_config JSONB,
ADD COLUMN IF NOT EXISTS cloud_storage_quota_gb INTEGER DEFAULT 5,
ADD COLUMN IF NOT EXISTS cloud_storage_used_gb DECIMAL(10,2) DEFAULT 0.00,
ADD COLUMN IF NOT EXISTS cloud_storage_connected_at TIMESTAMP;

-- Add cloud storage columns to videos table (if not already present)
ALTER TABLE videos
ADD COLUMN IF NOT EXISTS cloud_storage_url TEXT,
ADD COLUMN IF NOT EXISTS storage_type VARCHAR(20) DEFAULT 'local';

-- Create dedicated table for OAuth tokens (more secure than JSONB)
CREATE TABLE IF NOT EXISTS user_cloud_storage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    provider VARCHAR(50) NOT NULL CHECK (provider IN ('google_drive', 'dropbox', 'onedrive')),
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    folder_path TEXT DEFAULT '/BackgroundFX',
    connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, provider)  -- One provider per user
);

-- Create indexes for faster cloud storage queries
CREATE INDEX IF NOT EXISTS idx_users_cloud_provider ON users(cloud_storage_provider);
CREATE INDEX IF NOT EXISTS idx_videos_storage_type ON videos(storage_type);
CREATE INDEX IF NOT EXISTS idx_cloud_storage_user ON user_cloud_storage(user_id);
CREATE INDEX IF NOT EXISTS idx_cloud_storage_active ON user_cloud_storage(is_active);

-- Add constraints (PostgreSQL version - comment out for SQLite)
/*
ALTER TABLE users 
ADD CONSTRAINT IF NOT EXISTS chk_cloud_provider 
CHECK (cloud_storage_provider IN ('google_drive', 'dropbox', 'onedrive', 'aws_s3') OR cloud_storage_provider IS NULL);

ALTER TABLE videos
ADD CONSTRAINT IF NOT EXISTS chk_storage_type 
CHECK (storage_type IN ('local', 'cloud_user', 'cloudinary', 'external'));
*/

-- SQLite version of constraints (if using SQLite, uncomment these)
-- Note: SQLite CHECK constraints are added during table creation, not after
-- So we create a new constraint by recreating the constraint in a transaction if needed

-- Update existing videos to have storage_type
UPDATE videos 
SET storage_type = CASE 
    WHEN url LIKE 'https://drive.google.com%' OR url LIKE 'https://dropbox.com%' OR url LIKE 'https://onedrive.live.com%' THEN 'cloud_user'
    WHEN url LIKE 'https://res.cloudinary.com%' THEN 'cloudinary'
    WHEN url IS NOT NULL THEN 'external'
    ELSE 'local'
END
WHERE storage_type = 'local' OR storage_type IS NULL;

-- Alternative update for your original approach
UPDATE videos SET storage_type = 'external' WHERE url IS NOT NULL AND storage_type = 'local';
UPDATE videos SET storage_type = 'local' WHERE url IS NULL AND id IS NOT NULL AND storage_type = 'local';

-- Create cloud storage log table for debugging (enhanced version)
CREATE TABLE IF NOT EXISTS cloud_storage_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- For SQLite
    -- id SERIAL PRIMARY KEY,              -- For PostgreSQL - uncomment if using PostgreSQL
    user_id INTEGER,
    provider VARCHAR(50),
    action VARCHAR(100),
    status VARCHAR(20),
    details TEXT,  -- For SQLite compatibility (use JSONB for PostgreSQL)
    -- details JSONB,  -- For PostgreSQL - uncomment if using PostgreSQL
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Create indexes for logs
CREATE INDEX IF NOT EXISTS idx_cloud_logs_user ON cloud_storage_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_cloud_logs_created ON cloud_storage_logs(created_at);

-- Insert initial log entries (preserving your original + adding BackgroundFX)
INSERT INTO cloud_storage_logs (user_id, provider, action, status, details)
VALUES (NULL, 'system', 'migration_completed', 'success', 
        '{"migration": "add_cloud_storage", "version": "1.0"}');

INSERT INTO cloud_storage_logs (user_id, provider, action, status, details)
VALUES (NULL, 'system', 'backgroundfx_migration_completed', 'success', 
        '{"migration": "add_backgroundfx_cloud_storage", "version": "2.0", "features": ["oauth_tokens", "multi_provider", "backgroundfx_integration"]}');

-- Add trigger to update timestamp on cloud storage changes (SQLite version)
CREATE TRIGGER IF NOT EXISTS update_cloud_storage_timestamp
AFTER UPDATE ON user_cloud_storage
FOR EACH ROW
BEGIN
    UPDATE user_cloud_storage 
    SET updated_at = CURRENT_TIMESTAMP 
    WHERE id = NEW.id;
END;

-- Optional: Sync existing cloud storage config from users table to new table
-- Run this if you already have users with cloud_storage_provider set
/*
INSERT INTO user_cloud_storage (user_id, provider, access_token, folder_path, connected_at, is_active)
SELECT 
    id as user_id,
    cloud_storage_provider as provider,
    'migration_placeholder' as access_token,  -- You'll need to re-authenticate these users
    '/BackgroundFX' as folder_path,
    cloud_storage_connected_at as connected_at,
    1 as is_active
FROM users 
WHERE cloud_storage_provider IS NOT NULL 
AND id NOT IN (SELECT user_id FROM user_cloud_storage);
*/