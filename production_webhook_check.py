#!/usr/bin/env python3
"""
Production webhook registration check - deploy this to Railway
"""
import requests
import os
import json
import sys

def check_and_register_webhook():
    """Check webhook registration and register if needed"""
    
    api_key = os.getenv('HEYGEN_API_KEY')
    if not api_key:
        print("❌ HEYGEN_API_KEY not found in Railway environment")
        return False
    
    print(f"🔑 Using HeyGen API Key: {api_key[:10]}...")
    
    # List registered webhooks first
    list_url = "https://api.heygen.com/v1/webhook/endpoint.list"
    headers = {
        "Accept": "application/json",
        "X-Api-Key": api_key
    }
    
    try:
        print("🔍 Checking registered webhooks with HeyGen...")
        response = requests.get(list_url, headers=headers)
        
        print(f"📊 Response status: {response.status_code}")
        print(f"📋 Response headers: {dict(response.headers)}")
        
        if response.status_code != 200:
            print(f"❌ API request failed: {response.status_code}")
            print(f"📄 Response text: {response.text}")
            return False
            
        result = response.json()
        print(f"📊 API Response: {result}")
        
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
                print(f"   🔧 Attempting to register webhook...")
                
                # Register the webhook
                return register_webhook(api_key)
                
        else:
            print(f"❌ API Error: {result}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking webhooks: {e}")
        import traceback
        traceback.print_exc()
        return False

def register_webhook(api_key):
    """Register webhook with HeyGen"""
    
    webhook_url = "https://app.myavatar.dk/api/heygen/webhook"
    events = [
        "avatar_video.success",  # Video generation completed successfully
        "avatar_video.fail"      # Video generation failed
    ]
    
    registration_url = "https://api.heygen.com/v1/webhook/endpoint.add"
    
    payload = {
        "url": webhook_url,
        "events": events
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": api_key
    }
    
    try:
        print(f"🔧 Registering webhook: {webhook_url}")
        print(f"📋 Events: {events}")
        
        response = requests.post(
            registration_url,
            headers=headers,
            data=json.dumps(payload)
        )
        
        print(f"📊 Registration response status: {response.status_code}")
        print(f"📄 Registration response: {response.text}")
        
        if response.status_code != 200:
            print(f"❌ Registration failed with status: {response.status_code}")
            return False
            
        result = response.json()
        
        if result.get("code") == 100:
            webhook_data = result.get("data", {})
            endpoint_id = webhook_data.get("endpoint_id")
            secret = webhook_data.get("secret")
            status = webhook_data.get("status")
            
            print("✅ Webhook registered successfully!")
            print(f"📝 Endpoint ID: {endpoint_id}")
            print(f"🔐 Webhook Secret: {secret}")
            print(f"🟢 Status: {status}")
            
            print(f"\n🔑 IMPORTANT: Add this to Railway environment:")
            print(f"HEYGEN_WEBHOOK_SECRET={secret}")
            
            return True
        else:
            print(f"❌ Registration failed: {result}")
            return False
            
    except Exception as e:
        print(f"❌ Registration error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔗 Production HeyGen Webhook Check")
    print("=" * 50)
    
    success = check_and_register_webhook()
    
    if success:
        print(f"\n🎉 Webhook setup complete!")
    else:
        print(f"\n❌ Webhook setup failed!")
        sys.exit(1)
