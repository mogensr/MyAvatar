import os
import sys
sys.path.append('.')

try:
    from app.db.user_manager import Database
    from app.logger.log_handler import log_info, log_error
except ImportError:
    try:
        from db.user_manager import Database
        from logger.log_handler import log_info, log_error
    except ImportError:
        print("❌ Could not import required modules")
        sys.exit(1)

def check_users():
    """Check what users exist in the database"""
    try:
        db = Database()
        print("✅ Database connection established")
        
        # Try to get all users
        print("\n🔍 Checking users in database...")
        
        try:
            # Try direct query
            from db.database import execute_query
            result = execute_query("SELECT id, username, email FROM users", fetch_all=True)
            if result:
                print("📋 Users found:")
                for row in result:
                    print(f"  ID: {row[0]}, Username: '{row[1]}', Email: {row[2]}")
            else:
                print("❌ No users found")
        except Exception as e:
            print(f"❌ Error querying users: {e}")
            
    except Exception as e:
        print(f"❌ Database connection failed: {e}")

if __name__ == "__main__":
    check_users()
