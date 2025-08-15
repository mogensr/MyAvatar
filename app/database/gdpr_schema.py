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
        # Enforce PostgreSQL-only
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
        
        # Create gdpr_consent_log table (PostgreSQL only)
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
        log_info("Created gdpr_consent_log table", "Database")
        # Create account_deletion_log table (PostgreSQL only)
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
        log_info("Created account_deletion_log table", "Database")
        log_info("GDPR schema initialization completed successfully!", "Database")
        return True
        
    except Exception as e:
        log_error(f"Error during GDPR schema initialization: {e}", "Database", e)
        return False
