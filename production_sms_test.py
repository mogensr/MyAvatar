#!/usr/bin/env python3
"""
Production SMS Test Endpoint
============================
Add this to main.py to test SMS in Railway production environment
"""

from fastapi import Request
from fastapi.responses import JSONResponse
import os
import logging

logger = logging.getLogger(__name__)

async def test_sms_production(request: Request):
    """Test SMS functionality in production environment"""
    try:
        # Check credentials
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        from_number = os.getenv('TWILIO_PHONE_NUMBER')
        
        credentials_status = {
            "TWILIO_ACCOUNT_SID": "SET" if account_sid else "MISSING",
            "TWILIO_AUTH_TOKEN": "SET" if auth_token else "MISSING", 
            "TWILIO_PHONE_NUMBER": from_number if from_number else "MISSING"
        }
        
        if not all([account_sid, auth_token, from_number]):
            return JSONResponse({
                "success": False,
                "error": "Missing Twilio credentials",
                "credentials": credentials_status
            })
        
        # Test SMS send
        try:
            from twilio.rest import Client
            
            client = Client(account_sid, auth_token)
            
            # Send test SMS to Mogens
            message = client.messages.create(
                body="🧪 TEST: MyAvatar SMS system is working! This is a production test from Railway.",
                from_=from_number,
                to="+4530604639"  # Mogens' number
            )
            
            return JSONResponse({
                "success": True,
                "message": "SMS sent successfully!",
                "credentials": credentials_status,
                "sms_details": {
                    "sid": message.sid,
                    "to": message.to,
                    "from": message.from_,
                    "status": message.status
                }
            })
            
        except Exception as sms_error:
            return JSONResponse({
                "success": False,
                "error": f"SMS send failed: {str(sms_error)}",
                "credentials": credentials_status
            })
            
    except Exception as e:
        logger.error(f"SMS test error: {e}")
        return JSONResponse({
            "success": False,
            "error": f"SMS test failed: {str(e)}"
        })

# Add this endpoint to main.py:
# @app.get("/admin/test-sms")
# async def admin_test_sms(request: Request):
#     return await test_sms_production(request)
