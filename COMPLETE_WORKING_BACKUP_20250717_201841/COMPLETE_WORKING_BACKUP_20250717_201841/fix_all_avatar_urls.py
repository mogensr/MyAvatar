#!/usr/bin/env python3
"""
Comprehensive Avatar URL Fixer for MyAvatar Project
FINAL VERSION - Fixes all incomplete avatar URLs in the database

This script:
1. Loads environment variables properly
2. Connects to the database (SQLite or PostgreSQL)
3. Finds all avatars with incomplete URLs (missing .jpg/.png extension)
4. Tests and fixes incomplete URLs by appending .jpg
5. Updates the database with working URLs
6. Provides detailed progress reporting

Usage:
    python fix_all_avatar_urls.py
"""

import os
import sys
import requests
from datetime import datetime
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

def setup_database():
    """Setup database connection based on environment"""
    database_url = os.getenv('DATABASE_URL')
    
    if database_url and database_url.startswith('postgresql'):
        # PostgreSQL (Production)
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        print("🔗 Connecting to PostgreSQL database...")
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        use_postgres = True
        
    else:
        # SQLite (Local)
        import sqlite3
        
        db_path = project_root / "myavatar.db"
        print(f"🔗 Connecting to SQLite database: {db_path}")
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        use_postgres = False
    
    return conn, cursor, use_postgres

def test_url_accessibility(url: str, timeout: int = 10) -> bool:
    """Test if a URL is accessible via HTTP HEAD request"""
    try:
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False
    except Exception:
        return False

def fix_incomplete_avatar_url(url: str) -> tuple[str, bool]:
    """
    Fix incomplete avatar URLs by appending .jpg if needed
    
    Returns:
        (fixed_url, was_fixed) - The fixed URL and whether it was actually fixed
    """
    if not url:
        return url, False
        
    # Check if URL already has an extension
    if url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
        # URL already has extension, test if it works
        if test_url_accessibility(url):
            return url, False  # No fix needed
        else:
            return url, False  # Can't fix complete URLs that don't work
    
    # Try appending .jpg to incomplete URL
    fixed_url = url + '.jpg'
    if test_url_accessibility(fixed_url):
        return fixed_url, True  # Successfully fixed
    
    # Try appending .png as fallback
    fixed_url_png = url + '.png'
    if test_url_accessibility(fixed_url_png):
        return fixed_url_png, True  # Successfully fixed with PNG
    
    # Could not fix
    return url, False

def main():
    """Main function to fix all avatar URLs"""
    print("🚀 MyAvatar URL Fixer - Starting comprehensive fix...")
    print("=" * 60)
    
    # Verify environment variables
    heygen_api_key = os.getenv('HEYGEN_API_KEY')
    if not heygen_api_key:
        print("❌ ERROR: HEYGEN_API_KEY not found in environment variables")
        return False
    
    database_url = os.getenv('DATABASE_URL')
    print(f"📊 Database: {'PostgreSQL (Production)' if database_url and database_url.startswith('postgresql') else 'SQLite (Local)'}")
    print(f"🔑 HeyGen API Key: {'✅ Found' if heygen_api_key else '❌ Missing'}")
    print()
    
    try:
        # Setup database connection
        conn, cursor, use_postgres = setup_database()
        
        # Get all avatars with URLs
        print("🔍 Scanning database for avatar URLs...")
        
        if use_postgres:
            cursor.execute("""
                SELECT id, user_id, avatar_id, avatar_name, avatar_image_url
                FROM user_avatars 
                WHERE avatar_image_url IS NOT NULL AND avatar_image_url != ''
                ORDER BY id
            """)
        else:
            cursor.execute("""
                SELECT id, user_id, avatar_id, avatar_name, avatar_image_url
                FROM user_avatars 
                WHERE avatar_image_url IS NOT NULL AND avatar_image_url != ''
                ORDER BY id
            """)
        
        avatars = cursor.fetchall()
        total_avatars = len(avatars)
        
        print(f"📋 Found {total_avatars} avatars with URLs")
        
        if total_avatars == 0:
            print("✅ No avatars found to process")
            return True
        
        # Analyze URLs
        incomplete_urls = []
        complete_urls = []
        
        for avatar in avatars:
            url = avatar['avatar_image_url']
            if url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                complete_urls.append(avatar)
            else:
                incomplete_urls.append(avatar)
        
        print(f"✅ Complete URLs: {len(complete_urls)}")
        print(f"⚠️  Incomplete URLs: {len(incomplete_urls)}")
        print()
        
        if len(incomplete_urls) == 0:
            print("🎉 All avatar URLs are already complete!")
            return True
        
        # Fix incomplete URLs
        print(f"🔧 Fixing {len(incomplete_urls)} incomplete URLs...")
        print("-" * 40)
        
        fixed_count = 0
        failed_count = 0
        
        for i, avatar in enumerate(incomplete_urls, 1):
            avatar_id = avatar['avatar_id']
            current_url = avatar['avatar_image_url']
            db_id = avatar['id']
            
            print(f"[{i:3d}/{len(incomplete_urls)}] {avatar_id}")
            print(f"    Current: {current_url}")
            
            # Try to fix the URL
            fixed_url, was_fixed = fix_incomplete_avatar_url(current_url)
            
            if was_fixed:
                print(f"    Fixed:   {fixed_url}")
                
                # Update database
                try:
                    if use_postgres:
                        cursor.execute(
                            "UPDATE user_avatars SET avatar_image_url = %s WHERE id = %s",
                            (fixed_url, db_id)
                        )
                    else:
                        cursor.execute(
                            "UPDATE user_avatars SET avatar_image_url = ? WHERE id = ?",
                            (fixed_url, db_id)
                        )
                    
                    conn.commit()
                    print(f"    Status:  ✅ Updated in database")
                    fixed_count += 1
                    
                except Exception as e:
                    print(f"    Status:  ❌ Database update failed: {e}")
                    failed_count += 1
            else:
                print(f"    Status:  ❌ Could not fix URL")
                failed_count += 1
            
            print()
        
        # Final summary
        print("=" * 60)
        print("🎯 FINAL RESULTS:")
        print(f"   Total avatars processed: {len(incomplete_urls)}")
        print(f"   ✅ Successfully fixed: {fixed_count}")
        print(f"   ❌ Failed to fix: {failed_count}")
        print(f"   📊 Success rate: {(fixed_count/len(incomplete_urls)*100):.1f}%")
        
        if fixed_count > 0:
            print()
            print("🚀 Next steps:")
            print("   1. Restart your web application")
            print("   2. Test avatar image display in the UI")
            print("   3. If deploying to Railway, push these changes")
        
        return fixed_count > 0
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if 'conn' in locals():
            conn.close()
            print("🔒 Database connection closed")

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
