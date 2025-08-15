"""
Temporary endpoint to run webhook registration check
Add this to your FastAPI routes temporarily
"""
from fastapi import APIRouter
import requests
import os
import json

router = APIRouter()

@router.get("/admin/check-webhook")
async def check_webhook_registration():
    """Temporary endpoint to check webhook registration"""
    
    try:
        api_key = os.getenv('HEYGEN_API_KEY')
        if not api_key:
            return {"error": "HEYGEN_API_KEY not found in environment"}
        
        # List registered webhooks
        list_url = "https://api.heygen.com/v1/webhook/endpoint.list"
        headers = {
            "Accept": "application/json",
            "X-Api-Key": api_key
        }
        
        response = requests.get(list_url, headers=headers)
        
        if response.status_code != 200:
            return {
                "error": f"API request failed: {response.status_code}",
                "response": response.text
            }
            
        result = response.json()
        
        if result.get("code") == 100:
            endpoints = result.get("data", [])
            our_webhook_url = "https://app.myavatar.dk/api/heygen/webhook"
            
            webhook_found = False
            webhook_details = None
            
            for endpoint in endpoints:
                if our_webhook_url in endpoint.get('url', ''):
                    webhook_found = True
                    webhook_details = endpoint
                    break
            
            if webhook_found:
                return {
                    "status": "registered",
                    "message": "Webhook IS registered with HeyGen",
                    "webhook": webhook_details,
                    "total_webhooks": len(endpoints)
                }
            else:
                # Try to register webhook
                registration_result = await register_webhook_now(api_key)
                return {
                    "status": "not_registered",
                    "message": "Webhook was NOT registered, attempted registration",
                    "registration_result": registration_result,
                    "total_webhooks": len(endpoints)
                }
        else:
            return {"error": f"API Error: {result}"}
            
    except Exception as e:
        return {"error": f"Exception: {str(e)}"}

async def register_webhook_now(api_key):
    """Register webhook with HeyGen"""
    
    webhook_url = "https://app.myavatar.dk/api/heygen/webhook"
    events = ["avatar_video.success", "avatar_video.fail"]
    
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
        response = requests.post(
            registration_url,
            headers=headers,
            data=json.dumps(payload)
        )
        
        if response.status_code != 200:
            return {
                "success": False,
                "error": f"Registration failed: {response.status_code}",
                "response": response.text
            }
            
        result = response.json()
        
        if result.get("code") == 100:
            webhook_data = result.get("data", {})
            return {
                "success": True,
                "endpoint_id": webhook_data.get("endpoint_id"),
                "secret": webhook_data.get("secret"),
                "status": webhook_data.get("status"),
                "message": "Webhook registered successfully!",
                "important": f"Add HEYGEN_WEBHOOK_SECRET={webhook_data.get('secret')} to Railway environment"
            }
        else:
            return {
                "success": False,
                "error": f"Registration failed: {result}"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"Registration exception: {str(e)}"
        }
