"""
Fix testuser avatar - assigns the specified HeyGen public avatar to the testuser account
"""
import os
import sqlite3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def ensure_testuser_avatar():
    """Ensure testuser has a valid avatar_id associated with their account"""
    # Connection to SQLite database
    db_path = os.getenv("DATABASE_URL", "myavatar.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Set these avatar IDs
    abigail_avatar_id = "Abigail_expressive_2024112501"
    adrian_avatar_id = "Adrian_public_2_20240312"
    
    try:
        # First, find testuser's ID
        cursor.execute("SELECT id, username, avatar_id FROM users WHERE username = ?", ("testuser",))
        testuser = cursor.fetchone()
        
        if not testuser:
            print("Error: testuser not found in database")
            return False
        
        testuser_id = testuser["id"]
        print(f"Found testuser with ID: {testuser_id}, current avatar_id: {testuser['avatar_id']}")
        
        # Check if user already has avatar entries
        cursor.execute("SELECT * FROM user_avatars WHERE user_id = ?", (testuser_id,))
        existing_avatars = cursor.fetchall()
        
        if existing_avatars:
            print(f"Found {len(existing_avatars)} existing avatars for testuser")
            
            # Check if any of the existing avatars match our target avatars
            has_abigail = any(a["avatar_id"] == abigail_avatar_id for a in existing_avatars)
            has_adrian = any(a["avatar_id"] == adrian_avatar_id for a in existing_avatars)
            
            if not has_abigail:
                print(f"Adding Abigail avatar for testuser")
                cursor.execute(
                    """
                    INSERT INTO user_avatars (user_id, avatar_id, avatar_name, avatar_image_url, is_default)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (testuser_id, abigail_avatar_id, "Abigail (Public)", "/static/avatars/default_female.png", False)
                )
                
            if not has_adrian:
                print(f"Adding Adrian avatar for testuser")
                cursor.execute(
                    """
                    INSERT INTO user_avatars (user_id, avatar_id, avatar_name, avatar_image_url, is_default)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (testuser_id, adrian_avatar_id, "Adrian (Public)", "/static/avatars/default_male.png", True)
                )
                
            # Make sure Adrian is the default
            cursor.execute(
                "UPDATE user_avatars SET is_default = CASE WHEN avatar_id = ? THEN 1 ELSE 0 END WHERE user_id = ?",
                (adrian_avatar_id, testuser_id)
            )
        else:
            print("No avatars found for testuser, adding both public avatars")
            
            # Add both avatars
            cursor.execute(
                """
                INSERT INTO user_avatars (user_id, avatar_id, avatar_name, avatar_image_url, is_default)
                VALUES (?, ?, ?, ?, ?)
                """,
                (testuser_id, abigail_avatar_id, "Abigail (Public)", "/static/avatars/default_female.png", False)
            )
            
            cursor.execute(
                """
                INSERT INTO user_avatars (user_id, avatar_id, avatar_name, avatar_image_url, is_default)
                VALUES (?, ?, ?, ?, ?)
                """,
                (testuser_id, adrian_avatar_id, "Adrian (Public)", "/static/avatars/default_male.png", True)
            )
        
        # Update the user's primary avatar_id
        cursor.execute(
            "UPDATE users SET avatar_id = ? WHERE id = ?",
            (adrian_avatar_id, testuser_id)
        )
        
        # Commit changes
        conn.commit()
        print(f"Successfully updated testuser's avatar to {adrian_avatar_id}")
        return True
        
    except Exception as e:
        print(f"Error: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("Fixing testuser avatar...")
    if ensure_testuser_avatar():
        print("Success! Testuser avatar has been fixed.")
    else:
        print("Failed to fix testuser avatar.")
