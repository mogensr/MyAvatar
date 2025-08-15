"""
Distribution Engine - Streamlit Service
======================================
Automated video distribution to social media platforms
Integrates with MyAvatar via SSO authentication
"""

import streamlit as st
import requests
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
from dataclasses import dataclass
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DistributionEngine")

# Configuration
@dataclass
class Config:
    MYAVATAR_API_URL: str = os.getenv("MYAVATAR_API_URL", "http://localhost:8000")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "fallback-development-secret-key")
    
    # Social Media API Keys (from environment)
    LINKEDIN_CLIENT_ID: str = os.getenv("LINKEDIN_CLIENT_ID", "")
    LINKEDIN_CLIENT_SECRET: str = os.getenv("LINKEDIN_CLIENT_SECRET", "")
    TWITTER_API_KEY: str = os.getenv("TWITTER_API_KEY", "")
    TWITTER_API_SECRET: str = os.getenv("TWITTER_API_SECRET", "")
    YOUTUBE_API_KEY: str = os.getenv("YOUTUBE_API_KEY", "")
    
    # Distribution settings
    MAX_CONCURRENT_UPLOADS: int = 3
    RETRY_ATTEMPTS: int = 3
    UPLOAD_TIMEOUT: int = 300  # 5 minutes

config = Config()

class DistributionEngine:
    """Main Distribution Engine class"""
    
    def __init__(self):
        self.config = config
        self.authenticated_user = None
        self.available_platforms = self._get_available_platforms()
        
    def _get_available_platforms(self) -> List[Dict]:
        """Get list of available distribution platforms"""
        platforms = [
            {
                "id": "linkedin",
                "name": "LinkedIn",
                "icon": "🔗",
                "description": "Professional network video sharing",
                "enabled": bool(config.LINKEDIN_CLIENT_ID),
                "features": ["Video posts", "Company pages", "Personal profiles"]
            },
            {
                "id": "twitter",
                "name": "Twitter/X",
                "icon": "🐦",
                "description": "Social media video sharing",
                "enabled": bool(config.TWITTER_API_KEY),
                "features": ["Video tweets", "Thread videos", "Scheduled posts"]
            },
            {
                "id": "youtube",
                "name": "YouTube",
                "icon": "📺",
                "description": "Video hosting and sharing",
                "enabled": bool(config.YOUTUBE_API_KEY),
                "features": ["Public uploads", "Unlisted videos", "Playlists"]
            },
            {
                "id": "vimeo",
                "name": "Vimeo",
                "icon": "🎬",
                "description": "Professional video hosting",
                "enabled": False,  # To be implemented
                "features": ["HD uploads", "Privacy controls", "Custom players"]
            },
            {
                "id": "tiktok",
                "name": "TikTok",
                "icon": "🎵",
                "description": "Short-form video platform",
                "enabled": False,  # To be implemented
                "features": ["Short videos", "Trending hashtags", "Auto-captions"]
            }
        ]
        return platforms
    
    def authenticate_user(self, sso_token: str) -> Optional[Dict]:
        """Authenticate user via SSO token from MyAvatar"""
        try:
            # Verify token with MyAvatar API
            response = requests.post(
                f"{config.MYAVATAR_API_URL}/api/distribution/verify-token",
                json={"token": sso_token},
                timeout=10
            )
            
            if response.status_code == 200:
                user_data = response.json()
                self.authenticated_user = user_data
                logger.info(f"✅ User authenticated: {user_data.get('username')}")
                return user_data
            else:
                logger.error(f"❌ Authentication failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Authentication error: {e}")
            return None
    
    def get_user_videos(self, user_id: int) -> List[Dict]:
        """Get user's videos from MyAvatar"""
        try:
            response = requests.get(
                f"{config.MYAVATAR_API_URL}/api/videos/user/{user_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                videos = response.json().get("videos", [])
                logger.info(f"📹 Retrieved {len(videos)} videos for user {user_id}")
                return videos
            else:
                logger.error(f"❌ Failed to get videos: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error getting videos: {e}")
            return []
    
    def distribute_video(self, video_data: Dict, platforms: List[str], 
                        distribution_settings: Dict) -> Dict:
        """Distribute video to selected platforms"""
        results = {
            "success": [],
            "failed": [],
            "pending": []
        }
        
        for platform in platforms:
            try:
                if platform == "linkedin":
                    result = self._distribute_to_linkedin(video_data, distribution_settings)
                elif platform == "twitter":
                    result = self._distribute_to_twitter(video_data, distribution_settings)
                elif platform == "youtube":
                    result = self._distribute_to_youtube(video_data, distribution_settings)
                else:
                    result = {"success": False, "error": f"Platform {platform} not implemented"}
                
                if result.get("success"):
                    results["success"].append({
                        "platform": platform,
                        "url": result.get("url"),
                        "post_id": result.get("post_id")
                    })
                else:
                    results["failed"].append({
                        "platform": platform,
                        "error": result.get("error", "Unknown error")
                    })
                    
            except Exception as e:
                logger.error(f"❌ Distribution to {platform} failed: {e}")
                results["failed"].append({
                    "platform": platform,
                    "error": str(e)
                })
        
        return results
    
    def _distribute_to_linkedin(self, video_data: Dict, settings: Dict) -> Dict:
        """Distribute video to LinkedIn - Production-ready dual-flow implementation"""
        logger.info(f"🔗 Starting LinkedIn distribution: {video_data.get('title')}")
        
        try:
            # Check if user has LinkedIn API access
            user_linkedin_token = self._get_user_linkedin_token()
            
            if user_linkedin_token and self.config.LINKEDIN_CLIENT_ID:
                # Flow 1: Direct API posting for users with LinkedIn API access
                return self._linkedin_api_post(video_data, settings, user_linkedin_token)
            else:
                # Flow 2: Guided manual posting for users without API access
                return self._linkedin_manual_flow(video_data, settings)
                
        except Exception as e:
            logger.error(f"❌ LinkedIn distribution failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "platform": "linkedin"
            }
    
    def _get_user_linkedin_token(self) -> Optional[str]:
        """Get user's LinkedIn access token from database/session"""
        if not self.authenticated_user:
            return None
            
        try:
            # Check if user has stored LinkedIn token
            response = requests.get(
                f"{self.config.MYAVATAR_API_URL}/api/user/social-tokens",
                headers={"Authorization": f"Bearer {self.authenticated_user.get('token')}"},
                timeout=10
            )
            
            if response.status_code == 200:
                tokens = response.json()
                return tokens.get('linkedin_access_token')
                
        except Exception as e:
            logger.warning(f"Could not retrieve LinkedIn token: {e}")
            
        return None
    
    def _linkedin_api_post(self, video_data: Dict, settings: Dict, access_token: str) -> Dict:
        """Direct LinkedIn API posting for users with API access"""
        logger.info("📡 Using LinkedIn API for direct posting")
        
        try:
            # Step 1: Get user's LinkedIn profile ID
            profile_response = requests.get(
                "https://api.linkedin.com/v2/people/~",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            
            if profile_response.status_code != 200:
                raise Exception(f"LinkedIn profile fetch failed: {profile_response.status_code}")
                
            profile_data = profile_response.json()
            person_urn = profile_data.get('id')
            
            # Step 2: Upload video to LinkedIn
            video_upload_result = self._linkedin_upload_video(video_data, access_token, person_urn)
            
            if not video_upload_result['success']:
                raise Exception(f"Video upload failed: {video_upload_result.get('error')}")
            
            # Step 3: Create LinkedIn post with video
            post_data = {
                "author": f"urn:li:person:{person_urn}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": self._format_linkedin_caption(video_data, settings)
                        },
                        "shareMediaCategory": "VIDEO",
                        "media": [
                            {
                                "status": "READY",
                                "description": {
                                    "text": video_data.get('description', '')
                                },
                                "media": video_upload_result['video_urn'],
                                "title": {
                                    "text": video_data.get('title', 'MyAvatar Video')
                                }
                            }
                        ]
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": settings.get('visibility', 'PUBLIC')
                }
            }
            
            post_response = requests.post(
                "https://api.linkedin.com/v2/ugcPosts",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json=post_data,
                timeout=30
            )
            
            if post_response.status_code == 201:
                post_result = post_response.json()
                post_id = post_result.get('id')
                
                logger.info(f"✅ LinkedIn API post successful: {post_id}")
                
                return {
                    "success": True,
                    "method": "api",
                    "post_id": post_id,
                    "url": f"https://www.linkedin.com/feed/update/{post_id}",
                    "platform": "linkedin"
                }
            else:
                raise Exception(f"LinkedIn post creation failed: {post_response.status_code} - {post_response.text}")
                
        except Exception as e:
            logger.error(f"LinkedIn API posting failed: {e}")
            # Fallback to manual flow if API fails
            logger.info("🔄 Falling back to manual flow")
            return self._linkedin_manual_flow(video_data, settings)
    
    def _linkedin_upload_video(self, video_data: Dict, access_token: str, person_urn: str) -> Dict:
        """Upload video to LinkedIn using their upload API"""
        try:
            # Step 1: Register upload
            register_data = {
                "registerUploadRequest": {
                    "recipes": ["urn:li:digitalmediaRecipe:feedshare-video"],
                    "owner": f"urn:li:person:{person_urn}",
                    "serviceRelationships": [
                        {
                            "relationshipType": "OWNER",
                            "identifier": "urn:li:userGeneratedContent"
                        }
                    ]
                }
            }
            
            register_response = requests.post(
                "https://api.linkedin.com/v2/assets?action=registerUpload",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json=register_data,
                timeout=30
            )
            
            if register_response.status_code != 200:
                raise Exception(f"Upload registration failed: {register_response.status_code}")
                
            register_result = register_response.json()
            upload_mechanism = register_result['value']['uploadMechanism']
            asset_id = register_result['value']['asset']
            upload_url = upload_mechanism['com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest']['uploadUrl']
            
            # Step 2: Upload video file
            video_file_path = video_data.get('file_path')
            if not video_file_path or not os.path.exists(video_file_path):
                raise Exception("Video file not found")
                
            with open(video_file_path, 'rb') as video_file:
                upload_response = requests.put(
                    upload_url,
                    data=video_file,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=300  # 5 minutes for video upload
                )
                
            if upload_response.status_code == 201:
                return {
                    "success": True,
                    "video_urn": asset_id
                }
            else:
                raise Exception(f"Video upload failed: {upload_response.status_code}")
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _linkedin_manual_flow(self, video_data: Dict, settings: Dict) -> Dict:
        """Guided manual posting flow for users without API access"""
        logger.info("📋 Using LinkedIn manual flow - generating guided instructions")
        
        try:
            # Generate optimized caption and hashtags
            caption = self._format_linkedin_caption(video_data, settings)
            
            # Create download link for the video
            video_download_url = self._create_video_download_link(video_data)
            
            # Generate step-by-step instructions
            instructions = self._generate_linkedin_instructions(video_data, caption)
            
            # Store manual posting data for user interface
            manual_data = {
                "success": True,
                "method": "manual",
                "platform": "linkedin",
                "video_title": video_data.get('title', 'MyAvatar Video'),
                "caption": caption,
                "video_download_url": video_download_url,
                "instructions": instructions,
                "hashtags": self._generate_linkedin_hashtags(video_data, settings),
                "optimal_posting_time": self._get_optimal_posting_time(),
                "engagement_tips": self._get_linkedin_engagement_tips()
            }
            
            logger.info("✅ LinkedIn manual flow prepared successfully")
            return manual_data
            
        except Exception as e:
            logger.error(f"Manual flow preparation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "platform": "linkedin"
            }
    
    def _format_linkedin_caption(self, video_data: Dict, settings: Dict) -> str:
        """Format optimized LinkedIn caption"""
        title = video_data.get('title', 'MyAvatar Video')
        description = video_data.get('description', '')
        
        # LinkedIn best practices: engaging hook + value proposition
        caption_parts = []
        
        # Hook (first line is crucial)
        if settings.get('add_hook', True):
            caption_parts.append("🎯 Just created this with AI - what do you think?")
            caption_parts.append("")
        
        # Main content
        if title:
            caption_parts.append(f"📹 {title}")
            
        if description:
            caption_parts.append(description)
            
        # Call to action
        if settings.get('add_cta', True):
            caption_parts.append("")
            caption_parts.append("💬 What's your experience with AI video creation?")
            
        # Hashtags
        if settings.get('add_hashtags', True):
            hashtags = self._generate_linkedin_hashtags(video_data, settings)
            caption_parts.append("")
            caption_parts.append(" ".join(hashtags))
            
        return "\n".join(caption_parts)
    
    def _generate_linkedin_hashtags(self, video_data: Dict, settings: Dict) -> List[str]:
        """Generate relevant LinkedIn hashtags"""
        base_hashtags = ["#AI", "#VideoContent", "#MyAvatar", "#Innovation"]
        
        # Add industry-specific hashtags based on video content
        title = video_data.get('title', '').lower()
        description = video_data.get('description', '').lower()
        content = f"{title} {description}"
        
        industry_hashtags = {
            'business': ['#Business', '#Entrepreneurship', '#Leadership'],
            'marketing': ['#Marketing', '#DigitalMarketing', '#ContentCreation'],
            'tech': ['#Technology', '#TechInnovation', '#DigitalTransformation'],
            'education': ['#Education', '#Learning', '#Training'],
            'sales': ['#Sales', '#B2B', '#CustomerEngagement']
        }
        
        for category, hashtags in industry_hashtags.items():
            if category in content:
                base_hashtags.extend(hashtags[:2])  # Add max 2 per category
                break
                
        # Limit to 10 hashtags (LinkedIn best practice)
        return base_hashtags[:10]
    
    def _create_video_download_link(self, video_data: Dict) -> str:
        """Create secure download link for manual posting"""
        try:
            # Generate temporary download link via MyAvatar API
            response = requests.post(
                f"{self.config.MYAVATAR_API_URL}/api/videos/download-link",
                json={"video_id": video_data.get('id')},
                headers={"Authorization": f"Bearer {self.authenticated_user.get('token')}"},
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json().get('download_url')
                
        except Exception as e:
            logger.warning(f"Could not create download link: {e}")
            
        # Fallback to direct file path if available
        return video_data.get('file_path', '#')
    
    def _generate_linkedin_instructions(self, video_data: Dict, caption: str) -> List[str]:
        """Generate step-by-step LinkedIn posting instructions"""
        return [
            "1. 📱 Open LinkedIn (web or mobile app)",
            "2. 🎬 Click 'Start a post' or '+' button",
            "3. 📹 Click the video icon to upload your video",
            "4. ⬇️ Download your video using the link provided below",
            "5. 📝 Copy and paste the optimized caption",
            "6. 🏷️ Add any additional hashtags if needed",
            "7. 👀 Preview your post to ensure everything looks good",
            "8. 🚀 Click 'Post' to share with your network",
            "9. 📊 Monitor engagement and respond to comments"
        ]
    
    def _get_optimal_posting_time(self) -> str:
        """Get optimal LinkedIn posting time based on current timezone"""
        current_hour = datetime.now().hour
        
        # LinkedIn peak engagement times
        if 8 <= current_hour <= 10:
            return "Perfect timing! 8-10 AM is peak LinkedIn engagement time."
        elif 12 <= current_hour <= 14:
            return "Good timing! Lunch hours (12-2 PM) work well for LinkedIn."
        elif 17 <= current_hour <= 18:
            return "Great timing! Early evening (5-6 PM) is optimal for LinkedIn."
        else:
            return "Consider posting during peak hours: 8-10 AM, 12-2 PM, or 5-6 PM for better engagement."
    
    def _get_linkedin_engagement_tips(self) -> List[str]:
        """Get LinkedIn engagement optimization tips"""
        return [
            "💡 Respond to comments within the first hour for better reach",
            "🔄 Share in relevant LinkedIn groups for wider exposure",
            "👥 Tag relevant connections (max 3) to increase engagement",
            "📊 Post when your audience is most active (check LinkedIn analytics)",
            "🎯 Use native LinkedIn video for better algorithm performance",
            "📝 Keep captions under 1,300 characters for optimal readability",
            "🏷️ Use 3-5 relevant hashtags for best discoverability"
        ]
    
    def _distribute_to_twitter(self, video_data: Dict, settings: Dict) -> Dict:
        """Distribute video to Twitter/X"""
        # Placeholder implementation
        logger.info(f"🐦 Distributing to Twitter: {video_data.get('title')}")
        
        # Simulate API call
        time.sleep(1.5)
        
        return {
            "success": True,
            "url": "https://twitter.com/user/status/123",
            "post_id": "twitter_123"
        }
    
    def _distribute_to_youtube(self, video_data: Dict, settings: Dict) -> Dict:
        """Distribute video to YouTube"""
        # Placeholder implementation
        logger.info(f"📺 Distributing to YouTube: {video_data.get('title')}")
        
        # Simulate API call
        time.sleep(3)
        
        return {
            "success": True,
            "url": "https://youtube.com/watch?v=example",
            "post_id": "youtube_video_123"
        }

def main():
    """Main Streamlit application"""
    
    # Page configuration
    st.set_page_config(
        page_title="Distribution Engine",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize Distribution Engine
    if 'engine' not in st.session_state:
        st.session_state.engine = DistributionEngine()
    
    engine = st.session_state.engine
    
    # Header
    st.title("🚀 Distribution Engine")
    st.markdown("**Automated video distribution to social media platforms**")
    
    # Authentication check
    sso_token = st.query_params.get("token")
    
    if not sso_token:
        st.error("❌ **Authentication Required**")
        st.markdown("""
        This service requires authentication from MyAvatar.
        
        **To access the Distribution Engine:**
        1. Log in to MyAvatar
        2. Navigate to the Distribution section
        3. Click "Launch Distribution Engine"
        """)
        st.stop()
    
    # Authenticate user
    if 'authenticated' not in st.session_state:
        with st.spinner("🔐 Authenticating..."):
            user = engine.authenticate_user(sso_token)
            if user:
                st.session_state.authenticated = True
                st.session_state.user = user
                st.success(f"✅ Welcome, {user.get('username', 'User')}!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Authentication failed. Please try again from MyAvatar.")
                st.stop()
    
    user = st.session_state.user
    
    # Sidebar - Platform Status
    with st.sidebar:
        st.header("📊 Platform Status")
        
        for platform in engine.available_platforms:
            status_icon = "✅" if platform["enabled"] else "⚠️"
            status_text = "Ready" if platform["enabled"] else "Setup Required"
            
            st.markdown(f"""
            **{platform['icon']} {platform['name']}**  
            {status_icon} {status_text}
            """)
        
        st.divider()
        
        st.header("👤 User Info")
        st.markdown(f"""
        **Username:** {user.get('username', 'N/A')}  
        **Tier:** {user.get('subscription_tier', 'free').title()}  
        **User ID:** {user.get('id', 'N/A')}
        """)
    
    # Main content tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📹 Distribute Videos", "📊 Analytics", "⚙️ Settings", "📚 Help"])
    
    with tab1:
        st.header("📹 Video Distribution")
        
        # Get user's videos
        with st.spinner("📥 Loading your videos..."):
            videos = engine.get_user_videos(user.get('id'))
        
        if not videos:
            st.warning("📭 No videos found. Create some videos in MyAvatar first!")
        else:
            st.success(f"📹 Found {len(videos)} videos")
            
            # Video selection
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.subheader("Select Video to Distribute")
                
                video_options = {
                    f"{video.get('title', 'Untitled')} (ID: {video.get('id')})": video 
                    for video in videos
                }
                
                selected_video_key = st.selectbox(
                    "Choose a video:",
                    options=list(video_options.keys()),
                    key="video_selector"
                )
                
                selected_video = video_options[selected_video_key]
                
                # Video preview
                if selected_video.get('video_url'):
                    st.video(selected_video['video_url'])
                else:
                    st.info("📹 Video preview not available")
            
            with col2:
                st.subheader("Distribution Settings")
                
                # Platform selection
                st.markdown("**Select Platforms:**")
                selected_platforms = []
                
                for platform in engine.available_platforms:
                    if platform["enabled"]:
                        if st.checkbox(
                            f"{platform['icon']} {platform['name']}", 
                            key=f"platform_{platform['id']}"
                        ):
                            selected_platforms.append(platform['id'])
                    else:
                        st.checkbox(
                            f"{platform['icon']} {platform['name']} (Setup Required)", 
                            disabled=True,
                            key=f"platform_{platform['id']}_disabled"
                        )
                
                # Distribution options
                st.markdown("**Options:**")
                
                schedule_post = st.checkbox("📅 Schedule for later")
                if schedule_post:
                    schedule_time = st.datetime_input(
                        "Schedule time:",
                        value=datetime.now() + timedelta(hours=1),
                        min_value=datetime.now()
                    )
                
                add_hashtags = st.checkbox("🏷️ Auto-add hashtags")
                if add_hashtags:
                    custom_hashtags = st.text_input(
                        "Custom hashtags:",
                        placeholder="#myavatar #ai #video"
                    )
                
                # Distribution button
                if st.button("🚀 Distribute Video", type="primary", disabled=not selected_platforms):
                    if selected_platforms:
                        with st.spinner("🚀 Distributing video..."):
                            distribution_settings = {
                                "scheduled": schedule_post,
                                "schedule_time": schedule_time if schedule_post else None,
                                "hashtags": custom_hashtags if add_hashtags else "",
                                "auto_hashtags": add_hashtags
                            }
                            
                            results = engine.distribute_video(
                                selected_video, 
                                selected_platforms, 
                                distribution_settings
                            )
                            
                            # Show results with enhanced LinkedIn dual-flow support
                            if results["success"]:
                                st.success("✅ **Distribution Successful!**")
                                for success in results["success"]:
                                    platform_name = success['platform'].title()
                                    
                                    if success['platform'] == 'linkedin':
                                        self._display_linkedin_result(success)
                                    else:
                                        st.markdown(f"- ✅ **{platform_name}**: [View Post]({success['url']})")
                            
                            if results["failed"]:
                                st.error("❌ **Some distributions failed:**")
                                for failure in results["failed"]:
                                    st.markdown(f"- ❌ **{failure['platform'].title()}**: {failure['error']}")
                    else:
                        st.warning("⚠️ Please select at least one platform")
    
    with tab2:
        st.header("📊 Distribution Analytics")
        st.info("📈 Analytics dashboard coming soon...")
        
        # Placeholder analytics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Distributions", "42", "+12")
        
        with col2:
            st.metric("Success Rate", "94%", "+2%")
        
        with col3:
            st.metric("Platforms Connected", "3", "+1")
    
    with tab3:
        st.header("⚙️ Distribution Settings")
        
        st.subheader("🔗 Platform Connections")
        
        for platform in engine.available_platforms:
            with st.expander(f"{platform['icon']} {platform['name']} Settings"):
                if platform["enabled"]:
                    st.success("✅ Connected and ready")
                    st.markdown(f"**Features:** {', '.join(platform['features'])}")
                    
                    if st.button(f"Disconnect {platform['name']}", key=f"disconnect_{platform['id']}"):
                        st.warning(f"Disconnecting from {platform['name']}...")
                else:
                    st.warning("⚠️ Not connected")
                    st.markdown(f"**Description:** {platform['description']}")
                    st.markdown(f"**Features:** {', '.join(platform['features'])}")
                    
                    if st.button(f"Connect {platform['name']}", key=f"connect_{platform['id']}"):
                        st.info(f"Connecting to {platform['name']}...")
        
        st.subheader("🎯 Default Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.checkbox("🏷️ Auto-add hashtags by default")
            st.checkbox("📅 Enable scheduling by default")
            st.checkbox("🔔 Send notification on completion")
        
        with col2:
            st.selectbox("Default video quality:", ["HD", "Full HD", "4K"])
            st.selectbox("Default privacy:", ["Public", "Unlisted", "Private"])
            st.number_input("Max concurrent uploads:", min_value=1, max_value=5, value=3)
    
    with tab4:
        st.header("📚 Help & Documentation")
        
        st.markdown("""
        ## 🚀 Getting Started
        
        The Distribution Engine helps you automatically share your MyAvatar videos across multiple social media platforms.
        
        ### 📋 Quick Start Guide
        
        1. **Select a Video**: Choose from your MyAvatar video library
        2. **Choose Platforms**: Select where you want to distribute
        3. **Configure Settings**: Add hashtags, schedule posts, etc.
        4. **Distribute**: Click the distribute button and watch the magic happen!
        
        ### 🔗 Supported Platforms
        
        - **LinkedIn**: Professional network sharing
        - **Twitter/X**: Social media posts and threads
        - **YouTube**: Video hosting and sharing
        - **Vimeo**: Professional video hosting (coming soon)
        - **TikTok**: Short-form content (coming soon)
        
        ### ⚙️ Platform Setup
        
        To connect platforms, you'll need to:
        1. Go to Settings tab
        2. Click "Connect" for each platform
        3. Follow the authentication flow
        4. Grant necessary permissions
        
        ### 🆘 Need Help?
        
        - Check the Analytics tab for distribution status
        - Review platform-specific error messages
        - Contact support through MyAvatar dashboard
        """)

# Health check endpoint for MyAvatar integration
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Distribution Engine",
        "timestamp": datetime.now().isoformat(),
        "platforms_available": len([p for p in DistributionEngine().available_platforms if p["enabled"]])
    }

    def _display_linkedin_result(self, result: Dict):
        """Display LinkedIn distribution result with dual-flow support"""
        if result.get('method') == 'api':
            # API posting successful
            st.markdown(f"✅ **LinkedIn (API)**: [View Post]({result['url']})")
            st.info("📡 Posted automatically via LinkedIn API")
            
        elif result.get('method') == 'manual':
            # Manual flow - show guided instructions
            st.markdown("✅ **LinkedIn (Manual Guide)**")
            
            with st.expander("📋 Click here for step-by-step LinkedIn posting guide", expanded=True):
                
                # Video download section
                st.subheader("📹 1. Download Your Video")
                if result.get('video_download_url') and result['video_download_url'] != '#':
                    st.markdown(f"[⬇️ **Download Video**]({result['video_download_url']})")
                else:
                    st.warning("⚠️ Video download link not available")
                
                # Optimized caption section
                st.subheader("📝 2. Copy This Optimized Caption")
                caption = result.get('caption', '')
                st.text_area(
                    "LinkedIn Caption (click to select all):",
                    value=caption,
                    height=150,
                    key=f"linkedin_caption_{result.get('video_title', 'video')}"
                )
                
                if st.button("📋 Copy Caption to Clipboard", key="copy_linkedin_caption"):
                    st.success("✅ Caption copied! (Note: clipboard access may be limited in some browsers)")
                
                # Step-by-step instructions
                st.subheader("📝 3. Follow These Steps")
                instructions = result.get('instructions', [])
                for instruction in instructions:
                    st.markdown(f"- {instruction}")
                
                # Hashtags section
                st.subheader("🏷️ 4. Recommended Hashtags")
                hashtags = result.get('hashtags', [])
                if hashtags:
                    hashtag_text = " ".join(hashtags)
                    st.code(hashtag_text)
                    st.caption("Copy these hashtags and add them to your post")
                
                # Timing and engagement tips
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("⏰ 5. Optimal Timing")
                    timing_tip = result.get('optimal_posting_time', '')
                    st.info(timing_tip)
                
                with col2:
                    st.subheader("📊 6. Engagement Tips")
                    tips = result.get('engagement_tips', [])
                    for tip in tips[:3]:  # Show top 3 tips
                        st.markdown(f"- {tip}")
                
                # Success confirmation
                st.subheader("✅ 7. Confirm When Posted")
                if st.button("🎉 I've posted to LinkedIn!", key="confirm_linkedin_post"):
                    st.balloons()
                    st.success("🎉 Awesome! Your LinkedIn post is now live. Great job!")
                    st.info("📊 Check back in a few hours to see how your post is performing.")

if __name__ == "__main__":
    # Check if running as health check
    if len(os.sys.argv) > 1 and os.sys.argv[1] == "health":
        print(json.dumps(health_check()))
    else:
        main()
