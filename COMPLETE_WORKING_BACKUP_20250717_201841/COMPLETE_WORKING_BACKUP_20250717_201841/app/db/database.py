"""
Database functions for MyAvatar
FIXED VERSION - Proper PostgreSQL placeholder handling + .env loading
"""
import os
import sqlite3
from datetime import datetime
import traceback
from dotenv import load_dotenv
from ..logger.log_handler import log_info, log_error, log_warning

# Load environment variables from .env file
load_dotenv()

# ============================================================================
# POSTGRESQL SETUP
# ============================================================================

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

log_info(f"Database configuration - USE_POSTGRES: {USE_POSTGRES}, POSTGRESQL_AVAILABLE: {POSTGRESQL_AVAILABLE}", "Database")
log_info(f"DATABASE_URL detected: {'YES' if DATABASE_URL else 'NO'}", "Database")

# ============================================================================
# DATABASE CONNECTION FUNCTIONS
# ============================================================================

def get_db_connection():
    """Get a database connection based on configuration"""
    try:
        if USE_POSTGRES and POSTGRESQL_AVAILABLE:
            log_info("Attempting PostgreSQL database connection", "Database")
            conn = psycopg2.connect(DATABASE_URL)
            conn.autocommit = True
            log_info("PostgreSQL database connection successful", "Database")
            return conn
        else:
            log_info("Attempting SQLite database connection", "Database")
            conn = sqlite3.connect('myavatar.db')
            conn.row_factory = sqlite3.Row
            log_info("SQLite database connection successful", "Database")
            return conn
    except psycopg2.Error as e:
        log_error(f"PostgreSQL connection failed: {e.pgcode} - {e.pgerror}", "Database", e)
        raise
    except sqlite3.Error as e:
        log_error(f"SQLite connection failed: {str(e)}", "Database", e)
        raise
    except Exception as e:
        log_error(f"Unexpected database connection error: {type(e).__name__}", "Database", e)
        raise

def execute_query(query: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = False):
    """Execute SQL query with proper PostgreSQL/SQLite handling"""
    connection = None
    cursor = None
    original_query = query
    original_params = params
    
    try:
        log_info(f"Executing query: {query[:100]}{'...' if len(query) > 100 else ''}", "Database")
        log_info(f"Query parameters: {params}", "Database")
        
        connection = get_db_connection()
        
        if USE_POSTGRES:
            # Use RealDictCursor for PostgreSQL to return dictionary-like objects
            cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # For PostgreSQL, we need to convert ? to %s
            if "?" in query:
                # Count the number of ? placeholders
                placeholder_count = query.count("?")
                # Convert ? to %s
                postgres_query = query.replace("?", "%s")
                log_info(f"Converted {placeholder_count} placeholders for PostgreSQL", "Database")
                query = postgres_query
                
        else:
            cursor = connection.cursor()
            
        # Execute query
        start_time = datetime.now()
        cursor.execute(query, params)
        execution_time = (datetime.now() - start_time).total_seconds()
        
        log_info(f"Query executed successfully in {execution_time:.3f}s", "Database")
        
        if fetch_one:
            result = cursor.fetchone()
            log_info(f"Fetched one record: {'Found' if result else 'No record found'}", "Database")
            return result
        elif fetch_all:
            result = cursor.fetchall()
            log_info(f"Fetched {len(result) if result else 0} records", "Database")
            return result
        else:
            # For INSERT/UPDATE/DELETE without fetch
            if not USE_POSTGRES:  # PostgreSQL has autocommit=True
                connection.commit()
            log_info("Query committed successfully", "Database")
            return None
            
    except psycopg2.Error as e:
        log_error(f"PostgreSQL query error - Code: {e.pgcode}", "Database", e)
        log_error(f"PostgreSQL error details: {e.pgerror}", "Database")
        log_error(f"Failed query: {original_query}", "Database")
        log_error(f"Query parameters: {original_params}", "Database")
        if connection and not USE_POSTGRES:
            connection.rollback()
        raise
    except sqlite3.Error as e:
        log_error(f"SQLite query error: {str(e)}", "Database", e)
        log_error(f"Failed query: {original_query}", "Database")
        log_error(f"Query parameters: {original_params}", "Database")
        if connection:
            connection.rollback()
        raise
    except Exception as e:
        log_error(f"Unexpected query error: {type(e).__name__}", "Database", e)
        log_error(f"Error details: {str(e)}", "Database")
        log_error(f"Failed query: {original_query}", "Database")
        log_error(f"Stack trace: {traceback.format_exc()}", "Database")
        if connection and not USE_POSTGRES:
            connection.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
            log_info("Database connection closed", "Database")

# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

def init_database():
    """Initialize database tables if they don't exist"""
    try:
        log_info("Starting database initialization", "Database")
        
        # Create users table
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
        
        # Create videos table
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
            description TEXT,
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
            heygen_avatar_id TEXT,
            avatar_name TEXT,
            avatar_image_url TEXT,
            preview_video_url TEXT,
            is_default INTEGER DEFAULT 0,
            is_custom BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
        '''
        
        tables_to_create = [
            ("users", users_table),
            ("videos", videos_table),
            ("user_avatars", avatars_table)
        ]
        
        if USE_POSTGRES and POSTGRESQL_AVAILABLE:
            log_info("Creating tables with PostgreSQL", "Database")
            conn = get_db_connection()
            cursor = conn.cursor()
            
            for table_name, table_sql in tables_to_create:
                try:
                    log_info(f"Creating table: {table_name}", "Database")
                    cursor.execute(table_sql)
                    log_info(f"Table {table_name} created successfully", "Database")
                except psycopg2.Error as e:
                    if "already exists" in str(e):
                        log_info(f"Table {table_name} already exists", "Database")
                    else:
                        log_error(f"Error creating table {table_name}: {e}", "Database")
                        raise
            
            conn.close()
        else:
            log_info("Creating tables with SQLite", "Database")
            # Modify for SQLite
            modified_tables = []
            for table_name, table_sql in tables_to_create:
                table_sql = table_sql.replace('SERIAL PRIMARY KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT')
                modified_tables.append((table_name, table_sql))
            
            conn = get_db_connection()
            conn.execute("PRAGMA foreign_keys = ON")
            
            for table_name, table_sql in modified_tables:
                try:
                    log_info(f"Creating SQLite table: {table_name}", "Database")
                    conn.execute(table_sql)
                    log_info(f"SQLite table {table_name} created successfully", "Database")
                except sqlite3.Error as e:
                    if "already exists" in str(e):
                        log_info(f"SQLite table {table_name} already exists", "Database")
                    else:
                        log_error(f"Error creating SQLite table {table_name}: {e}", "Database")
                        raise
            
            conn.close()
            
        log_info("Database initialization completed successfully", "Database")
        
        # Update schema after initialization
        update_database_schema()
        
    except Exception as e:
        log_error("Failed to initialize database", "Database", e)
        log_error(f"Stack trace: {traceback.format_exc()}", "Database")
        raise

def update_database_schema():
    """Update database schema if needed"""
    try:
        log_info("Starting database schema update", "Database")
        
        # Add heygen_avatar_id column if it doesn't exist
        if USE_POSTGRES:
            # Check if column exists
            check_column = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='user_avatars' AND column_name='heygen_avatar_id'
            """
            result = execute_query(check_column, fetch_all=True)
            
            if not result:
                log_info("Adding heygen_avatar_id column to user_avatars table", "Database")
                execute_query("ALTER TABLE user_avatars ADD COLUMN heygen_avatar_id TEXT")
                
                # Populate heygen_avatar_id with avatar_id values
                log_info("Populating heygen_avatar_id with avatar_id values", "Database")
                execute_query("UPDATE user_avatars SET heygen_avatar_id = avatar_id WHERE heygen_avatar_id IS NULL")
                
                log_info("heygen_avatar_id column added and populated successfully", "Database")
            else:
                log_info("heygen_avatar_id column already exists", "Database")
        else:
            # SQLite - check if column exists
            try:
                execute_query("SELECT heygen_avatar_id FROM user_avatars LIMIT 1", fetch_one=True)
                log_info("heygen_avatar_id column already exists in SQLite", "Database")
            except:
                log_info("Adding heygen_avatar_id column to user_avatars table (SQLite)", "Database")
                execute_query("ALTER TABLE user_avatars ADD COLUMN heygen_avatar_id TEXT")
                
                # Populate heygen_avatar_id with avatar_id values
                log_info("Populating heygen_avatar_id with avatar_id values (SQLite)", "Database")
                execute_query("UPDATE user_avatars SET heygen_avatar_id = avatar_id WHERE heygen_avatar_id IS NULL")
                
                log_info("heygen_avatar_id column added and populated successfully (SQLite)", "Database")
        
        log_info("Database schema update completed successfully", "Database")
        
    except Exception as e:
        log_error("Failed to update database schema", "Database", e)
        log_error(f"Stack trace: {traceback.format_exc()}", "Database")
        # Don't raise - schema updates should be non-fatal
        log_warning("Continuing despite schema update failure", "Database")
