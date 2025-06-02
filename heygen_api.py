"""
HeyGen API Integration - Fixed Content-Type problem
Handles video generation using HeyGen's v2 API endpoints
"""

import requests
import json
import time
from typing import Dict, Any, Optional

class HeyGenAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.heygen.com"
        self.upload_url = "https://upload.heygen.com"  # KORREKT UPLOAD URL
        self.headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }
    
    def test_connection(self) -> Dict[str, Any]:
        """Test the API connection and get user quota"""
        try:
            response = requests.get(
                f"{self.base_url}/v2/user/remaining_quota",
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "quota": data.get("data", {}),
                    "message": "API connection successful"
                }
            else:
                return {
                    "success": False,
                    "error": f"API test failed: {response.status_code}",
                    "response": response.text
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Connection error: {str(e)}"
            }
    
    def generate_video_with_audio_url(self, avatar_id: str, audio_url: str, voice_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate video using audio URL (works with ngrok URLs)
        """
        try:
            print(f"📤 Sending video generation request to HeyGen...")
            print(f"🎯 Avatar ID: {avatar_id}")
            print(f"🎵 Audio URL: {audio_url}")
            
            # Payload for HeyGen v2 API
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
                "dimension": {
                    "width": 1280,
                    "height": 720
                },
                "aspect_ratio": "16:9"
            }
            
            # Add voice_id if provided
            if voice_id:
                payload["video_inputs"][0]["voice"]["voice_id"] = voice_id
            
            print(f"📋 Payload: {json.dumps(payload, indent=2)}")
            
            response = requests.post(
                f"{self.base_url}/v2/video/generate",
                headers=self.headers,
                json=payload,
                timeout=120  # 2 minute timeout
            )
            
            print(f"📡 HeyGen Response Status: {response.status_code}")
            print(f"📄 HeyGen Response: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                video_id = data.get("data", {}).get("video_id")
                
                if video_id:
                    return {
                        "success": True,
                        "video_id": video_id,
                        "message": "Video generation started successfully",
                        "full_response": data
                    }
                else:
                    return {
                        "success": False,
                        "error": "No video_id in response",
                        "response": data
                    }
            else:
                return {
                    "success": False,
                    "error": f"HeyGen API error: {response.status_code}",
                    "response": response.text
                }
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Request timeout - HeyGen took too long to respond"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Request failed: {str(e)}"
            }
    
    def generate_video_with_audio_file(self, avatar_id: str, audio_file_path: str, voice_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate video by uploading audio file directly
        Uses correct upload.heygen.com endpoint - FIXED CONTENT-TYPE
        """
        try:
            print(f"📁 Uploading audio file: {audio_file_path}")
            print(f"🌐 Upload URL: {self.upload_url}/v1/asset")
            
            # First upload the audio file
            with open(audio_file_path, 'rb') as f:
                files = {
                    'file': ('audio.mp3', f, 'audio/mpeg')
                }
                
                # FIXED: Lad requests sætte Content-Type automatisk
                headers = {
                    "X-API-KEY": self.api_key
                    # Fjernet Content-Type - requests sætter den automatisk med files
                }
                
                upload_response = requests.post(
                    f"{self.upload_url}/v1/asset",  # KORREKT UPLOAD URL
                    headers=headers,
                    files=files
                )
                
                print(f"📡 Upload Response Status: {upload_response.status_code}")
                print(f"📄 Upload Response: {upload_response.text}")
                
                if upload_response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Audio upload failed: {upload_response.status_code}",
                        "response": upload_response.text
                    }
                
                upload_data = upload_response.json()
                asset_url = upload_data.get("data", {}).get("url")
                
                if not asset_url:
                    return {
                        "success": False,
                        "error": "No asset URL returned from upload",
                        "response": upload_data
                    }
                
                print(f"✅ Audio uploaded successfully: {asset_url}")
                
                # Now generate video with uploaded asset URL
                return self.generate_video_with_audio_url(avatar_id, asset_url, voice_id)
                
        except Exception as e:
            return {
                "success": False,
                "error": f"File upload failed: {str(e)}"
            }
    
    def get_video_status(self, video_id: str) -> Dict[str, Any]:
        """Check the status of a video generation"""
        try:
            response = requests.get(
                f"{self.base_url}/v1/video_status.get?video_id={video_id}",
                headers={"X-API-KEY": self.api_key, "Accept": "application/json"}
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json()
                }
            else:
                return {
                    "success": False,
                    "error": f"Status check failed: {response.status_code}",
                    "response": response.text
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Status check error: {str(e)}"
            }


def create_video_from_audio_file(api_key: str, avatar_id: str, audio_file_path: str, audio_url: Optional[str] = None, voice_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Main function to create video from audio
    Supports both URL (preferred for ngrok) and file upload methods
    """
    print("🎬 Starting SMART video creation workflow...")
    print(f"🎯 Avatar ID: {avatar_id}")
    print(f"📁 Audio file: {audio_file_path}")
    
    heygen = HeyGenAPI(api_key)
    
    # Test connection first
    connection_test = heygen.test_connection()
    if not connection_test["success"]:
        return {
            "success": False,
            "error": f"API connection failed: {connection_test['error']}"
        }
    
    print("✅ HeyGen API connection successful")
    
    # If audio_url is provided (ngrok), use URL method
    if audio_url:
        print(f"🌐 Using audio URL method: {audio_url}")
        result = heygen.generate_video_with_audio_url(avatar_id, audio_url, voice_id)
        
        # If URL method fails, fallback to file upload
        if not result["success"]:
            print("⚠️ URL method failed, trying file upload...")
            result = heygen.generate_video_with_audio_file(avatar_id, audio_file_path, voice_id)
    else:
        # Use file upload method
        print("📁 Using file upload method")
        result = heygen.generate_video_with_audio_file(avatar_id, audio_file_path, voice_id)
    
    return result


def check_video_status(api_key: str, video_id: str) -> Dict[str, Any]:
    """
    Check the status of a video generation
    """
    heygen = HeyGenAPI(api_key)
    return heygen.get_video_status(video_id)


# Example usage
if __name__ == "__main__":
    # Test the API
    API_KEY = "your_api_key_here"
    AVATAR_ID = "b5038ba7bd9b4d94ac6b5c9ea70f8d28"
    
    # Test connection
    heygen = HeyGenAPI(API_KEY)
    test_result = heygen.test_connection()
    print(f"Connection test: {test_result}")
    
    # Example video generation with URL
    audio_url = "https://your-ngrok-url.ngrok.io/static/uploads/audio/example.mp3"
    result = create_video_from_audio_file(
        api_key=API_KEY,
        avatar_id=AVATAR_ID,
        audio_file_path="path/to/local/audio.mp3",
        audio_url=audio_url
    )
    print(f"Video generation result: {result}")
