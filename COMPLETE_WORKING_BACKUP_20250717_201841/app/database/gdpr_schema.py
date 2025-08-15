"""
GDPR schema module for MyAvatar
Contains database schema definitions for GDPR-related tables
"""
from app.db.database import execute_query, get_db_connection
from app.logger.log_handler import log_info, log_error

def initialize_gdpr_schema():
    """
    Initialize GDPR-related database schema.
    Creates necessary tables for GDPR compliance if they don't exist.
    """
    log_info("Initializing GDPR database schema...", "Database")
    
    try:
        # Check if we're using PostgreSQL or SQLite
        conn = get_db_connection()
        is_postgres = conn.__class__.__module__.startswith('psycopg2')
        
        # Add GDPR columns to users table
        if is_postgres:
            # PostgreSQL - check if columns exist first
            try:
                execute_query("""
                    ALTER TABLE users 
                    ADD COLUMN IF NOT EXISTS gdpr_consent_given BOOLEAN DEFAULT FALSE,
                    ADD COLUMN IF NOT EXISTS gdpr_consent_timestamp TIMESTAMP,
                    ADD COLUMN IF NOT EXISTS gdpr_consent_version VARCHAR(10)
                """)
                log_info("Added GDPR columns to users table", "Database")
            except Exception as e:
                # Handle case where columns might already exist
                log_error(f"Error adding GDPR columns to users table: {e}", "Database")
        else:
            # SQLite - check columns one by one (SQLite doesn't support ADD COLUMN IF NOT EXISTS)
            columns = execute_query("PRAGMA table_info(users)", fetch_all=True)
            column_names = [col['name'] for col in columns]
            
            if 'gdpr_consent_given' not in column_names:
                execute_query("ALTER TABLE users ADD COLUMN gdpr_consent_given BOOLEAN DEFAULT 0")
                log_info("Added gdpr_consent_given column to users table", "Database")
                
            if 'gdpr_consent_timestamp' not in column_names:
                execute_query("ALTER TABLE users ADD COLUMN gdpr_consent_timestamp TIMESTAMP")
                log_info("Added gdpr_consent_timestamp column to users table", "Database")
                
            if 'gdpr_consent_version' not in column_names:
                execute_query("ALTER TABLE users ADD COLUMN gdpr_consent_version TEXT")
                log_info("Added gdpr_consent_version column to users table", "Database")
                
        # Create gdpr_consent_log table
        if is_postgres:
            execute_query("""
                CREATE TABLE IF NOT EXISTS gdpr_consent_log (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    consent_given BOOLEAN NOT NULL,
                    consent_version VARCHAR(10),
                    ip_address VARCHAR(50),
                    user_agent TEXT,
                    consent_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
        else:
            # SQLite
            execute_query("""
                CREATE TABLE IF NOT EXISTS gdpr_consent_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    email TEXT NOT NULL,
                    consent_given INTEGER NOT NULL,
                    consent_version TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    consent_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)
            
        log_info("Created gdpr_consent_log table", "Database")
        
        # Create account_deletion_log table if needed
        if is_postgres:
            execute_query("""
                CREATE TABLE IF NOT EXISTS account_deletion_log (
                    id SERIAL PRIMARY KEY,
                    deleted_user_id INTEGER NOT NULL,
                    user_email VARCHAR(255) NOT NULL,
                    admin_user_id INTEGER,
                    deletion_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    deletion_reason TEXT
                )
            """)
        else:
            # SQLite
            execute_query("""
                CREATE TABLE IF NOT EXISTS account_deletion_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    deleted_user_id INTEGER NOT NULL,
                    user_email TEXT NOT NULL,
                    admin_user_id INTEGER,
                    deletion_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    deletion_reason TEXT
                )
            """)
            
        log_info("Created account_deletion_log table", "Database")
        log_info("GDPR schema initialization completed successfully!", "Database")
        return True
        
    except Exception as e:
        log_error(f"Error during GDPR schema initialization: {e}", "Database", e)
        return False
