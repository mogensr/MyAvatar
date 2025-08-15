#!/usr/bin/env python3
"""
BackgroundFX Processed Video Saver
Simple script to save processed videos to "My Videos" 
Usage: python save_processed_video.py <video_url> <user_id> [filename]
"""

import os
import sys
import requests
import uuid
from datetime import datetime
from pathlib import Path
import psycopg2
from urllib.parse import urlparse

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://user:pass@localhost/myavatar')

def download_video(video_url, save_path):
    """Download video from URL to local path"""
    print(f"📥 Downloading video from: {video_url}")
    
    try:
        response = requests.get(video_url, stream=True, timeout=30)
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        file_size = os.path.getsize(save_path)
        print(f"✅ Downloaded {file_size:,} bytes to: {save_path}")
        return file_size
        
    except Exception as e:
        print(f"❌ Download failed: {e}")
        raise

def save_to_database(user_id, filename, file_path, file_size):
    """Save video metadata to database"""
    print(f"💾 Saving to database for user {user_id}")
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Insert into videos table (same as HeyGen videos)
        cur.execute("""
            INSERT INTO videos (user_id, title, video_path, status, created_at, source)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            user_id,
            filename,
            str(file_path),
            'completed',
            datetime.now(),
            'backgroundfx'
        ))
        
        video_id = cur.fetchone()[0]
        conn.commit()
        
        print(f"✅ Saved to database with ID: {video_id}")
        return video_id
        
    except Exception as e:
        print(f"❌ Database save failed: {e}")
        raise
    finally:
        if conn:
            conn.close()

def save_processed_video(video_url, user_id, filename=None):
    """Main function to save processed video to My Videos"""
    
    # Generate filename if not provided
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backgroundfx_processed_{timestamp}.mp4"
    
    # Ensure filename has .mp4 extension
    if not filename.lower().endswith('.mp4'):
        filename += '.mp4'
    
    print(f"🎬 Saving processed video to My Videos")
    print(f"   User ID: {user_id}")
    print(f"   Filename: {filename}")
    print(f"   Source URL: {video_url}")
    
    # Create user video directory
    video_dir = Path("user_uploads/videos") / str(user_id)
    video_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename to avoid conflicts
    unique_filename = f"{uuid.uuid4()}_{filename}"
    file_path = video_dir / unique_filename
    
    try:
        # Download video
        file_size = download_video(video_url, file_path)
        
        # Save to database
        video_id = save_to_database(user_id, filename, file_path, file_size)
        
        print(f"🎉 SUCCESS! Video saved to My Videos")
        print(f"   Database ID: {video_id}")
        print(f"   File Path: {file_path}")
        print(f"   File Size: {file_size:,} bytes")
        
        return {
            'success': True,
            'video_id': video_id,
            'file_path': str(file_path),
            'file_size': file_size,
            'filename': filename
        }
        
    except Exception as e:
        # Clean up partial download on error
        if file_path.exists():
            file_path.unlink()
        
        print(f"💥 FAILED to save video: {e}")
        return {
            'success': False,
            'error': str(e)
        }

def main():
    """Command line interface"""
    if len(sys.argv) < 3:
        print("Usage: python save_processed_video.py <video_url> <user_id> [filename]")
        print("Example: python save_processed_video.py https://example.com/video.mp4 123 my_video.mp4")
        sys.exit(1)
    
    video_url = sys.argv[1]
    user_id = int(sys.argv[2])
    filename = sys.argv[3] if len(sys.argv) > 3 else None
    
    # Validate URL
    parsed = urlparse(video_url)
    if not parsed.scheme or not parsed.netloc:
        print("❌ Invalid video URL provided")
        sys.exit(1)
    
    # Save the video
    result = save_processed_video(video_url, user_id, filename)
    
    if result['success']:
        print(f"\n✅ Video successfully saved to My Videos!")
        sys.exit(0)
    else:
        print(f"\n❌ Failed to save video: {result['error']}")
        sys.exit(1)

if __name__ == "__main__":
    main()
