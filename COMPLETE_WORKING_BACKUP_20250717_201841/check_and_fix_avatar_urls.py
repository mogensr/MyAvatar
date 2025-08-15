#!/usr/bin/env python3
"""
Check current avatar URLs and fix them if needed
"""
import os
import sys
import requests
from dotenv import load_dotenv

# Load environment
load_dotenv()
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

def check_and_fix_avatars():
    """Check current avatar URLs and fix incomplete ones"""
    try:
        from app.db.database import execute_query
        from app.services.heygen_service import get_available_avatars
        
        print("=== CHECKING AVATAR URLs ===")
        
        # Get current avatars from database
        avatars = execute_query("""
            SELECT id, avatar_id, avatar_name, avatar_image_url
            FROM user_avatars
            ORDER BY created_at DESC
        """, fetch_all=True)
        
        print(f"Found {len(avatars)} avatars in database")
        
        incomplete_count = 0
        fixed_count = 0
        
        for avatar in avatars:
            url = avatar['avatar_image_url']
            print(f"\nAvatar: {avatar['avatar_name']}")
            print(f"Current URL: {url}")
            
            # Check if URL is incomplete (doesn't end with .jpg/.png)
            if url and not url.endswith(('.jpg', '.png', '.jpeg')):
                incomplete_count += 1
                print("❌ URL is incomplete - missing file extension")
                
                # Try to fix by adding .jpg
                fixed_url = url + '.jpg'
                print(f"Trying fixed URL: {fixed_url}")
                
                # Test if the fixed URL works
                try:
                    response = requests.head(fixed_url, timeout=10)
                    if response.status_code == 200:
                        print("✅ Fixed URL works! Updating database...")
                        
                        # Update database
                        execute_query("""
                            UPDATE user_avatars 
                            SET avatar_image_url = ?
                            WHERE id = ?
                        """, (fixed_url, avatar['id']))
                        
                        fixed_count += 1
                        print("✅ Database updated successfully")
                    else:
                        print(f"❌ Fixed URL doesn't work (status: {response.status_code})")
                except Exception as e:
                    print(f"❌ Error testing fixed URL: {e}")
            else:
                print("✅ URL looks complete")
        
        print(f"\n=== SUMMARY ===")
        print(f"Total avatars: {len(avatars)}")
        print(f"Incomplete URLs found: {incomplete_count}")
        print(f"URLs fixed: {fixed_count}")
        
        if fixed_count > 0:
            print("\n🎉 Avatar URLs have been fixed! Try refreshing your browser.")
        
        return fixed_count > 0
        
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    check_and_fix_avatars()
