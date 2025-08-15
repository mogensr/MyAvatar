#!/usr/bin/env python3
"""
Fix premium status and SMS settings for MogensR
"""

import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def fix_premium_status():
    """Fix premium status and SMS settings for user ID 3 (MogensR)"""
    try:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            print("❌ DATABASE_URL not found")
            return
        
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cursor:
                # Update user to premium and enable SMS
                cursor.execute("""
                    UPDATE users 
                    SET is_premium = TRUE,
                        sms_notifications = TRUE,
                        phone_number = COALESCE(phone_number, '12345678'),
                        country_code = COALESCE(country_code, '+45')
                    WHERE id = 3
                    RETURNING id, username, is_premium, sms_notifications, phone_number, country_code
                """)
                
                result = cursor.fetchone()
                if result:
                    user_id, username, is_premium, sms_opt_in, phone, country_code = result
                    print(f"✅ UPDATED {username} (ID: {user_id}):")
                    print(f"   💎 Premium: {is_premium}")
                    print(f"   📲 SMS Notifications: {sms_opt_in}")
                    print(f"   📱 Phone: {phone}")
                    print(f"   🌍 Country Code: {country_code}")
                else:
                    print("❌ User ID 3 not found")
                
                # Verify the update
                cursor.execute("""
                    SELECT id, username, email, phone_number, country_code, 
                           sms_notifications, is_premium
                    FROM users 
                    WHERE id = 3
                """)
                
                verify_result = cursor.fetchone()
                if verify_result:
                    user_id, username, email, phone, country_code, sms_opt_in, is_premium = verify_result
                    
                    print(f"\n🔍 VERIFIED SMS SETTINGS for {username}:")
                    print(f"   📧 Email: {email}")
                    print(f"   📱 Phone: {phone}")
                    print(f"   🌍 Country Code: {country_code}")
                    print(f"   📲 SMS Notifications: {sms_opt_in}")
                    print(f"   💎 Premium: {is_premium}")
                    
                    # Check if SMS should work
                    sms_ready = is_premium and phone and country_code and sms_opt_in
                    print(f"   ✅ SMS Ready: {sms_ready}")
                    
                    if sms_ready:
                        print("\n🎉 SMS SHOULD NOW WORK!")
                    else:
                        print("\n❌ SMS STILL BLOCKED:")
                        if not is_premium:
                            print("   - User is not premium")
                        if not phone:
                            print("   - No phone number")
                        if not country_code:
                            print("   - No country code")
                        if not sms_opt_in:
                            print("   - SMS notifications disabled")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_premium_status()
