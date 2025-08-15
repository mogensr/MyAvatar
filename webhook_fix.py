#!/usr/bin/env python3
"""
CRITICAL WEBHOOK FIX
This is the corrected webhook handler code that should replace the existing one.
The issue: webhook tries to update 'video_url' field that doesn't exist in database.
"""

# CORRECTED WEBHOOK HANDLER - Replace lines 1860-1869 and 1903-1912 in api_routes.py

# FIRST OCCURRENCE (around line 1860):
execute_query("""
    UPDATE videos 
    SET status = 'completed', 
        video_path = %s,
        duration = %s,
        completed_at = NOW(),
        updated_at = NOW()
    WHERE heygen_video_id = %s
""", (video_url, duration, video_id))

# SECOND OCCURRENCE (around line 1903):
execute_query("""
    UPDATE videos 
    SET status = 'completed', 
        video_path = %s,
        duration = %s,
        completed_at = NOW(),
        updated_at = NOW()
    WHERE heygen_video_id = %s
""", (video_url, duration, video_id))

# ALSO REMOVE THE PARAMETER (video_url, video_url, duration, video_id) 
# AND CHANGE TO (video_url, duration, video_id)
