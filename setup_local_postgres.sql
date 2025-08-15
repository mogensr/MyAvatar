-- Setup Local PostgreSQL Database for MyAvatar
-- Run this after PostgreSQL installation

-- Create the database
CREATE DATABASE myavatar;

-- Connect to the database (you'll need to do this manually)
\c myavatar;

-- Create tables (same structure as Railway)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_admin BOOLEAN DEFAULT FALSE,
    last_login TIMESTAMP,
    last_video_created TIMESTAMP
);

CREATE TABLE user_avatars (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    avatar_id VARCHAR(100) NOT NULL,
    avatar_name VARCHAR(100) NOT NULL,
    avatar_image_url TEXT,
    preview_video_url TEXT,
    is_default INTEGER DEFAULT 0,
    is_custom BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE videos (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    heygen_video_id VARCHAR(100),
    status VARCHAR(20) DEFAULT 'pending',
    video_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    format VARCHAR(10) DEFAULT '16:9',
    title VARCHAR(200),
    description TEXT,
    voice_id VARCHAR(100),
    template_id VARCHAR(100),
    background_config TEXT,
    script_content TEXT,
    thumbnail_url TEXT,
    duration INTEGER,
    completed_at TIMESTAMP,
    avatar_id VARCHAR(100),
    quality VARCHAR(10) DEFAULT '720p',
    aspect_ratio VARCHAR(10) DEFAULT '16:9'
);

CREATE TABLE avatars (
    id SERIAL PRIMARY KEY,
    avatar_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    image_url TEXT,
    preview_video_url TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE backgrounds (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    image_url TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE settings (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) UNIQUE NOT NULL,
    value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE api_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    endpoint VARCHAR(200),
    method VARCHAR(10),
    status_code INTEGER,
    response_time INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE templates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    config TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX idx_user_avatars_user_id ON user_avatars(user_id);
CREATE INDEX idx_videos_user_id ON videos(user_id);
CREATE INDEX idx_videos_status ON videos(status);
CREATE INDEX idx_api_logs_user_id ON api_logs(user_id);

-- Success message
SELECT 'Database setup completed successfully!' as message;
