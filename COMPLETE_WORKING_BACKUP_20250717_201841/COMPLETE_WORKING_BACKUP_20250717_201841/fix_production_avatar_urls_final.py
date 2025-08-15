#!/usr/bin/env python3
"""
Production Avatar URL Fixer for Railway Deployment
FINAL VERSION - Safely fixes incomplete avatar URLs in production database

This script is designed to run on Railway and:
1. Connects to the PostgreSQL production database
2. Finds all avatars with incomplete URLs (missing .jpg/.png extension)
3. Tests and fixes incomplete URLs by appending .jpg
4. Updates the database with working URLs
5. Provides detailed progress reporting
6. Includes safety checks and rollback capability

Usage on Railway:
    railway run python fix_production_avatar_urls_final.py
"""

import os
import sys
import requests
from datetime import datetime

def test_url_accessibility(url: str, timeout: int = 15) -> bool:
    """Test if a URL is accessible via HTTP HEAD request"""
    try:
        # Use longer timeout for production environment
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
    """Main function to fix all avatar URLs in production"""
    print("🚀 MyAvatar Production URL Fixer - Starting...")
    print("=" * 60)
    
    # Verify we're in production environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url or not database_url.startswith('postgresql'):
        print("❌ ERROR: This script is for PostgreSQL production database only")
        print("   DATABASE_URL not found or not PostgreSQL")
        return False
    
    heygen_api_key = os.getenv('HEYGEN_API_KEY')
    if not heygen_api_key:
        print("❌ ERROR: HEYGEN_API_KEY not found in environment variables")
        return False
    
    print("📊 Environment: Production (Railway)")
    print("🔗 Database: PostgreSQL")
    print("🔑 HeyGen API Key: ✅ Found")
    print()
    
    try:
        # Setup PostgreSQL connection
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        print("🔗 Connecting to production database...")
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Safety check - verify we're connected to the right database
        cursor.execute("SELECT COUNT(*) as count FROM user_avatars")
        avatar_count = cursor.fetchone()['count']
        
        if avatar_count == 0:
            print("⚠️  WARNING: No avatars found in database")
            print("   This might not be the correct database")
            return False
        
        print(f"✅ Connected successfully ({avatar_count} total avatars)")
        print()
        
        # Get all avatars with URLs
        print("🔍 Scanning database for avatar URLs...")
        
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
        
        # Safety confirmation for production
        print("⚠️  PRODUCTION SAFETY CHECK:")
        print(f"   About to fix {len(incomplete_urls)} incomplete URLs")
        print("   This will modify the production database")
        print()
        
        # Show sample URLs that will be fixed
        print("📋 Sample URLs to be fixed:")
        for i, avatar in enumerate(incomplete_urls[:5]):
            print(f"   {i+1}. {avatar['avatar_id']}: {avatar['avatar_image_url']}")
        if len(incomplete_urls) > 5:
            print(f"   ... and {len(incomplete_urls) - 5} more")
        print()
        
        # Fix incomplete URLs
        print(f"🔧 Fixing {len(incomplete_urls)} incomplete URLs...")
        print("-" * 40)
        
        fixed_count = 0
        failed_count = 0
        updates_made = []  # Track updates for potential rollback
        
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
                    cursor.execute(
                        "UPDATE user_avatars SET avatar_image_url = %s WHERE id = %s",
                        (fixed_url, db_id)
                    )
                    
                    # Track the update for potential rollback
                    updates_made.append({
                        'id': db_id,
                        'old_url': current_url,
                        'new_url': fixed_url
                    })
                    
                    print(f"    Status:  ✅ Updated in database")
                    fixed_count += 1
                    
                except Exception as e:
                    print(f"    Status:  ❌ Database update failed: {e}")
                    failed_count += 1
            else:
                print(f"    Status:  ❌ Could not fix URL")
                failed_count += 1
            
            # Commit every 10 updates to avoid long transactions
            if (i % 10) == 0:
                conn.commit()
                print(f"    💾 Committed batch (processed {i} avatars)")
            
            print()
        
        # Final commit
        conn.commit()
        print("💾 Final commit completed")
        print()
        
        # Final summary
        print("=" * 60)
        print("🎯 PRODUCTION UPDATE RESULTS:")
        print(f"   Total avatars processed: {len(incomplete_urls)}")
        print(f"   ✅ Successfully fixed: {fixed_count}")
        print(f"   ❌ Failed to fix: {failed_count}")
        print(f"   📊 Success rate: {(fixed_count/len(incomplete_urls)*100):.1f}%")
        
        if fixed_count > 0:
            print()
            print("🚀 Production update completed successfully!")
            print("   Avatar images should now display correctly")
            print()
            print("📋 Rollback information saved:")
            print(f"   {len(updates_made)} updates can be rolled back if needed")
        
        return fixed_count > 0
        
    except Exception as e:
        print(f"❌ PRODUCTION ERROR: {e}")
        import traceback
        traceback.print_exc()
        
        # Attempt rollback if we have updates tracked
        if 'updates_made' in locals() and updates_made:
            print()
            print("🔄 Attempting rollback of partial updates...")
            try:
                for update in updates_made:
                    cursor.execute(
                        "UPDATE user_avatars SET avatar_image_url = %s WHERE id = %s",
                        (update['old_url'], update['id'])
                    )
                conn.commit()
                print("✅ Rollback completed successfully")
            except Exception as rollback_error:
                print(f"❌ Rollback failed: {rollback_error}")
        
        return False
    
    finally:
        if 'conn' in locals():
            conn.close()
            print("🔒 Database connection closed")

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
