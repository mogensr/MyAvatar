#!/usr/bin/env python3
"""
EMERGENCY: Fix premium status corruption in database
=====================================================
Execute via Railway deployment to fix premium user statuses
"""

import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def fix_premium_status():
    """Emergency fix for premium status corruption"""
    
    # Get database URL
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not found")
        return False
    
    # Fix postgres:// to postgresql:// if needed
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    try:
        print("🔗 Connecting to database...")
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        print("🚨 EXECUTING EMERGENCY PREMIUM STATUS FIX...")
        
        # 1. Fix Mogens (User ID: 3) - Owner/Premium
        print("🔧 Fixing Mogens (ID: 3)...")
        cursor.execute("""
            UPDATE users 
            SET subscription_tier = 'premium', 
                is_premium = true,
                sms_notifications = true,
                phone_number = '30604639',
                country_code = '+45'
            WHERE id = 3
        """)
        print(f"✅ Mogens updated: {cursor.rowcount} rows affected")
        
        # 2. Fix Lars-Christian
        print("🔧 Fixing Lars-Christian...")
        cursor.execute("""
            UPDATE users 
            SET subscription_tier = 'premium', 
                is_premium = true,
                sms_notifications = true
            WHERE name ILIKE '%lars%' OR name ILIKE '%christian%' OR email ILIKE '%lars%' OR email ILIKE '%christian%'
        """)
        print(f"✅ Lars-Christian updated: {cursor.rowcount} rows affected")
        
        # 3. Fix Admin users
        print("🔧 Fixing Admin users...")
        cursor.execute("""
            UPDATE users 
            SET subscription_tier = 'premium', 
                is_premium = true,
                sms_notifications = true
            WHERE is_admin = true OR role = 'admin'
        """)
        print(f"✅ Admin users updated: {cursor.rowcount} rows affected")
        
        # 4. Give premium features to 7-day trial users
        print("🔧 Upgrading 7-day trial users to premium...")
        cursor.execute("""
            UPDATE users 
            SET subscription_tier = 'premium', 
                is_premium = true,
                sms_notifications = true
            WHERE created_at >= NOW() - INTERVAL '7 days'
        """)
        print(f"✅ 7-day trial users upgraded: {cursor.rowcount} rows affected")
        
        # Commit all changes
        conn.commit()
        print("💾 All changes committed to database!")
        
        # 5. VERIFICATION: Check the fixes
        print("\n📋 VERIFICATION - Checking updated users:")
        cursor.execute("""
            SELECT id, name, email, subscription_tier, is_premium, sms_notifications, phone_number, country_code
            FROM users 
            WHERE id = 3 OR name ILIKE '%lars%' OR name ILIKE '%christian%' OR is_admin = true
            ORDER BY id
        """)
        
        results = cursor.fetchall()
        print("\n✅ UPDATED USERS:")
        print("ID | Name | Email | Tier | Premium | SMS | Phone")
        print("-" * 60)
        for row in results:
            print(f"{row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} | {row[6]}")
        
        # Check total premium users
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_premium = true")
        premium_count = cursor.fetchone()[0]
        print(f"\n📊 Total premium users: {premium_count}")
        
        cursor.close()
        conn.close()
        
        print("\n🎉 EMERGENCY FIX COMPLETED SUCCESSFULLY!")
        print("📱 SMS notifications should now work for premium users!")
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

if __name__ == "__main__":
    print("🚨 EMERGENCY PREMIUM STATUS FIX")
    print("=" * 50)
    
    success = fix_premium_status()
    
    if success:
        print("\n✅ SUCCESS: Premium status corruption fixed!")
        print("🧪 Next step: Test SMS notifications by creating a video")
    else:
        print("\n❌ FAILED: Could not fix premium status corruption")
        print("🔍 Check database connection and try again")
