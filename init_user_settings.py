#!/usr/bin/env python3
"""
Initialize user_settings table for MyAvatar
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.user_manager import Database

def main():
    """Initialize the user_settings table"""
    print("Initializing user_settings table...")
    
    db = Database()
    success = db.create_user_settings_table()
    
    if success:
        print("✅ user_settings table created successfully!")
        
        # Set a default voice ID for existing users
        print("Setting default voice ID for users...")
        default_voice_id = "0f04c50500bf417396ba2e846d7bd3d7"  # Valid HeyGen voice ID
        
        # You can add logic here to set default voice for specific users
        # For now, we'll just confirm the table is ready
        print(f"✅ Ready to use voice_id: {default_voice_id}")
        
    else:
        print("❌ Failed to create user_settings table")
        return False
    
    return True

if __name__ == "__main__":
    main()
