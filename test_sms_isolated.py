#!/usr/bin/env python3
"""
Isolated SMS Test Script
========================
Test SMS delivery independently from the notification system
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_sms_credentials():
    """Test if SMS credentials are available"""
    print("🔍 SMS CREDENTIALS CHECK:")
    print("=" * 50)
    
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN') 
    phone_number = os.getenv('TWILIO_PHONE_NUMBER')
    
    print(f"TWILIO_ACCOUNT_SID: {'✅ SET' if account_sid else '❌ MISSING'}")
    print(f"TWILIO_AUTH_TOKEN: {'✅ SET' if auth_token else '❌ MISSING'}")
    print(f"TWILIO_PHONE_NUMBER: {phone_number if phone_number else '❌ MISSING'}")
    
    if account_sid and auth_token and phone_number:
        print("\n✅ All credentials are available!")
        return True
    else:
        print("\n❌ Missing credentials - SMS cannot work!")
        return False

def test_sms_send(to_number="+4530604639"):
    """Test sending SMS to a specific number"""
    try:
        from twilio.rest import Client
        
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        from_number = os.getenv('TWILIO_PHONE_NUMBER')
        
        if not all([account_sid, auth_token, from_number]):
            print("❌ Missing Twilio credentials")
            return False
        
        print(f"\n📱 TESTING SMS SEND TO: {to_number}")
        print("=" * 50)
        
        client = Client(account_sid, auth_token)
        
        message = client.messages.create(
            body="🧪 TEST: MyAvatar SMS notification system is working! This is a test message.",
            from_=from_number,
            to=to_number
        )
        
        print(f"✅ SMS sent successfully!")
        print(f"📋 Message SID: {message.sid}")
        print(f"📱 To: {message.to}")
        print(f"📞 From: {message.from_}")
        print(f"📝 Status: {message.status}")
        
        return True
        
    except Exception as e:
        print(f"❌ SMS send failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_twilio_account():
    """Test Twilio account status"""
    try:
        from twilio.rest import Client
        
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        
        if not account_sid or not auth_token:
            print("❌ Missing account credentials")
            return False
            
        print(f"\n💰 TWILIO ACCOUNT STATUS:")
        print("=" * 50)
        
        client = Client(account_sid, auth_token)
        account = client.api.accounts(account_sid).fetch()
        
        print(f"📋 Account SID: {account.sid}")
        print(f"📝 Status: {account.status}")
        print(f"🏷️  Name: {account.friendly_name}")
        
        # Check balance
        try:
            balance = client.balance.fetch()
            print(f"💰 Balance: {balance.balance} {balance.currency}")
        except:
            print("💰 Balance: Unable to fetch")
        
        return True
        
    except Exception as e:
        print(f"❌ Account check failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 ISOLATED SMS TEST")
    print("=" * 60)
    
    # Step 1: Check credentials
    if not test_sms_credentials():
        print("\n🛑 Cannot proceed without credentials!")
        exit(1)
    
    # Step 2: Check account
    test_twilio_account()
    
    # Step 3: Test SMS (you can change the number)
    test_number = input("\n📱 Enter phone number to test (e.g. +4512345678): ").strip()
    if test_number:
        test_sms_send(test_number)
    else:
        print("⏭️  Skipping SMS send test")
    
    print("\n🎉 SMS test complete!")
