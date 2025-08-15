#!/usr/bin/env python
"""
Universal script to add heygen_voice_id to users table and update user records.
Works with both SQLite and PostgreSQL databases.
"""
import os
import sys
import logging
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Define voice ID
HEYGEN_VOICE_ID = "0f04c50500bf417396ba2e846d7bd3d7"

# Determine which user to update (defaults to testuser but can be changed)
TARGET_USER = os.getenv("TARGET_USER", "testuser")

def main():
    # Get database connection settings
    db_url = os.getenv("DATABASE_URL", "myavatar.db")
    logger.info(f"Database URL: {db_url}")
    
    # Determine if we're using PostgreSQL or SQLite
    is_postgres = db_url.startswith("postgresql://")
    logger.info(f"Database type: {'PostgreSQL' if is_postgres else 'SQLite'}")
    
    try:
        if is_postgres:
            update_postgres(db_url)
        else:
            update_sqlite(db_url)
    except Exception as e:
        logger.error(f"Error updating database: {str(e)}")
        sys.exit(1)

def update_postgres(db_url):
    """Update the PostgreSQL database"""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        logger.info("Connecting to PostgreSQL database...")
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if column exists
        logger.info("Checking if heygen_voice_id column exists...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' AND column_name='heygen_voice_id'
        """)
        
        column_exists = cursor.fetchone() is not None
        
        if not column_exists:
            logger.info("Adding heygen_voice_id column to users table")
            cursor.execute("ALTER TABLE users ADD COLUMN heygen_voice_id VARCHAR(255)")
        
        # List available users for reference
        logger.info("Available users in database:")
        cursor.execute("SELECT id, username FROM users")
        users = cursor.fetchall()
        for user in users:
            logger.info(f"User ID: {user['id']}, Username: {user['username']}")
        
        # Update specified user record
        logger.info(f"Updating user '{TARGET_USER}' with voice ID: {HEYGEN_VOICE_ID}")
        cursor.execute(
            "UPDATE users SET heygen_voice_id = %s WHERE username = %s",
            (HEYGEN_VOICE_ID, TARGET_USER)
        )
        
        # Also update user voice settings if that table exists
        try:
            cursor.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'user_settings'")
            if cursor.fetchone():
                logger.info("Updating user_settings table with voice ID")
                cursor.execute("SELECT id FROM users WHERE username = %s", (TARGET_USER,))
                user = cursor.fetchone()
                if user:
                    user_id = user['id']
                    # Delete existing voice_id setting if it exists
                    cursor.execute(
                        "DELETE FROM user_settings WHERE user_id = %s AND setting_name = 'voice_id'",
                        (user_id,)
                    )
                    # Insert new voice_id setting
                    cursor.execute(
                        "INSERT INTO user_settings (user_id, setting_name, setting_value) VALUES (%s, %s, %s)",
                        (user_id, "voice_id", HEYGEN_VOICE_ID)
                    )
        except Exception as e:
            logger.warning(f"Could not update user_settings: {str(e)}")
        
        # Verify the update
        cursor.execute("SELECT id, username, heygen_voice_id FROM users WHERE username = %s", (TARGET_USER,))
        user = cursor.fetchone()
        if user:
            logger.info(f"Updated user {user['username']} with voice ID: {user['heygen_voice_id']}")
        else:
            logger.warning(f"User '{TARGET_USER}' not found")
        
        conn.close()
        logger.info("PostgreSQL update completed")
        
    except ImportError:
        logger.error("psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)

def update_sqlite(db_path):
    """Update the SQLite database"""
    import sqlite3
    
    logger.info(f"Connecting to SQLite database at {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Check if column exists
    logger.info("Checking if heygen_voice_id column exists...")
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if "heygen_voice_id" not in columns:
        logger.info("Adding heygen_voice_id column to users table")
        cursor.execute("ALTER TABLE users ADD COLUMN heygen_voice_id TEXT")
    
    # List available users for reference
    logger.info("Available users in database:")
    cursor.execute("SELECT id, username FROM users")
    users = cursor.fetchall()
    for user in users:
        logger.info(f"User ID: {user['id']}, Username: {user['username']}")
    
    # Update specified user record
    logger.info(f"Updating user '{TARGET_USER}' with voice ID: {HEYGEN_VOICE_ID}")
    cursor.execute(
        "UPDATE users SET heygen_voice_id = ? WHERE username = ?",
        (HEYGEN_VOICE_ID, TARGET_USER)
    )
    conn.commit()
    
    # Also update user_settings if that table exists
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_settings'")
        if cursor.fetchone():
            logger.info("Updating user_settings table with voice ID")
            cursor.execute("SELECT id FROM users WHERE username = ?", (TARGET_USER,))
            user = cursor.fetchone()
            if user:
                user_id = user['id']
                # Delete existing voice_id setting if it exists
                cursor.execute(
                    "DELETE FROM user_settings WHERE user_id = ? AND setting_name = ?",
                    (user_id, "voice_id")
                )
                # Insert new voice_id setting
                cursor.execute(
                    "INSERT INTO user_settings (user_id, setting_name, setting_value) VALUES (?, ?, ?)",
                    (user_id, "voice_id", HEYGEN_VOICE_ID)
                )
                conn.commit()
    except Exception as e:
        logger.warning(f"Could not update user_settings: {str(e)}")
    
    # Verify the update
    cursor.execute("SELECT id, username, heygen_voice_id FROM users WHERE username = ?", (TARGET_USER,))
    user = cursor.fetchone()
    if user:
        logger.info(f"Updated user {user['username']} with voice ID: {user['heygen_voice_id'] if 'heygen_voice_id' in user.keys() else None}")
    else:
        logger.warning(f"User '{TARGET_USER}' not found")
        
        # Show all usernames for reference
        logger.info("All available usernames:")
        cursor.execute("SELECT username FROM users")
        all_users = [user['username'] for user in cursor.fetchall()]
        logger.info(', '.join(all_users))
    
    conn.close()
    logger.info("SQLite update completed")

if __name__ == "__main__":
    main()
