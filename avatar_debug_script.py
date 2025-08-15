#!/usr/bin/env python3
"""
Avatar Debug & Repair Script for MyAvatar
Systematically identifies and fixes broken avatar URLs
"""

import asyncio
import aiohttp
import json
from datetime import datetime
import sys
import os

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from app.db.database import execute_query
    print("✅ Database import successful")
except ImportError as e:
    print(f"❌ Database import failed: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)

try:
    from app.api.heygen import get_avatar_from_any_endpoint
    print("✅ HeyGen API import successful")
except ImportError as e:
    print(f"❌ HeyGen API import failed: {e}")
    print("Will skip API refresh functionality")
    get_avatar_from_any_endpoint = None

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AvatarDebugger:
    def __init__(self):
        self.broken_avatars = []
        self.fixed_avatars = []
        self.unreachable_avatars = []
        
    async def audit_all_avatars(self):
        """Phase 1: Audit all avatars in database"""
        print("🔍 Starting comprehensive avatar audit...")
        
        # Get all avatars
        try:
            avatars = execute_query(
                """
                SELECT ua.*, u.username 
                FROM user_avatars ua 
                JOIN users u ON ua.user_id = u.id 
                ORDER BY ua.user_id, ua.created_at DESC
                """,
                fetch_one=False
            )
        except Exception as e:
            print(f"❌ Database query failed: {e}")
            return None
        
        if not avatars:
            print("❌ No avatars found in database")
            return None
            
        print(f"📊 Found {len(avatars)} avatars to audit")
        
        results = {
            'total': len(avatars),
            'working': 0,
            'broken_urls': 0,
            'missing_urls': 0,
            'api_failures': 0,
            'details': []
        }
        
        for i, avatar in enumerate(avatars):
            print(f"Checking avatar {i+1}/{len(avatars)}: {avatar.get('avatar_name', 'Unnamed')}")
            result = await self.check_single_avatar(avatar)
            results['details'].append(result)
            
            if result['status'] == 'working':
                results['working'] += 1
            elif result['status'] == 'broken_url':
                results['broken_urls'] += 1
            elif result['status'] == 'missing_url':
                results['missing_urls'] += 1
            elif result['status'] == 'api_failure':
                results['api_failures'] += 1
        
        self.print_audit_summary(results)
        return results
    
    async def check_single_avatar(self, avatar):
        """Check a single avatar's status"""
        result = {
            'id': avatar['id'],
            'user_id': avatar['user_id'],
            'username': avatar.get('username', 'Unknown'),
            'avatar_id': avatar.get('avatar_id'),
            'avatar_name': avatar.get('avatar_name', 'Unnamed'),
            'current_url': avatar.get('avatar_image_url'),
            'status': 'unknown',
            'error': None,
            'new_url': None
        }
        
        # Check 1: Missing URL
        if not avatar.get('avatar_image_url'):
            result['status'] = 'missing_url'
            result['error'] = 'No avatar_image_url in database'
            self.broken_avatars.append(result)
            return result
        
        # Check 2: URL Accessibility
        url_status = await self.check_url_accessibility(avatar['avatar_image_url'])
        if not url_status['accessible']:
            result['status'] = 'broken_url'
            result['error'] = url_status['error']
            self.broken_avatars.append(result)
            
            # Try to fix via HeyGen API if available
            if get_avatar_from_any_endpoint:
                fixed_url = await self.try_fix_avatar_url(avatar)
                if fixed_url:
                    result['new_url'] = fixed_url
                    result['status'] = 'fixable'
        else:
            result['status'] = 'working'
        
        return result
    
    async def check_url_accessibility(self, url):
        """Check if avatar URL is accessible"""
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.head(url) as response:
                    if response.status == 200:
                        content_type = response.headers.get('content-type', '')
                        if content_type.startswith('image/'):
                            return {'accessible': True, 'error': None}
                        else:
                            return {'accessible': False, 'error': f'Invalid content-type: {content_type}'}
                    else:
                        return {'accessible': False, 'error': f'HTTP {response.status}'}
        except Exception as e:
            return {'accessible': False, 'error': str(e)}
    
    async def try_fix_avatar_url(self, avatar):
        """Try to get fresh URL from HeyGen API"""
        if not get_avatar_from_any_endpoint:
            return None
            
        try:
            print(f"🔧 Attempting to fix avatar {avatar.get('avatar_name')} (ID: {avatar.get('avatar_id')})")
            
            # Use your existing function
            avatar_data = await get_avatar_from_any_endpoint(avatar['avatar_id'])
            
            if avatar_data and 'preview_image_url' in avatar_data:
                new_url = avatar_data['preview_image_url']
                
                # Verify new URL works
                url_check = await self.check_url_accessibility(new_url)
                if url_check['accessible']:
                    print(f"✅ Fixed avatar {avatar.get('avatar_name')}: {new_url}")
                    return new_url
                else:
                    print(f"❌ New URL also broken for {avatar.get('avatar_name')}: {url_check['error']}")
            
        except Exception as e:
            print(f"❌ Failed to fix avatar {avatar.get('avatar_name')}: {e}")
        
        return None
    
    def print_audit_summary(self, results):
        """Print comprehensive audit summary"""
        print("\n" + "="*80)
        print("🎯 AVATAR AUDIT SUMMARY")
        print("="*80)
        print(f"📊 Total Avatars: {results['total']}")
        print(f"✅ Working: {results['working']} ({results['working']/results['total']*100:.1f}%)")
        print(f"🔗 Broken URLs: {results['broken_urls']} ({results['broken_urls']/results['total']*100:.1f}%)")
        print(f"❌ Missing URLs: {results['missing_urls']} ({results['missing_urls']/results['total']*100:.1f}%)")
        print(f"🔌 API Failures: {results['api_failures']} ({results['api_failures']/results['total']*100:.1f}%)")
        
        print("\n🔍 BROKEN AVATARS DETAIL:")
        broken_count = 0
        for detail in results['details']:
            if detail['status'] != 'working':
                broken_count += 1
                if broken_count <= 10:  # Show first 10
                    print(f"  👤 {detail['username']} - {detail['avatar_name']}")
                    print(f"     ID: {detail['avatar_id']} | Status: {detail['status']}")
                    print(f"     Error: {detail['error']}")
                    if detail.get('new_url'):
                        print(f"     🔧 Fixable with: {detail['new_url'][:50]}...")
                    print()
        
        if broken_count > 10:
            print(f"  ... and {broken_count - 10} more broken avatars")

# Specific diagnostic queries
class AvatarDiagnostics:
    @staticmethod
    def find_duplicate_avatars():
        """Find duplicate avatar_ids for same user"""
        try:
            result = execute_query(
                """
                SELECT user_id, avatar_id, COUNT(*) as count
                FROM user_avatars 
                GROUP BY user_id, avatar_id 
                HAVING COUNT(*) > 1
                ORDER BY count DESC
                """,
                fetch_one=False
            )
            return result if result is not None else []
        except Exception as e:
            print(f"Error in find_duplicate_avatars: {e}")
            return []
    
    @staticmethod
    def find_missing_image_urls():
        """Find avatars with NULL or empty image URLs"""
        try:
            result = execute_query(
                """
                SELECT ua.*, u.username 
                FROM user_avatars ua 
                JOIN users u ON ua.user_id = u.id 
                WHERE ua.avatar_image_url IS NULL 
                   OR ua.avatar_image_url = '' 
                   OR ua.avatar_image_url = 'null'
                ORDER BY ua.user_id, ua.created_at DESC
                """,
                fetch_one=False
            )
            return result if result is not None else []
        except Exception as e:
            print(f"Error in find_missing_image_urls: {e}")
            return []
    
    @staticmethod
    def find_old_avatars():
        """Find avatars that haven't been updated recently"""
        try:
            result = execute_query(
                """
                SELECT ua.*, u.username,
                       EXTRACT(DAYS FROM NOW() - ua.updated_at) as days_old
                FROM user_avatars ua 
                JOIN users u ON ua.user_id = u.id 
                WHERE ua.updated_at < NOW() - INTERVAL '7 days'
                   OR ua.updated_at IS NULL
                ORDER BY days_old DESC NULLS LAST
                """,
                fetch_one=False
            )
            return result if result is not None else []
        except Exception as e:
            print(f"Error in find_old_avatars: {e}")
            return []
    
    @staticmethod
    def analyze_url_patterns():
        """Analyze patterns in avatar URLs"""
        try:
            result = execute_query(
                """
                SELECT 
                    CASE 
                        WHEN avatar_image_url LIKE '%heygen%' THEN 'HeyGen'
                        WHEN avatar_image_url LIKE '%cloudinary%' THEN 'Cloudinary'
                        WHEN avatar_image_url LIKE '%placeholder%' THEN 'Placeholder'
                        WHEN avatar_image_url IS NULL THEN 'NULL'
                        ELSE 'Other'
                    END as url_type,
                    COUNT(*) as count,
                    AVG(CASE WHEN avatar_image_url IS NOT NULL AND avatar_image_url != '' THEN 1 ELSE 0 END) * 100 as filled_percentage
                FROM user_avatars 
                GROUP BY url_type
                ORDER BY count DESC
                """,
                fetch_one=False
            )
            return result if result is not None else []
        except Exception as e:
            print(f"Error in analyze_url_patterns: {e}")
            return []

# Main execution
async def main():
    """Run comprehensive avatar debugging"""
    print("🚀 Starting Avatar Debug & Repair System")
    
    # Phase 1: Basic diagnostics
    print("\n📊 PHASE 1: BASIC DIAGNOSTICS")
    diagnostics = AvatarDiagnostics()
    
    duplicates = diagnostics.find_duplicate_avatars()
    if duplicates:
        print(f"⚠️ Found {len(duplicates)} duplicate avatar entries")
        for dup in duplicates[:5]:  # Show first 5
            print(f"   User {dup['user_id']}: Avatar {dup['avatar_id']} x{dup['count']}")
    else:
        print("✅ No duplicate avatars found")
    
    missing_urls = diagnostics.find_missing_image_urls()
    print(f"❌ Found {len(missing_urls)} avatars with missing image URLs")
    
    old_avatars = diagnostics.find_old_avatars()
    print(f"⏰ Found {len(old_avatars)} avatars older than 7 days")
    
    url_patterns = diagnostics.analyze_url_patterns()
    print(f"🔗 URL Pattern Analysis:")
    for pattern in url_patterns:
        print(f"   {pattern['url_type']}: {pattern['count']} avatars ({pattern['filled_percentage']:.1f}% filled)")
    
    # Phase 2: Comprehensive audit
    print("\n🔍 PHASE 2: COMPREHENSIVE AUDIT")
    debugger = AvatarDebugger()
    audit_results = await debugger.audit_all_avatars()
    
    if audit_results is None:
        print("❌ Audit failed - stopping here")
        return
    
    # Phase 3: Report results
    print(f"\n📄 PHASE 3: SUMMARY")
    if debugger.broken_avatars:
        print(f"Found {len(debugger.broken_avatars)} broken avatars that need fixing")
        print("Next steps:")
        print("1. Add API endpoints to main.py for avatar refresh")
        print("2. Update templates with error handling")
        print("3. Run batch repair")
    else:
        print("🎉 All avatars are working correctly!")
    
    print("\n✅ Avatar debugging complete!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Interrupted by user")
    except Exception as e:
        print(f"\n❌ Script failed: {e}")
        import traceback
        traceback.print_exc()