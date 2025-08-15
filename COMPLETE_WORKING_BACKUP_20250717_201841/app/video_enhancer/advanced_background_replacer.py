"""
Advanced Background Replacer for MyAvatar
Combines VideoProcessor with AI Segmentation for professional background replacement
"""
import cv2
import numpy as np
import os
import time
from typing import Optional, Dict, Any, Tuple, Union
import logging

# MyAvatar imports
try:
    from app.logger.log_handler import log_info, log_error, log_warning
    from app.video_enhancer.videotix_processor import VideoProcessor
    from app.video_enhancer.segmentation_models import (
        create_segmentation_model, 
        SegmentationModel,
        SegmentationModelFactory
    )
except ImportError as e:
    # Fallback for development/testing
    logging.error(f"Import error: {e}")
    raise ImportError(f"Required MyAvatar modules not found: {e}")

logger = logging.getLogger(__name__)

class AdvancedBackgroundReplacer(VideoProcessor):
    """
    Advanced background replacement using AI segmentation
    Extends VideoProcessor to provide professional-grade background replacement
    """
    
    def __init__(self, user_id: int = None, temp_dir: str = None, 
                 enable_gpu: bool = True, quality: str = "medium",
                 segmentation_model: str = "auto"):
        """
        Initialize Advanced Background Replacer
        
        Args:
            user_id: MyAvatar user ID for context and permissions
            temp_dir: Custom temp directory
            enable_gpu: Whether to use GPU acceleration
            quality: Processing quality ("low", "medium", "high")
            segmentation_model: Segmentation model ("rvm", "mediapipe", "fallback", "auto")
        """
        super().__init__(user_id, temp_dir, enable_gpu, quality)
        
        self.segmentation_model_type = segmentation_model
        self.segmenter: Optional[SegmentationModel] = None
        self.background_image: Optional[np.ndarray] = None
        self.background_type = "image"  # "image", "color", "blur"
        
        # Processing parameters based on quality
        self._set_quality_parameters()
        
        # Performance tracking
        self.segmentation_time = 0.0
        self.compositing_time = 0.0
        self.preprocessing_time = 0.0
        
        log_info(f"AdvancedBackgroundReplacer initialized with {quality} quality", "BackgroundReplacer")
    
    def _set_quality_parameters(self):
        """Set processing parameters based on quality setting"""
        if self.quality == "low":
            self.feather_radius = 1
            self.sharpen_strength = 0.0
            self.edge_enhancement = False
            self.temporal_smoothing = False
        elif self.quality == "medium":
            self.feather_radius = 3
            self.sharpen_strength = 0.5
            self.edge_enhancement = True
            self.temporal_smoothing = False
        else:  # high
            self.feather_radius = 5
            self.sharpen_strength = 0.8
            self.edge_enhancement = True
            self.temporal_smoothing = True
    
    def initialize_segmentation(self) -> bool:
        """
        Initialize segmentation model
        
        Returns:
            True if successful, False otherwise
        """
        try:
            log_info(f"Initializing segmentation model: {self.segmentation_model_type}", "BackgroundReplacer")
            
            self.segmenter = create_segmentation_model(
                model_type=self.segmentation_model_type,
                enable_gpu=self.enable_gpu,
                quality=self.quality
            )
            
            log_info(f"Segmentation model initialized: {self.segmenter.__class__.__name__}", "BackgroundReplacer")
            return True
            
        except Exception as e:
            log_error(f"Failed to initialize segmentation model: {e}", "BackgroundReplacer", e)
            return False
    
    def set_background_image(self, background_path: str) -> bool:
        """
        Load and set background image
        
        Args:
            background_path: Path to background image
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self._validate_file_permissions(background_path):
                log_error("Background image permission validation failed", "BackgroundReplacer")
                return False
            
            # Load background image
            self.background_image = cv2.imread(background_path)
            if self.background_image is None:
                log_error(f"Could not load background image: {background_path}", "BackgroundReplacer")
                return False
            
            self.background_type = "image"
            log_info(f"Background image loaded: {background_path}", "BackgroundReplacer")
            return True
            
        except Exception as e:
            log_error(f"Error loading background image: {e}", "BackgroundReplacer", e)
            return False
    
    def set_background_color(self, color: Union[Tuple[int, int, int], str]) -> bool:
        """
        Set solid color background
        
        Args:
            color: BGR color tuple (B, G, R) or hex string "#RRGGBB"
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if isinstance(color, str):
                # Convert hex to BGR
                if color.startswith('#'):
                    color = color[1:]
                r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
                color = (b, g, r)  # Convert RGB to BGR
            
            # Create 1x1 color image (will be resized during processing)
            self.background_image = np.full((1, 1, 3), color, dtype=np.uint8)
            self.background_type = "color"
            
            log_info(f"Background color set: {color}", "BackgroundReplacer")
            return True
            
        except Exception as e:
            log_error(f"Error setting background color: {e}", "BackgroundReplacer", e)
            return False
    
    def set_background_blur(self, blur_strength: int = 15) -> bool:
        """
        Set blurred version of original video as background
        
        Args:
            blur_strength: Blur kernel size (must be odd)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.background_type = "blur"
            self.blur_strength = blur_strength if blur_strength % 2 == 1 else blur_strength + 1
            
            log_info(f"Background blur set with strength: {self.blur_strength}", "BackgroundReplacer")
            return True
            
        except Exception as e:
            log_error(f"Error setting background blur: {e}", "BackgroundReplacer", e)
            return False
    
    def _prepare_background(self, frame_shape: Tuple[int, int]) -> np.ndarray:
        """
        Prepare background image to match frame dimensions
        
        Args:
            frame_shape: (height, width) of the video frame
            
        Returns:
            Background image resized to frame dimensions
        """
        height, width = frame_shape
        
        if self.background_type == "blur":
            # Return None for blur - will be processed per frame
            return None
        elif self.background_type == "color":
            # Create solid color background
            color = self.background_image[0, 0]
            return np.full((height, width, 3), color, dtype=np.uint8)
        else:  # image
            # Resize background image to frame size
            return cv2.resize(self.background_image, (width, height))
    
    def _feather_mask(self, mask: np.ndarray) -> np.ndarray:
        """
        Apply feathering to mask edges for smoother compositing
        
        Args:
            mask: Binary mask (0-255)
            
        Returns:
            Feathered alpha mask as float32 array (0.0-1.0)
        """
        # Convert to float and normalize
        alpha = mask.astype(np.float32) / 255.0
        
        # Apply gaussian blur for feathering
        if self.feather_radius > 0:
            alpha = cv2.GaussianBlur(alpha, (self.feather_radius*2+1, self.feather_radius*2+1), 
                                   self.feather_radius/2)
        
        return np.clip(alpha, 0.0, 1.0)
    
    def _enhance_edges(self, img: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """
        Enhance edges around the subject for better compositing
        
        Args:
            img: Input image
            mask: Segmentation mask
            
        Returns:
            Edge-enhanced image
        """
        if not self.edge_enhancement or self.sharpen_strength <= 0:
            return img
        
        try:
            # Create edge mask from segmentation
            edge_mask = cv2.morphologyEx(mask, cv2.MORPH_GRADIENT, 
                                       np.ones((3, 3), np.uint8))
            edge_mask = edge_mask.astype(np.float32) / 255.0
            
            # Apply unsharp masking to edges
            blurred = cv2.GaussianBlur(img, (3, 3), 1.0)
            diff = img.astype(np.float32) - blurred.astype(np.float32)
            
            # Apply sharpening only to edge areas
            sharpened = img.astype(np.float32) + diff * self.sharpen_strength * edge_mask[..., np.newaxis]
            
            return np.clip(sharpened, 0, 255).astype(np.uint8)
            
        except Exception as e:
            log_warning(f"Edge enhancement failed: {e}", "BackgroundReplacer")
            return img
    
    def _temporal_smoothing(self, current_mask: np.ndarray, 
                           previous_mask: Optional[np.ndarray]) -> np.ndarray:
        """
        Apply temporal smoothing to reduce mask flickering
        
        Args:
            current_mask: Current frame mask
            previous_mask: Previous frame mask (if available)
            
        Returns:
            Temporally smoothed mask
        """
        if not self.temporal_smoothing or previous_mask is None:
            return current_mask
        
        try:
            # Blend current and previous masks
            alpha = 0.7  # Weight for current frame
            smoothed = (alpha * current_mask.astype(np.float32) + 
                       (1 - alpha) * previous_mask.astype(np.float32))
            
            return np.clip(smoothed, 0, 255).astype(np.uint8)
            
        except Exception as e:
            log_warning(f"Temporal smoothing failed: {e}", "BackgroundReplacer")
            return current_mask
    
    def process_frame(self, frame: np.ndarray, frame_number: int, **kwargs) -> Optional[np.ndarray]:
        """
        Process a single frame for background replacement
        
        Args:
            frame: Input frame (BGR format)
            frame_number: Frame index
            **kwargs: Additional parameters
            
        Returns:
            Processed frame with replaced background or None if failed
        """
        try:
            start_time = time.time()
            
            # Initialize segmentation model if needed
            if self.segmenter is None:
                if not self.initialize_segmentation():
                    log_error("Segmentation initialization failed", "BackgroundReplacer")
                    return None
            
            # Prepare background for this frame
            t0 = time.time()
            if self.background_type == "blur":
                background = cv2.GaussianBlur(frame, (self.blur_strength, self.blur_strength), 0)
            else:
                background = self._prepare_background(frame.shape[:2])
                if background is None:
                    log_error("Background preparation failed", "BackgroundReplacer")
                    return None
            self.preprocessing_time += time.time() - t0
            
            # Segment the frame
            t0 = time.time()
            mask = self.segmenter.segment_frame(frame)
            self.segmentation_time += time.time() - t0
            
            # Apply temporal smoothing if enabled
            if hasattr(self, '_previous_mask'):
                mask = self._temporal_smoothing(mask, self._previous_mask)
            self._previous_mask = mask.copy()
            
            # Apply feathering to mask
            alpha = self._feather_mask(mask)
            alpha_3ch = np.stack([alpha, alpha, alpha], axis=2)
            
            # Enhance edges if enabled
            enhanced_frame = self._enhance_edges(frame, mask)
            
            # Composite frame with background
            t0 = time.time()
            result = (enhanced_frame.astype(np.float32) * alpha_3ch + 
                     background.astype(np.float32) * (1.0 - alpha_3ch))
            result = np.clip(result, 0, 255).astype(np.uint8)
            self.compositing_time += time.time() - t0
            
            # Update progress every 30 frames
            if frame_number % 30 == 0:
                total_time = time.time() - start_time
                log_info(f"Frame {frame_number} processed in {total_time*1000:.1f}ms", "BackgroundReplacer")
            
            return result
            
        except Exception as e:
            log_error(f"Error processing frame {frame_number}: {e}", "BackgroundReplacer", e)
            return None
    
    def replace_background(self, input_video_path: str, output_video_path: str,
                          background_config: Dict[str, Any], job_id: str = None) -> bool:
        """
        Complete background replacement workflow
        
        Args:
            input_video_path: Path to input video
            output_video_path: Path for output video
            background_config: Background configuration dict
            job_id: Processing job ID for tracking
            
        Returns:
            True if successful, False otherwise
        """
        try:
            log_info(f"Starting background replacement: {input_video_path}", "BackgroundReplacer")
            
            # Load video
            if not self.load_video(input_video_path):
                log_error("Failed to load input video", "BackgroundReplacer")
                return False
            
            # Setup background based on configuration
            bg_type = background_config.get("type", "color")
            
            if bg_type == "image":
                bg_path = background_config.get("path")
                if not bg_path or not self.set_background_image(bg_path):
                    log_error("Failed to set background image", "BackgroundReplacer")
                    return False
            elif bg_type == "color":
                bg_color = background_config.get("color", "#4a90e2")
                if not self.set_background_color(bg_color):
                    log_error("Failed to set background color", "BackgroundReplacer")
                    return False
            elif bg_type == "blur":
                blur_strength = background_config.get("blur_strength", 15)
                if not self.set_background_blur(blur_strength):
                    log_error("Failed to set background blur", "BackgroundReplacer")
                    return False
            else:
                log_error(f"Unknown background type: {bg_type}", "BackgroundReplacer")
                return False
            
            # Process video
            success = self.process_video(output_video_path, job_id)
            
            if success:
                # Log performance statistics
                self._log_performance_stats()
                log_info(f"Background replacement completed: {output_video_path}", "BackgroundReplacer")
            else:
                log_error("Video processing failed", "BackgroundReplacer")
            
            return success
            
        except Exception as e:
            log_error(f"Error in background replacement: {e}", "BackgroundReplacer", e)
            return False
        finally:
            # Cleanup resources
            self.cleanup()
    
    def _log_performance_stats(self):
        """Log detailed performance statistics"""
        if self.frame_count > 0:
            total_processing_time = self.segmentation_time + self.compositing_time + self.preprocessing_time
            
            stats = {
                "frames_processed": self.frame_count,
                "total_time": total_processing_time,
                "avg_time_per_frame": total_processing_time / self.frame_count,
                "segmentation_time": self.segmentation_time,
                "compositing_time": self.compositing_time,
                "preprocessing_time": self.preprocessing_time,
                "fps": self.frame_count / total_processing_time if total_processing_time > 0 else 0
            }
            
            # Get segmentation model stats
            if self.segmenter:
                seg_stats = self.segmenter.get_performance_stats()
                stats.update({"segmentation_model": seg_stats})
            
            log_info(f"Performance stats: {stats}", "BackgroundReplacer")
    
    def cleanup(self):
        """Enhanced cleanup with segmentation model cleanup"""
        try:
            # Cleanup segmentation model
            if self.segmenter:
                self.segmenter.cleanup()
                self.segmenter = None
            
            # Reset previous mask for temporal smoothing
            if hasattr(self, '_previous_mask'):
                delattr(self, '_previous_mask')
            
            # Call parent cleanup
            super().cleanup()
            
            log_info("AdvancedBackgroundReplacer cleanup completed", "BackgroundReplacer")
            
        except Exception as e:
            log_error(f"Error during cleanup: {e}", "BackgroundReplacer", e)

# Convenience function for easy background replacement
def replace_video_background(input_video_path: str, output_video_path: str,
                           background_config: Dict[str, Any], user_id: int = None,
                           quality: str = "medium", segmentation_model: str = "auto") -> bool:
    """
    Convenience function for background replacement
    
    Args:
        input_video_path: Path to input video
        output_video_path: Path for output video  
        background_config: Background configuration
        user_id: MyAvatar user ID
        quality: Processing quality ("low", "medium", "high")
        segmentation_model: Segmentation model to use
        
    Returns:
        True if successful, False otherwise
    """
    replacer = AdvancedBackgroundReplacer(
        user_id=user_id,
        quality=quality,
        segmentation_model=segmentation_model
    )
    
    try:
        return replacer.replace_background(
            input_video_path=input_video_path,
            output_video_path=output_video_path,
            background_config=background_config
        )
    finally:
        replacer.cleanup()
