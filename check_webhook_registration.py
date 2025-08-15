#!/usr/bin/env python3
"""
Check if webhook is registered with HeyGen API
"""
import requests
import os
import json

def check_webhook_registration():
    """Check if our webhook is registered with HeyGen"""
    
    api_key = os.getenv('HEYGEN_API_KEY')
    if not api_key:
        print("❌ HEYGEN_API_KEY not found in environment")
        return False
    
    # List registered webhooks
    list_url = "https://api.heygen.com/v1/webhook/endpoint.list"
    headers = {
        "Accept": "application/json",
        "X-Api-Key": api_key
    }
    
    try:
        print("🔍 Checking registered webhooks with HeyGen...")
        response = requests.get(list_url, headers=headers)
        response.raise_for_status()
        result = response.json()
        
        if result.get("code") == 100:
            endpoints = result.get("data", [])
            print(f"📋 Found {len(endpoints)} registered webhook(s)")
            
            # Check if our webhook is registered
            our_webhook_url = "https://app.myavatar.dk/api/heygen/webhook"
            webhook_found = False
            
            for i, endpoint in enumerate(endpoints, 1):
                url = endpoint.get('url', '')
                status = endpoint.get('status', '')
                events = endpoint.get('events', [])
                
                print(f"\n📌 Webhook {i}:")
                print(f"   URL: {url}")
                print(f"   Status: {status}")
                print(f"   Events: {events}")
                print(f"   ID: {endpoint.get('endpoint_id')}")
                
                if our_webhook_url in url:
                    webhook_found = True
                    print(f"   ✅ THIS IS OUR WEBHOOK!")
            
            if webhook_found:
                print(f"\n✅ Our webhook IS registered with HeyGen!")
                return True
            else:
                print(f"\n❌ Our webhook is NOT registered with HeyGen!")
                print(f"   Expected URL: {our_webhook_url}")
                print(f"   🔧 Need to register webhook endpoint")
                return False
                
        else:
            print(f"❌ API Error: {result}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking webhooks: {e}")
        return False

if __name__ == "__main__":
    print("🔗 HeyGen Webhook Registration Check")
    print("=" * 40)
    
    is_registered = check_webhook_registration()
    
    if not is_registered:
        print(f"\n🚨 SOLUTION: Run webhook registration script to fix this!")
        print(f"   python webhook_registration.py")
    else:
        print(f"\n🎉 Webhook is registered - problem must be elsewhere!")
