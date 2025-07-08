#!/usr/bin/env python3
"""
Direct fix: Replace the dashboard route's video fetching logic
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Read the current web_routes.py
with open('app/routes/web_routes.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the problematic video fetching section
old_section = '''        # Get user videos
        videos = db.get_user_videos(user["id"])
        logger.info(f"Dashboard: Fetched {len(videos) if videos else 0} videos for user {user['username']}")'''

new_section = '''        # Get user videos - DIRECT FIX
        try:
            videos = db.get_user_videos(user["id"])
            logger.info(f"Dashboard: Fetched {len(videos) if videos else 0} videos for user {user['username']}")
            
            # FORCE: Ensure videos is a list of dicts
            if videos and not isinstance(videos, list):
                videos = [videos] if isinstance(videos, dict) else []
            
            # FORCE: Convert each video to dict if needed
            if videos:
                converted_videos = []
                for video in videos:
                    if hasattr(video, '_asdict'):  # namedtuple
                        converted_videos.append(video._asdict())
                    elif hasattr(video, 'keys'):  # dict-like
                        converted_videos.append(dict(video))
                    else:
                        converted_videos.append(video)
                videos = converted_videos
                logger.info(f"Dashboard: Converted {len(videos)} videos to dict format")
        except Exception as e:
            logger.error(f"Dashboard: Error fetching videos: {e}")
            videos = []'''

if old_section in content:
    content = content.replace(old_section, new_section)
    
    # Write back
    with open('app/routes/web_routes.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Applied direct fix to video fetching logic")
else:
    print("❌ Could not find the target section to replace")
