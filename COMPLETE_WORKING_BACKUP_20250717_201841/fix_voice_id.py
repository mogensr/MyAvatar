#!/usr/bin/env python
"""
Script to add heygen_voice_id column to the users table and update the testuser record
"""
import os
import sqlite3
import logging
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Define the voice ID to set for testuser
VOICE_ID = "0f04c50500bf417396ba2e846d7bd3d7"

def main():
    # Get database path from environment or use default
    db_path = os.getenv("DATABASE_URL", "myavatar.db")
    
    # Connect to the database
    logger.info(f"Connecting to database at {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Check if heygen_voice_id column exists in the users table
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    
    # Add the column if it doesn't exist
    if "heygen_voice_id" not in columns:
        logger.info("Adding heygen_voice_id column to users table")
        cursor.execute("ALTER TABLE users ADD COLUMN heygen_voice_id TEXT")
        conn.commit()
    
    # Update the testuser record with the voice ID
    cursor.execute(
        "UPDATE users SET heygen_voice_id = ? WHERE username = ?",
        (VOICE_ID, "testuser")
    )
    conn.commit()
    
    # Verify the update
    cursor.execute("SELECT id, username, heygen_voice_id FROM users WHERE username = ?", ("testuser",))
    user = cursor.fetchone()
    if user:
        logger.info(f"Updated user {user['username']} (ID: {user['id']}) with voice ID: {user['heygen_voice_id']}")
    else:
        logger.error("Failed to find testuser in the database")
    
    conn.close()
    logger.info("Database update completed")

if __name__ == "__main__":
    main()
