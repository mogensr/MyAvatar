"""
Database functions for MyAvatar
Supports both SQLite and PostgreSQL
"""
import os
import sqlite3
from datetime import datetime
import traceback
from ..logger.log_handler import log_info, log_error, log_warning

# PostgreSQL support
try:
    import psycopg2
    import psycopg2.extras
    POSTGRESQL_AVAILABLE = True
    log_info("PostgreSQL support is available", "Database")
except ImportError:
    POSTGRESQL_AVAILABLE = False
    log_warning("PostgreSQL support is not available, falling back to SQLite", "Database")

# Environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
USE_POSTGRES = DATABASE_URL is not None and POSTGRESQL_AVAILABLE

def get_db_connection():
    """Get a database connection based on configuration"""
    try:
        if USE_POSTGRES and POSTGRESQL_AVAILABLE:
            log_info("Using PostgreSQL database", "Database")
            conn = psycopg2.connect(DATABASE_URL)
            conn.autocommit = True
            return conn
        else:
            log_info("Using SQLite database", "Database")
            conn = sqlite3.connect('myavatar.db')
            conn.row_factory = sqlite3.Row
            return conn
    except Exception as e:
        log_error("Failed to establish database connection", "Database", e)
        raise

def execute_query(query: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = False):
    """Execute SQL query with proper error handling"""
    connection = None
    try:
        # Convert SQLite placeholders to PostgreSQL placeholders
        if USE_POSTGRES and "?" in query:
            original_query = query  # Store original for debugging
            query = query.replace("?", "%s")
            log_info(f"Converted query from: {original_query} to: {query}", "Database")
            
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(query, params)
        
        if fetch_one:
            result = cursor.fetchone()
            return result
        elif fetch_all:
            result = cursor.fetchall()
            return result
        else:
            connection.commit()
            return None
            
    except Exception as e:
        log_error(f"Database query error: {query}", "Database", e)
        if connection and not USE_POSTGRES:
            connection.rollback()
        raise
    finally:
        if connection:
            connection.close()

def init_database():
    """Initialize database tables if they don't exist"""
    try:
        log_info("Initializing database", "Database")
        
        # Create users table with all required columns
        users_table = '''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_admin BOOLEAN DEFAULT FALSE,
            api_key TEXT,
            avatar_id TEXT,
            avatar_img_url TEXT,
            avatar_video_url TEXT,
            is_premium BOOLEAN DEFAULT FALSE,
            credits_remaining INTEGER DEFAULT 3,
            subscription_tier TEXT DEFAULT 'free',
            subscription_expires TIMESTAMP,
            api_usage_count INTEGER DEFAULT 0,
            display_name TEXT,
            bio TEXT,
            company TEXT,
            total_videos_created INTEGER DEFAULT 0,
            total_minutes_generated REAL DEFAULT 0.0,
            last_video_created TIMESTAMP
        )
        '''
        
        # Create videos table with foreign key constraint
        videos_table = '''
        CREATE TABLE IF NOT EXISTS videos (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            heygen_video_id TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            video_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            format TEXT DEFAULT '16:9',
            title TEXT,
            voice_id TEXT,
            template_id TEXT,
            background_config TEXT,
            script_content TEXT,
            thumbnail_url TEXT,
            duration REAL,
            completed_at TIMESTAMP,
            avatar_id TEXT,
            quality TEXT DEFAULT '720p',
            aspect_ratio TEXT DEFAULT '16:9',
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
        '''
        
        # Create user_avatars table
        avatars_table = '''
        CREATE TABLE IF NOT EXISTS user_avatars (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            avatar_id TEXT NOT NULL,
            avatar_name TEXT,
            avatar_image_url TEXT,
            preview_video_url TEXT,
            is_default BOOLEAN DEFAULT FALSE,
            is_custom BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
        '''
        
        # Create system settings table
        settings_table = '''
        CREATE TABLE IF NOT EXISTS settings (
            id SERIAL PRIMARY KEY,
            setting_key TEXT UNIQUE NOT NULL,
            setting_value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
        
        # Create API logs table
        logs_table = '''
        CREATE TABLE IF NOT EXISTS api_logs (
            id SERIAL PRIMARY KEY,
            endpoint TEXT NOT NULL,
            request_data TEXT,
            response_data TEXT,
            status_code INTEGER,
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
        )
        '''
        
        # Create templates table
        templates_table = '''
        CREATE TABLE IF NOT EXISTS templates (
            id SERIAL PRIMARY KEY,
            template_id TEXT UNIQUE NOT NULL,
            template_name TEXT NOT NULL,
            description TEXT,
            thumbnail_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
        
        if USE_POSTGRES and POSTGRESQL_AVAILABLE:
            # Execute with PostgreSQL connection
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(users_table)
            cursor.execute(videos_table)
            cursor.execute(avatars_table)
            cursor.execute(settings_table)
            cursor.execute(logs_table)
            cursor.execute(templates_table)
            conn.close()
        else:
            # Modify for SQLite
            users_table = users_table.replace('SERIAL PRIMARY KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT')
            users_table = users_table.replace('REAL', 'REAL')
            users_table = users_table.replace('TIMESTAMP', 'TIMESTAMP')
            
            videos_table = videos_table.replace('SERIAL PRIMARY KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT')
            avatars_table = avatars_table.replace('SERIAL PRIMARY KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT')
            settings_table = settings_table.replace('SERIAL PRIMARY KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT')
            logs_table = logs_table.replace('SERIAL PRIMARY KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT')
            templates_table = templates_table.replace('SERIAL PRIMARY KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT')
            
            # Execute with SQLite connection
            conn = get_db_connection()
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(users_table)
            conn.execute(videos_table)
            conn.execute(avatars_table)
            conn.execute(settings_table)
            conn.execute(logs_table)
            conn.execute(templates_table)
            conn.close()
            
        log_info("Database initialization complete", "Database")
    except Exception as e:
        log_error("Failed to initialize database", "Database", e)
        raise

def update_database_schema():
    """Update database schema for premium features"""
    try:
        log_info("Database schema is up to date", "Database")
        # Schema is now complete in init_database, no updates needed
    except Exception as e:
        log_error("Failed to update database schema", "Database", e)
        raise

# Helper function for placeholder compatibility
def get_placeholder():
    """Get the correct placeholder for the database type"""
    return "%s" if USE_POSTGRES else "?"

# Helper function to format queries
def format_query(query: str):
    """Format query for current database type"""
    if USE_POSTGRES and "?" in query:
        return query.replace("?", "%s")
    return query