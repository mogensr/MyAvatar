import os
import sys
from typing import Dict, Any, Optional
import requests

# Extract just the HeyGenAPI class for testing purposes
class HeyGenAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.heygen.com/v2"
        self.headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json"
        }
    
    def generate_video_with_audio_url(self, avatar_id: str, audio_url: str, voice_id: Optional[str] = None, video_format: str = "16:9") -> Dict[str, Any]:
        """
        Generate a video using an audio URL with the specified video format
        """
        try:
            print(f"📤 Sending video generation request to HeyGen...")
            print(f"🎯 Avatar ID: {avatar_id}")
            print(f"🎵 Audio URL: {audio_url}")
            print(f"🎞️ Video Format: {video_format}")
            
            # Set dimensions and aspect ratio based on video format
            dimensions = {
                "width": 1280,
                "height": 720
            }
            aspect_ratio = "16:9"
            
            if video_format == "9:16":
                dimensions = {
                    "width": 720,
                    "height": 1280
                }
                aspect_ratio = "9:16"
            elif video_format == "1:1":
                dimensions = {
                    "width": 720,
                    "height": 720
                }
                aspect_ratio = "1:1"
            
            # Print the dimensions and aspect ratio for debugging
            print(f"📏 Dimensions: {dimensions}")
            print(f"📐 Aspect Ratio: {aspect_ratio}")
            
            # Payload structure for video generation
            payload = {
                "video_inputs": [
                    {
                        "character": {
                            "type": "avatar",
                            "avatar_id": avatar_id
                        },
                        "voice": {
                            "type": "audio",
                            "audio_url": audio_url
                        }
                    }
                ],
                "dimension": dimensions,
                "aspect_ratio": aspect_ratio
            }
            
            # Add voice_id if provided
            if voice_id:
                payload["video_inputs"][0]["voice"] = {
                    "type": "voice",
                    "voice_id": voice_id
                }
            
            # Mock success response for testing
            mock_response = {
                "success": True,
                "task_id": "mock-task-12345",
                "request": payload,
                "message": "Video generation request submitted successfully (MOCK)",
                "status": "pending",
                "format": video_format,
                "dimensions": f"{dimensions['width']}x{dimensions['height']}",
                "aspect_ratio": aspect_ratio
            }
            
            # Return mock success response for testing
            return mock_response
            
            # The real API call would be:
            # url = f"{self.base_url}/videos"
            # response = requests.post(url, headers=self.headers, json=payload)
            # return response.json()
            
        except Exception as e:
            print(f"❌ Error generating video: {str(e)}")
            return {"success": False, "error": str(e)}

def test_formats():
    # Set API key (use a mock one for testing)
    api_key = os.environ.get('HEYGEN_API_KEY', 'test-api-key-12345')
    
    # Create HeyGenAPI instance
    heygen = HeyGenAPI(api_key)
    
    # Test URL for audio
    test_audio_url = "https://example.com/test-audio.mp3"
    
    # Test avatar ID
    test_avatar_id = "test-avatar-12345"
    
    # Test all three formats
    formats = ["16:9", "9:16", "1:1"]
    
    for format in formats:
        print(f"\n{'='*50}")
        print(f"Testing {format} format")
        print(f"{'='*50}")
        
        result = heygen.generate_video_with_audio_url(
            avatar_id=test_avatar_id,
            audio_url=test_audio_url,
            video_format=format
        )
        
        print(f"\nResult:")
        for key, value in result.items():
            print(f"{key}: {value}")

if __name__ == "__main__":
    test_formats()
