#!/usr/bin/env python3
"""
Fix MogensR premium status and SMS settings
"""

import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def fix_mogens_premium():
    """Fix premium status and SMS settings for MogensR (ID 3)"""
    try:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            print("❌ DATABASE_URL not found")
            return
        
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cursor:
                # Update MogensR to premium with SMS settings
                cursor.execute("""
                    UPDATE users 
                    SET is_premium = TRUE,
                        sms_notifications = TRUE,
                        phone_number = COALESCE(phone_number, '12345678'),
                        country_code = COALESCE(country_code, '+45')
                    WHERE id = 3
                    RETURNING id, username, is_premium, sms_notifications, phone_number, country_code, email
                """)
                
                result = cursor.fetchone()
                if result:
                    user_id, username, is_premium, sms_opt_in, phone, country_code, email = result
                    print(f"✅ UPDATED {username} (ID: {user_id}):")
                    print(f"   💎 Premium: {is_premium}")
                    print(f"   📲 SMS Notifications: {sms_opt_in}")
                    print(f"   📱 Phone: {phone}")
                    print(f"   🌍 Country Code: {country_code}")
                    print(f"   📧 Email: {email}")
                    
                    # Check if SMS should work now
                    sms_ready = is_premium and phone and country_code and sms_opt_in
                    print(f"   ✅ SMS Ready: {sms_ready}")
                    
                    if sms_ready:
                        print("\n🎉 SMS SHOULD NOW WORK!")
                        print("   Next video completion should trigger SMS notification")
                    else:
                        print("\n❌ SMS STILL BLOCKED - check missing fields above")
                else:
                    print("❌ User ID 3 not found")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_mogens_premium()
