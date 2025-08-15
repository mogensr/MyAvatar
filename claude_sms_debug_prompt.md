# Claude SMS Notification Debug Prompt - CRITICAL ISSUE

## URGENT CONTEXT
MyAvatar platform has a notification system where:
- ✅ **Email notifications work perfectly** (via Resend)
- ❌ **SMS notifications don't work** (via Twilio)
- ✅ **Video completion detection works** (webhook + polling)
- ✅ **Database-triggered notifications implemented**
- ❌ **Railway deployment issues prevent direct SMS testing**

## CURRENT STATUS
- Email notifications are being sent successfully to basic users
- SMS notifications are NOT being received by premium users
- Twilio credentials are confirmed set in Railway environment variables
- No SMS-related logs appear in production logs (critical clue)
- Railway deployment issues prevent direct SMS testing endpoints
- User is frustrated with deployment failures

## TECHNICAL SETUP

### Notification System Architecture:
```python
# Database-triggered notification service
# Located in: notification_service_complete.py
# Triggers when video status = 'completed'

def send_notifications(video_id, user_id):
    user = get_user_from_db(user_id)
    
    if user['subscription_tier'] == 'premium':
        # Should send BOTH email + SMS
        send_email_notification(user, video_id)  # ✅ WORKS
        send_sms_notification(user, video_id)    # ❌ FAILS SILENTLY
    else:
        # Should send email only
        send_email_notification(user, video_id)  # ✅ WORKS
```

### SMS Implementation:
```python
def send_sms_notification(user, video_id):
    try:
        from twilio.rest import Client
        
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        from_number = os.getenv('TWILIO_PHONE_NUMBER')
        
        client = Client(account_sid, auth_token)
        
        message = client.messages.create(
            body=f"🎬 Your MyAvatar video is ready! Video ID: {video_id}",
            from_=from_number,
            to=user['phone_number']  # Format: +4530604639
        )
        
        logger.info(f"✅ SMS sent: {message.sid}")
        return True
        
    except Exception as e:
        logger.error(f"❌ SMS failed: {e}")
        return False
```

### Environment Variables (Railway):
- `TWILIO_ACCOUNT_SID` = Set ✅
- `TWILIO_AUTH_TOKEN` = Set ✅  
- `TWILIO_PHONE_NUMBER` = Set ✅
- `RESEND_API_KEY` = Set ✅ (email works)

### User Data:
- User ID: 3 (MogensR)
- Phone: +4530604639 (Danish number)
- Premium: True
- SMS Opt-in: True

## CRITICAL SYMPTOMS
1. **Email notifications arrive immediately** after video completion
2. **No SMS notifications received** at +4530604639
3. **No SMS-related logs** in Railway production logs (CRITICAL CLUE)
4. **No Twilio error logs** visible
5. **Railway deployment issues** prevent direct SMS testing
6. **User frustration** with deployment failures blocking debugging

## DEBUGGING ATTEMPTS MADE
1. ✅ Verified Twilio credentials are set in Railway
2. ✅ Confirmed user has premium status and phone number
3. ✅ Verified SMS opt-in is enabled
4. ❌ Cannot test SMS directly due to Railway deployment issues
5. ❌ No SMS logs appear in production (suggests SMS code not executing)
6. ❌ Multiple attempts to add SMS test endpoints failed to deploy

## MOST LIKELY ROOT CAUSES
1. **Import Issues**: Twilio library not installed in Railway requirements.txt
2. **Code Path**: SMS notification code not being called at all
3. **Silent Exceptions**: SMS errors being caught and not logged
4. **Environment Access**: Twilio credentials not accessible at runtime
5. **Phone Format**: International number format issues
6. **Twilio Account**: Suspended, no credits, or restrictions

## QUESTIONS FOR CLAUDE

### 1. IMMEDIATE DIAGNOSIS
Given that email works but SMS fails with NO logs appearing, what are the top 3 most likely root causes? The absence of SMS logs suggests the SMS code may not be executing at all.

### 2. REQUIREMENTS.TXT CHECK
What should be in requirements.txt for Twilio SMS to work? Could missing dependencies cause silent failures?

### 3. DEBUGGING WITHOUT ENDPOINTS
How can we debug SMS delivery when Railway deployment prevents direct testing endpoints? What alternative approaches exist?

### 4. TWILIO ACCOUNT VERIFICATION
What Twilio account issues could cause silent SMS failures:
- Account verification status
- Credit balance
- Phone number verification
- International SMS restrictions for Denmark (+45)

### 5. CODE PATH ANALYSIS
How to verify if SMS notification code is being called at all when email notifications work? Could there be a conditional logic error?

### 6. PRODUCTION LOGGING
What logging strategy would help identify where SMS delivery fails in the notification pipeline?

### 7. PHONE NUMBER FORMAT
Is +4530604639 the correct format for Twilio SMS to Denmark? Should it be formatted differently?

### 8. ALTERNATIVE SMS TESTING
What's the simplest way to test SMS delivery in production without adding new endpoints that fail to deploy?

## IMMEDIATE ACTION NEEDED
Provide a step-by-step debugging plan that:
1. Identifies why SMS logs don't appear
2. Tests SMS delivery without new endpoints
3. Verifies Twilio account and configuration
4. Fixes the root cause of silent SMS failures

## PRIORITY
**CRITICAL** - User is frustrated with deployment issues. Need working solution ASAP.