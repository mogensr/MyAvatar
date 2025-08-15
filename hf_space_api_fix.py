#!/usr/bin/env python3
"""
URGENT HF SPACE API FIX - Replace your HF Space submission section with this code
"""

# FIXED HF Space API Call - Replace your existing submit section

# Submit job asynchronously
logger.error("🎬 🔧 Submitting job asynchronously...")
try:
    # FIXED: Correct HF Space API format
    if bg_path:
        # Submit with both video and background
        job_handle = client.submit(
            video_path,          # First parameter: input video
            bg_path,            # Second parameter: background image
            api_name="/predict"
        )
        logger.error(f"🎬 ✅ Job submitted with background: video={video_path}, bg={bg_path}")
    else:
        # Submit with video only (will use green screen)
        job_handle = client.submit(
            video_path,          # First parameter: input video
            None,               # Second parameter: no background (green screen)
            api_name="/predict"
        )
        logger.error(f"🎬 ✅ Job submitted video-only: video={video_path}")
    
    logger.error(f"🎬 ✅ Job handle created: {job_handle}")
    
    # Track the job
    track_job_start(job_id, user["id"], job_handle)
    
    # Start enhanced background monitoring with tracking
    asyncio.create_task(enhanced_monitor_hf_job(job_handle, job_id, user["id"]))
    
    logger.error("🎬 ✅ Enhanced monitoring with tracking started")
    
    return JSONResponse({
        "success": True,
        "job_id": job_id,
        "status": "processing",
        "message": "Video processing started with enhanced monitoring",
        "estimated_time": "30-90 seconds for 8 second video",
        "cloudinary_status": "verified" if cloudinary_test["success"] else "fallback_mode",
        "tracking_endpoints": {
            "status": f"/api/backgroundfx/status/{job_id}",
            "force_check": f"/api/backgroundfx/force-check/{job_id}",
            "stuck_jobs": "/api/backgroundfx/stuck-jobs",
            "logs": "/backgroundfx/logs"
        }
    })
    
except Exception as e:
    logger.error(f"🎬 ❌ Job submission failed: {e}")
    logger.error(f"🎬 ❌ Error type: {type(e)}")
    logger.error(f"🎬 ❌ Error details: {str(e)}")
    
    # Enhanced synchronous fallback
    logger.error("🎬 🔄 Trying enhanced synchronous fallback...")
    
    try:
        if bg_path:
            result = client.predict(
                video_path,
                bg_path,
                api_name="/predict"
            )
        else:
            result = client.predict(
                video_path,
                None,
                api_name="/predict"
            )
        
        logger.error(f"🎬 ✅ Synchronous result received: {type(result)}")
        
        # Process result with enhanced upload
        if result and len(result) >= 1:
            output_video_path = result[0]
            logger.error(f"🎬 ✅ Synchronous result: {output_video_path}")
            
            # Enhanced upload and save
            final_url = await robust_upload_and_save_video(output_video_path, job_id, user["id"])
            
            if final_url:
                track_job_completion(job_id, "completed", final_url)
                return JSONResponse({
                    "success": True,
                    "job_id": job_id,
                    "status": "completed",
                    "message": "Video processed successfully with enhanced upload!",
                    "output_url": final_url
                })
            else:
                raise HTTPException(status_code=500, detail="Processing completed but upload failed")
        else:
            raise HTTPException(status_code=500, detail="HF Space returned unexpected result")
            
    except Exception as sync_error:
        logger.error(f"🎬 ❌ Synchronous fallback failed: {sync_error}")
        raise HTTPException(status_code=500, detail=f"Both async and sync processing failed: {str(sync_error)}")

print("🚀 HF SPACE API FIX READY!")
print("📝 Instructions:")
print("1. Find your HF Space submission section in backgroundfx_routes.py")
print("2. Replace it with the code above")
print("3. Deploy to Railway immediately!")
print("4. Test with a new video")
print("⚡ This should fix the API parameter format issue!")
