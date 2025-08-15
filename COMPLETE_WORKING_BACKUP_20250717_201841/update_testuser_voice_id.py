#!/usr/bin/env python
"""
Script to update the testuser record with the correct HeyGen voice ID directly in the users table.
This fixes the issue where the system is looking for heygen_voice_id in the users table.
"""
import os
import sqlite3
import logging
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# HeyGen voice ID for testuser
HEYGEN_VOICE_ID = "0f04c50500bf417396ba2e846d7bd3d7"

# Check if using PostgreSQL or SQLite
db_url = os.getenv("DATABASE_URL", "myavatar.db")
using_postgres = db_url.startswith("postgresql://")

def update_user_voice_id():
    """Update the testuser record with the HeyGen voice ID"""
    if using_postgres:
        # PostgreSQL connection
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if column exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' AND column_name='heygen_voice_id'
        """)
        
        column_exists = cursor.fetchone() is not None
        
        if not column_exists:
            logger.info("Adding heygen_voice_id column to users table")
            cursor.execute("ALTER TABLE users ADD COLUMN heygen_voice_id VARCHAR(255)")
        
        # Update testuser record
        cursor.execute(
            "UPDATE users SET heygen_voice_id = %s WHERE username = %s",
            (HEYGEN_VOICE_ID, "testuser")
        )
        
        # Verify the update
        cursor.execute("SELECT id, username, heygen_voice_id FROM users WHERE username = %s", ("testuser",))
        user = cursor.fetchone()
        if user:
            logger.info(f"Updated user {user['username']} (ID: {user['id']}) with voice ID: {user['heygen_voice_id']}")
        else:
            logger.error("Failed to find testuser")
            
    else:
        # SQLite connection
        conn = sqlite3.connect(db_url)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if "heygen_voice_id" not in columns:
            logger.info("Adding heygen_voice_id column to users table")
            cursor.execute("ALTER TABLE users ADD COLUMN heygen_voice_id TEXT")
        
        # Update testuser record
        cursor.execute(
            "UPDATE users SET heygen_voice_id = ? WHERE username = ?",
            (HEYGEN_VOICE_ID, "testuser")
        )
        conn.commit()
        
        # Verify the update
        cursor.execute("SELECT id, username, heygen_voice_id FROM users WHERE username = ?", ("testuser",))
        user = cursor.fetchone()
        if user:
            logger.info(f"Updated user {user['username']} (ID: {user['id']}) with voice ID: {user['heygen_voice_id']}")
        else:
            logger.error("Failed to find testuser")
    
    conn.close()

if __name__ == "__main__":
    update_user_voice_id()
    logger.info("Script completed")
