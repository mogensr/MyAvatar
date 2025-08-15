import os
import requests
import time
import json
import shutil
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

class ProcessingStatus(Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class ProcessingJob:
    job_id: str
    status: ProcessingStatus
    input_file: str
    output_file: Optional[str] = None
    progress: float = 0.0
    error_message: Optional[str] = None
    created_at: float = None
    completed_at: Optional[float] = None

class HuggingFaceVideoProcessor:
    def __init__(self, hf_space_url: str, hf_token: Optional[str] = None):
        """
        Initialize HF Space integration for SAM2 + MatAnyone pipeline via Gradio
        
        Args:
            hf_space_url: Your HF Space URL (e.g., "https://MogensR-VideoBackgroundReplacer.hf.space")
            hf_token: HuggingFace API token (optional but recommended)
        """
        self.hf_space_url = hf_space_url.rstrip('/')
        self.hf_token = hf_token
        self._gradio_results = {}  # Store results from Gradio processing
        self._gradio_client = None
    
    def _get_gradio_client(self):
        """Get or create Gradio client"""
        if self._gradio_client is None:
            try:
                from gradio_client import Client  # gradio-client 0.6.1 uses underscore
                print(f"🔍 GRADIO DEBUG: Connecting to {self.hf_space_url}")
                
                # Initialize Gradio client
                if self.hf_token:
                    self._gradio_client = Client(self.hf_space_url, hf_token=self.hf_token)
                else:
                    self._gradio_client = Client(self.hf_space_url)
                    
                print(f"✅ Gradio client connected successfully")
                
            except Exception as e:
                print(f"❌ Failed to create Gradio client: {str(e)}")
                raise
                
        return self._gradio_client
    
    def submit_video_processing(self, video_file_path: str, background_image_path: str) -> str:
        """
        Submit video for SAM2 + MatAnyone processing via Gradio
        
        Args:
            video_file_path: Path to input video file
            background_image_path: Path to new background image
            
        Returns:
            job_id: Unique identifier for tracking the job
        """
        try:
            print(f"🔍 GRADIO DEBUG: Processing video: {video_file_path}")
            print(f"🔍 GRADIO DEBUG: Background image: {background_image_path}")
            
            # Verify files exist
            if not os.path.exists(video_file_path):
                raise Exception(f"Video file not found: {video_file_path}")
            if not os.path.exists(background_image_path):
                raise Exception(f"Background image not found: {background_image_path}")
            
            # Get Gradio client
            client = self._get_gradio_client()
            
            print(f"🔍 GRADIO DEBUG: Submitting to Gradio interface...")
            
            # Submit to your Gradio app's process_video_sam2_matanyone function
            # The function signature from your app.py: (input_video, background_image)
            result = client.predict(
                input_video=video_file_path,
                background_image=background_image_path,
                api_name="/predict"
            )
            
            print(f"🔍 GRADIO DEBUG: Raw Gradio result = {result}")
            
            # Your Gradio function returns: (output_video_path, status_message)
            if isinstance(result, (list, tuple)) and len(result) >= 2:
                output_video_path, status_message = result[0], result[1]
                
                print(f"🔍 GRADIO DEBUG: Output video path = {output_video_path}")
                print(f"🔍 GRADIO DEBUG: Status message = {status_message}")
                
                if output_video_path and "COMPLETE" in str(status_message):
                    # Generate job ID
                    job_id = f"gradio_{int(time.time())}"
                    
                    # Store result for later download
                    self._gradio_results[job_id] = {
                        'output_path': output_video_path,
                        'status_message': status_message,
                        'completed_at': time.time()
                    }
                    
                    print(f"✅ Video processing successful! Job ID: {job_id}")
                    return job_id
                else:
                    # Processing failed
                    error_msg = str(status_message) if status_message else "Unknown Gradio processing error"
                    raise Exception(f"Gradio processing failed: {error_msg}")
            else:
                raise Exception(f"Unexpected Gradio result format: {result}")
                
        except Exception as e:
            print(f"❌ Failed to submit video processing: {str(e)}")
            raise
    
    def check_processing_status(self, job_id: str) -> ProcessingJob:
        """
        Check the status of a processing job
        For Gradio, jobs are processed synchronously, so they're either completed or failed
        """
        try:
            if job_id in self._gradio_results:
                result_data = self._gradio_results[job_id]
                
                return ProcessingJob(
                    job_id=job_id,
                    status=ProcessingStatus.COMPLETED,
                    input_file="",
                    output_file=result_data['output_path'],
                    progress=100.0,
                    error_message=None,
                    created_at=result_data['completed_at'],
                    completed_at=result_data['completed_at']
                )
            else:
                return ProcessingJob(
                    job_id=job_id,
                    status=ProcessingStatus.FAILED,
                    input_file="",
                    error_message="Job not found in results"
                )
                
        except Exception as e:
            print(f"❌ Failed to check job status: {str(e)}")
            return ProcessingJob(
                job_id=job_id,
                status=ProcessingStatus.FAILED,
                input_file="",
                error_message=str(e)
            )
    
    def download_result(self, job_id: str, output_path: str) -> bool:
        """
        Download the processed video result from Gradio
        
        Args:
            job_id: Job identifier
            output_path: Local path to save the processed video
            
        Returns:
            bool: True if download successful, False otherwise
        """
        try:
            print(f"🔍 GRADIO DEBUG: Downloading result for job {job_id}")
            
            # Get stored result path
            if job_id not in self._gradio_results:
                print(f"❌ No result found for job {job_id}")
                return False
                
            result_data = self._gradio_results[job_id]
            gradio_output_path = result_data['output_path']
            
            print(f"🔍 GRADIO DEBUG: Gradio output path = {gradio_output_path}")
            
            # Check if the Gradio output file exists
            if not os.path.exists(gradio_output_path):
                print(f"❌ Gradio output file not found: {gradio_output_path}")
                return False
            
            # Copy file from Gradio temp location to our output location
            shutil.copy2(gradio_output_path, output_path)
            
            print(f"✅ Video downloaded successfully: {output_path}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to download result: {str(e)}")
            return False
    
    def wait_for_completion(self, job_id: str, timeout: int = 300, poll_interval: int = 5) -> ProcessingJob:
        """
        Wait for job completion
        For Gradio, processing is synchronous, so we just check the stored result
        """
        try:
            # For Gradio, the job is already complete when submit_video_processing returns
            return self.check_processing_status(job_id)
            
        except Exception as e:
            return ProcessingJob(
                job_id=job_id,
                status=ProcessingStatus.FAILED,
                input_file="",
                error_message=str(e)
            )

# MyAvatar Integration Class
class MyAvatarVideoProcessor:
    def __init__(self, hf_space_url: str, temp_dir: str = "./temp", output_dir: str = "./output"):
        """
        MyAvatar integration with HF SAM2 + MatAnyone pipeline via Gradio
        
        Args:
            hf_space_url: Your HF Space URL
            temp_dir: Directory for temporary files
            output_dir: Directory for processed videos
        """
        self.hf_processor = HuggingFaceVideoProcessor(hf_space_url)
        self.temp_dir = temp_dir
        self.output_dir = output_dir
        
        # Create directories if they don't exist
        os.makedirs(temp_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)
    
    def process_video(self, video_data: bytes, background_data: bytes, user_id: str) -> Dict[str, Any]:
        """
        Full video processing pipeline for MyAvatar using Gradio
        
        Args:
            video_data: Raw video file bytes
            background_data: Raw background image bytes
            user_id: User identifier for file naming
            
        Returns:
            Dict with processing results and file paths
        """
        timestamp = int(time.time())
        
        # Save input files
        video_path = os.path.join(self.temp_dir, f"{user_id}_{timestamp}_input.mp4")
        background_path = os.path.join(self.temp_dir, f"{user_id}_{timestamp}_bg.jpg")
        
        with open(video_path, 'wb') as f:
            f.write(video_data)
        with open(background_path, 'wb') as f:
            f.write(background_data)
        
        print(f"🔍 PROCESSING DEBUG: Saved video to {video_path}")
        print(f"🔍 PROCESSING DEBUG: Saved background to {background_path}")
        
        try:
            # Submit processing job to Gradio
            job_id = self.hf_processor.submit_video_processing(video_path, background_path)
            
            print(f"🔍 PROCESSING DEBUG: Got job ID: {job_id}")
            
            # Check result (for Gradio, this is immediate)
            result = self.hf_processor.check_processing_status(job_id)
            
            if result.status == ProcessingStatus.COMPLETED:
                # Download result to our output directory
                output_path = os.path.join(self.output_dir, f"{user_id}_{timestamp}_processed.mp4")
                success = self.hf_processor.download_result(job_id, output_path)
                
                if success:
                    processing_time = result.completed_at - result.created_at if result.completed_at and result.created_at else 0
                    
                    return {
                        'success': True,
                        'job_id': job_id,
                        'output_file': output_path,
                        'processing_time': processing_time
                    }
            
            return {
                'success': False,
                'job_id': job_id,
                'error': result.error_message,
                'status': result.status.value
            }
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ PROCESSING ERROR: {error_msg}")
            
            return {
                'success': False,
                'error': error_msg
            }
        finally:
            # Cleanup temp files
            try:
                if os.path.exists(video_path):
                    os.remove(video_path)
                if os.path.exists(background_path):
                    os.remove(background_path)
            except Exception as e:
                print(f"⚠️ Cleanup warning: {str(e)}")

# Example usage for testing
if __name__ == "__main__":
    # Configuration
    HF_SPACE_URL = "https://MogensR-VideoBackgroundReplacer.hf.space"
    HF_TOKEN = "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"
    
    # Initialize processor
    processor = MyAvatarVideoProcessor(HF_SPACE_URL)
    processor.hf_processor.hf_token = HF_TOKEN
    
    print("🚀 MyAvatar Gradio integration ready!")
    print(f"HF Space: {HF_SPACE_URL}")
    
    # Test with sample files (uncomment to test)
    # with open("sample_video.mp4", "rb") as vf, open("sample_background.jpg", "rb") as bf:
    #     result = processor.process_video(vf.read(), bf.read(), "test_user_123")
    #     print(f"Processing result: {result}")
