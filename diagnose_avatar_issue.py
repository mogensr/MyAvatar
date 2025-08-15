#!/usr/bin/env python3
"""
Comprehensive avatar display issue diagnosis
"""
import os
import sys
import requests
from datetime import datetime

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.db.database import execute_query

def check_database_avatars():
    """Check avatar URLs in database"""
    print("=== DATABASE AVATAR CHECK ===")
    
    try:
        # Get sample of avatar URLs from database
        avatars = execute_query("""
            SELECT ua.id, ua.user_id, ua.avatar_id, ua.avatar_name, ua.avatar_image_url,
                   u.username
            FROM user_avatars ua
            JOIN users u ON ua.user_id = u.id
            ORDER BY ua.created_at DESC
            LIMIT 10
        """, fetch_all=True)
        
        if not avatars:
            print("❌ No avatars found in database")
            return False
            
        print(f"✅ Found {len(avatars)} avatars in database")
        
        for avatar in avatars:
            print(f"\nAvatar ID: {avatar['id']}")
            print(f"User: {avatar['username']} (ID: {avatar['user_id']})")
            print(f"Avatar Name: {avatar['avatar_name']}")
            print(f"HeyGen ID: {avatar['avatar_id']}")
            print(f"Image URL: {avatar['avatar_image_url']}")
            
            # Test URL accessibility
            if avatar['avatar_image_url']:
                test_url_accessibility(avatar['avatar_image_url'])
            else:
                print("❌ No image URL stored")
                
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def test_url_accessibility(url):
    """Test if URL is accessible"""
    if not url:
        print("❌ Empty URL")
        return False
        
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '')
            if 'image' in content_type:
                print(f"✅ URL accessible - {content_type}")
                return True
            else:
                print(f"⚠️  URL accessible but not an image - {content_type}")
                return False
        else:
            print(f"❌ URL returned status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ URL test failed: {e}")
        return False

def check_heygen_api():
    """Check if HeyGen API is accessible"""
    print("\n=== HEYGEN API CHECK ===")
    
    api_key = os.getenv('HEYGEN_API_KEY')
    if not api_key:
        print("❌ HEYGEN_API_KEY not found in environment")
        return False
        
    print("✅ HeyGen API key found")
    
    try:
        headers = {
            'X-API-KEY': api_key,
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            'https://api.heygen.com/v2/avatars',
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ HeyGen API accessible")
            data = response.json()
            avatars = data.get('data', {}).get('avatars', [])
            print(f"✅ Found {len(avatars)} avatars from HeyGen API")
            
            # Show first few avatars
            for i, avatar in enumerate(avatars[:3]):
                print(f"\nHeyGen Avatar {i+1}:")
                print(f"  ID: {avatar.get('avatar_id')}")
                print(f"  Name: {avatar.get('avatar_name', 'Unknown')}")
                print(f"  Preview: {avatar.get('preview_image_url', 'No preview')}")
                
            return True
        else:
            print(f"❌ HeyGen API returned status {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ HeyGen API test failed: {e}")
        return False

def check_environment():
    """Check environment variables"""
    print("\n=== ENVIRONMENT CHECK ===")
    
    required_vars = ['DATABASE_URL', 'HEYGEN_API_KEY']
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if 'KEY' in var or 'PASSWORD' in var:
                masked = value[:8] + '...' + value[-4:] if len(value) > 12 else '***'
                print(f"✅ {var}: {masked}")
            else:
                print(f"✅ {var}: {value}")
        else:
            print(f"❌ {var}: Not set")

def main():
    """Main diagnostic function"""
    print("=== MYAVATAR AVATAR DISPLAY DIAGNOSIS ===")
    print(f"Timestamp: {datetime.now()}")
    
    # Check environment
    check_environment()
    
    # Check database avatars
    db_ok = check_database_avatars()
    
    # Check HeyGen API
    api_ok = check_heygen_api()
    
    print("\n=== DIAGNOSIS SUMMARY ===")
    print(f"Database Access: {'✅' if db_ok else '❌'}")
    print(f"HeyGen API Access: {'✅' if api_ok else '❌'}")
    
    if not db_ok:
        print("\n🔧 RECOMMENDATION: Fix database connection issues first")
    elif not api_ok:
        print("\n🔧 RECOMMENDATION: Check HeyGen API key and connectivity")
    else:
        print("\n🔧 RECOMMENDATION: Check avatar URL formats and web server CORS settings")

if __name__ == "__main__":
    main()
