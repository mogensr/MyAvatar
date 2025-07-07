#!/usr/bin/env python3
"""
Debug avatar images issue - check current URLs and identify problems
"""
import os
from dotenv import load_dotenv
from app.db.database import execute_query
import requests

def debug_avatar_images():
    try:
        # Load environment variables
        load_dotenv()
        
        print("🔍 Debugging Avatar Images Issue")
        print("=" * 50)
        
        # Get all avatars with their image URLs
        avatars = execute_query("""
            SELECT ua.id, ua.user_id, ua.avatar_id, ua.avatar_name, ua.avatar_image_url,
                   u.username
            FROM user_avatars ua
            JOIN users u ON ua.user_id = u.id
            ORDER BY ua.user_id, ua.id
        """, fetch_all=True)
        
        print(f"📊 Found {len(avatars)} total avatars")
        
        # Group by user
        users_avatars = {}
        for avatar in avatars:
            user_id = avatar['user_id']
            if user_id not in users_avatars:
                users_avatars[user_id] = []
            users_avatars[user_id].append(avatar)
        
        # Check each user's avatars
        for user_id, user_avatars in users_avatars.items():
            username = user_avatars[0]['username']
            print(f"\n👤 User {user_id} ({username}) - {len(user_avatars)} avatars:")
            
            for avatar in user_avatars:
                avatar_id = avatar['avatar_id']
                avatar_name = avatar['avatar_name']
                image_url = avatar['avatar_image_url']
                
                print(f"  🎭 {avatar_name} (ID: {avatar_id})")
                print(f"     URL: {image_url}")
                
                # Check if URL is accessible
                if image_url:
                    if image_url.startswith('http'):
                        # External URL - test accessibility
                        try:
                            response = requests.head(image_url, timeout=5)
                            if response.status_code == 200:
                                print(f"     ✅ External URL accessible")
                            else:
                                print(f"     ❌ External URL returns {response.status_code}")
                        except Exception as e:
                            print(f"     ❌ External URL error: {e}")
                    elif image_url.startswith('/static'):
                        # Static file - check if exists
                        static_path = f"static{image_url[7:]}"  # Remove /static prefix
                        if os.path.exists(static_path):
                            print(f"     ✅ Static file exists")
                        else:
                            print(f"     ❌ Static file missing: {static_path}")
                    else:
                        print(f"     ⚠️  Unknown URL format")
                else:
                    print(f"     ❌ No image URL")
        
        # Check static directory structure
        print(f"\n📁 Static Directory Structure:")
        static_dirs = ['static', 'static/avatars', 'static/images']
        for dir_path in static_dirs:
            if os.path.exists(dir_path):
                files = os.listdir(dir_path)
                print(f"  ✅ {dir_path}/ - {len(files)} files")
                if len(files) <= 10:  # Show files if not too many
                    for file in files[:10]:
                        print(f"     - {file}")
            else:
                print(f"  ❌ {dir_path}/ - Directory missing")
        
        return avatars
        
    except Exception as e:
        print(f"❌ Error debugging avatar images: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_avatar_images()
