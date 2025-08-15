#!/usr/bin/env python3
"""
MISSING WEBHOOK HANDLER - Add this to your api_routes.py

This is the ACTUAL webhook handler that processes HeyGen completion notifications.
Currently missing from your deployed code!
"""

@router.post("/api/heygen/webhook")
async def heygen_webhook(request: Request):
    """
    ACTUAL HeyGen webhook handler - processes video completion notifications
    """
    try:
        # Get the webhook payload
        payload = await request.json()
        log_info(f"🔔 HeyGen webhook received: {payload}", "API")
        
        # Extract video information
        video_id = payload.get('video_id') or payload.get('id')
        status = payload.get('status')
        event_type = payload.get('event_type')
        
        # Handle nested data structure
        data = payload.get('data', {})
        if not video_id and data:
            video_id = data.get('video_id') or data.get('id')
        if not status:
            status = data.get('status')
            
        if not video_id:
            log_error("No video_id in webhook payload", "API")
            return JSONResponse(status_code=400, content={"error": "Missing video_id"})
            
        log_info(f"Processing webhook for video {video_id}: status={status}", "API")
            
        # Update video status in database
        if status == 'completed' or event_type == 'video.succeed':
            # Video completed - get the video URL
            video_url = (
                payload.get('video_url') or 
                data.get('video_url') or 
                payload.get('url') or 
                data.get('url')
            )
            duration = payload.get('duration') or data.get('duration', 0)
            
            if video_url:
                # Update database - ONLY use video_path (no video_url field!)
                execute_query("""
                    UPDATE videos 
                    SET status = 'completed', 
                        video_path = %s,
                        duration = %s,
                        completed_at = NOW(),
                        updated_at = NOW()
                    WHERE heygen_video_id = %s
                """, (video_url, duration, video_id))
                
                log_info(f"✅ Video {video_id} marked as completed", "API")
            else:
                log_error(f"Video {video_id} completed but no URL provided", "API")
                
        elif status == 'failed' or event_type == 'video.fail':
            # Video failed
            error_message = payload.get('error') or data.get('error') or 'Video processing failed'
            
            execute_query("""
                UPDATE videos 
                SET status = 'failed', 
                    error_message = %s,
                    updated_at = NOW()
                WHERE heygen_video_id = %s
            """, (error_message, video_id))
            
            log_error(f"❌ Video {video_id} failed: {error_message}", "API")
            
        return JSONResponse(content={"success": True, "message": "Webhook processed"})
        
    except Exception as e:
        log_error(f"Webhook processing error: {str(e)}", "API")
        return JSONResponse(
            status_code=500, 
            content={"error": "Webhook processing failed"}
        )
