#!/usr/bin/env python3
"""
Update production avatar image URLs with fresh HeyGen API data
This script connects directly to production PostgreSQL and updates broken image URLs
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import requests
import json

def get_production_connection():
    """Get connection to production PostgreSQL database"""
    load_dotenv()
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise Exception("DATABASE_URL not found in environment")
    
    return psycopg2.connect(database_url, cursor_factory=RealDictCursor)

def get_fresh_heygen_avatars(api_key):
    """Get fresh avatar data from HeyGen API v2"""
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    try:
        print("🌐 Fetching fresh avatar data from HeyGen API v2...")
        response = requests.get(
            "https://api.heygen.com/v2/avatars",
            headers=headers,
            timeout=30
        )
        
        print(f"📡 HeyGen API response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Handle v2 response format
            avatars = []
            if "data" in data:
                avatars.extend(data["data"].get("avatars", []))
                avatars.extend(data["data"].get("talking_photos", []))
            
            print(f"✅ Retrieved {len(avatars)} avatars from HeyGen")
            return avatars
        else:
            print(f"❌ HeyGen API error: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        print(f"❌ Error fetching from HeyGen API: {e}")
        return []

def update_production_avatar_images():
    try:
        # Load environment variables
        load_dotenv()
        
        print("🔧 Updating Production Avatar Images")
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
        db_avatars = cursor.fetchall()
        
        print(f"📊 Found {len(db_avatars)} avatars in production database")
        
        # Get fresh avatar data from HeyGen API
        heygen_avatars = get_fresh_heygen_avatars(api_key)
        
        if not heygen_avatars:
            print("❌ No avatars retrieved from HeyGen API")
            return
        
        # Create lookup dictionary for HeyGen avatars
        heygen_lookup = {}
        for avatar in heygen_avatars:
            # Handle both avatar_id and id fields
            avatar_id = avatar.get('avatar_id') or avatar.get('id')
            if avatar_id:
                heygen_lookup[avatar_id] = avatar
        
        print(f"🔍 Created lookup for {len(heygen_lookup)} HeyGen avatars")
        
        # Check and update each avatar
        updates_made = 0
        broken_urls = 0
        working_urls = 0
        
        for db_avatar in db_avatars:
            avatar_id = db_avatar['avatar_id']
            current_url = db_avatar['avatar_image_url']
            avatar_name = db_avatar['avatar_name']
            username = db_avatar['username']
            
            print(f"\n👤 {username} - {avatar_name}")
            print(f"   ID: {avatar_id}")
            
            # Check if current URL is accessible
            url_working = False
            if current_url and current_url.startswith('http'):
                try:
                    response = requests.head(current_url, timeout=10)
                    if response.status_code == 200:
                        url_working = True
                        working_urls += 1
                        print(f"   ✅ Current URL working")
                    else:
                        broken_urls += 1
                        print(f"   ❌ Current URL returns {response.status_code}")
                except Exception as e:
                    broken_urls += 1
                    print(f"   ❌ Current URL error: {str(e)[:50]}...")
            else:
                broken_urls += 1
                print(f"   ❌ Invalid current URL")
            
            # If URL is broken, try to fix it
            if not url_working:
                if avatar_id in heygen_lookup:
                    heygen_avatar = heygen_lookup[avatar_id]
                    
                    # Try different image URL fields from HeyGen response
                    new_url = (
                        heygen_avatar.get('preview_image_url') or 
                        heygen_avatar.get('image_url') or
                        heygen_avatar.get('preview_image') or
                        heygen_avatar.get('thumbnail_image_url')
                    )
                    
                    if new_url and new_url != current_url:
                        print(f"   🔄 Testing new URL: {new_url[:60]}...")
                        
                        # Test new URL before updating
                        try:
                            test_response = requests.head(new_url, timeout=10)
                            if test_response.status_code == 200:
                                # Update database
                                cursor.execute("""
                                    UPDATE user_avatars 
                                    SET avatar_image_url = %s 
                                    WHERE id = %s
                                """, (new_url, db_avatar['id']))
                                
                                updates_made += 1
                                print(f"   ✅ Updated successfully")
                            else:
                                print(f"   ⚠️  New URL also returns {test_response.status_code}")
                        except Exception as e:
                            print(f"   ⚠️  New URL also broken: {str(e)[:30]}...")
                    else:
                        print(f"   ⚠️  No new URL available from HeyGen")
                else:
                    print(f"   ⚠️  Avatar ID not found in HeyGen API response")
        
        # Commit changes
        if updates_made > 0:
            conn.commit()
            print(f"\n🎉 Successfully updated {updates_made} avatar image URLs!")
        else:
            print(f"\n⚠️  No updates made")
        
        print(f"📊 Summary:")
        print(f"   ✅ Working URLs: {working_urls}")
        print(f"   ❌ Broken URLs: {broken_urls}")
        print(f"   🔄 Fixed URLs: {updates_made}")
        
        # Test a few updated URLs
        if updates_made > 0:
            print(f"\n🧪 Testing updated URLs...")
            cursor.execute("""
                SELECT avatar_name, avatar_image_url 
                FROM user_avatars 
                WHERE avatar_image_url IS NOT NULL
                ORDER BY id DESC
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
        
        print(f"\n🚀 Avatar image update complete!")
        
    except Exception as e:
        print(f"❌ Error updating production avatar images: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    update_production_avatar_images()
