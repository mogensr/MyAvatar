#!/usr/bin/env python3
"""
Quick fix for avatar names - update specific avatars with better names
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

try:
    from db.user_manager import Database
    from logger.log_handler import log_info, log_error
except ImportError:
    try:
        from app.db.user_manager import Database
        from app.logger.log_handler import log_info, log_error
    except ImportError:
        print("❌ Could not import required modules")
        sys.exit(1)

def update_avatar_names():
    """Update specific avatar names with better descriptions"""
    print("🔧 Quick Avatar Name Fix")
    print("=" * 40)
    
    try:
        db = Database()
        print("✅ Database connection established")
        
        # Define better names for specific avatar IDs
        avatar_updates = {
            "0fe4ee2efeb7497182973cc8c75ddaac": "Professional Avatar 1",
            "b5038ba7bd9b4d94ac6b5c9ea70f8d28": "Professional Avatar 2",
            "7c58319b4e02412cb5d83732fb64e93e": "Business Avatar",
            "6ef17fb1237644d5bf0e0cecad883b51": "Casual Avatar",
        }
        
        print(f"🎯 Updating {len(avatar_updates)} avatar names...")
        
        updated_count = 0
        for avatar_id, new_name in avatar_updates.items():
            try:
                # Update avatar name in database
                from db.database import execute_query
                
                # For PostgreSQL, use %s instead of ?
                result = execute_query(
                    "UPDATE user_avatars SET avatar_name = %s WHERE avatar_id = %s",
                    (new_name, avatar_id)
                )
                
                print(f"✅ Updated avatar {avatar_id[:8]}... -> '{new_name}'")
                updated_count += 1
                
            except Exception as e:
                print(f"❌ Error updating avatar {avatar_id[:8]}...: {e}")
        
        print(f"\n📊 Summary: Updated {updated_count} avatar names")
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

if __name__ == "__main__":
    update_avatar_names()
