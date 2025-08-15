"""
Enhanced HeyGen API integration with robust error handling and status tracking
app/api/heygen_enhanced.py
"""

import requests
import json
import time
import logging
from typing import Dict, Optional, Tuple
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class HeyGenAPIError(Exception):
    """Custom exception for HeyGen API errors"""
    def __init__(self, message: str, status_code: int = None, response_data: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data

class HeyGenAPI:
    def __init__(self):
        self.api_key = os.getenv('HEYGEN_API_KEY')
        self.base_url = os.getenv('HEYGEN_BASE_URL', 'https://api.heygen.com')
        self.timeout = int(os.getenv('HEYGEN_TIMEOUT', '30'))
        
        if not self.api_key:
            raise ValueError("HEYGEN_API_KEY not configured")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get standard headers for HeyGen API requests"""
        return {
            'X-API-Key': self.api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def _make_request(self, method: str, endpoint: str, data: dict = None, params: dict = None) -> dict:
        """
        Make a request to HeyGen API with proper error handling
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self._get_headers()
        
        try:
            logger.info(f"Making {method} request to {url}")
            
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=data if data else None,
                params=params,
                timeout=self.timeout
            )
            
            # Log response for debugging
            logger.info(f"HeyGen API response: {response.status_code}")
            
            # Parse response
            try:
                response_data = response.json()
            except json.JSONDecodeError:
                response_data = {'raw_response': response.text}
            
            # Check for errors
            if not response.ok:
                error_msg = f"HeyGen API error: {response.status_code}"
                if 'message' in response_data:
                    error_msg += f" - {response_data['message']}"
                elif 'error' in response_data:
                    error_msg += f" - {response_data['error']}"
                
                logger.error(f"{error_msg}. Response: {response_data}")
                raise HeyGenAPIError(error_msg, response.status_code, response_data)
            
            return response_data
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout making request to {url}")
            raise HeyGenAPIError("Request timeout", 504)
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error making request to {url}")
            raise HeyGenAPIError("Connection error", 503)
        except requests.exceptions.RequestException as e:
            logger.error(f"Request exception: {str(e)}")
            raise HeyGenAPIError(f"Request failed: {str(e)}")
    
    def create_video(self, avatar_id: str, voice_id: str, script: str, **kwargs) -> Tuple[str, dict]:
        """
        Create a video using HeyGen API
        
        Returns:
            Tuple[str, dict]: (video_id, full_response)
        """
        # Prepare video creation payload
        payload = {
            "video_inputs": [{
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id,
                    "avatar_style": kwargs.get('avatar_style', 'normal')
                },
                "voice": {
                    "type": "text",
                    "input_text": script,
                    "voice_id": voice_id,
                    "speed": kwargs.get('speed', 1.0),
                    "emotion": kwargs.get('emotion', 'friendly')
                }
            }],
            "dimension": {
                "width": kwargs.get('width', 1080),
                "height": kwargs.get('height', 1920)
            },
            "aspect_ratio": kwargs.get('aspect_ratio', '9:16'),
            "test": kwargs.get('test', False),
            "caption": kwargs.get('caption', False)
        }
        
        # Add callback_id if webhook is configured
        webhook_url = os.getenv('HEYGEN_WEBHOOK_URL')
        if webhook_url:
            callback_id = f"myavatar_{int(time.time())}_{kwargs.get('user_id', 'unknown')}"
            payload["callback_id"] = callback_id
            logger.info(f"Added callback_id: {callback_id}")
        
        try:
            response = self._make_request('POST', '/v2/video/generate', data=payload)
            
            # Extract video ID
            video_id = response.get('data', {}).get('video_id')
            if not video_id:
                raise HeyGenAPIError("No video_id in response", response_data=response)
            
            logger.info(f"Video created successfully: {video_id}")
            return video_id, response
            
        except HeyGenAPIError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating video: {str(e)}")
            raise HeyGenAPIError(f"Video creation failed: {str(e)}")
    
    def get_video_status(self, video_id: str) -> dict:
        """
        Get video status from HeyGen API
        
        Returns:
            dict: Status information including status, video_url, etc.
        """
        try:
            response = self._make_request('GET', f'/v1/video_status.get', params={'video_id': video_id})
            
            data = response.get('data', {})
            if not data:
                raise HeyGenAPIError("No data in status response", response_data=response)
            
            # Normalize status response
            status_info = {
                'video_id': video_id,
                'status': data.get('status', 'unknown'),
                'video_url': data.get('video_url'),
                'thumbnail_url': data.get('thumbnail_url'),
                'duration': data.get('duration'),
                'created_at': data.get('created_at'),
                'completed_at': data.get('completed_at'),
                'error': data.get('error'),
                'callback_id': data.get('callback_id'),
                'raw_response': data
            }
            
            logger.info(f"Video {video_id} status: {status_info['status']}")
            return status_info
            
        except HeyGenAPIError:
            raise
        except Exception as e:
            logger.error(f"Error getting video status: {str(e)}")
            raise HeyGenAPIError(f"Status check failed: {str(e)}")
    
    def list_avatars(self) -> list:
        """Get list of available avatars"""
        try:
            response = self._make_request('GET', '/v1/avatar.list')
            return response.get('data', {}).get('avatars', [])
        except Exception as e:
            logger.error(f"Error listing avatars: {str(e)}")
            raise HeyGenAPIError(f"Failed to list avatars: {str(e)}")
    
    def list_voices(self) -> list:
        """Get list of available voices"""
        try:
            response = self._make_request('GET', '/v1/voice.list')
            return response.get('data', {}).get('voices', [])
        except Exception as e:
            logger.error(f"Error listing voices: {str(e)}")
            raise HeyGenAPIError(f"Failed to list voices: {str(e)}")
    
    def get_voice_parameters(self, avatar_id: str, user_voice_id: str = None) -> dict:
        """
        Get voice parameters for an avatar, with fallback logic
        """
        try:
            # If user has a personal voice, use it
            if user_voice_id:
                # Verify the voice exists
                voices = self.list_voices()
                user_voice = next((v for v in voices if v.get('voice_id') == user_voice_id), None)
                if user_voice:
                    return {
                        'voice_id': user_voice_id,
                        'voice_name': user_voice.get('name', 'Personal Voice'),
                        'voice_type': 'personal',
                        'language': user_voice.get('language', 'en'),
                        'gender': user_voice.get('gender', 'neutral')
                    }
            
            # Fallback: Get avatar's default voice
            avatars = self.list_avatars()
            avatar = next((a for a in avatars if a.get('avatar_id') == avatar_id), None)
            
            if avatar and avatar.get('voice_id'):
                return {
                    'voice_id': avatar['voice_id'],
                    'voice_name': avatar.get('voice_name', 'Default Voice'),
                    'voice_type': 'default',
                    'language': avatar.get('language', 'en'),
                    'gender': avatar.get('gender', 'neutral')
                }
            
            # Final fallback: Use system default
            default_voice_id = os.getenv('DEFAULT_VOICE_ID', '1bd001e7e50f421d891986aad5158bc8')
            return {
                'voice_id': default_voice_id,
                'voice_name': 'System Default',
                'voice_type': 'system',
                'language': 'en',
                'gender': 'neutral'
            }
            
        except Exception as e:
            logger.error(f"Error getting voice parameters: {str(e)}")
            # Return safe defaults
            return {
                'voice_id': os.getenv('DEFAULT_VOICE_ID', '1bd001e7e50f421d891986aad5158bc8'),
                'voice_name': 'Default Voice',
                'voice_type': 'default',
                'language': 'en',
                'gender': 'neutral'
            }
    
    def validate_connection(self) -> bool:
        """Validate API connection and credentials"""
        try:
            self.list_avatars()
            return True
        except Exception as e:
            logger.error(f"HeyGen connection validation failed: {str(e)}")
            return False

# Singleton instance
heygen_api = HeyGenAPI()
