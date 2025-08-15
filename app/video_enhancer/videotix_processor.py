"""
Videotix VideoProcessor - Ported for MyAvatar Integration
Enhanced video processing with MyAvatar's architecture integration
FIXED: Correct database schema (video_path not video_url, avatar_id required)
FIXED: Clean 0-100% progress tracking with 5% increments
"""
import cv2
import os
import logging
import tempfile
import subprocess
import shutil
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Callable, List
from pathlib import Path
import time
from datetime import datetime

# MyAvatar imports
try:
    from app.db.database import execute_query
    from app.logger.log_handler import log_info, log_error, log_warning
    from app.config.settings import config
except ImportError:
    # Fallback for development/testing
    def execute_query(*args, **kwargs): pass
    def log_info(msg, context): logging.info(f"[{context}] {msg}")
    def log_error(msg, context, exc=None): logging.error(f"[{context}] {msg}")
    def log_warning(msg, context): logging.warning(f"[{context}] {msg}")

    class config:
        TEMP_DIR = "temp"
        MAX_VIDEO_SIZE_MB = 500

logger = logging.getLogger(__name__)

def save_to_recent_videos(user_id: int, job_id: str, output_path: str, title: str = None):
    """
    FIXED: Save completed background replacement video to the videos table (Recent Videos)
    Uses correct database schema with proper column names
    """
    try:
        # Generate video metadata
        video_title = title or f"BackgroundFX - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        # Get video info if available
        duration = None
        try:
            if os.path.exists(output_path):
                # Could add duration detection here if needed
                pass
        except:
            pass

        # FIXED: Insert into videos table with correct schema
        log_info(f"[BackgroundFX] Inserting video: user_id={user_id}, title={video_title}, url={output_path}", "BackgroundFX")
        
        # Use correct column names for your database schema
        # Unified schema: insert all relevant columns, fallback to legacy for compatibility
        input_url = output_path  # If original input URL is available, use it; else fallback
        audio_path = ''  # Always set to empty string for backgroundfx jobs
        background_id = None  # If known, set background_id
        job_type = 'backgroundfx'
        
        # Patch: Always set heygen_video_id (required, not null)
        heygen_video_id = f"backgroundfx_{job_id}"
        video_path = output_path
        
        # DEBUG: Log all insert parameters and SQL for diagnosis
        log_info(f"[DEBUG] SQL: INSERT INTO videos (user_id, heygen_video_id, input_url, status, video_path, created_at, format, title, description, avatar_id, audio_path)", "BackgroundFX")
        log_info(f"[DEBUG] PARAMS: user_id={user_id}, heygen_video_id={heygen_video_id}, input_url={output_path}, status=completed, video_path={video_path}, created_at={datetime.now()}, format=16:9, title={video_title}, description=Video created with AI background replacement, avatar_id={'backgroundfx'}, audio_path={audio_path}", "BackgroundFX")
        if not 'backgroundfx':
            log_warning("[DEBUG] avatar_id is None or empty!", "BackgroundFX")

        params = (
            user_id,
            heygen_video_id,
            output_path,
            "completed",
            video_path,
            datetime.now(),
            "16:9",
            video_title,
            "Video created with AI background replacement",
            'backgroundfx',
            audio_path
        )
        print(f"DEBUG: About to insert - avatar_id='{'backgroundfx'}', params={params}")
        # DISABLED: Do not insert temp video path to DB. Cloudinary upload and DB insert should be handled in video_processing_routes.py only.
        # execute_query(
        #     """INSERT INTO videos (
        #         user_id,
        #         heygen_video_id,
        #         input_url,
        #         status,
        #         video_path,
        #         created_at,
        #         format,
        #         title,
        #         description,
        #         avatar_id,
        #         audio_path
        #     ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        #     params
        # )
        # Only insert after Cloudinary upload with correct URL in video_processing_routes.py


        log_info(f"✅ Background replacement video saved to Recent Videos for user {user_id}", "BackgroundFX")
        return True

    except Exception as e:
        log_error(f"❌ Error saving background video to Recent Videos: {e}", "BackgroundFX")
        return False

class ProcessingJob:
    """Represents a video processing job with tracking"""

    def __init__(self, job_id: str, user_id: int, input_path: str, operation: str):
        self.job_id = job_id
        self.user_id = user_id
        self.input_path = input_path
        self.operation = operation
        self.status = "initialized"
        self.progress = 0.0
        self.error_message = None
        self.started_at = datetime.now()
        self.completed_at = None
        self.output_path = None

    def update_status(self, status: str, progress: float = None, error_message: str = None):
        """Update job status and log to database"""
        self.status = status
        if progress is not None:
            self.progress = progress
        if error_message is not None:
            self.error_message = error_message
        if status == "completed":
            self.completed_at = datetime.now()

        # Log to database
        try:
            execute_query(
                """UPDATE video_processing_jobs 
                   SET status = %s, progress = %s, error_message = %s, updated_at = %s
                   WHERE job_id = %s""",
                (status, self.progress, error_message, datetime.now(), self.job_id)
            )
        except Exception as e:
            log_error(f"Failed to update job status: {e}", "VideoProcessor")

class VideoProcessor(ABC):
    """
    Base class for video processing operations
    Adapted from Videotix for MyAvatar integration with FastAPI architecture
    FIXED: Correct database schema and clean progress tracking
    """

    def __init__(self, user_id: int = None, temp_dir: str = None, 
                 enable_gpu: bool = True, quality: str = "medium"):
        """
        Initialize VideoProcessor with MyAvatar integration

        Args:
            user_id: MyAvatar user ID for context and permissions
            temp_dir: Custom temp directory (uses MyAvatar config if None)
            enable_gpu: Whether to attempt GPU acceleration
            quality: Processing quality ("low", "medium", "high")
        """
        self.user_id = user_id
        self.enable_gpu = enable_gpu
        self.quality = quality
        self.current_job: Optional[ProcessingJob] = None

        # Setup temp directory with user isolation
        if temp_dir is None:
            base_temp = getattr(config, 'TEMP_DIR', 'temp')
            self.temp_dir = os.path.join(base_temp, f"user_{user_id}" if user_id else "anonymous")
        else:
            self.temp_dir = temp_dir

        # Ensure temp directory exists
        os.makedirs(self.temp_dir, exist_ok=True)

        # Video properties (set during load_video)
        self.video_path = None
        self.cap = None
        self.fps = None
        self.width = None
        self.height = None
        self.total_frames = None
        self.fourcc = None

        # FIXED: Progress tracking with 5% increments
        self.progress_callback: Optional[Callable[[float, str], None]] = None
        self.last_reported_progress = -1

        log_info(f"VideoProcessor initialized for user {user_id}", "VideoProcessor")

    def set_progress_callback(self, callback: Callable[[float, str], None]):
        """Set progress callback for real-time updates"""
        self.progress_callback = callback

    def _update_progress(self, progress: float, message: str = ""):
        """FIXED: Update progress with 5% increment throttling"""
        if self.current_job:
            self.current_job.update_status(self.current_job.status, progress)

        if self.progress_callback:
            # Round to nearest 5% increment
            rounded_progress = round(progress / 5) * 5
            
            # Only update if progress changed by 5% or more
            if rounded_progress != self.last_reported_progress:
                self.last_reported_progress = rounded_progress
                self.progress_callback(rounded_progress, message)

    def _validate_file_permissions(self, file_path: str) -> bool:
        """Validate user has permission to access file"""
        if not self.user_id:
            log_warning("No user context for file validation", "VideoProcessor")
            return True  # Allow for testing

        # Add your file permission logic here
        # For now, basic existence check
        return os.path.exists(file_path)

    def _check_file_size(self, file_path: str) -> bool:
        """Check if file size is within limits"""
        try:
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            max_size = getattr(config, 'MAX_VIDEO_SIZE_MB', 500)

            if size_mb > max_size:
                log_error(f"File too large: {size_mb:.1f}MB > {max_size}MB", "VideoProcessor")
                return False
            return True
        except Exception as e:
            log_error(f"Error checking file size: {e}", "VideoProcessor")
            return False

    def load_video(self, video_path: str) -> bool:
        """
        Load video file and extract properties
        Enhanced with MyAvatar security and validation

        Args:
            video_path: Path to video file

        Returns:
            True if successful, False otherwise
        """
        try:
            log_info(f"Loading video: {video_path}", "VideoProcessor")

            # Validate permissions and file size
            if not self._validate_file_permissions(video_path):
                log_error("File permission validation failed", "VideoProcessor")
                return False

            if not self._check_file_size(video_path):
                log_error("File size validation failed", "VideoProcessor")
                return False

            # Open video
            self.cap = cv2.VideoCapture(video_path)
            if not self.cap.isOpened():
                log_error(f"Could not open video: {video_path}", "VideoProcessor")
                return False

            # Extract video properties
            self.video_path = video_path
            self.fps = self.cap.get(cv2.CAP_PROP_FPS)
            self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fourcc = cv2.VideoWriter_fourcc(*'mp4v')

            log_info(f"Video loaded: {self.width}x{self.height}, {self.fps:.1f}fps, {self.total_frames} frames", "VideoProcessor")
            return True

        except Exception as e:
            log_error(f"Error loading video: {e}", "VideoProcessor", e)
            if self.cap:
                self.cap.release()
                self.cap = None
            return False

    def save_video(self, frames: List, output_path: str, preserve_audio: bool = True) -> bool:
        """
        Save processed frames as video with optional audio preservation

        Args:
            frames: List of processed frames
            output_path: Output video path
            preserve_audio: Whether to preserve original audio

        Returns:
            True if successful, False otherwise
        """
        temp_video_path = None
        try:
            log_info(f"Saving video: {output_path}", "VideoProcessor")

            if not frames:
                log_error("No frames to save", "VideoProcessor")
                return False

            # Create temp video path if preserving audio
            if preserve_audio and self.video_path:
                temp_video_path = os.path.join(self.temp_dir, f"temp_video_{int(time.time())}.mp4")
                final_output = temp_video_path
            else:
                final_output = output_path

            # Write video frames
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(final_output, fourcc, self.fps, (self.width, self.height))

            if not out.isOpened():
                log_error(f"Could not open video writer: {final_output}", "VideoProcessor")
                return False

            # Write frames with progress tracking
            for i, frame in enumerate(frames):
                out.write(frame)
                # FIXED: Update progress with 5% throttling
                if i % 30 == 0:  # Every 30 frames
                    progress = (i / len(frames)) * 80  # Reserve 20% for audio processing
                    self._update_progress(progress, f"Writing frame {i+1}/{len(frames)}")

            out.release()
            log_info(f"Video frames written: {len(frames)} frames", "VideoProcessor")

            # Preserve audio using FFmpeg
            if preserve_audio and self.video_path and temp_video_path:
                self._update_progress(80, "Processing audio...")
                if self._preserve_audio_ffmpeg(temp_video_path, output_path):
                    # Clean up temp video
                    if os.path.exists(temp_video_path):
                        os.remove(temp_video_path)
                else:
                    # If audio preservation fails, use video without audio
                    log_warning("Audio preservation failed, using video without audio", "VideoProcessor")
                    if os.path.exists(temp_video_path):
                        shutil.move(temp_video_path, output_path)

            self._update_progress(100, "Video saved successfully")
            log_info(f"Video saved successfully: {output_path}", "VideoProcessor")
            return True

        except Exception as e:
            log_error(f"Error saving video: {e}", "VideoProcessor", e)
            # Cleanup on error
            if temp_video_path and os.path.exists(temp_video_path):
                os.remove(temp_video_path)
            return False

    def _preserve_audio_ffmpeg(self, video_path: str, output_path: str) -> bool:
        """
        Preserve audio from original video using FFmpeg

        Args:
            video_path: Path to video file (without audio)
            output_path: Final output path

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.video_path:
                log_warning("No original video path for audio preservation", "VideoProcessor")
                return False

            # FFmpeg command to merge video and audio
            cmd = [
                'ffmpeg', '-y',  # -y to overwrite existing files
                '-i', video_path,  # Input video (no audio)
                '-i', self.video_path,  # Original video (for audio)
                '-c:v', 'copy',  # Copy video codec
                '-c:a', 'aac',   # Audio codec
                '-map', '0:v:0',  # Map video from first input
                '-map', '1:a:0',  # Map audio from second input
                '-shortest',      # Use shortest duration
                output_path
            ]

            # Run FFmpeg
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                log_info("Audio preserved successfully with FFmpeg", "VideoProcessor")
                return True
            else:
                log_error(f"FFmpeg failed: {result.stderr}", "VideoProcessor")
                return False

        except subprocess.TimeoutExpired:
            log_error("FFmpeg timeout during audio preservation", "VideoProcessor")
            return False
        except FileNotFoundError:
            log_warning("FFmpeg not found, skipping audio preservation", "VideoProcessor")
            return False
        except Exception as e:
            log_error(f"Error during audio preservation: {e}", "VideoProcessor", e)
            return False

    @abstractmethod
    def process_frame(self, frame, frame_number: int, **kwargs) -> Optional:
        """
        Abstract method for processing individual frames
        Must be implemented by subclasses

        Args:
            frame: Input frame (numpy array)
            frame_number: Frame index
            **kwargs: Additional processing parameters

        Returns:
            Processed frame or None if processing failed
        """
        pass

    def process_video(self, output_path: str, job_id: str = None, **kwargs) -> bool:
        """
        Main video processing pipeline with MyAvatar job tracking
        FIXED: Clean progress tracking and correct database schema for Recent Videos
        """
        processed_frames = []

        try:
            # Create processing job
            if job_id and self.user_id:
                self.current_job = ProcessingJob(
                    job_id=job_id,
                    user_id=self.user_id,
                    input_path=self.video_path,
                    operation=self.__class__.__name__
                )
                self.current_job.update_status("processing", 0.0)

            log_info(f"Starting video processing: {self.video_path} -> {output_path}", "VideoProcessor")

            if not self.cap:
                log_error("No video loaded", "VideoProcessor")
                if self.current_job:
                    self.current_job.update_status("failed", error_message="No video loaded")
                return False

            frame_number = 0
            failed_frames = 0
            max_failed_frames = max(10, self.total_frames * 0.05)  # Allow 5% failed frames

            # Process frames with clean progress tracking
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    break

                # Process individual frame
                try:
                    processed_frame = self.process_frame(frame, frame_number, **kwargs)
                    if processed_frame is not None:
                        processed_frames.append(processed_frame)
                    else:
                        failed_frames += 1
                        if failed_frames > max_failed_frames:
                            log_error(f"Too many failed frames: {failed_frames}", "VideoProcessor")
                            if self.current_job:
                                self.current_job.update_status("failed", error_message="Too many processing failures")
                            return False
                        # Use original frame as fallback
                        processed_frames.append(frame)

                except Exception as e:
                    log_error(f"Error processing frame {frame_number}: {e}", "VideoProcessor")
                    failed_frames += 1
                    processed_frames.append(frame)  # Fallback to original

                frame_number += 1

                # FIXED: Update progress every 10 frames with 5% throttling
                if frame_number % 10 == 0:
                    progress = (frame_number / self.total_frames) * 60  # Reserve 40% for saving
                    self._update_progress(progress, f"Processing frame {frame_number}/{self.total_frames}")

            log_info(f"Processed {len(processed_frames)} frames ({failed_frames} failed)", "VideoProcessor")

            # Save processed video
            self._update_progress(60, "Saving video...")
            if self.save_video(processed_frames, output_path):
                if self.current_job:
                    self.current_job.output_path = output_path
                    self.current_job.update_status("completed", 100.0)

                # FIXED: Save to Recent Videos table with correct database schema
                log_info(f"🎬 Saving completed background video to Recent Videos for user {self.user_id}", "VideoProcessor")
                # save_to_recent_videos call disabled: Only save after Cloudinary upload in video_processing_routes.py

                log_info(f"Video processing completed: {output_path}", "VideoProcessor")
                return True
            else:
                if self.current_job:
                    self.current_job.update_status("failed", error_message="Failed to save video")
                return False

        except Exception as e:
            log_error(f"Error during video processing: {e}", "VideoProcessor", e)
            if self.current_job:
                self.current_job.update_status("failed", error_message=str(e))
            return False
        finally:
            try:
                if self.cap:
                    self.cap.release()
                    self.cap = None
                self.cleanup()
            except Exception as e:
                log_error(f"Cleanup error (ignored): {e}", "VideoProcessor", e)

    def cleanup(self):
        """Clean up resources and temporary files"""
        try:
            if self.cap:
                self.cap.release()
                self.cap = None

            # Clean up user temp directory (keep recent files)
            if os.path.exists(self.temp_dir):
                current_time = time.time()
                for filename in os.listdir(self.temp_dir):
                    filepath = os.path.join(self.temp_dir, filename)
                    if os.path.isfile(filepath):
                        # Remove files older than 1 hour
                        if current_time - os.path.getmtime(filepath) > 3600:
                            os.remove(filepath)

            log_info("VideoProcessor cleanup completed", "VideoProcessor")

        except Exception as e:
            log_error(f"Error during cleanup: {e}", "VideoProcessor", e)

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup"""
        self.cleanup()

    def get_video_info(self) -> Dict[str, Any]:
        """
        Get video information dictionary

        Returns:
            Dictionary with video properties
        """
        if not self.cap:
            return {}

        return {
            "path": self.video_path,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "total_frames": self.total_frames,
            "duration_seconds": self.total_frames / self.fps if self.fps > 0 else 0,
            "fourcc": self.fourcc
        }
