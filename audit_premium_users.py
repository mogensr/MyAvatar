#!/usr/bin/env python3
"""
Audit all premium users - check for inconsistencies between admin UI and database
"""

import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def audit_premium_users():
    """Check all users marked as premium in admin UI vs database"""
    try:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            print("❌ DATABASE_URL not found")
            return
        
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cursor:
                # Get all users and their premium status
                cursor.execute("""
                    SELECT id, username, email, is_premium, sms_notifications, 
                           phone_number, country_code
                    FROM users 
                    ORDER BY id
                """)
                
                results = cursor.fetchall()
                
                print("🔍 ALL USERS PREMIUM STATUS AUDIT:")
                print("=" * 80)
                
                premium_count = 0
                sms_ready_count = 0
                
                for result in results:
                    user_id, username, email, is_premium, sms_opt_in, phone, country_code = result
                    
                    # Check if SMS ready
                    sms_ready = is_premium and phone and country_code and sms_opt_in
                    
                    status_icon = "💎" if is_premium else "👤"
                    sms_icon = "📱" if sms_ready else "❌"
                    
                    print(f"{status_icon} ID {user_id:2d} | {username:15s} | Premium: {str(is_premium):5s} | SMS: {sms_icon}")
                    print(f"     📧 {email}")
                    if phone and country_code:
                        print(f"     📱 {country_code}{phone} | SMS Opt-in: {sms_opt_in}")
                    else:
                        print(f"     📱 No phone/country | SMS Opt-in: {sms_opt_in}")
                    print()
                    
                    if is_premium:
                        premium_count += 1
                    if sms_ready:
                        sms_ready_count += 1
                
                print("=" * 80)
                print(f"📊 SUMMARY:")
                print(f"   Total users: {len(results)}")
                print(f"   💎 Premium users: {premium_count}")
                print(f"   📱 SMS ready users: {sms_ready_count}")
                
                # Check for users who should be premium based on admin UI
                print(f"\n🔍 KNOWN PREMIUM USERS FROM ADMIN UI:")
                known_premium = [
                    (3, "MogensR"),
                    (10, "adminfx"),  # From admin UI screenshot
                    (2, "testuser")   # From admin UI screenshot
                ]
                
                for user_id, expected_username in known_premium:
                    cursor.execute("""
                        SELECT username, is_premium, sms_notifications
                        FROM users 
                        WHERE id = %s
                    """, (user_id,))
                    
                    db_result = cursor.fetchone()
                    if db_result:
                        db_username, db_premium, db_sms = db_result
                        status = "✅" if db_premium else "❌"
                        print(f"   {status} ID {user_id} ({expected_username}): DB Premium = {db_premium}")
                        
                        if not db_premium:
                            print(f"      🚨 MISMATCH: Should be premium according to admin UI!")
                    else:
                        print(f"   ❌ ID {user_id} ({expected_username}): NOT FOUND in database")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    audit_premium_users()
