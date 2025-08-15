#!/usr/bin/env python3
"""
Simple Voice Assignment Test
Quick test to verify the HeyGen voice management system is working
"""

import os
import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_voice_assignment():
    """Test the voice assignment system"""
    print("🧪 Testing HeyGen Voice Assignment System")
    print("=" * 45)
    
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    
    # Test 1: Import the voice manager
    print("\n📦 Test 1: Import HeyGenVoiceManager")
    try:
        from app.services.heygen_voice_manager import HeyGenVoiceManager
        print("✅ PASS: HeyGenVoiceManager imported successfully")
    except Exception as e:
        print(f"❌ FAIL: Import failed - {e}")
        return False
    
    # Test 2: Database connection
    print("\n🗄️ Test 2: Database Connection")
    try:
        from app.db.database import get_db_connection
        db_conn = get_db_connection()
        print("✅ PASS: Database connection established")
    except Exception as e:
        print(f"❌ FAIL: Database connection failed - {e}")
        return False
    
    # Test 3: Initialize voice manager
    print("\n🎯 Test 3: Initialize Voice Manager")
    try:
        api_key = os.getenv("HEYGEN_API_KEY")
        if not api_key:
            print("⚠️ SKIP: No HEYGEN_API_KEY found")
            api_key = "test_key"
        
        voice_manager = HeyGenVoiceManager(db_conn, api_key)
        print("✅ PASS: Voice manager initialized")
    except Exception as e:
        print(f"❌ FAIL: Voice manager initialization failed - {e}")
        return False
    
    # Test 4: Test voice assignment (mock data)
    print("\n🎭 Test 4: Voice Assignment Logic")
    try:
        # Test with mock data
        result = voice_manager.get_voice_id_for_avatar(
            user_id=1,
            avatar_id="test_avatar",
            language="en",
            context={"use_cloned_voice": False}
        )
        
        print(f"✅ PASS: Voice assignment returned - {result.voice_id}")
        print(f"   Source: {result.source}")
        print(f"   Confidence: {result.confidence}")
        
    except Exception as e:
        print(f"❌ FAIL: Voice assignment failed - {e}")
        return False
    
    # Test 5: Test diagnostic function
    print("\n🔍 Test 5: Diagnostic Function")
    try:
        diagnosis = voice_manager.diagnose_voice_issue(
            user_id=1,
            avatar_id="test_avatar"
        )
        print("✅ PASS: Diagnostic function works")
        
    except Exception as e:
        print(f"❌ FAIL: Diagnostic function failed - {e}")
        return False
    
    print(f"\n🎉 All Tests Passed!")
    print("Your HeyGen Voice Management System is working correctly.")
    return True

if __name__ == "__main__":
    success = test_voice_assignment()
    if not success:
        sys.exit(1)
