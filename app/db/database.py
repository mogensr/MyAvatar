"""
Database functions for MyAvatar
Supports both SQLite and PostgreSQL
FIXED VERSION - PostgreSQL now returns dictionary-like objects
FIXED: is_default column changed from BOOLEAN to INTEGER to match queries
ENHANCED: Added comprehensive error logging and debugging
"""
import os
import sqlite3
from datetime import datetime
import traceback
from ..logger.log_handler import log_info, log_error, log_warning

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

# ============================================================================
# DATABASE CONNECTION FUNCTIONS - ENHANCED WITH ERROR LOGGING
# ============================================================================

def get_db_connection():
    """Get a database connection based on configuration with enhanced error logging"""
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
        log_error(f"Database URL (masked): {DATABASE_URL[:20]}...", "Database")
        raise
    except sqlite3.Error as e:
        log_error(f"SQLite connection failed: {str(e)}", "Database", e)
        raise
    except Exception as e:
        log_error(f"Unexpected database connection error: {type(e).__name__}", "Database", e)
        log_error(f"Error details: {str(e)}", "Database")
        raise

def execute_query(query: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = False):
    """Execute SQL query with comprehensive error handling and logging"""
    connection = None
    cursor = None
    original_query = query
    
    try:
        log_info(f"Executing query: {query[:100]}{'...' if len(query) > 100 else ''}", "Database")
        log_info(f"Query parameters: {params}", "Database")
        
        # Convert SQLite placeholders to PostgreSQL placeholders
        if USE_POSTGRES and "?" in query:
            query = query.replace("?", "%s")
            log_info(f"Converted query placeholders for PostgreSQL", "Database")
            
        connection = get_db_connection()
        
        # Use RealDictCursor for PostgreSQL to return dictionary-like objects
        if USE_POSTGRES:
            cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            log_info("Using PostgreSQL RealDictCursor", "Database")
        else:
            cursor = connection.cursor()
            log_info("Using SQLite cursor", "Database")
            
        # Execute query with detailed logging
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
            if not USE_POSTGRES:  # PostgreSQL has autocommit=True
                connection.commit()
            log_info("Query committed successfully", "Database")
            return None
            
    except psycopg2.Error as e:
        log_error(f"PostgreSQL query error - Code: {e.pgcode}", "Database", e)
        log_error(f"PostgreSQL error details: {e.pgerror}", "Database")
        log_error(f"Failed query: {original_query}", "Database")
        log_error(f"Query parameters: {params}", "Database")
        if connection and not USE_POSTGRES:
            connection.rollback()
            log_info("Transaction rolled back", "Database")
        raise
    except sqlite3.Error as e:
        log_error(f"SQLite query error: {str(e)}", "Database", e)
        log_error(f"Failed query: {original_query}", "Database")
        log_error(f"Query parameters: {params}", "Database")
        if connection:
            connection.rollback()
            log_info("Transaction rolled back", "Database")
        raise
    except Exception as e:
        log_error(f"Unexpected query error: {type(e).__name__}", "Database", e)
        log_error(f"Error details: {str(e)}", "Database")
        log_error(f"Failed query: {original_query}", "Database")
        log_error(f"Query parameters: {params}", "Database")
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
# DATABASE INITIALIZATION - FIXED is_default COLUMN
# ============================================================================

def init_database():
    """Initialize database tables if they don't exist - FIXED VERSION"""
    try:
        log_info("Starting database initialization", "Database")
        
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
        
        # FIXED: Create user_avatars table - Changed is_default from BOOLEAN to INTEGER
        avatars_table = '''
        CREATE TABLE IF NOT EXISTS user_avatars (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            avatar_id TEXT NOT NULL,
            avatar_name TEXT,
            avatar_image_url TEXT,
            preview_video_url TEXT,
            is_default INTEGER DEFAULT 0,
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
        
        # Create backgrounds table (since it's referenced in your error search)
        backgrounds_table = '''
        CREATE TABLE IF NOT EXISTS backgrounds (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            file_path TEXT,
            thumbnail_path TEXT,
            is_default INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
        
        tables_to_create = [
            ("users", users_table),
            ("videos", videos_table),
            ("user_avatars", avatars_table),
            ("settings", settings_table),
            ("api_logs", logs_table),
            ("templates", templates_table),
            ("backgrounds", backgrounds_table)
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
                table_sql = table_sql.replace('REAL', 'REAL')
                table_sql = table_sql.replace('TIMESTAMP', 'TIMESTAMP')
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
        
        # Verify tables were created
        verify_database_schema()
        
    except Exception as e:
        log_error("Failed to initialize database", "Database", e)
        log_error(f"Initialization error details: {str(e)}", "Database")
        log_error(f"Stack trace: {traceback.format_exc()}", "Database")
        raise

def verify_database_schema():
    """Verify database schema is correct"""
    try:
        log_info("Verifying database schema", "Database")
        
        if USE_POSTGRES:
            # Check PostgreSQL schema
            schema_query = """
            SELECT table_name, column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'user_avatars' 
            ORDER BY ordinal_position
            """
        else:
            # Check SQLite schema
            schema_query = "PRAGMA table_info(user_avatars)"
            
        result = execute_query(schema_query, fetch_all=True)
        
        if result:
            log_info("user_avatars table schema:", "Database")
            for row in result:
                log_info(f"  {dict(row)}", "Database")
                
            # Check specifically for is_default column
            is_default_found = False
            for row in result:
                row_dict = dict(row)
                if USE_POSTGRES:
                    if row_dict.get('column_name') == 'is_default':
                        is_default_found = True
                        log_info(f"is_default column type: {row_dict.get('data_type')}", "Database")
                else:
                    if row_dict.get('name') == 'is_default':
                        is_default_found = True
                        log_info(f"is_default column type: {row_dict.get('type')}", "Database")
            
            if not is_default_found:
                log_warning("is_default column not found in user_avatars table!", "Database")
            else:
                log_info("is_default column verified in user_avatars table", "Database")
        else:
            log_warning("user_avatars table not found or empty schema", "Database")
            
    except Exception as e:
        log_error("Failed to verify database schema", "Database", e)
        # Don't raise here, just log the warning

def update_database_schema():
    """Update database schema for premium features"""
    try:
        log_info("Checking database schema updates", "Database")
        
        # Check if we need to migrate is_default from BOOLEAN to INTEGER
        try:
            # Test query to see if we have the boolean/integer mismatch
            test_query = "SELECT is_default FROM user_avatars WHERE is_default = 1 LIMIT 1"
            execute_query(test_query, fetch_one=True)
            log_info("is_default column accepts integer values - schema is correct", "Database")
        except Exception as e:
            if "operator does not exist: boolean = integer" in str(e):
                log_warning("Detected boolean/integer mismatch in is_default column", "Database")
                log_info("This should be fixed by recreating the database with the new schema", "Database")
            else:
                log_info("Schema test completed", "Database")
        
        log_info("Database schema check complete", "Database")
        
    except Exception as e:
        log_error("Failed to update database schema", "Database", e)
        # Don't raise here unless it's critical

# ============================================================================
# HELPER FUNCTIONS - ENHANCED
# ============================================================================

def get_placeholder():
    """Get the correct placeholder for the database type"""
    placeholder = "%s" if USE_POSTGRES else "?"
    log_info(f"Using database placeholder: {placeholder}", "Database")
    return placeholder

def format_query(query: str):
    """Format query for current database type"""
    original_query = query
    if USE_POSTGRES and "?" in query:
        query = query.replace("?", "%s")
        log_info(f"Query formatted for PostgreSQL: {original_query} -> {query}", "Database")
    return query

def log_database_stats():
    """Log current database statistics for debugging"""
    try:
        log_info("=== DATABASE STATISTICS ===", "Database")
        log_info(f"Database Type: {'PostgreSQL' if USE_POSTGRES else 'SQLite'}", "Database")
        log_info(f"PostgreSQL Available: {POSTGRESQL_AVAILABLE}", "Database")
        
        # Count records in main tables
        tables_to_check = ['users', 'videos', 'user_avatars', 'backgrounds']
        
        for table in tables_to_check:
            try:
                count_query = f"SELECT COUNT(*) as count FROM {table}"
                result = execute_query(count_query, fetch_one=True)
                count = result['count'] if result else 0
                log_info(f"{table} table: {count} records", "Database")
            except Exception as e:
                log_warning(f"Could not count records in {table}: {str(e)}", "Database")
        
        log_info("=== END DATABASE STATISTICS ===", "Database")
        
    except Exception as e:
        log_error("Failed to generate database statistics", "Database", e)

# ============================================================================
# END OF FILE
# ============================================================================