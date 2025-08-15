-- MyAvatar PostgreSQL Initialization Script
-- This will be run automatically when the container starts

-- Enable UUID extension (useful for future features)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create database user with proper permissions
-- (This is handled by environment variables, but keeping for reference)

-- Set timezone
SET timezone = 'UTC';

-- Create initial tables will be handled by the application's init_database() function
-- This file ensures the database is ready for the application
