"""
Enhanced Background Video and Avatar URL Refresher
Automatically refreshes expiring HeyGen video URLs and broken avatar image URLs
COMPLETE VERSION with Photo Avatar API Support + Talking Photo Detection
"""
import os
import time
import requests
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, parse_qs
import logging

# Import your existing modules
from app.db.database import execute_query
from app.api.heygen import get_video_details
from app.logger.log_handler import log_info, log_error

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class VideoAvatarURLRefresher:
    def __init__(self):
        self.heygen_api_key = os.getenv("HEYGEN_API_KEY")
        if not self.heygen_api_key:
            logger.error("HEYGEN_API_KEY not found in environment variables")
            raise ValueError("HEYGEN_API_KEY is required")
    
    # ===============================================================================
    # CHAPTER 1: VIDEO URL REFRESH METHODS (EXISTING FUNCTIONALITY - NO CHANGES)
    # ===============================================================================
    
    def is_url_expiring_soon(self, video_path, hours_threshold=6):
        """Check if URL expires within the threshold hours"""
        try:
            if not video_path or 'Expires=' not in video_path:
                return False
            
            # Parse expiry timestamp
            parsed = urlparse(video_path)
            query_params = parse_qs(parsed.query)
            
            expires_value = None
            for key, value in query_params.items():
                if key.lower() == 'expires':
                    expires_value = value[0] if value else None
                    break
            
            if not expires_value:
                return False
            
            expires_timestamp = int(expires_value)
            expires_datetime = datetime.fromtimestamp(expires_timestamp, tz=timezone.utc)
            threshold_datetime = datetime.now(timezone.utc) + timedelta(hours=hours_threshold)
            
            # Return True if URL expires within threshold
            return expires_datetime <= threshold_datetime
            
        except Exception as e:
            logger.error(f"Error checking URL expiry: {e}")
            return False
    
    def get_expiring_videos(self, hours_threshold=6):
        """Get all videos with URLs expiring soon"""
        try:
            # Get all videos with video_path containing Expires
            videos = execute_query(
                "SELECT id, heygen_video_id, video_path, user_id, title FROM videos WHERE video_path LIKE '%Expires=%' AND status = 'completed'",
                fetch_all=True
            )
            
            if not videos:
                logger.info("No videos with expiring URLs found")
                return []
            
            expiring_videos = []
            for video in videos:
                video_dict = dict(video) if hasattr(video, '_asdict') else video
                if self.is_url_expiring_soon(video_dict['video_path'], hours_threshold):
                    expiring_videos.append(video_dict)
            
            logger.info(f"Found {len(expiring_videos)} videos with URLs expiring within {hours_threshold} hours")
            return expiring_videos
            
        except Exception as e:
            logger.error(f"Error fetching expiring videos: {e}")
            return []
    
    def refresh_video_url(self, video):
        """Refresh a single video URL"""
        try:
            logger.info(f"Refreshing URL for video {video['id']} (HeyGen ID: {video['heygen_video_id']})")
            
            # Get fresh URL from HeyGen
            result = get_video_details(self.heygen_api_key, video['heygen_video_id'])
            
            if result['success'] and result.get('details'):
                details = result['details']
                fresh_url = (details.get('video_url') or 
                           details.get('video_url_caption') or 
                           details.get('url') or 
                           details.get('download_url'))
                
                if fresh_url:
                    # Update database with fresh URL
                    execute_query(
                        "UPDATE videos SET video_path = %s, updated_at = NOW() WHERE id = %s",
                        (fresh_url, video['id'])
                    )
                    
                    logger.info(f"✅ Successfully refreshed URL for video {video['id']}")
                    return True
                else:
                    logger.error(f"❌ No video URL found in HeyGen response for video {video['id']}")
                    return False
            else:
                logger.error(f"❌ Failed to get fresh URL for video {video['id']}: {result.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error refreshing video {video['id']}: {e}")
            return False
    
    # ===============================================================================
    # CHAPTER 2: REGULAR AVATAR API METHODS (EXISTING FUNCTIONALITY - NO CHANGES)
    # ===============================================================================
    
    def is_avatar_url_accessible(self, avatar_image_url):
        """Check if avatar image URL is accessible"""
        try:
            if not avatar_image_url or not avatar_image_url.startswith('http'):
                return False
            
            response = requests.head(avatar_image_url, timeout=10)
            return response.status_code == 200
            
        except Exception as e:
            logger.debug(f"Avatar URL not accessible: {e}")
            return False
    
    def get_fresh_heygen_avatars(self):
        """Get fresh avatar data from HeyGen API v2 - REGULAR AVATARS ONLY"""
        headers = {
            "X-Api-Key": self.heygen_api_key,
            "Content-Type": "application/json"
        }
        
        try:
            logger.info("🌐 Fetching fresh avatar data from HeyGen API v2...")
            response = requests.get(
                "https://api.heygen.com/v2/avatars",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Handle v2 response format
                avatars = []
                if "data" in data:
                    avatars.extend(data["data"].get("avatars", []))
                    avatars.extend(data["data"].get("talking_photos", []))
                
                logger.info(f"✅ Retrieved {len(avatars)} avatars from HeyGen regular API")
                return avatars
            else:
                logger.error(f"❌ HeyGen API error: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error fetching from HeyGen API: {e}")
            return []
    
    # ===============================================================================
    # CHAPTER 3: NEW PHOTO AVATAR API METHODS (ENHANCED FUNCTIONALITY)
    # ===============================================================================
    
    def get_photo_avatar_groups(self):
        """Get all photo avatar groups from HeyGen API"""
        headers = {
            "X-Api-Key": self.heygen_api_key,
            "Content-Type": "application/json"
        }
        
        try:
            logger.info("📸 Fetching photo avatar groups from HeyGen API...")
            response = requests.get(
                "https://api.heygen.com/v2/avatar_group.list",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("error") is None:
                    groups = data.get("data", {}).get("avatar_group_list", [])
                    logger.info(f"✅ Found {len(groups)} photo avatar groups")
                    return groups
            
            logger.error(f"❌ Failed to fetch photo avatar groups: {response.status_code}")
            return []
            
        except Exception as e:
            logger.error(f"❌ Error fetching photo avatar groups: {e}")
            return []
    
    def get_photo_avatars_in_group(self, group_id):
        """Get photo avatars within a specific group"""
        headers = {
            "X-Api-Key": self.heygen_api_key,
            "Content-Type": "application/json"
        }
        
        try:
            logger.info(f"📸 Fetching photo avatars in group {group_id}...")
            response = requests.get(
                f"https://api.heygen.com/v2/avatar_group/{group_id}/avatars",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("error") is None:
                    avatars = data.get("data", {}).get("avatar_list", [])
                    logger.info(f"✅ Found {len(avatars)} photo avatars in group {group_id}")
                    return avatars
            
            logger.error(f"❌ Failed to fetch photo avatars in group {group_id}: {response.status_code}")
            return []
            
        except Exception as e:
            logger.error(f"❌ Error fetching photo avatars in group {group_id}: {e}")
            return []
    
    def get_individual_photo_avatar(self, photo_avatar_id):
        """Get individual photo avatar details"""
        headers = {
            "X-Api-Key": self.heygen_api_key,
            "Content-Type": "application/json"
        }
        
        try:
            logger.info(f"📸 Fetching individual photo avatar {photo_avatar_id}...")
            response = requests.get(
                f"https://api.heygen.com/v2/photo_avatar/{photo_avatar_id}",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("error") is None:
                    avatar_data = data.get("data", {})
                    logger.info(f"✅ Found individual photo avatar {photo_avatar_id}")
                    return avatar_data
            
            logger.error(f"❌ Failed to fetch photo avatar {photo_avatar_id}: {response.status_code}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error fetching photo avatar {photo_avatar_id}: {e}")
            return None
    
    def get_all_photo_avatars(self):
        """Get ALL photo avatars from all groups and individual endpoints"""
        all_photo_avatars = []
        
        try:
            # STEP 1: Get all photo avatar groups
            groups = self.get_photo_avatar_groups()
            
            # STEP 2: Get avatars from each group
            for group in groups:
                group_id = group.get('id')
                if group_id:
                    avatars = self.get_photo_avatars_in_group(group_id)
                    if avatars:
                        # Add group info to each avatar
                        for avatar in avatars:
                            avatar['group_id'] = group_id
                            avatar['group_name'] = group.get('name', 'Unknown Group')
                            all_photo_avatars.append(avatar)
            
            logger.info(f"✅ Retrieved {len(all_photo_avatars)} total photo avatars from all groups")
            return all_photo_avatars
            
        except Exception as e:
            logger.error(f"❌ Error getting all photo avatars: {e}")
            return []
    
    # ===============================================================================
    # CHAPTER 4: TALKING PHOTO DETECTION (NEW FUNCTIONALITY)
    # ===============================================================================
    
    def is_talking_photo_url(self, url):
        """Detect if URL is from old talking photo system"""
        if not url:
            return False
        return '/talking_photo/' in url
    
    # ===============================================================================
    # CHAPTER 5: ENHANCED AVATAR REFRESH METHODS (COMBINES REGULAR + PHOTO AVATARS)
    # ===============================================================================
    
    def get_broken_avatars(self):
        """Get all avatars with broken or inaccessible image URLs"""
        try:
            # Get all avatars with image URLs
            avatars = execute_query("""
                SELECT ua.id, ua.user_id, ua.avatar_id, ua.avatar_name, ua.avatar_image_url,
                       u.username
                FROM user_avatars ua
                JOIN users u ON ua.user_id = u.id
                WHERE ua.avatar_image_url IS NOT NULL
                ORDER BY ua.user_id, ua.id
            """, fetch_all=True)
            
            if not avatars:
                logger.info("No avatars with image URLs found")
                return []
            
            broken_avatars = []
            for avatar in avatars:
                avatar_dict = dict(avatar) if hasattr(avatar, '_asdict') else avatar
                
                # Check if URL is accessible
                if not self.is_avatar_url_accessible(avatar_dict['avatar_image_url']):
                    broken_avatars.append(avatar_dict)
            
            logger.info(f"Found {len(broken_avatars)} avatars with broken image URLs out of {len(avatars)} total")
            return broken_avatars
            
        except Exception as e:
            logger.error(f"Error fetching broken avatars: {e}")
            return []
    
    def create_combined_avatar_lookup(self):
        """Create a combined lookup of regular avatars AND photo avatars"""
        lookup = {}
        
        try:
            # STEP 1: Get regular avatars (including talking photos)
            regular_avatars = self.get_fresh_heygen_avatars()
            for avatar in regular_avatars:
                avatar_id = avatar.get('avatar_id') or avatar.get('id')
                if avatar_id:
                    lookup[avatar_id] = {
                        'type': 'regular',
                        'data': avatar
                    }
            
            # STEP 2: Get photo avatars
            photo_avatars = self.get_all_photo_avatars()
            for avatar in photo_avatars:
                avatar_id = avatar.get('id')
                if avatar_id:
                    lookup[avatar_id] = {
                        'type': 'photo',
                        'data': avatar
                    }
            
            logger.info(f"🔍 Created combined lookup for {len(lookup)} total avatars")
            logger.info(f"   • Regular avatars: {len(regular_avatars)}")
            logger.info(f"   • Photo avatars: {len(photo_avatars)}")
            
            return lookup
            
        except Exception as e:
            logger.error(f"❌ Error creating combined avatar lookup: {e}")
            return {}
    
    def refresh_avatar_url(self, avatar, combined_lookup):
        """Refresh a single avatar image URL using combined lookup"""
        try:
            avatar_id = avatar['avatar_id']
            current_url = avatar['avatar_image_url']
            avatar_name = avatar['avatar_name']
            username = avatar['username']
            
            logger.info(f"🔄 Refreshing avatar image for {username} - {avatar_name} (ID: {avatar_id})")
            
            # NEW: Check if it's an old talking photo URL
            if self.is_talking_photo_url(current_url):
                logger.warning(f"🚨 OLD TALKING PHOTO URL DETECTED: {avatar_name}")
                logger.warning(f"   • User: {username}")
                logger.warning(f"   • Avatar ID: {avatar_id}")
                logger.warning(f"   • URL: {current_url[:80]}...")
                logger.warning(f"   • ACTION REQUIRED: Please re-upload this avatar to use V2 Photo Avatar system")
                logger.warning(f"   • The old talking photo system uses signed URLs that cannot be refreshed")
                return False  # Skip refreshing old talking photo URLs
            
            # STEP 1: Look up avatar in combined lookup
            if avatar_id in combined_lookup:
                avatar_info = combined_lookup[avatar_id]
                avatar_type = avatar_info['type']
                heygen_avatar = avatar_info['data']
                
                logger.info(f"   • Found avatar in {avatar_type} API")
                
                # STEP 2: Get the appropriate image URL based on type
                if avatar_type == 'regular':
                    # Regular avatar or talking photo
                    new_url = (
                        heygen_avatar.get('preview_image_url') or 
                        heygen_avatar.get('image_url') or
                        heygen_avatar.get('preview_image') or
                        heygen_avatar.get('thumbnail_image_url')
                    )
                elif avatar_type == 'photo':
                    # Photo avatar
                    new_url = heygen_avatar.get('image_url')
                else:
                    new_url = None
                
                if new_url and new_url != current_url:
                    logger.info(f"   • Testing new URL: {new_url[:60]}...")
                    
                    # STEP 3: For photo avatars, don't test accessibility (they need auth)
                    should_test = avatar_type == 'regular' and not ('talking_photo' in new_url or 'files2.heygen.ai' in new_url)
                    
                    if should_test:
                        # Test accessibility for regular avatars
                        if self.is_avatar_url_accessible(new_url):
                            url_valid = True
                        else:
                            logger.warning(f"   • New URL not accessible for {avatar_type} avatar {avatar_id}")
                            url_valid = False
                    else:
                        # For photo avatars and talking photos, assume valid
                        logger.info(f"   • Skipping accessibility test for {avatar_type} avatar (requires auth)")
                        url_valid = True
                    
                    if url_valid:
                        # STEP 4: Update database
                        execute_query("""
                            UPDATE user_avatars 
                            SET avatar_image_url = %s 
                            WHERE id = %s
                        """, (new_url, avatar['id']))
                        
                        logger.info(f"✅ Successfully refreshed {avatar_type} avatar image for {avatar_name}")
                        return True
                    else:
                        return False
                else:
                    logger.warning(f"   • No new URL available for {avatar_type} avatar {avatar_id}")
                    return False
            else:
                logger.warning(f"   • Avatar ID {avatar_id} not found in any HeyGen API")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error refreshing avatar {avatar.get('id', 'unknown')}: {e}")
            return False
    
    # ===============================================================================
    # CHAPTER 6: ENHANCED AVATAR REFRESH CYCLE (USES COMBINED LOOKUP)
    # ===============================================================================
    
    def run_avatar_refresh_cycle(self):
        """Run one complete avatar refresh cycle with photo avatar support"""
        logger.info("🎭 Starting ENHANCED avatar image URL refresh cycle")
        logger.info("   • Includes regular avatars, talking photos, AND photo avatars")
        logger.info("   • Detects and skips old talking photo URLs")
        
        start_time = time.time()
        
        # STEP 1: Get avatars that need refreshing
        broken_avatars = self.get_broken_avatars()
        
        if not broken_avatars:
            logger.info("✅ No avatars need image URL refreshing at this time")
            return
        
        # STEP 2: Create combined lookup of all avatar types
        combined_lookup = self.create_combined_avatar_lookup()
        
        if not combined_lookup:
            logger.error("❌ Could not create combined avatar lookup")
            return
        
        # STEP 3: Refresh each broken avatar
        success_count = 0
        failure_count = 0
        talking_photo_count = 0
        
        for avatar in broken_avatars:
            if self.is_talking_photo_url(avatar['avatar_image_url']):
                talking_photo_count += 1
                failure_count += 1  # Count as failure since it needs manual action
            elif self.refresh_avatar_url(avatar, combined_lookup):
                success_count += 1
            else:
                failure_count += 1
            
            # Small delay to avoid overwhelming HeyGen API
            time.sleep(0.5)
        
        # STEP 4: Summary
        elapsed_time = time.time() - start_time
        logger.info("=" * 50)
        logger.info(f"🎭 ENHANCED Avatar refresh cycle completed in {elapsed_time:.2f} seconds")
        logger.info(f"✅ Successfully refreshed: {success_count} avatar images")
        logger.info(f"❌ Failed to refresh: {failure_count} avatar images")
        if talking_photo_count > 0:
            logger.warning(f"🚨 Old talking photo URLs detected: {talking_photo_count}")
            logger.warning(f"   • These avatars need to be re-uploaded to use V2 Photo Avatar system")
        logger.info("=" * 50)
    
    # ===============================================================================
    # CHAPTER 7: COMBINED REFRESH METHODS (NO CHANGES TO EXISTING LOGIC)
    # ===============================================================================
    
    def run_refresh_cycle(self, hours_threshold=6):
        """Run one complete refresh cycle for both videos and avatars"""
        logger.info("=" * 60)
        logger.info("🔄 Starting COMBINED video and avatar URL refresh cycle")
        logger.info("=" * 60)
        
        start_time = time.time()
        
        # 1. Refresh expiring video URLs
        logger.info("📹 PHASE 1: Video URL Refresh")
        logger.info("-" * 30)
        
        expiring_videos = self.get_expiring_videos(hours_threshold)
        video_success = 0
        video_failure = 0
        
        if expiring_videos:
            for video in expiring_videos:
                if self.refresh_video_url(video):
                    video_success += 1
                else:
                    video_failure += 1
                time.sleep(1)  # Delay between video refreshes
        else:
            logger.info("✅ No videos need URL refreshing")
        
        # 2. Refresh broken avatar image URLs
        logger.info("\n🎭 PHASE 2: ENHANCED Avatar Image URL Refresh")
        logger.info("-" * 45)
        
        self.run_avatar_refresh_cycle()
        
        # Final summary
        total_elapsed = time.time() - start_time
        logger.info("=" * 60)
        logger.info(f"📊 COMBINED refresh cycle completed in {total_elapsed:.2f} seconds")
        logger.info(f"📹 Videos - ✅ Success: {video_success}, ❌ Failed: {video_failure}")
        logger.info(f"🎭 Enhanced avatar refresh cycle completed (see detailed results above)")
        logger.info("=" * 60)
    
    def run_continuous(self, interval_hours=4, hours_threshold=6):
        """Run the refresher continuously for both videos and avatars"""
        logger.info(f"🚀 Starting continuous video + avatar URL refresher")
        logger.info(f"   • Refresh interval: {interval_hours} hours")
        logger.info(f"   • Video expiry threshold: {hours_threshold} hours")
        logger.info(f"   • Avatar images: Check accessibility and refresh broken URLs")
        logger.info(f"   • ENHANCED: Includes regular avatars, talking photos, AND photo avatars")
        logger.info(f"   • NEW: Detects and skips old talking photo URLs")
        
        while True:
            try:
                self.run_refresh_cycle(hours_threshold)
                
                # Wait for next cycle
                next_run = datetime.now() + timedelta(hours=interval_hours)
                logger.info(f"⏰ Next refresh cycle at: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
                
                time.sleep(interval_hours * 3600)  # Convert hours to seconds
                
            except KeyboardInterrupt:
                logger.info("🛑 Refresher stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Error in refresh cycle: {e}")
                logger.info("⏰ Retrying in 30 minutes...")
                time.sleep(1800)  # Wait 30 minutes before retrying

# ===============================================================================
# CHAPTER 8: MAIN FUNCTION AND ENTRY POINT (NO CHANGES)
# ===============================================================================

def main():
    """Main function to run the enhanced refresher"""
    try:
        refresher = VideoAvatarURLRefresher()
        
        # Check command line arguments or environment variables
        mode = os.getenv('REFRESHER_MODE', 'continuous')
        
        if mode == 'once':
            # Run once and exit
            refresher.run_refresh_cycle()
        elif mode == 'avatars_only':
            # Run avatar refresh only
            refresher.run_avatar_refresh_cycle()
        else:
            # Run continuously
            interval = int(os.getenv('REFRESH_INTERVAL_HOURS', '4'))
            threshold = int(os.getenv('EXPIRY_THRESHOLD_HOURS', '6'))
            refresher.run_continuous(interval, threshold)
            
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        exit(1)

if __name__ == "__main__":
    main()
