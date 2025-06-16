"""
Video Enhancement Module for MyAvatar

This module provides background replacement and other video enhancement
capabilities for videos created with the HeyGen API.
"""

from .background_replacer import BackgroundReplacer
from .video_processor import VideoProcessor

__all__ = ['BackgroundReplacer', 'VideoProcessor']
