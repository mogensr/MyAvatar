# Claude Webhook Diagnosis Prompt

## Problem Statement
MyAvatar video completion notifications are not working. The HeyGen webhook endpoint is not being triggered after video completion, despite the webhook handler being correctly implemented and integrated.

## Current Situation

### ✅ What Works:
- Video creation works perfectly
- HeyGen API responds correctly with video_id: `eba31efc9a5743298a417d789b61aa07`
- Video status shows "processing" correctly
- Webhook handler exists at `/api/heygen/webhook` and is functional
- SMS/Email notification system is fully implemented and integrated

### ❌ What Doesn't Work:
- HeyGen webhook is NEVER called after video completion
- No `🔔 WEBHOOK CALLED` logs appear in Railway logs
- No notifications are sent (because webhook isn't triggered)

## Log Evidence

### Video Creation (Working):
```
2025-08-11 10:31:11 - [HeyGen API] 📋 HeyGen API response text: {"error":null,"data":{"video_id":"eba31efc9a5743298a417d789b61aa07"}}
2025-08-11 10:31:23 - [VideoPolling] 🔍 HeyGen API Response Body: {"code":100,"data":{"status":"processing",...}}
```

### Missing Webhook Logs:
- **NO** `🔔 WEBHOOK CALLED` entries
- **NO** webhook processing logs
- **NO** notification attempts

## Technical Details

### Webhook Handler Location:
- File: `app/routes/api_routes.py`
- Endpoint: `@router.post("/api/heygen/webhook")`
- URL: `https://app.myavatar.dk/api/heygen/webhook`

### Video Creation Process:
1. User creates video via text-to-video
2. HeyGen API called successfully
3. Video ID returned: `eba31efc9a5743298a417d789b61aa07`
4. Video status: "processing"
5. **WEBHOOK NEVER CALLED** ❌

### Environment:
- Platform: Railway
- Domain: `app.myavatar.dk`
- Framework: FastAPI
- Database: PostgreSQL

## Questions for Claude:

1. **Why would HeyGen not call the webhook after video completion?**
   - Is there a webhook URL configuration missing in HeyGen?
   - Are there specific HeyGen API settings required?
   - Could there be a connectivity issue?

2. **How to verify webhook URL is registered with HeyGen?**
   - Is there a HeyGen dashboard setting?
   - API endpoint to check webhook configuration?
   - Required headers or authentication?

3. **Debugging steps to identify root cause:**
   - How to test if webhook endpoint is accessible from external?
   - HeyGen webhook configuration verification?
   - Alternative methods to trigger webhook manually?

4. **Common causes of webhook failures:**
   - SSL/HTTPS issues?
   - Response code requirements?
   - Timeout issues?
   - Authentication problems?

## Expected Behavior:
When video completes, HeyGen should POST to `https://app.myavatar.dk/api/heygen/webhook` with completion payload, triggering our notification system.

## Request:
Please provide a comprehensive diagnosis and step-by-step solution to resolve why the HeyGen webhook is not being triggered after video completion.
