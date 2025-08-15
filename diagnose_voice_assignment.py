#!/usr/bin/env python3
"""
Voice Assignment Diagnostic Script
Comprehensive tool to diagnose and test HeyGen voice assignment issues
"""

import os
import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.heygen_voice_manager import HeyGenVoiceManager
from app.db.database import get_db_connection, execute_query
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("VoiceDiagnostic")

def main():
    """Main diagnostic function"""
    print("🔍 HeyGen Voice Assignment Diagnostic Tool")
    print("=" * 50)
    
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    
    # Get HeyGen API key
    api_key = os.getenv("HEYGEN_API_KEY")
    if not api_key:
        print("❌ HEYGEN_API_KEY not found in environment")
        return
    
    print(f"✅ HeyGen API Key: {api_key[:10]}...")
    
    # Get database connection
    try:
        db_conn = get_db_connection()
        print("✅ Database connection established")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return
    
    # Initialize voice manager
    try:
        voice_manager = HeyGenVoiceManager(db_conn, api_key)
        print("✅ HeyGenVoiceManager initialized")
    except Exception as e:
        print(f"❌ Voice manager initialization failed: {e}")
        return
    
    # Get test data
    print("\n📊 Getting test data...")
    
    # Get users with cloned voices
    users_with_voices = execute_query("""
        SELECT id, username, heygen_voice_id 
        FROM users 
        WHERE heygen_voice_id IS NOT NULL 
        LIMIT 5
    """)
    
    print(f"Found {len(users_with_voices)} users with cloned voices:")
    for user in users_with_voices:
        print(f"  - User {user['id']} ({user['username']}): {user['heygen_voice_id']}")
    
    # Get user avatars
    user_avatars = execute_query("""
        SELECT ua.avatar_id, ua.user_id, ua.avatar_name, ua.is_custom, u.username
        FROM user_avatars ua
        LEFT JOIN users u ON ua.user_id = u.id
        LIMIT 10
    """)
    
    print(f"\nFound {len(user_avatars)} user avatars:")
    for avatar in user_avatars:
        print(f"  - Avatar {avatar['avatar_id']} ({avatar['avatar_name']}) - User: {avatar['username']} - Custom: {avatar['is_custom']}")
    
    # Test voice assignment for different scenarios
    print("\n🧪 Testing Voice Assignment Scenarios")
    print("-" * 40)
    
    if users_with_voices and user_avatars:
        # Test 1: Custom avatar with cloned voice
        test_user = users_with_voices[0]
        test_avatar = None
        
        # Find a custom avatar for this user
        for avatar in user_avatars:
            if avatar['user_id'] == test_user['id'] and avatar['is_custom']:
                test_avatar = avatar
                break
        
        if not test_avatar:
            # Use any avatar for this user
            for avatar in user_avatars:
                if avatar['user_id'] == test_user['id']:
                    test_avatar = avatar
                    break
        
        if test_avatar:
            print(f"\n🎯 Test 1: Custom Avatar with Cloned Voice")
            print(f"User: {test_user['username']} (ID: {test_user['id']})")
            print(f"Avatar: {test_avatar['avatar_name']} (ID: {test_avatar['avatar_id']})")
            print(f"Expected Voice: {test_user['heygen_voice_id']}")
            
            try:
                result = voice_manager.get_voice_id_for_avatar(
                    user_id=test_user['id'],
                    avatar_id=test_avatar['avatar_id'],
                    language="en",
                    context={"use_cloned_voice": True}
                )
                
                print(f"✅ Result: {result.voice_id}")
                print(f"   Source: {result.source}")
                print(f"   Confidence: {result.confidence}")
                print(f"   Avatar Type: {result.avatar_type}")
                if result.warning:
                    print(f"   ⚠️ Warning: {result.warning}")
                
                # Check if it matches expected
                if result.voice_id == test_user['heygen_voice_id']:
                    print("✅ PASS: Voice matches user's cloned voice")
                else:
                    print("❌ FAIL: Voice doesn't match user's cloned voice")
                    
            except Exception as e:
                print(f"❌ Error in test 1: {e}")
        
        # Test 2: Public avatar with default voice
        print(f"\n🎯 Test 2: Public Avatar with Default Voice")
        print(f"User: {test_user['username']} (ID: {test_user['id']})")
        print(f"Avatar: public_avatar_test")
        print(f"Language: Danish (da)")
        
        try:
            result = voice_manager.get_voice_id_for_avatar(
                user_id=test_user['id'],
                avatar_id="public_avatar_test",  # Non-existent avatar (should be treated as public)
                language="da",
                context={"use_cloned_voice": False}
            )
            
            print(f"✅ Result: {result.voice_id}")
            print(f"   Source: {result.source}")
            print(f"   Confidence: {result.confidence}")
            print(f"   Avatar Type: {result.avatar_type}")
            if result.warning:
                print(f"   ⚠️ Warning: {result.warning}")
                
        except Exception as e:
            print(f"❌ Error in test 2: {e}")
        
        # Test 3: Voice validation
        print(f"\n🎯 Test 3: Voice Validation")
        test_voice = test_user['heygen_voice_id']
        print(f"Testing voice: {test_voice}")
        
        try:
            is_valid = voice_manager._validate_voice_id_cached(test_voice)
            if is_valid:
                print("✅ PASS: Voice is valid in HeyGen API")
            else:
                print("❌ FAIL: Voice is not valid in HeyGen API")
                
        except Exception as e:
            print(f"❌ Error in test 3: {e}")
    
    # Test 4: Diagnostic function
    if users_with_voices and user_avatars:
        print(f"\n🎯 Test 4: Diagnostic Function")
        test_user = users_with_voices[0]
        test_avatar = user_avatars[0]
        
        try:
            diagnosis = voice_manager.diagnose_voice_issue(
                user_id=test_user['id'],
                avatar_id=test_avatar['avatar_id']
            )
            print("✅ Diagnostic completed (see output above)")
            
        except Exception as e:
            print(f"❌ Error in diagnostic: {e}")
    
    # Check database tables
    print(f"\n📋 Database Table Status")
    print("-" * 30)
    
    # Check if voice_assignment_log table exists
    try:
        log_count = execute_query("SELECT COUNT(*) as count FROM voice_assignment_log")
        if log_count:
            print(f"✅ voice_assignment_log table exists with {log_count[0]['count']} entries")
        else:
            print("✅ voice_assignment_log table exists (empty)")
    except Exception as e:
        print(f"⚠️ voice_assignment_log table may not exist: {e}")
    
    # Check users table structure
    try:
        users_sample = execute_query("SELECT id, username, heygen_voice_id FROM users LIMIT 1")
        if users_sample:
            print("✅ users.heygen_voice_id column exists")
        else:
            print("⚠️ No users found in database")
    except Exception as e:
        print(f"❌ Error checking users table: {e}")
    
    # Check user_avatars table structure
    try:
        avatars_sample = execute_query("SELECT avatar_id, user_id, is_custom FROM user_avatars LIMIT 1")
        if avatars_sample:
            print("✅ user_avatars table structure looks good")
        else:
            print("⚠️ No avatars found in database")
    except Exception as e:
        print(f"❌ Error checking user_avatars table: {e}")
    
    print(f"\n🎉 Diagnostic Complete!")
    print("If you see any failures, check the logs and database structure.")

if __name__ == "__main__":
    main()
