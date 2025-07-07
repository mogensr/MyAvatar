#!/usr/bin/env python3
"""
Fix avatar URLs in Railway production database
Run this after deploying to Railway to fix avatar image display
"""
import os
import sys
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add app to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

def fix_production_avatars():
    """Fix incomplete avatar URLs in production database"""
    print("🔧 FIXING PRODUCTION AVATAR URLs ON RAILWAY")
    print("=" * 50)
    
    try:
        from app.db.database import execute_query
        
        # Get all avatars with potentially incomplete URLs
        avatars = execute_query("""
            SELECT id, avatar_id, avatar_name, avatar_image_url, user_id
            FROM user_avatars
            WHERE avatar_image_url IS NOT NULL
            ORDER BY created_at DESC
        """, fetch_all=True)
        
        print(f"📊 Found {len(avatars)} avatars to check")
        
        fixed_count = 0
        already_complete = 0
        
        for i, avatar in enumerate(avatars, 1):
            print(f"\n[{i}/{len(avatars)}] Processing: {avatar['avatar_name']}")
            
            current_url = avatar['avatar_image_url']
            print(f"Current URL: {current_url}")
            
            # Check if URL is already complete
            if current_url.endswith(('.jpg', '.png', '.jpeg')):
                print("✅ URL already complete")
                already_complete += 1
                continue
            
            # Try to fix incomplete URL
            fixed_url = current_url + '.jpg'
            print(f"Testing fixed URL: {fixed_url}")
            
            try:
                # Test if the fixed URL works
                response = requests.head(fixed_url, timeout=10)
                if response.status_code == 200:
                    print("✅ Fixed URL works! Updating database...")
                    
                    # Update the database
                    execute_query("""
                        UPDATE user_avatars 
                        SET avatar_image_url = ?
                        WHERE id = ?
                    """, (fixed_url, avatar['id']))
                    
                    fixed_count += 1
                    print("✅ Database updated successfully")
                else:
                    print(f"❌ Fixed URL failed (HTTP {response.status_code})")
                    
            except requests.RequestException as e:
                print(f"❌ Network error testing URL: {e}")
            except Exception as e:
                print(f"❌ Database error: {e}")
        
        print(f"\n" + "=" * 50)
        print(f"🎯 SUMMARY:")
        print(f"   Total avatars processed: {len(avatars)}")
        print(f"   Already complete: {already_complete}")
        print(f"   URLs fixed: {fixed_count}")
        print(f"   Status: {'✅ SUCCESS' if fixed_count > 0 else '⚠️ NO FIXES NEEDED'}")
        
        if fixed_count > 0:
            print(f"\n🎉 Avatar images should now display correctly on Railway!")
            print(f"🔄 Refresh your browser to see the changes.")
        
        return True
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_environment():
    """Verify environment variables are set"""
    print("🔍 CHECKING ENVIRONMENT VARIABLES")
    print("-" * 30)
    
    required_vars = ['DATABASE_URL', 'HEYGEN_API_KEY']
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {'*' * 8}...{value[-8:] if len(value) > 16 else '*' * len(value)}")
        else:
            print(f"❌ {var}: NOT SET")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n❌ Missing environment variables: {', '.join(missing_vars)}")
        return False
    
    print("✅ All required environment variables are set")
    return True

if __name__ == "__main__":
    print("🚀 RAILWAY PRODUCTION AVATAR FIX")
    print("=" * 50)
    
    if not verify_environment():
        print("❌ Environment check failed. Please set missing variables.")
        sys.exit(1)
    
    success = fix_production_avatars()
    
    if success:
        print("\n✅ Script completed successfully!")
    else:
        print("\n❌ Script failed. Check the errors above.")
        sys.exit(1)
