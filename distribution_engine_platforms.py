#!/usr/bin/env python3
"""
Social Media Platform Configuration for DistributionEngine
Modular platform definitions with OAuth and API configurations
"""

# Phase 1 Platforms - The Essential 5
PHASE_1_PLATFORMS = {
    "youtube": {
        "name": "YouTube",
        "icon": "📺",
        "type": "video_hosting",
        "description": "World's largest video platform",
        "oauth_required": True,
        "video_formats": ["mp4", "mov", "avi"],
        "max_duration": 43200,  # 12 hours in seconds
        "api_endpoint": "https://www.googleapis.com/youtube/v3/",
        "oauth_scope": ["https://www.googleapis.com/auth/youtube.upload"],
        "priority": 1
    },
    
    "linkedin": {
        "name": "LinkedIn", 
        "icon": "💼",
        "type": "professional",
        "description": "Professional networking platform",
        "oauth_required": True,
        "video_formats": ["mp4", "mov"],
        "max_duration": 600,  # 10 minutes
        "api_endpoint": "https://api.linkedin.com/v2/",
        "oauth_scope": ["w_member_social"],
        "priority": 2
    },
    
    "twitter": {
        "name": "Twitter/X",
        "icon": "🐦", 
        "type": "microblogging",
        "description": "Microblogging and real-time updates",
        "oauth_required": True,
        "video_formats": ["mp4", "mov"],
        "max_duration": 140,  # 2 minutes 20 seconds
        "api_endpoint": "https://api.twitter.com/2/",
        "oauth_scope": ["tweet.write", "users.read"],
        "priority": 3
    },
    
    "substack": {
        "name": "Substack",
        "icon": "✍️",
        "type": "newsletter", 
        "description": "Newsletter platform with video support",
        "oauth_required": True,
        "video_formats": ["mp4", "mov"],
        "max_duration": 3600,  # 1 hour
        "api_endpoint": "https://substack.com/api/v1/",
        "oauth_scope": ["write"],
        "priority": 4
    },
    
    "facebook": {
        "name": "Facebook",
        "icon": "😤",  # User's sentiment included!
        "type": "social_network",
        "description": "(Suk) But still necessary...",
        "oauth_required": True,
        "video_formats": ["mp4", "mov"],
        "max_duration": 7200,  # 2 hours
        "api_endpoint": "https://graph.facebook.com/",
        "oauth_scope": ["pages_manage_posts", "pages_read_engagement"],
        "priority": 5
    }
}

# Future Phase 2 Platforms
PHASE_2_PLATFORMS = {
    "tiktok": {
        "name": "TikTok",
        "icon": "🎵",
        "type": "short_video",
        "description": "Short-form vertical video platform",
        "oauth_required": True,
        "video_formats": ["mp4"],
        "max_duration": 180,  # 3 minutes
        "aspect_ratio": "9:16",  # Vertical
        "priority": 6
    },
    
    "instagram": {
        "name": "Instagram",
        "icon": "📸",
        "type": "visual_social",
        "description": "Photo and video sharing",
        "oauth_required": True,
        "video_formats": ["mp4", "mov"],
        "max_duration": 3600,  # 1 hour for IGTV
        "priority": 7
    },
    
    "vimeo": {
        "name": "Vimeo",
        "icon": "🎬",
        "type": "professional_video",
        "description": "Professional video hosting",
        "oauth_required": True,
        "video_formats": ["mp4", "mov", "avi"],
        "max_duration": 43200,  # 12 hours
        "priority": 8
    }
}

# Combine all platforms
ALL_PLATFORMS = {**PHASE_1_PLATFORMS, **PHASE_2_PLATFORMS}

def get_active_platforms():
    """Get currently active platforms (Phase 1)"""
    return PHASE_1_PLATFORMS

def get_platform_config(platform_id):
    """Get configuration for specific platform"""
    return ALL_PLATFORMS.get(platform_id)

def get_platforms_by_type(platform_type):
    """Get platforms filtered by type"""
    return {k: v for k, v in ALL_PLATFORMS.items() if v["type"] == platform_type}

def validate_video_for_platform(platform_id, video_duration, video_format):
    """Validate if video meets platform requirements"""
    config = get_platform_config(platform_id)
    if not config:
        return False, "Platform not found"
    
    if video_duration > config["max_duration"]:
        return False, f"Video too long. Max: {config['max_duration']}s"
    
    if video_format.lower() not in [fmt.lower() for fmt in config["video_formats"]]:
        return False, f"Format not supported. Allowed: {config['video_formats']}"
    
    return True, "Video compatible"

# OAuth Configuration Templates
OAUTH_CONFIGS = {
    "youtube": {
        "auth_url": "https://accounts.google.com/o/oauth2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "redirect_uri": "https://app.myavatar.dk/auth/youtube/callback"
    },
    
    "linkedin": {
        "auth_url": "https://www.linkedin.com/oauth/v2/authorization", 
        "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
        "redirect_uri": "https://app.myavatar.dk/auth/linkedin/callback"
    },
    
    "twitter": {
        "auth_url": "https://twitter.com/i/oauth2/authorize",
        "token_url": "https://api.twitter.com/2/oauth2/token", 
        "redirect_uri": "https://app.myavatar.dk/auth/twitter/callback"
    },
    
    "substack": {
        "auth_url": "https://substack.com/oauth/authorize",
        "token_url": "https://substack.com/api/v1/oauth/token",
        "redirect_uri": "https://app.myavatar.dk/auth/substack/callback"
    },
    
    "facebook": {
        "auth_url": "https://www.facebook.com/v18.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v18.0/oauth/access_token",
        "redirect_uri": "https://app.myavatar.dk/auth/facebook/callback"
    }
}

if __name__ == "__main__":
    # Test the platform configurations
    print("🚀 DistributionEngine Platform Map")
    print("=" * 50)
    
    print("\n📊 Phase 1 Platforms:")
    for platform_id, config in PHASE_1_PLATFORMS.items():
        print(f"  {config['icon']} {config['name']} - {config['description']}")
    
    print(f"\n✅ Total Phase 1 Platforms: {len(PHASE_1_PLATFORMS)}")
    print(f"🔮 Total Future Platforms: {len(PHASE_2_PLATFORMS)}")
