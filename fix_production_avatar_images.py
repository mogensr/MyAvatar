#!/usr/bin/env python3
"""
Fix broken avatar image URLs in PRODUCTION database by updating with fresh HeyGen API data
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from app.api.heygen import get_available_avatars
import requests
import json

def get_production_connection():
    """Get connection to production PostgreSQL database"""
    load_dotenv()
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise Exception("DATABASE_URL not found in environment")
    
    return psycopg2.connect(database_url, cursor_factory=RealDictCursor)

def fix_production_avatar_images():
    try:
        # Load environment variables
        load_dotenv()
        
        print("🔧 Fixing Production Avatar Images")
        print("=" * 45)
        
        # Get API key
        api_key = os.getenv("HEYGEN_API_KEY")
        if not api_key:
            print("❌ HEYGEN_API_KEY not found in environment")
            return
        
        # Connect to production database
        print("🔌 Connecting to production database...")
        conn = get_production_connection()
        cursor = conn.cursor()
        
        # Get all avatars from production database
        cursor.execute("""
            SELECT ua.id, ua.user_id, ua.avatar_id, ua.avatar_name, ua.avatar_image_url,
                   u.username
            FROM user_avatars ua
            JOIN users u ON ua.user_id = u.id
            ORDER BY ua.user_id, ua.id
        """)
        avatars = cursor.fetchall()
        
        print(f"📊 Found {len(avatars)} avatars in production")
        
        # Get fresh avatar data from HeyGen API
        print("🌐 Fetching fresh avatar data from HeyGen API...")
        heygen_avatars = get_available_avatars(api_key)
        
        if not heygen_avatars:
            print("❌ Failed to get avatars from HeyGen API")
            return
        
        print(f"✅ Got {len(heygen_avatars)} avatars from HeyGen API")
        
        # Create lookup dictionary for HeyGen avatars
        heygen_lookup = {}
        for avatar in heygen_avatars:
            avatar_id = avatar.get('avatar_id')
            if avatar_id:
                heygen_lookup[avatar_id] = avatar
        
        # Check and update each avatar
        updates_made = 0
        broken_urls = 0
        
        for avatar in avatars:
            avatar_id = avatar['avatar_id']
            current_url = avatar['avatar_image_url']
            avatar_name = avatar['avatar_name']
            user_id = avatar['user_id']
            username = avatar['username']
            
            print(f"\n👤 {username} - {avatar_name}")
            print(f"   ID: {avatar_id}")
            
            # Check if current URL is accessible
            url_working = False
            if current_url and current_url.startswith('http'):
                try:
                    response = requests.head(current_url, timeout=10)
                    if response.status_code == 200:
                        url_working = True
                        print(f"   ✅ Current URL working")
                    else:
                        print(f"   ❌ Current URL returns {response.status_code}")
                        broken_urls += 1
                except Exception as e:
                    print(f"   ❌ Current URL error: {str(e)[:50]}...")
                    broken_urls += 1
            else:
                print(f"   ❌ Invalid current URL")
                broken_urls += 1
            
            # If URL is broken, try to fix it
            if not url_working:
                if avatar_id in heygen_lookup:
                    heygen_avatar = heygen_lookup[avatar_id]
                    new_url = heygen_avatar.get('preview_image_url') or heygen_avatar.get('image_url')
                    
                    if new_url and new_url != current_url:
                        print(f"   🔄 New URL: {new_url[:60]}...")
                        
                        # Test new URL before updating
                        try:
                            test_response = requests.head(new_url, timeout=10)
                            if test_response.status_code == 200:
                                # Update database
                                cursor.execute("""
                                    UPDATE user_avatars 
                                    SET avatar_image_url = %s 
                                    WHERE id = %s
                                """, (new_url, avatar['id']))
                                
                                updates_made += 1
                                print(f"   ✅ Updated successfully")
                            else:
                                print(f"   ⚠️  New URL also returns {test_response.status_code}")
                        except Exception as e:
                            print(f"   ⚠️  New URL also broken: {str(e)[:30]}...")
                    else:
                        print(f"   ⚠️  No better URL available from HeyGen")
                else:
                    print(f"   ⚠️  Avatar ID not found in HeyGen API")
        
        # Commit changes
        if updates_made > 0:
            conn.commit()
            print(f"\n🎉 Successfully updated {updates_made} avatar image URLs")
            print(f"📊 Found {broken_urls} broken URLs total")
        else:
            print(f"\n⚠️  No updates made. Found {broken_urls} broken URLs")
        
        # Test a few updated URLs
        if updates_made > 0:
            print("\n🧪 Testing updated URLs...")
            cursor.execute("""
                SELECT avatar_name, avatar_image_url 
                FROM user_avatars 
                WHERE avatar_image_url LIKE 'https://files%heygen%'
                ORDER BY id
                LIMIT 3
            """)
            updated_avatars = cursor.fetchall()
            
            for avatar in updated_avatars:
                name = avatar['avatar_name']
                url = avatar['avatar_image_url']
                try:
                    response = requests.head(url, timeout=5)
                    status = "✅ Working" if response.status_code == 200 else f"❌ {response.status_code}"
                    print(f"   {name}: {status}")
                except Exception as e:
                    print(f"   {name}: ❌ Error")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error fixing production avatar images: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_production_avatar_images()
