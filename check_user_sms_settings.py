#!/usr/bin/env python3
"""
Check user SMS settings for notification debugging
"""

import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_user_sms_settings():
    """Check SMS settings for user ID 3 (MogensR)"""
    try:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            print("❌ DATABASE_URL not found")
            return
        
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cursor:
                # Check user SMS settings
                cursor.execute("""
                    SELECT id, username, email, phone_number, country_code, 
                           sms_notifications, is_premium
                    FROM users 
                    WHERE id = 3
                """)
                
                result = cursor.fetchone()
                if result:
                    user_id, username, email, phone, country_code, sms_opt_in, is_premium = result
                    
                    print(f"🔍 USER SMS SETTINGS for {username} (ID: {user_id}):")
                    print(f"   📧 Email: {email}")
                    print(f"   📱 Phone: {phone}")
                    print(f"   🌍 Country Code: {country_code}")
                    print(f"   📲 SMS Notifications: {sms_opt_in}")
                    print(f"   💎 Premium: {is_premium}")
                    
                    # Check if SMS should work
                    sms_ready = is_premium and phone and country_code and sms_opt_in
                    print(f"   ✅ SMS Ready: {sms_ready}")
                    
                    if not sms_ready:
                        print("\n❌ SMS BLOCKERS:")
                        if not is_premium:
                            print("   - User is not premium")
                        if not phone:
                            print("   - No phone number")
                        if not country_code:
                            print("   - No country code")
                        if not sms_opt_in:
                            print("   - SMS notifications disabled")
                else:
                    print("❌ User ID 3 not found")
                
                # Check Twilio credentials
                print(f"\n🔍 TWILIO CREDENTIALS:")
                twilio_sid = os.getenv('TWILIO_ACCOUNT_SID')
                twilio_token = os.getenv('TWILIO_AUTH_TOKEN')
                twilio_phone = os.getenv('TWILIO_PHONE_NUMBER')
                
                print(f"   SID: {'✅ Set' if twilio_sid else '❌ Missing'}")
                print(f"   Token: {'✅ Set' if twilio_token else '❌ Missing'}")
                print(f"   Phone: {'✅ Set' if twilio_phone else '❌ Missing'} ({twilio_phone})")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_user_sms_settings()
