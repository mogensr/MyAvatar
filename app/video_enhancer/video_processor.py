"""
Video processor for background replacement in MyAvatar
Manages loading, processing, and saving videos with audio preservation
"""
import cv2
import os
import numpy as np
import logging
import tempfile
import subprocess
import shutil
from typing import List, Tuple, Optional

# Configure logging
logger = logging.getLogger(__name__)

class VideoProcessor:
    """
    Video processor for MyAvatar that handles loading, processing and saving videos
    while preserving audio from the original
    """
    
    def __init__(self, config=None):
        """Initialize the video processor with optional configuration."""
        self.config = config or {}
        self.temp_dir = self.config.get('temp_dir', os.path.join('temp', 'video_processing'))
        
        # Create temp directory if it doesn't exist
        os.makedirs(self.temp_dir, exist_ok=True)
        
        logger.info(f"VideoProcessor initialized with temp directory: {self.temp_dir}")
    
    def load_video(self, path: str) -> Tuple[cv2.VideoCapture, int, int, float, int]:
        """
        Load a video file and return capture object with properties.
        
        Args:
            path: Path to the video file
            
        Returns:
            Tuple of (capture, width, height, fps, frame_count)
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Video file not found: {path}")
        
        capture = cv2.VideoCapture(path)
        if not capture.isOpened():
            raise ValueError(f"Could not open video file: {path}")
        
        # Get video properties
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = capture.get(cv2.CAP_PROP_FPS)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        
        logger.info(f"Loaded video: {path}, Resolution: {width}x{height}, FPS: {fps}, Frames: {frame_count}")
        
        return capture, width, height, fps, frame_count
    
    def save_video(self, frames: List[np.ndarray], output_path: str, 
                  width: int, height: int, fps: float, 
                  input_video_path: Optional[str] = None) -> str:
        """
        Save processed frames as a video file with audio from original video.
        
        Args:
            frames: List of processed frames
            output_path: Path to save the video
            width: Frame width
            height: Frame height
            fps: Frames per second
            input_video_path: Path to original video for audio extraction
            
        Returns:
            Path to the saved video file
        """
        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # First save without audio using OpenCV
        temp_output = tempfile.mktemp(suffix='.mp4')
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_output, fourcc, fps, (width, height))
        
        # Write frames to the video file
        for frame in frames:
            out.write(frame)
        
        # Release the VideoWriter
        out.release()
        
        # If input video is provided, try to copy the audio
        if input_video_path and os.path.exists(input_video_path):
            try:
                # Use FFmpeg to copy audio from original to the new video
                cmd = [
                    'ffmpeg',
                    '-i', temp_output,
                    '-i', input_video_path,
                    '-c:v', 'copy',
                    '-c:a', 'aac',
                    '-map', '0:v:0',
                    '-map', '1:a:0?',
                    '-shortest',
                    output_path,
                    '-y'  # Overwrite output if exists
                ]
                
                logger.info(f"Running FFmpeg to add audio: {' '.join(cmd)}")
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                logger.info(f"Video saved with original audio to: {output_path}")
                
                # Remove temporary file
                os.remove(temp_output)
                return output_path
                
            except Exception as e:
                logger.error(f"Failed to copy audio: {e}")
                logger.info(f"Falling back to video without audio")
                
                # If FFmpeg fails, just rename the temp file
                shutil.move(temp_output, output_path)
                return output_path
        else:
            # If no input video provided, just rename the temp file
            shutil.move(temp_output, output_path)
            logger.info(f"Video saved without audio to: {output_path}")
            return output_path
    
    def process_video(self, input_path: str, output_path: str, processor_func=None):
        """
        Process an entire video using the provided processor function.
        
        Args:
            input_path: Path to input video
            output_path: Path to save the output video
            processor_func: Function that takes a frame and returns processed frame
        """
        # Load video
        capture, width, height, fps, frame_count = self.load_video(input_path)
        
        # Process frames
        processed_frames = []
        frame_idx = 0
        
        while capture.isOpened():
            ret, frame = capture.read()
            if not ret:
                break
            
            # Process this frame
            if processor_func:
                processed_frame = processor_func(frame)
            else:
                processed_frame = frame
                
            processed_frames.append(processed_frame)
            
            # Log progress
            frame_idx += 1
            if frame_idx % 10 == 0 or frame_idx == frame_count:
                logger.info(f"Processed {frame_idx}/{frame_count} frames ({frame_idx/frame_count*100:.1f}%)")
        
        # Release the video capture
        capture.release()
        
        # Save the processed video with audio from the original
        return self.save_video(processed_frames, output_path, width, height, fps, input_video_path=input_path)
