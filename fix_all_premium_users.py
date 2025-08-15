#!/usr/bin/env python3
"""
Fix all premium users based on admin UI screenshot
"""

import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def fix_all_premium_users():
    """Fix premium status for all users who should be premium based on admin UI"""
    try:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            print("❌ DATABASE_URL not found")
            return
        
        # Users who are premium according to admin UI screenshot
        premium_users = [
            (3, "MogensR"),      # You - confirmed premium
            (10, "adminfx"),     # Admin user - shown as premium in UI
            (2, "testuser")      # Test user - shown as premium in UI
        ]
        
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cursor:
                print("🔧 FIXING PREMIUM STATUS FOR ALL USERS:")
                print("=" * 60)
                
                for user_id, expected_username in premium_users:
                    # Update user to premium with SMS settings
                    cursor.execute("""
                        UPDATE users 
                        SET is_premium = TRUE,
                            sms_notifications = TRUE
                        WHERE id = %s
                        RETURNING id, username, is_premium, sms_notifications, email
                    """, (user_id,))
                    
                    result = cursor.fetchone()
                    if result:
                        db_id, db_username, is_premium, sms_opt_in, email = result
                        print(f"✅ FIXED ID {db_id} ({db_username}):")
                        print(f"   💎 Premium: {is_premium}")
                        print(f"   📲 SMS Notifications: {sms_opt_in}")
                        print(f"   📧 Email: {email}")
                    else:
                        print(f"❌ User ID {user_id} ({expected_username}) not found")
                    print()
                
                # Verify all changes
                print("🔍 VERIFICATION - ALL PREMIUM USERS:")
                print("=" * 60)
                
                cursor.execute("""
                    SELECT id, username, email, is_premium, sms_notifications
                    FROM users 
                    WHERE is_premium = TRUE
                    ORDER BY id
                """)
                
                premium_results = cursor.fetchall()
                
                for result in premium_results:
                    user_id, username, email, is_premium, sms_opt_in = result
                    print(f"💎 ID {user_id:2d} | {username:15s} | Premium: {is_premium} | SMS: {sms_opt_in}")
                    print(f"     📧 {email}")
                    print()
                
                print(f"📊 Total premium users in database: {len(premium_results)}")
                print("🎉 All premium users should now receive SMS notifications!")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_all_premium_users()
