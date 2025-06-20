"""
Set voice ID for testuser
"""
import os
import sqlite3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def set_testuser_voice():
    """Set the voice ID for testuser account"""
    # Connection to SQLite database
    db_path = os.getenv("DATABASE_URL", "myavatar.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Voice ID to set
    voice_id = "0f04c50500bf417396ba2e846d7bd3d7"
    
    try:
        # Find testuser's ID
        cursor.execute("SELECT id, username, avatar_id FROM users WHERE username = ?", ("testuser",))
        testuser = cursor.fetchone()
        
        if not testuser:
            print("Error: testuser not found in database")
            return False
        
        testuser_id = testuser["id"]
        print(f"Found testuser with ID: {testuser_id}")
        
        # Check if user_settings table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_settings'")
        if not cursor.fetchone():
            print("Creating user_settings table...")
            cursor.execute("""
                CREATE TABLE user_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    setting_name TEXT NOT NULL,
                    setting_value TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, setting_name),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
        
        # Insert or update voice_id setting
        cursor.execute("""
            INSERT INTO user_settings (user_id, setting_name, setting_value)
            VALUES (?, 'voice_id', ?)
            ON CONFLICT(user_id, setting_name) 
            DO UPDATE SET setting_value=excluded.setting_value
        """, (testuser_id, voice_id))
        
        # Also update it in the users table if that column exists
        try:
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'")
            table_def = cursor.fetchone()[0]
            if "voice_id" in table_def:
                cursor.execute("UPDATE users SET voice_id = ? WHERE id = ?", (voice_id, testuser_id))
        except:
            print("No voice_id column in users table")
        
        # Commit changes
        conn.commit()
        print(f"Successfully set testuser's voice ID to {voice_id}")
        return True
        
    except Exception as e:
        print(f"Error: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("Setting testuser voice ID...")
    if set_testuser_voice():
        print("Success! Testuser voice ID has been set.")
    else:
        print("Failed to set testuser voice ID.")
