"""
Advanced Background Replacer for MyAvatar
Combines VideoProcessor with AI Segmentation for professional background replacement
FIXED: Removed all placeholders and implemented actual video processing
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
        self.background_type = "color"  # "image", "color", "blur"
        self._previous_mask: Optional[np.ndarray] = None
        
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
            img = cv2.imread(background_path)
            if img is None:
                log_error(f"Failed to load background image: {background_path}", "BackgroundReplacer")
                return False
            self.background_image = img
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
            if isinstance(color, str) and color.startswith("#"):
                # Convert hex to BGR
                color = tuple(int(color.lstrip("#")[i:i+2], 16) for i in (4, 2, 0))
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
    
    def _setup_background_from_config(self, background_config: Dict[str, Any]) -> bool:
        """
        Setup background based on configuration
        
        Args:
            background_config: Background configuration dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            bg_type = background_config.get('type', 'color')
            
            if bg_type == 'image':
                bg_path = background_config.get('path')
                if bg_path and os.path.exists(bg_path):
                    return self.set_background_image(bg_path)
                else:
                    log_warning(f"Background image not found: {bg_path}, using default color", "BackgroundReplacer")
                    return self.set_background_color("#4a90e2")
                    
            elif bg_type == 'color':
                color = background_config.get('color', '#4a90e2')
                return self.set_background_color(color)
                
            elif bg_type == 'blur':
                blur_strength = background_config.get('blur_strength', 15)
                return self.set_background_blur(blur_strength)
                
            else:
                log_warning(f"Unknown background type: {bg_type}, using default color", "BackgroundReplacer")
                return self.set_background_color("#4a90e2")
                
        except Exception as e:
            log_error(f"Error setting up background from config: {e}", "BackgroundReplacer", e)
            return False
    
    def _prepare_background(self, frame_shape: Tuple[int, int], original_frame: np.ndarray = None) -> np.ndarray:
        """
        Prepare background image to match frame dimensions
        
        Args:
            frame_shape: (height, width) of the video frame
            original_frame: Original frame for blur background
            
        Returns:
            Background image resized to frame dimensions
        """
        height, width = frame_shape[:2]
        
        if self.background_type == "image" and self.background_image is not None:
            return cv2.resize(self.background_image, (width, height))
            
        elif self.background_type == "color" and self.background_image is not None:
            color = self.background_image[0, 0]
            return np.full((height, width, 3), color, dtype=np.uint8)
            
        elif self.background_type == "blur" and original_frame is not None:
            # Create blurred version of original frame
            blurred = cv2.GaussianBlur(original_frame, (self.blur_strength, self.blur_strength), 0)
            return blurred
            
        else:
            # Default: solid blue background
            return np.full((height, width, 3), (230, 144, 74), dtype=np.uint8)
    
    def _feather_mask(self, mask: np.ndarray) -> np.ndarray:
        """
        Apply feathering to mask edges for smoother compositing
        
        Args:
            mask: Binary mask (0-255)
            
        Returns:
            Feathered alpha mask as float32 array (0.0-1.0)
        """
        if self.feather_radius <= 0:
            return mask.astype(np.float32) / 255.0
            
        kernel_size = self.feather_radius * 2 + 1
        feathered = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (kernel_size, kernel_size), 0)
        return np.clip(feathered, 0, 1)
    
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
            # Create sharpening kernel
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]]) * self.sharpen_strength
            kernel[1,1] = 8 - (kernel.sum() - kernel[1,1])
            
            # Apply sharpening only to areas around mask edges
            edges = cv2.Canny((mask * 255).astype(np.uint8), 50, 150)
            edges_dilated = cv2.dilate(edges, np.ones((5,5), np.uint8), iterations=1)
            
            # Apply sharpening
            sharpened = cv2.filter2D(img, -1, kernel)
            
            # Blend sharpened version only around edges
            edge_mask = (edges_dilated / 255.0).astype(np.float32)
            edge_mask = np.stack([edge_mask] * 3, axis=-1)
            
            result = img.astype(np.float32) * (1 - edge_mask) + sharpened.astype(np.float32) * edge_mask
            return np.clip(result, 0, 255).astype(np.uint8)
            
        except Exception as e:
            log_warning(f"Edge enhancement failed: {e}", "BackgroundReplacer")
            return img
    
    def _temporal_smoothing(self, current_mask: np.ndarray, previous_mask: Optional[np.ndarray]) -> np.ndarray:
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
            # Ensure masks have same dimensions
            if previous_mask.shape != current_mask.shape:
                previous_mask = cv2.resize(previous_mask, (current_mask.shape[1], current_mask.shape[0]))
            
            # Weighted blend: 70% current, 30% previous
            smoothed = cv2.addWeighted(current_mask, 0.7, previous_mask, 0.3, 0)
            return smoothed
            
        except Exception as e:
            log_warning(f"Temporal smoothing failed: {e}", "BackgroundReplacer")
            return current_mask
    
    def process_frame(self, frame: np.ndarray, frame_number: int, **kwargs) -> np.ndarray:
        """
        Process a single frame with background replacement
        FIXED: Binary compositing for green screen output to prevent transparency bleeding
        
        Args:
            frame: Input frame
            frame_number: Frame index
            **kwargs: Additional parameters
            
        Returns:
            Processed frame with background replaced
        """
        start_time = time.time()
        
        try:
            # Initialize segmentation if not done
            if self.segmenter is None:
                if not self.initialize_segmentation():
                    log_warning(f"Segmentation model not available for frame {frame_number}, using original", "BackgroundReplacer")
                    return frame
            
            # Get segmentation mask
            seg_start = time.time()
            mask = self.segmenter.segment_frame(frame)
            self.segmentation_time += time.time() - seg_start
            
            # Check if mask is valid
            if mask is None or (isinstance(mask, np.ndarray) and np.count_nonzero(mask) == 0):
                log_warning(f"Invalid segmentation mask at frame {frame_number}, using original", "BackgroundReplacer")
                return frame
            
            # Apply temporal smoothing
            if hasattr(self, '_previous_mask') and self._previous_mask is not None:
                mask = self._temporal_smoothing(mask, self._previous_mask)
            self._previous_mask = mask.copy()
            
            # Compositing
            comp_start = time.time()
            
            # Prepare background
            background = self._prepare_background(frame.shape, frame)
            
            # CRITICAL FIX: Check if this is green screen output and use binary compositing
            is_green_screen = (hasattr(self, 'background_type') and self.background_type == "color" and 
                              self.background_image is not None and 
                              np.array_equal(self.background_image[0, 0], [0, 255, 0]))  # Pure green BGR
            
            if is_green_screen:
                # BINARY COMPOSITING FOR GREEN SCREEN - NO FEATHERING/GRADUAL TRANSPARENCY
                log_info("🎬 Using binary compositing for green screen output (no transparency bleeding)", "BackgroundReplacer")
                
                # 🔍 DEBUG: Log incoming mask from RVM
                log_info(f"🔍 COMPOSITING INPUT DEBUG:", "BackgroundReplacer")
                log_info(f"   - Input mask shape: {mask.shape}", "BackgroundReplacer")
                log_info(f"   - Input mask dtype: {mask.dtype}", "BackgroundReplacer")
                log_info(f"   - Input mask range: {mask.min()} to {mask.max()}", "BackgroundReplacer")
                log_info(f"   - Input mask unique values: {np.unique(mask)}", "BackgroundReplacer")
                log_info(f"   - Pixels > 127: {(mask > 127).sum()}/{mask.size} ({(mask > 127).sum()/mask.size*100:.1f}%)", "BackgroundReplacer")
                
                # Convert mask to strict binary alpha (0.0 or 1.0 only)
                binary_alpha = (mask > 127).astype(np.float32)  # Convert 0-255 mask to 0.0/1.0
                
                # 🔍 DEBUG: Verify binary conversion
                log_info(f"🔍 BINARY CONVERSION DEBUG:", "BackgroundReplacer")
                log_info(f"   - Binary alpha shape: {binary_alpha.shape}", "BackgroundReplacer")
                log_info(f"   - Binary alpha dtype: {binary_alpha.dtype}", "BackgroundReplacer")
                log_info(f"   - Binary alpha range: {binary_alpha.min():.3f} to {binary_alpha.max():.3f}", "BackgroundReplacer")
                log_info(f"   - Binary alpha unique values: {np.unique(binary_alpha)}", "BackgroundReplacer")
                
                # Verify binary nature
                unique_vals = np.unique(binary_alpha)
                if len(unique_vals) > 2:
                    log_warning(f"🚨 Non-binary alpha detected in compositing: {unique_vals}, forcing binary", "BackgroundReplacer")
                    binary_alpha = (binary_alpha > 0.5).astype(np.float32)
                    log_info(f"   - After forcing binary: {np.unique(binary_alpha)}", "BackgroundReplacer")
                
                # Expand binary alpha to 3 channels
                alpha_3d = np.stack([binary_alpha] * 3, axis=-1)
                
                # Apply minimal edge enhancement (no blur that creates transparency)
                enhanced_frame = self._enhance_edges(frame, binary_alpha)
                
                # STRICT BINARY COMPOSITING: person pixels = completely opaque, background = completely transparent
                # This ensures solid subject against pure green background with NO original background bleeding
                result = np.where(alpha_3d > 0.5, enhanced_frame, background).astype(np.uint8)
                
                # 🔍 DEBUG: Analyze final compositing result
                log_info(f"🔍 FINAL COMPOSITING RESULT DEBUG:", "BackgroundReplacer")
                log_info(f"   - Result shape: {result.shape}", "BackgroundReplacer")
                log_info(f"   - Result dtype: {result.dtype}", "BackgroundReplacer")
                
                # Check for pure green pixels (should be background)
                pure_green = np.all(result == [0, 255, 0], axis=2)
                green_count = pure_green.sum()
                total_pixels = result.shape[0] * result.shape[1]
                log_info(f"   - Pure green pixels: {green_count}/{total_pixels} ({green_count/total_pixels*100:.1f}%)", "BackgroundReplacer")
                
                # Check for original background bleeding (problematic pixels)
                # Look for beige/tan colors that shouldn't be there
                beige_mask = np.all(np.abs(result.astype(np.int16) - [160, 180, 200]) < 30, axis=2)
                beige_count = beige_mask.sum()
                if beige_count > 0:
                    log_warning(f"   - 🚨 BACKGROUND BLEEDING DETECTED: {beige_count} beige pixels found!", "BackgroundReplacer")
                else:
                    log_info(f"   - ✅ No background bleeding detected", "BackgroundReplacer")
                
                # Check for semi-transparent green (the main problem)
                # Look for pixels that are not pure green but have green components
                mixed_green = np.logical_and(
                    result[:,:,1] > 200,  # High green component
                    np.logical_or(result[:,:,0] > 50, result[:,:,2] > 50)  # But also other colors
                )
                mixed_count = mixed_green.sum()
                if mixed_count > 0:
                    log_warning(f"   - 🚨 SEMI-TRANSPARENT GREEN DETECTED: {mixed_count} mixed pixels!", "BackgroundReplacer")
                else:
                    log_info(f"   - ✅ No semi-transparent green detected", "BackgroundReplacer")
                
                # Verification: Log compositing results
                subject_pixels = (binary_alpha > 0.5).sum()
                background_pixels = (binary_alpha <= 0.5).sum()
                log_info(f"🎬 Binary compositing complete: {subject_pixels} subject, {background_pixels} background pixels", "BackgroundReplacer")
                
            else:
                # STANDARD FEATHERED COMPOSITING FOR NON-GREEN SCREEN BACKGROUNDS
                # Apply feathering to mask for smooth edges
                alpha_mask = self._feather_mask(mask)
                
                # Expand alpha mask to 3 channels
                alpha_3d = np.stack([alpha_mask] * 3, axis=-1)
                
                # Apply edge enhancement to foreground
                enhanced_frame = self._enhance_edges(frame, alpha_mask)
                
                # Standard alpha compositing: foreground * alpha + background * (1 - alpha)
                foreground = enhanced_frame.astype(np.float32) * alpha_3d
                background_part = background.astype(np.float32) * (1.0 - alpha_3d)
                
                result = foreground + background_part
                result = np.clip(result, 0, 255).astype(np.uint8)
            
            self.compositing_time += time.time() - comp_start
            
            return result
            
        except Exception as e:
            log_error(f"Error processing frame {frame_number}: {e}", "BackgroundReplacer", e)
            return frame  # Return original frame on error
        
        finally:
            # Update frame count for progress tracking
            if hasattr(self, 'frame_count'):
                self.frame_count += 1
    
    def replace_background(self, input_video_path: str, output_video_path: str, 
                          background_config: Dict[str, Any], job_id: str = None) -> Dict[str, Any]:
        """
        Enhanced replace background with two-stage workflow support
        
        Args:
            input_video_path: Path to input video
            output_video_path: Path for output video
            background_config: Enhanced background configuration with workflow support
            job_id: Optional job ID for tracking
            
        Returns:
            Dictionary with success status and details
        """
        try:
            log_info(f"Starting enhanced background replacement: {input_video_path} -> {output_video_path}", "BackgroundReplacer")
            
            # Check if this is an enhanced two-stage workflow
            is_enhanced_workflow = background_config.get('workflow') == 'enhanced'
            is_custom_image = background_config.get('type') == 'image'
            is_green_screen = background_config.get('type') == 'green'
            
            if is_enhanced_workflow and is_custom_image:
                # Two-stage workflow: RVM + green screen, then chroma key replacement
                return self._process_two_stage_workflow(input_video_path, output_video_path, background_config, job_id)
            elif is_green_screen:
                # Single-stage green screen workflow
                return self._process_green_screen_workflow(input_video_path, output_video_path, background_config, job_id)
            else:
                # Standard single-stage workflow
                return self._process_standard_workflow(input_video_path, output_video_path, background_config, job_id)
                
        except Exception as e:
            error_msg = f"Unexpected error during enhanced background replacement: {e}"
            log_error(error_msg, "BackgroundReplacer", e)
            return {"success": False, "error_message": error_msg}
        
        finally:
            try:
                self.cleanup()
            except Exception as e:
                log_error(f"Cleanup error (ignored): {e}", "BackgroundReplacer", e)
    
    def _process_standard_workflow(self, input_video_path: str, output_video_path: str, 
                                  background_config: Dict[str, Any], job_id: str = None) -> Dict[str, Any]:
        """Standard single-stage background replacement workflow"""
        # Validate input video
        if not os.path.exists(input_video_path):
            error_msg = f"Input video file not found: {input_video_path}"
            log_error(error_msg, "BackgroundReplacer")
            return {"success": False, "error_message": error_msg}
        
        # Load video
        if not self.load_video(input_video_path):
            error_msg = f"Failed to load input video: {input_video_path}"
            log_error(error_msg, "BackgroundReplacer")
            return {"success": False, "error_message": error_msg}
        
        # Initialize segmentation
        if not self.initialize_segmentation():
            error_msg = "Failed to initialize segmentation model"
            log_error(error_msg, "BackgroundReplacer")
            return {"success": False, "error_message": error_msg}
        
        # Setup background
        if not self._setup_background_from_config(background_config):
            error_msg = "Failed to setup background configuration"
            log_error(error_msg, "BackgroundReplacer")
            return {"success": False, "error_message": error_msg}
        
        # Reset performance counters
        self.segmentation_time = 0.0
        self.compositing_time = 0.0
        self.preprocessing_time = 0.0
        self.frame_count = 0
        
        # Process the video using parent class method
        log_info("Starting standard video processing with background replacement", "BackgroundReplacer")
        
        success = self.process_video(output_video_path, job_id)
        
        if success:
            # Validate output file was created
            if not os.path.exists(output_video_path):
                error_msg = f"Output file was not created: {output_video_path}"
                log_error(error_msg, "BackgroundReplacer")
                return {"success": False, "error_message": error_msg}
            
            file_size = os.path.getsize(output_video_path)
            if file_size == 0:
                error_msg = f"Output file is empty: {output_video_path}"
                log_error(error_msg, "BackgroundReplacer")
                return {"success": False, "error_message": error_msg}
            
            # Log performance stats
            self._log_performance_stats()
            
            log_info(f"Standard background replacement completed successfully: {output_video_path} ({file_size} bytes)", "BackgroundReplacer")
            
            return {
                "success": True,
                "output_path": output_video_path,
                "file_size": file_size,
                "frames_processed": self.frame_count,
                "processing_time": self.segmentation_time + self.compositing_time
            }
        else:
            error_msg = "Standard video processing failed during frame processing"
            log_error(error_msg, "BackgroundReplacer")
            return {"success": False, "error_message": error_msg}
    
    def _process_green_screen_workflow(self, input_video_path: str, output_video_path: str, 
                                      background_config: Dict[str, Any], job_id: str = None) -> Dict[str, Any]:
        """Single-stage green screen background replacement workflow"""
        log_info("Starting green screen workflow", "BackgroundReplacer")
        
        # Force green background color
        green_config = background_config.copy()
        green_config['type'] = 'color'
        green_config['color'] = '#00FF00'  # Pure green
        
        # Use standard workflow with green background
        return self._process_standard_workflow(input_video_path, output_video_path, green_config, job_id)
    
    def _process_two_stage_workflow(self, input_video_path: str, output_video_path: str, 
                                   background_config: Dict[str, Any], job_id: str = None) -> Dict[str, Any]:
        """Two-stage workflow: RVM + green screen, then chroma key replacement"""
        import tempfile
        
        log_info("Starting two-stage workflow for custom image background", "BackgroundReplacer")
        
        try:
            # Stage 1: Create green screen version
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_green:
                temp_green_path = temp_green.name
            
            # Progress callback for stage 1
            if hasattr(self, 'progress_callback') and self.progress_callback:
                self.progress_callback(0, "Stage 1: Creating green screen background...")
            
            # Create green screen version
            green_config = {'type': 'color', 'color': '#00FF00'}
            stage1_result = self._process_standard_workflow(input_video_path, temp_green_path, green_config, job_id)
            
            if not stage1_result['success']:
                return stage1_result
            
            # Progress callback for stage 2
            if hasattr(self, 'progress_callback') and self.progress_callback:
                self.progress_callback(50, "Stage 2: Applying chroma key replacement...")
            
            # Stage 2: Apply chroma key replacement
            stage2_result = self._apply_chroma_key_replacement(temp_green_path, output_video_path, 
                                                              background_config, job_id)
            
            # Cleanup temporary file
            try:
                os.unlink(temp_green_path)
            except Exception as e:
                log_warning(f"Failed to cleanup temp file: {e}", "BackgroundReplacer")
            
            return stage2_result
            
        except Exception as e:
            error_msg = f"Two-stage workflow failed: {e}"
            log_error(error_msg, "BackgroundReplacer", e)
            return {"success": False, "error_message": error_msg}
    
    def _apply_chroma_key_replacement(self, green_video_path: str, output_video_path: str, 
                                     background_config: Dict[str, Any], job_id: str = None) -> Dict[str, Any]:
        """Apply chroma key replacement to replace green screen with custom background"""
        try:
            log_info("Applying chroma key replacement", "BackgroundReplacer")
            
            # Load the green screen video
            cap = cv2.VideoCapture(green_video_path)
            if not cap.isOpened():
                return {"success": False, "error_message": "Failed to open green screen video"}
            
            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Load background image
            background_path = background_config.get('path')
            if not background_path or not os.path.exists(background_path):
                return {"success": False, "error_message": "Background image not found"}
            
            background_img = cv2.imread(background_path)
            if background_img is None:
                return {"success": False, "error_message": "Failed to load background image"}
            
            # Resize background to match video dimensions
            background_img = cv2.resize(background_img, (width, height))
            
            # Setup video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_video_path, fourcc, fps, (width, height))
            
            frame_count = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Apply chroma key (green screen removal)
                # Convert to HSV for better color keying
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                
                # Define range for green color
                lower_green = np.array([40, 40, 40])
                upper_green = np.array([80, 255, 255])
                
                # Create mask for green pixels
                mask = cv2.inRange(hsv, lower_green, upper_green)
                
                # Invert mask to get non-green pixels
                mask_inv = cv2.bitwise_not(mask)
                
                # Apply morphological operations to clean up the mask
                kernel = np.ones((3,3), np.uint8)
                mask_inv = cv2.morphologyEx(mask_inv, cv2.MORPH_CLOSE, kernel)
                mask_inv = cv2.morphologyEx(mask_inv, cv2.MORPH_OPEN, kernel)
                
                # Create alpha mask (0-1 range)
                alpha = mask_inv.astype(np.float32) / 255.0
                alpha = np.stack([alpha, alpha, alpha], axis=2)
                
                # Composite the frame
                result_frame = (frame.astype(np.float32) * alpha + 
                               background_img.astype(np.float32) * (1 - alpha)).astype(np.uint8)
                
                out.write(result_frame)
                frame_count += 1
                
                # Update progress
                if hasattr(self, 'progress_callback') and self.progress_callback and total_frames > 0:
                    progress = (frame_count / total_frames) * 100
                    self.progress_callback(50 + (progress * 0.3), f"Chroma key processing: {frame_count}/{total_frames} frames")
            
            # Cleanup
            cap.release()
            out.release()
            
            # Validate output
            if not os.path.exists(output_video_path) or os.path.getsize(output_video_path) == 0:
                return {"success": False, "error_message": "Chroma key replacement failed - no output generated"}
            
            file_size = os.path.getsize(output_video_path)
            log_info(f"Chroma key replacement completed: {frame_count} frames, {file_size} bytes", "BackgroundReplacer")
            
            return {
                "success": True,
                "output_path": output_video_path,
                "file_size": file_size,
                "frames_processed": frame_count
            }
            
        except Exception as e:
            error_msg = f"Chroma key replacement failed: {e}"
            log_error(error_msg, "BackgroundReplacer", e)
            return {"success": False, "error_message": error_msg}
    
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
                try:
                    seg_stats = self.segmenter.get_performance_stats()
                    stats.update({"segmentation_model": seg_stats})
                except Exception as e:
                    log_warning(f"Could not get segmentation stats: {e}", "BackgroundReplacer")
            
            log_info(f"Performance stats: {stats}", "BackgroundReplacer")
    
    def cleanup(self):
        """Enhanced cleanup with segmentation model cleanup (never raises)"""
        try:
            if self.segmenter:
                try:
                    self.segmenter.cleanup()
                except Exception as e:
                    log_error(f"Segmentation model cleanup error: {e}", "BackgroundReplacer", e)
                self.segmenter = None
                
            if hasattr(self, '_previous_mask'):
                delattr(self, '_previous_mask')
                
            # Clear background image to free memory
            if hasattr(self, 'background_image'):
                self.background_image = None
                
            try:
                super().cleanup()
            except Exception as e:
                log_error(f"Parent cleanup error: {e}", "BackgroundReplacer", e)
                
            log_info("AdvancedBackgroundReplacer cleanup completed", "BackgroundReplacer")
            
        except Exception as e:
            log_error(f"Error during cleanup (outer): {e}", "BackgroundReplacer", e)

# Convenience function for easy background replacement
def replace_video_background(input_video_path: str, output_video_path: str,
                           background_config: Dict[str, Any], user_id: int = None,
                           quality: str = "medium", segmentation_model: str = "auto") -> Dict[str, Any]:
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
        Dictionary with success status and details
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
