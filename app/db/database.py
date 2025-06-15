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
USE_POSTGRES = DATABASE_URL is not None and DATABASE_URL.startswith("postgres://")

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
        
        # Create users table
        users_table = '''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_admin BOOLEAN DEFAULT FALSE,
            api_key TEXT,
            avatar_id TEXT
        )
        '''
        
        # Create videos table with foreign key constraint
        videos_table = '''
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            heygen_video_id TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            video_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            format TEXT DEFAULT '16:9',
            title TEXT,
            voice_id TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
        '''
        
        # Create user_avatars table
        avatars_table = '''
        CREATE TABLE IF NOT EXISTS user_avatars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            avatar_id TEXT NOT NULL,
            avatar_name TEXT,
            avatar_image_url TEXT,
            is_default BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
        '''
        
        # Create system settings table
        settings_table = '''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_key TEXT UNIQUE NOT NULL,
            setting_value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
        
        # Create API logs table
        logs_table = '''
        CREATE TABLE IF NOT EXISTS api_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            endpoint TEXT NOT NULL,
            request_data TEXT,
            response_data TEXT,
            status_code INTEGER,
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
        )
        '''
        
        if USE_POSTGRES and POSTGRESQL_AVAILABLE:
            # Modify SQL for PostgreSQL
            users_table = users_table.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
            users_table = users_table.replace('BOOLEAN DEFAULT FALSE', 'BOOLEAN DEFAULT FALSE')
            users_table = users_table.replace('TIMESTAMP DEFAULT CURRENT_TIMESTAMP', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
            
            videos_table = videos_table.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
            videos_table = videos_table.replace('INTEGER NOT NULL', 'INTEGER NOT NULL')
            
            avatars_table = avatars_table.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
            avatars_table = avatars_table.replace('INTEGER NOT NULL', 'INTEGER NOT NULL')
            
            settings_table = settings_table.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
            
            logs_table = logs_table.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
            
            # Execute with PostgreSQL connection
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(users_table)
            cursor.execute(videos_table)
            cursor.execute(avatars_table)
            cursor.execute(settings_table)
            cursor.execute(logs_table)
            conn.close()
        else:
            # Execute with SQLite connection
            conn = get_db_connection()
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(users_table)
            conn.execute(videos_table)
            conn.execute(avatars_table)
            conn.execute(settings_table)
            conn.execute(logs_table)
            conn.close()
            
        log_info("Database initialization complete", "Database")
    except Exception as e:
        log_error("Failed to initialize database", "Database", e)
        raise

def update_database_schema():
    """Update database schema for premium features"""
    try:
        log_info("Updating database schema for premium features", "Database")
        
        # Add new columns to existing tables
        
        # Add template_id to videos table
        try:
            if USE_POSTGRES and POSTGRESQL_AVAILABLE:
                execute_query("ALTER TABLE videos ADD COLUMN IF NOT EXISTS template_id TEXT")
                execute_query("ALTER TABLE videos ADD COLUMN IF NOT EXISTS background_config TEXT")
            else:
                # Check if column exists in SQLite
                cursor = get_db_connection().cursor()
                cursor.execute("PRAGMA table_info(videos)")
                columns = [col[1] for col in cursor.fetchall()]
                
                if "template_id" not in columns:
                    execute_query("ALTER TABLE videos ADD COLUMN template_id TEXT")
                    
                if "background_config" not in columns:
                    execute_query("ALTER TABLE videos ADD COLUMN background_config TEXT")
        except Exception as e:
            log_warning(f"Column may already exist: {str(e)}", "Database")
            
        # Create templates table if not exists
        templates_table = '''
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id TEXT UNIQUE NOT NULL,
            template_name TEXT NOT NULL,
            description TEXT,
            thumbnail_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
        
        if USE_POSTGRES and POSTGRESQL_AVAILABLE:
            templates_table = templates_table.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
        
        execute_query(templates_table)
        
        log_info("Database schema update complete", "Database")
    except Exception as e:
        log_error("Failed to update database schema", "Database", e)
        raise
