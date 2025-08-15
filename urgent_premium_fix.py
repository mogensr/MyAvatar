#!/usr/bin/env python3
"""
URGENT PREMIUM STATUS FIX
Fix MogensR premium status immediately
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add app to path
sys.path.append('.')
from app.db.database import execute_query

def fix_premium_status_urgent():
    """Fix MogensR premium status immediately"""
    try:
        print("🚨 URGENT: Fixing premium status for MogensR...")
        
        # Update user 3 (MogensR) to premium
        result = execute_query(
            "UPDATE users SET subscription_type = 'Premium' WHERE id = 3",
            ()
        )
        
        # Verify the update
        user = execute_query(
            "SELECT id, username, subscription_type FROM users WHERE id = 3",
            (),
            fetch_one=True
        )
        
        if user:
            print(f"✅ SUCCESS: User {user['username']} (ID: {user['id']}) is now {user['subscription_type']}")
            return True
        else:
            print("❌ FAILED: Could not verify user update")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

if __name__ == "__main__":
    print("🚨 URGENT PREMIUM STATUS FIX")
    print("=" * 40)
    
    success = fix_premium_status_urgent()
    
    if success:
        print("✅ PREMIUM STATUS FIXED - BackgroundFX should now work!")
    else:
        print("❌ PREMIUM STATUS FIX FAILED")
    
    print("=" * 40)
