"""
Advanced Segmentation Models for MyAvatar Background Processing
Ported from Videotix with MyAvatar architecture integration
FIXED: RVM segmentation mask variable bug corrected
"""
import cv2
import numpy as np
import logging
import time
from typing import Optional, Dict, Any, Tuple
from abc import ABC, abstractmethod

# MyAvatar imports
try:
    from app.logger.log_handler import log_info, log_error, log_warning
    from app.config.settings import config
except ImportError:
    # Fallback for development/testing
    def log_info(msg, context): logging.info(f"[{context}] {msg}")
    def log_error(msg, context, exc=None): logging.error(f"[{context}] {msg}")
    def log_warning(msg, context): logging.warning(f"[{context}] {msg}")

    class config:
        ENABLE_GPU = True

# Torch imports with fallback
try:
    import torch
    import torchvision.transforms as transforms
    TORCH_AVAILABLE = True
    log_info("PyTorch available for RVM segmentation", "SegmentationModels")
except ImportError:
    TORCH_AVAILABLE = False
    log_warning("PyTorch not available - RVM segmentation disabled", "SegmentationModels")

logger = logging.getLogger(__name__)

class SegmentationModel(ABC):
    """
    Abstract base class for segmentation models
    Provides common interface for different segmentation approaches
    """

    def __init__(self, enable_gpu: bool = True, model_quality: str = "medium"):
        """
        Initialize segmentation model

        Args:
            enable_gpu: Whether to use GPU acceleration if available
            model_quality: Quality setting ("low", "medium", "high")
        """
        self.enable_gpu = enable_gpu and getattr(config, 'ENABLE_GPU', True)
        self.model_quality = model_quality
        self.device = None
        self.model = None
        self.is_initialized = False

        # Performance tracking
        self.frame_count = 0
        self.total_time = 0.0
        self.initialization_time = 0.0

    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the segmentation model"""
        pass

    @abstractmethod
    def segment_frame(self, frame: np.ndarray, **kwargs) -> np.ndarray:
        """Segment a single frame"""
        pass

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        avg_time = self.total_time / max(1, self.frame_count)
        return {
            "model_type": self.__class__.__name__,
            "frames_processed": self.frame_count,
            "total_time": self.total_time,
            "avg_time_per_frame": avg_time,
            "fps": 1.0 / avg_time if avg_time > 0 else 0,
            "initialization_time": self.initialization_time,
            "device": str(self.device) if self.device else "unknown"
        }

    def cleanup(self):
        """Cleanup model resources (never raises)."""
        try:
            if hasattr(self, 'model') and self.model is not None:
                del self.model
                self.model = None
            if TORCH_AVAILABLE and torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception as e:
            log_error(f"SegmentationModel cleanup error: {e}", self.__class__.__name__, e)

class RVMSegmenter(SegmentationModel):
    """
    RobustVideoMatting segmentation model
    High-quality AI-based human segmentation
    """

    def __init__(self, model_name: str = 'mobilenetv3', enable_gpu: bool = True,
                 model_quality: str = "medium"):
        """
        Initialize RVM segmenter

        Args:
            model_name: RVM model variant ('mobilenetv3', 'resnet50')
            enable_gpu: Whether to use GPU acceleration
            model_quality: Quality setting affecting processing parameters
        """
        super().__init__(enable_gpu, model_quality)
        self.model_name = model_name
        self.rec = [None] * 4  # Recurrent states for temporal consistency

        # Quality-based parameters with aggressive segmentation settings
        if model_quality == "low":
            self.downsample_ratio = 0.25
            self.batch_size = 1
            self.confidence_threshold = 0.3  # More aggressive for low quality
            self.alpha_matting_threshold = 0.7
        elif model_quality == "medium":
            self.downsample_ratio = 0.5
            self.batch_size = 1
            self.confidence_threshold = 0.25  # More aggressive segmentation
            self.alpha_matting_threshold = 0.75  # Higher threshold for cleaner edges
        else:  # high
            self.downsample_ratio = 1.0
            self.batch_size = 1
            self.confidence_threshold = 0.2  # Most aggressive for high quality
            self.alpha_matting_threshold = 0.8
        
        # Morphological cleanup parameters
        self.enable_morphological_cleanup = True
        self.morph_kernel_size = 3
        self.enable_multi_pass = True
        
        # Subject preservation parameters
        self.enable_subject_preservation = True
        self.subject_confidence_threshold = 0.3  # Conservative for subject detection
        self.background_confidence_threshold = self.confidence_threshold  # Aggressive for background
        self.subject_dilation_size = 5  # Expand subject mask slightly for safety
        
        # Hard binary compositing (no gradual transparency)
        self.use_hard_binary_mask = True  # Force binary 0/1 alpha values
        self.binary_threshold = 0.5  # Threshold for binary decision

    def initialize(self) -> bool:
        """Initialize RobustVideoMatting model

        Returns:
            True if successful, False otherwise
        """
        if not TORCH_AVAILABLE:
            log_error("PyTorch not available for RVM segmentation", "RVMSegmenter")
            return False

        import torch
        import sys
        import platform
        import os
        # Deep environment diagnostics
        log_info("🔧 Environment Debug:", "RVMSegmenter")
        log_info(f"   Python version: {sys.version}", "RVMSegmenter")
        log_info(f"   Platform: {platform.platform()} ({platform.machine()})", "RVMSegmenter")
        log_info(f"   PyTorch version: {torch.__version__}", "RVMSegmenter")
        log_info(f"   CUDA available: {torch.cuda.is_available()}", "RVMSegmenter")
        log_info(f"   CUDA device count: {torch.cuda.device_count()}", "RVMSegmenter")
        log_info(f"   Device being used: {torch.device('cuda' if torch.cuda.is_available() else 'cpu')}", "RVMSegmenter")
        log_info(f"   CWD: {os.getcwd()}", "RVMSegmenter")
        log_info(f"   ENV PATH: {os.environ.get('PATH','')}", "RVMSegmenter")
        log_info(f"   ENV PYTHONPATH: {os.environ.get('PYTHONPATH','')}", "RVMSegmenter")

        start_time = time.time()

        try:
            log_info(f"Initializing RVM model: {self.model_name}", "RVMSegmenter")

            # Determine device
            if self.enable_gpu and torch.cuda.is_available():
                self.device = torch.device('cuda')
                gpu_name = torch.cuda.get_device_name(0)
                log_info(f"Using GPU: {gpu_name}", "RVMSegmenter")
            else:
                self.device = torch.device('cpu')
                log_warning("Using CPU for RVM segmentation", "RVMSegmenter")

            # Load model from local patched implementation
            from app.video_enhancer.rvm_pytorch2_compatible import model as rvm_local
            if self.model_name == 'mobilenetv3':
                self.model = rvm_local.MattingNetwork(variant='mobilenetv3')
            elif self.model_name == 'resnet50':
                self.model = rvm_local.MattingNetwork(variant='resnet50')
            else:
                raise ValueError(f"Unknown RVM model variant: {self.model_name}")
            self.model = self.model.to(self.device)
            self.model.eval()

            # Warm up model with dummy input
            self._warmup_model()

            self.is_initialized = True
            self.initialization_time = time.time() - start_time

            log_info(f"RVM model initialized successfully in {self.initialization_time:.2f}s", "RVMSegmenter")
            return True

        except Exception as e:
            log_error(f"Failed to initialize RVM model: {e}", "RVMSegmenter", e)
            self.is_initialized = False
            return False

    def _warmup_model(self):
        """Warm up model with dummy input for better performance"""
        try:
            with torch.no_grad():
                # Create dummy input tensor
                dummy_input = torch.randn(1, 3, 256, 256, device=self.device)
                # Run forward pass to warm up model
                self.model(dummy_input, *self.rec)
                log_info("RVM model warmed up successfully", "RVMSegmenter")
        except Exception as e:
            log_warning(f"Model warmup failed: {e}", "RVMSegmenter")

    @torch.no_grad()
    def segment_frame(self, frame: np.ndarray, downsample_ratio: float = None) -> np.ndarray:
        """
        Segment a single frame using RVM

        Args:
            frame: Input frame (BGR format)
            downsample_ratio: Override downsample ratio for this frame

        Returns:
            Segmentation mask as numpy array (H, W) with values 0-255
        """
        if not self.is_initialized:
            if not self.initialize():
                log_error("RVM model not initialized, returning empty mask", "RVMSegmenter")
                return np.zeros(frame.shape[:2], dtype=np.uint8)

        start_time = time.time()

        # FIXED: Initialize mask variable to avoid UnboundLocalError
        mask = np.zeros(frame.shape[:2], dtype=np.uint8)

        try:
            # FIXED: Ensure downsample_ratio is a Python float, not tensor
            if downsample_ratio is None:
                downsample_ratio = float(self.downsample_ratio)
            else:
                downsample_ratio = float(downsample_ratio)

            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Get original dimensions
            original_height, original_width = frame.shape[:2]
            
            # Resize frame for processing if needed
            if downsample_ratio != 1.0:
                new_width = int(original_width * downsample_ratio)
                new_height = int(original_height * downsample_ratio)
                frame_rgb = cv2.resize(frame_rgb, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
            
            # Convert to tensor and normalize
            frame_tensor = torch.from_numpy(frame_rgb).permute(2, 0, 1).float() / 255.0
            frame_tensor = frame_tensor.unsqueeze(0).to(self.device)
            
            # FIXED: Ensure recurrent states are properly initialized as tensors or None
            if any(r is not None and not isinstance(r, torch.Tensor) for r in self.rec):
                self.rec = [None] * 4  # Reset recurrent states
            
            # Run RVM inference with proper tensor handling
            with torch.no_grad():
                # FIXED: Pass downsample_ratio as a scalar value, not tensor
                pha, *self.rec = self.model(frame_tensor, *self.rec, downsample_ratio)
                
                # Convert alpha matte to mask with two-stage processing
                alpha = pha.squeeze().cpu().numpy()
                
                # 🔍 DEBUG: Log raw RVM alpha values
                log_info(f"🔍 RAW RVM ALPHA DEBUG:", "RVMSegmenter")
                log_info(f"   - Alpha shape: {alpha.shape}", "RVMSegmenter")
                log_info(f"   - Alpha dtype: {alpha.dtype}", "RVMSegmenter")
                log_info(f"   - Alpha range: {alpha.min():.3f} to {alpha.max():.3f}", "RVMSegmenter")
                log_info(f"   - Alpha mean: {alpha.mean():.3f}", "RVMSegmenter")
                log_info(f"   - Pixels > 0.5: {(alpha > 0.5).sum()}/{alpha.size} ({(alpha > 0.5).sum()/alpha.size*100:.1f}%)", "RVMSegmenter")
                log_info(f"   - Pixels > 0.3: {(alpha > 0.3).sum()}/{alpha.size} ({(alpha > 0.3).sum()/alpha.size*100:.1f}%)", "RVMSegmenter")
                log_info(f"   - Pixels > 0.7: {(alpha > 0.7).sum()}/{alpha.size} ({(alpha > 0.7).sum()/alpha.size*100:.1f}%)", "RVMSegmenter")
                
                # 🔥 CRITICAL FIX: SMART MULTI-LEVEL THRESHOLDING WITH EDGE PRESERVATION
                # This preserves hair, glasses, and fine details while maintaining binary output for green screen
                if self.use_hard_binary_mask:
                    log_info(f"🔥 APPLYING SMART MULTI-LEVEL THRESHOLDING", "RVMSegmenter")
                    
                    # STEP 1: Edge-preserving bilateral filtering to smooth alpha while preserving fine details
                    # This helps preserve hair and glasses edges before thresholding
                    alpha_8bit = (alpha * 255).astype(np.uint8)
                    alpha_filtered = cv2.bilateralFilter(alpha_8bit, d=9, sigmaColor=75, sigmaSpace=75)
                    alpha_smooth = alpha_filtered.astype(np.float32) / 255.0
                    
                    log_info(f"🔍 EDGE-PRESERVING FILTER DEBUG:", "RVMSegmenter")
                    log_info(f"   - Original alpha range: {alpha.min():.3f} to {alpha.max():.3f}", "RVMSegmenter")
                    log_info(f"   - Filtered alpha range: {alpha_smooth.min():.3f} to {alpha_smooth.max():.3f}", "RVMSegmenter")
                    
                    # STEP 2: Smart multi-level thresholding for better detail preservation
                    # Use graduated thresholds to capture different confidence levels
                    binary_alpha = np.zeros_like(alpha_smooth, dtype=np.float32)
                    
                    # High confidence: definitely person (core body, face)
                    definitely_person = alpha_smooth > 0.8
                    binary_alpha[definitely_person] = 1.0
                    
                    # Medium confidence: probably person (hair, glasses, clothing edges)
                    probably_person = np.logical_and(alpha_smooth > 0.3, alpha_smooth <= 0.8)
                    binary_alpha[probably_person] = 1.0
                    
                    # Low confidence: edge cleanup with morphological decision
                    edge_pixels = np.logical_and(alpha_smooth > 0.1, alpha_smooth <= 0.3)
                    
                    # For edge pixels, use local context to decide
                    if edge_pixels.sum() > 0:
                        # Create a small kernel to check local neighborhood
                        kernel_check = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                        
                        # If edge pixel is surrounded by person pixels, include it
                        person_dilated = cv2.dilate((binary_alpha > 0.5).astype(np.uint8), kernel_check, iterations=1)
                        edge_include = np.logical_and(edge_pixels, person_dilated > 0)
                        binary_alpha[edge_include] = 1.0
                    
                    # Very low confidence: definitely background
                    definitely_background = alpha_smooth <= 0.1
                    binary_alpha[definitely_background] = 0.0
                    
                    # 🔍 DEBUG: Multi-level thresholding results
                    log_info(f"🔍 MULTI-LEVEL THRESHOLDING DEBUG:", "RVMSegmenter")
                    log_info(f"   - Definitely person (>0.8): {definitely_person.sum()}/{alpha.size} ({definitely_person.sum()/alpha.size*100:.1f}%)", "RVMSegmenter")
                    log_info(f"   - Probably person (0.3-0.8): {probably_person.sum()}/{alpha.size} ({probably_person.sum()/alpha.size*100:.1f}%)", "RVMSegmenter")
                    log_info(f"   - Edge pixels (0.1-0.3): {edge_pixels.sum()}/{alpha.size} ({edge_pixels.sum()/alpha.size*100:.1f}%)", "RVMSegmenter")
                    log_info(f"   - Definitely background (<=0.1): {definitely_background.sum()}/{alpha.size} ({definitely_background.sum()/alpha.size*100:.1f}%)", "RVMSegmenter")
                    
                    # Update alpha with the smart thresholded result
                    alpha = binary_alpha
                    
                    # STEP 3: AGGRESSIVE MORPHOLOGICAL OPERATIONS TO FILL MISSING SUBJECT AREAS
                    # The RVM is missing large chunks of the person, so we need aggressive hole filling
                    log_info(f"🔧 APPLYING AGGRESSIVE MORPHOLOGICAL CLEANUP", "RVMSegmenter")
                    
                    # Convert to uint8 for morphological operations
                    alpha_uint8 = (alpha * 255).astype(np.uint8)
                    
                    # STEP 3A: Fill small holes in the subject
                    kernel_fill = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))  # Larger kernel for bigger holes
                    alpha_filled = cv2.morphologyEx(alpha_uint8, cv2.MORPH_CLOSE, kernel_fill)
                    
                    # STEP 3B: Connect nearby subject areas (for hair, clothing)
                    kernel_connect = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
                    alpha_connected = cv2.morphologyEx(alpha_filled, cv2.MORPH_DILATE, kernel_connect, iterations=2)
                    alpha_connected = cv2.morphologyEx(alpha_connected, cv2.MORPH_ERODE, kernel_connect, iterations=1)
                    
                    # STEP 3C: Remove small background noise
                    kernel_clean = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
                    alpha_cleaned = cv2.morphologyEx(alpha_connected, cv2.MORPH_OPEN, kernel_clean)
                    
                    # STEP 3D: Final hole filling pass
                    kernel_final = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
                    alpha_final = cv2.morphologyEx(alpha_cleaned, cv2.MORPH_CLOSE, kernel_final)
                    
                    # Convert back to float32
                    alpha_morphed = alpha_final.astype(np.float32) / 255.0
                    
                    # Ensure strict binary after morphological operations
                    alpha_morphed = (alpha_morphed > 0.5).astype(np.float32)
                    
                    # 🔍 DEBUG: Compare before and after morphological operations
                    log_info(f"🔍 MORPHOLOGICAL OPERATIONS DEBUG:", "RVMSegmenter")
                    log_info(f"   - Before morph subject pixels: {(alpha == 1.0).sum()}/{alpha.size} ({(alpha == 1.0).sum()/alpha.size*100:.1f}%)", "RVMSegmenter")
                    log_info(f"   - After morph subject pixels: {(alpha_morphed == 1.0).sum()}/{alpha_morphed.size} ({(alpha_morphed == 1.0).sum()/alpha_morphed.size*100:.1f}%)", "RVMSegmenter")
                    log_info(f"   - Subject area increase: {((alpha_morphed == 1.0).sum() - (alpha == 1.0).sum())}/{alpha.size} ({((alpha_morphed == 1.0).sum() - (alpha == 1.0).sum())/alpha.size*100:.1f}%)", "RVMSegmenter")
                    
                    # Update alpha with morphologically cleaned result
                    alpha = alpha_morphed
                    
                    # 🔍 DEBUG: Verify final binary conversion
                    log_info(f"🔍 FINAL BINARY CONVERSION DEBUG:", "RVMSegmenter")
                    log_info(f"   - Final alpha range: {alpha.min():.3f} to {alpha.max():.3f}", "RVMSegmenter")
                    log_info(f"   - Final unique values: {np.unique(alpha)}", "RVMSegmenter")
                    log_info(f"   - Subject pixels: {(alpha == 1.0).sum()}/{alpha.size} ({(alpha == 1.0).sum()/alpha.size*100:.1f}%)", "RVMSegmenter")
                    log_info(f"   - Background pixels: {(alpha == 0.0).sum()}/{alpha.size} ({(alpha == 0.0).sum()/alpha.size*100:.1f}%)", "RVMSegmenter")
                    
                    # Verify strict binary nature
                    unique_vals = np.unique(alpha)
                    if not np.array_equal(unique_vals, [0.0, 1.0]) and not np.array_equal(unique_vals, [0.0]) and not np.array_equal(unique_vals, [1.0]):
                        log_error(f"🚨 CRITICAL: Smart binary conversion failed! Values: {unique_vals}", "RVMSegmenter")
                        # Emergency fix
                        alpha = (alpha > 0.5).astype(np.float32)
                        log_info(f"   - Emergency binary fix applied: {np.unique(alpha)}", "RVMSegmenter")
                
                # CRITICAL FIX: STRICT BINARY THRESHOLDING FOR GREEN SCREEN OUTPUT
                # This fixes the alpha transparency issue where green shows through the subject
                if self.use_hard_binary_mask:
                    log_info(f"🎭 APPLYING BINARY THRESHOLDING (threshold: {self.subject_confidence_threshold})", "RVMSegmenter")
                    
                    # STEP 1: Apply strict binary threshold to RVM alpha matte
                    # Convert gradual transparency (0.3-0.7) to binary solid/transparent (0.0 or 1.0)
                    binary_mask = (alpha > self.subject_confidence_threshold).astype(np.uint8)
                    
                    # 🔍 DEBUG: Track binary thresholding
                    log_info(f"🔍 BINARY THRESHOLD DEBUG:", "RVMSegmenter")
                    log_info(f"   - Threshold used: {self.subject_confidence_threshold}", "RVMSegmenter")
                    log_info(f"   - Binary mask shape: {binary_mask.shape}", "RVMSegmenter")
                    log_info(f"   - Binary mask dtype: {binary_mask.dtype}", "RVMSegmenter")
                    log_info(f"   - Binary mask range: {binary_mask.min()} to {binary_mask.max()}", "RVMSegmenter")
                    log_info(f"   - Subject pixels (1s): {binary_mask.sum()}/{binary_mask.size} ({binary_mask.sum()/binary_mask.size*100:.1f}%)", "RVMSegmenter")
                    log_info(f"   - Background pixels (0s): {(binary_mask == 0).sum()}/{binary_mask.size} ({(binary_mask == 0).sum()/binary_mask.size*100:.1f}%)", "RVMSegmenter")
                    
                    # STEP 2: Enhanced morphological operations for clean binary mask
                    # Use larger kernels for better hole filling and edge cleanup
                    kernel_large = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
                    kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                    
                    # Close small gaps in the subject (fill holes)
                    binary_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_CLOSE, kernel_large, iterations=3)
                    
                    # Remove small noise outside subject
                    binary_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_OPEN, kernel_small, iterations=2)
                    
                    # Final hole filling pass
                    binary_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_CLOSE, kernel_large, iterations=2)
                    
                    log_info(f"🎭 After enhanced morphological cleanup: {binary_mask.sum()} pixels in final subject mask", "RVMSegmenter")
                    
                    # STEP 3: Apply edge refinement specifically for binary masks
                    binary_mask_refined = self._refine_binary_edges(binary_mask.astype(np.float32))
                    
                    # STEP 4: Convert to strict binary alpha values (0.0 or 1.0 ONLY)
                    final_alpha = binary_mask_refined.astype(np.float32)
                    
                    # STEP 5: CRITICAL - Force strict binary values to prevent transparency bleeding
                    # This ensures no gradual transparency that causes green screen bleeding
                    final_alpha = (final_alpha > 0.5).astype(np.float32)
                    
                    # STEP 6: Verification - ensure ONLY 0.0 and 1.0 values exist
                    unique_vals = np.unique(final_alpha)
                    log_info(f"🎭 Final alpha unique values: {unique_vals} (MUST be [0.0, 1.0] only)", "RVMSegmenter")
                    
                    if len(unique_vals) > 2:
                        log_error(f"🚨 CRITICAL: Non-binary alpha values detected: {unique_vals}", "RVMSegmenter")
                        # Emergency fix - force binary
                        final_alpha = (final_alpha > 0.0).astype(np.float32)
                        unique_vals = np.unique(final_alpha)
                        log_info(f"🎭 Emergency binary fix applied: {unique_vals}", "RVMSegmenter")
                    
                    solid_pixels = (final_alpha == 1.0).sum()
                    transparent_pixels = (final_alpha == 0.0).sum()
                    log_info(f"🎭 Final mask composition: {solid_pixels} solid, {transparent_pixels} transparent pixels", "RVMSegmenter")
                    
                    # 🔍 DEBUG: Final alpha verification before mask conversion
                    log_info(f"🔍 FINAL ALPHA DEBUG:", "RVMSegmenter")
                    log_info(f"   - Final alpha shape: {final_alpha.shape}", "RVMSegmenter")
                    log_info(f"   - Final alpha dtype: {final_alpha.dtype}", "RVMSegmenter")
                    log_info(f"   - Final alpha range: {final_alpha.min():.3f} to {final_alpha.max():.3f}", "RVMSegmenter")
                    log_info(f"   - Final alpha mean: {final_alpha.mean():.3f}", "RVMSegmenter")
                    log_info(f"   - Final unique values: {np.unique(final_alpha)}", "RVMSegmenter")
                    
                    # Convert final_alpha to 0-255 mask for output
                    mask = (final_alpha * 255).astype(np.uint8)
                    
                    # 🔍 DEBUG: Final mask output verification
                    log_info(f"🔍 FINAL MASK OUTPUT DEBUG:", "RVMSegmenter")
                    log_info(f"   - Output mask shape: {mask.shape}", "RVMSegmenter")
                    log_info(f"   - Output mask dtype: {mask.dtype}", "RVMSegmenter")
                    log_info(f"   - Output mask range: {mask.min()} to {mask.max()}", "RVMSegmenter")
                    log_info(f"   - Output unique values: {np.unique(mask)}", "RVMSegmenter")
                    log_info(f"   - Should be [0, 255] only for binary: {set(np.unique(mask)) == {0, 255}}", "RVMSegmenter")
                    
                else:
                    # Fallback to original multi-pass processing
                    confidence_threshold = self.confidence_threshold
                    alpha_threshold = self.alpha_matting_threshold
                    
                    if self.enable_multi_pass:
                        # First pass: aggressive threshold
                        mask_pass1 = (alpha > confidence_threshold).astype(np.float32)
                        
                        # Second pass: refine edges with alpha matting threshold
                        mask_pass2 = np.where(alpha > alpha_threshold, 1.0, 
                                             np.where(alpha > confidence_threshold, alpha, 0.0))
                        
                        # Combine passes for final mask
                        final_alpha = np.maximum(mask_pass1 * 0.7, mask_pass2)
                    else:
                        # Single pass with aggressive threshold
                        final_alpha = np.where(alpha > alpha_threshold, 1.0,
                                               np.where(alpha > confidence_threshold, alpha, 0.0))
                
                # VERIFY BINARY COMPOSITING BEFORE CONVERTING TO 8-BIT
                if self.use_hard_binary_mask:
                    binary_verification = self._verify_binary_compositing(final_alpha)
                    if not binary_verification.get("binary_compliance", False):
                        log_warning("Binary compositing verification failed - forcing binary values", "RVMSegmenter")
                        # Force strict binary values as fallback
                        final_alpha = (final_alpha > 0.5).astype(np.float32)
                
                # Convert to 8-bit mask
                mask = (final_alpha * 255).astype(np.uint8)
                
                # Apply morphological cleanup for cleaner edges (only if not using hard binary)
                if self.enable_morphological_cleanup and not self.use_hard_binary_mask:
                    mask = self._apply_morphological_cleanup(mask)
                elif self.use_hard_binary_mask:
                    log_info("Skipping morphological cleanup to preserve hard binary edges", "RVMSegmenter")
                
                # Debug logging for diagnostics
                if self.enable_subject_preservation:
                    log_info(f"Subject confidence threshold: {self.subject_confidence_threshold}", "RVMSegmenter")
                    log_info(f"Background confidence threshold: {self.background_confidence_threshold}", "RVMSegmenter")
                else:
                    log_info(f"RVM Model confidence threshold: {self.confidence_threshold}", "RVMSegmenter")
                log_info(f"Alpha matting threshold: {self.alpha_matting_threshold}", "RVMSegmenter")
                log_info(f"Segmentation mask min/max values: {alpha.min():.3f}/{alpha.max():.3f}", "RVMSegmenter")
                log_info(f"Final mask coverage: {(final_alpha > 0.1).sum() / final_alpha.size * 100:.1f}%", "RVMSegmenter")
                
                # Resize mask back to original size if needed
                if downsample_ratio != 1.0 or mask.shape != (original_height, original_width):
                    mask = cv2.resize(mask, (original_width, original_height), interpolation=cv2.INTER_LINEAR)

            # Update performance tracking
            self.frame_count += 1
            self.total_time += time.time() - start_time

            return mask

        except Exception as e:
            log_error(f"Error in RVM segmentation: {e}", "RVMSegmenter", e)
            # Return the initialized empty mask on error
            return mask
    
    def _apply_morphological_cleanup(self, mask: np.ndarray) -> np.ndarray:
        """
        Apply morphological operations to clean up segmentation mask
        
        Args:
            mask: Input segmentation mask (0-255)
            
        Returns:
            Cleaned up mask
        """
        try:
            # Create morphological kernel
            kernel_size = self.morph_kernel_size
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
            
            # Apply morphological operations for cleanup
            # 1. Opening: Remove small noise/holes
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
            
            # 2. Closing: Fill small gaps
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
            
            # 3. Median filter for additional noise reduction
            mask = cv2.medianBlur(mask, 3)
            
            # 4. Gaussian blur for smoother edges (very light)
            mask = cv2.GaussianBlur(mask, (3, 3), 0.5)
            
            # 5. Edge refinement: dilate then erode for smoother boundaries
            edge_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
            mask = cv2.dilate(mask, edge_kernel, iterations=1)
            mask = cv2.erode(mask, edge_kernel, iterations=1)
            
            return mask
            
        except Exception as e:
            log_error(f"Error in morphological cleanup: {e}", "RVMSegmenter", e)
            return mask  # Return original mask if cleanup fails
    
    def _verify_binary_compositing(self, alpha_values: np.ndarray) -> Dict[str, Any]:
        """
        Verify that the alpha values are strictly binary (0.0 or 1.0)
        
        Args:
            alpha_values: The alpha channel values to verify
            
        Returns:
            Dictionary with verification results
        """
        try:
            # Check for binary values only
            unique_values = np.unique(alpha_values)
            is_binary = np.all((unique_values == 0.0) | (unique_values == 1.0))
            
            # Count pixels
            solid_pixels = (alpha_values == 1.0).sum()
            transparent_pixels = (alpha_values == 0.0).sum()
            partial_pixels = ((alpha_values > 0.0) & (alpha_values < 1.0)).sum()
            
            verification = {
                "is_strictly_binary": is_binary,
                "unique_values": unique_values.tolist(),
                "solid_pixels": int(solid_pixels),
                "transparent_pixels": int(transparent_pixels),
                "partial_transparency_pixels": int(partial_pixels),
                "total_pixels": alpha_values.size,
                "binary_compliance": (partial_pixels == 0)
            }
            
            if verification["binary_compliance"]:
                log_info("✅ BINARY VERIFICATION PASSED: No gradual transparency detected", "RVMSegmenter")
                log_info(f"   Solid pixels: {solid_pixels}, Transparent pixels: {transparent_pixels}", "RVMSegmenter")
            else:
                log_warning(f"⚠️ BINARY VERIFICATION FAILED: {partial_pixels} pixels have partial transparency", "RVMSegmenter")
                log_warning(f"   Unique values found: {unique_values}", "RVMSegmenter")
            
            return verification
            
        except Exception as e:
            log_error(f"Error in binary verification: {e}", "RVMSegmenter", e)
            return {"is_strictly_binary": False, "error": str(e)}
    
    def _refine_binary_edges(self, binary_mask: np.ndarray) -> np.ndarray:
        """
        Apply edge refinement specifically for binary masks while maintaining strict binary values
        CRITICAL: This method MUST NOT introduce gradual transparency for green screen output
        
        Args:
            binary_mask: Binary mask (0 or 1 values only)
            
        Returns:
            Refined binary mask (strictly 0.0 or 1.0 values only)
        """
        try:
            # Convert to uint8 for OpenCV operations
            mask_uint8 = (binary_mask * 255).astype(np.uint8)
            
            # Apply median filter to remove salt-and-pepper noise
            # This preserves binary nature while cleaning noise
            mask_uint8 = cv2.medianBlur(mask_uint8, 3)
            
            # CRITICAL: Apply minimal Gaussian blur with immediate re-thresholding
            # This smooths edges but IMMEDIATELY converts back to binary to prevent transparency
            mask_uint8 = cv2.GaussianBlur(mask_uint8, (3, 3), 0.8)  # Reduced sigma for minimal blur
            _, mask_uint8 = cv2.threshold(mask_uint8, 127, 255, cv2.THRESH_BINARY)
            
            # Convert back to binary float and FORCE binary values
            refined_mask = (mask_uint8 > 127).astype(np.float32)
            
            # CRITICAL VERIFICATION: Ensure no gradual values were introduced
            unique_vals = np.unique(refined_mask)
            if len(unique_vals) > 2:
                log_warning(f"🚨 Edge refinement introduced non-binary values: {unique_vals}, forcing binary", "RVMSegmenter")
                refined_mask = (refined_mask > 0.5).astype(np.float32)
            
            log_info("✅ Applied binary edge refinement (no transparency bleeding)", "RVMSegmenter")
            return refined_mask
            
        except Exception as e:
            log_error(f"Error in edge refinement: {e}", "RVMSegmenter", e)
            return binary_mask
    
    def set_segmentation_aggressiveness(self, aggressiveness: str = "medium"):
        """
        Dynamically adjust segmentation parameters for different levels of aggressiveness
        Now with subject preservation - only background removal becomes more aggressive
        
        Args:
            aggressiveness: "conservative", "medium", "aggressive", or "extreme"
        """
        if aggressiveness == "conservative":
            # Conservative: Safer subject detection, less aggressive binary cutoff
            self.subject_confidence_threshold = 0.4
            self.background_confidence_threshold = 0.5
            self.alpha_matting_threshold = 0.6
            self.enable_multi_pass = False
            self.morph_kernel_size = 2
            self.subject_dilation_size = 3
            self.use_hard_binary_mask = True  # Always use binary for solid subjects
        elif aggressiveness == "medium":
            # Medium: Balanced binary approach (default)
            self.subject_confidence_threshold = 0.3
            self.background_confidence_threshold = 0.25
            self.alpha_matting_threshold = 0.75
            self.enable_multi_pass = True
            self.morph_kernel_size = 3
            self.subject_dilation_size = 5
            self.use_hard_binary_mask = True  # Always use binary for solid subjects
        elif aggressiveness == "aggressive":
            # Aggressive: More aggressive subject detection for binary cutoff
            self.subject_confidence_threshold = 0.25
            self.background_confidence_threshold = 0.15
            self.alpha_matting_threshold = 0.8
            self.enable_multi_pass = True
            self.morph_kernel_size = 4
            self.subject_dilation_size = 6
            self.use_hard_binary_mask = True  # Always use binary for solid subjects
        elif aggressiveness == "extreme":
            # Extreme: Most aggressive binary cutoff, maximum subject preservation
            self.subject_confidence_threshold = 0.2
            self.background_confidence_threshold = 0.1
            self.alpha_matting_threshold = 0.9
            self.enable_multi_pass = True
            self.morph_kernel_size = 5
            self.subject_dilation_size = 8
            self.use_hard_binary_mask = True  # Always use binary for solid subjects
        
        # Update the main confidence threshold for backward compatibility
        self.confidence_threshold = self.background_confidence_threshold
        
        log_info(f"Segmentation aggressiveness set to {aggressiveness}: "
                f"subject_threshold={self.subject_confidence_threshold}, "
                f"background_threshold={self.background_confidence_threshold}, "
                f"alpha={self.alpha_matting_threshold}", 
                "RVMSegmenter")

class MediaPipeSegmenter(SegmentationModel):
    """
    MediaPipe-based segmentation model
    Good balance between quality and performance
    """

    def __init__(self, enable_gpu: bool = True, model_quality: str = "medium"):
        """Initialize MediaPipe segmenter"""
        super().__init__(enable_gpu, model_quality)
        self.selfie_segmentation = None

        # Quality-based parameters
        if model_quality == "low":
            self.model_selection = 0  # Lighter model
            self.min_detection_confidence = 0.3
        else:
            self.model_selection = 1
            self.min_detection_confidence = 0.5

    def initialize(self) -> bool:
        """Initialize MediaPipe segmentation"""
        try:
            import mediapipe as mp

            start_time = time.time()
            log_info("Initializing MediaPipe segmentation", "MediaPipeSegmenter")

            mp_selfie_segmentation = mp.solutions.selfie_segmentation
            self.selfie_segmentation = mp_selfie_segmentation.SelfieSegmentation(
                model_selection=self.model_selection
            )

            self.is_initialized = True
            self.initialization_time = time.time() - start_time

            log_info(f"MediaPipe segmentation initialized in {self.initialization_time:.2f}s", "MediaPipeSegmenter")
            return True

        except ImportError:
            log_error("MediaPipe not available", "MediaPipeSegmenter")
            return False
        except Exception as e:
            log_error(f"Failed to initialize MediaPipe: {e}", "MediaPipeSegmenter", e)
            return False

    def segment_frame(self, frame: np.ndarray, **kwargs) -> np.ndarray:
        """
        Segment frame using MediaPipe

        Args:
            frame: Input frame (BGR format)

        Returns:
            Segmentation mask as numpy array (H, W) with values 0-255
        """
        if not self.is_initialized:
            if not self.initialize():
                log_error("MediaPipe segmentation not initialized, returning empty mask", "MediaPipeSegmenter")
                return np.zeros(frame.shape[:2], dtype=np.uint8)

        try:
            start_time = time.time()
            
            # Process frame with MediaPipe
            results = self.selfie_segmentation.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            
            if results.segmentation_mask is not None:
                # Convert to binary mask
                mask = (results.segmentation_mask > 0.5).astype(np.uint8) * 255
            else:
                mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            
            # Update performance tracking
            self.frame_count += 1
            self.total_time += time.time() - start_time
            
            return mask
            
        except Exception as e:
            log_error(f"Error in MediaPipe segmentation: {e}", "MediaPipeSegmenter", e)
            return np.zeros(frame.shape[:2], dtype=np.uint8)

    def cleanup(self):
        """Cleanup MediaPipe resources"""
        try:
            if self.selfie_segmentation:
                self.selfie_segmentation.close()
                self.selfie_segmentation = None
            super().cleanup()
        except Exception as e:
            log_error(f"MediaPipe cleanup error: {e}", "MediaPipeSegmenter", e)

class FallbackSegmenter(SegmentationModel):
    """
    OpenCV-based fallback segmentation
    Basic but reliable when AI models are not available
    """

    def __init__(self, enable_gpu: bool = True, model_quality: str = "medium"):
        """Initialize fallback segmenter"""
        super().__init__(enable_gpu, model_quality)

        # Quality-based parameters
        if model_quality == "low":
            self.blur_kernel = (3, 3)
            self.morph_kernel = (3, 3)
            self.contour_count = 2
        elif model_quality == "medium":
            self.blur_kernel = (5, 5)
            self.morph_kernel = (5, 5)
            self.contour_count = 3
        else:  # high
            self.blur_kernel = (7, 7)
            self.morph_kernel = (7, 7)
            self.contour_count = 5

    def initialize(self) -> bool:
        """Initialize fallback segmenter"""
        self.is_initialized = True
        self.initialization_time = 0.0
        log_info("Fallback segmentation initialized", "FallbackSegmenter")
        return True

    def segment_frame(self, frame: np.ndarray, **kwargs) -> np.ndarray:
        """
        Segment frame using OpenCV methods

        Args:
            frame: Input frame (BGR format)

        Returns:
            Segmentation mask as numpy array (H, W) with values 0-255
        """
        if not self.is_initialized:
            self.initialize()

        start_time = time.time()

        try:
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Apply Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(gray, self.blur_kernel, 0)

            # Simple thresholding to create mask
            _, mask = cv2.threshold(blurred, 127, 255, cv2.THRESH_BINARY)

            # Find contours and fill the largest ones
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                contours = sorted(contours, key=cv2.contourArea, reverse=True)[:self.contour_count]
                mask = np.zeros_like(mask)
                for contour in contours:
                    cv2.drawContours(mask, [contour], -1, 255, -1)

                # Apply morphological operations to clean up mask
                kernel = np.ones(self.morph_kernel, np.uint8)
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

                # Apply Gaussian blur for smoother edges
                mask = cv2.GaussianBlur(mask, (3, 3), 1)

            # Update performance tracking
            self.frame_count += 1
            self.total_time += time.time() - start_time

            return mask

        except Exception as e:
            log_error(f"Error in fallback segmentation: {e}", "FallbackSegmenter", e)
            return np.zeros(frame.shape[:2], dtype=np.uint8)

class SegmentationModelFactory:
    """
    Factory class for creating segmentation models
    Automatically selects best available model based on system capabilities
    """

    @staticmethod
    def create_segmenter(preferred_model: str = "auto", enable_gpu: bool = True,
                        model_quality: str = "medium") -> SegmentationModel:
        """
        Create segmentation model based on preferences and availability

        Args:
            preferred_model: "rvm", "mediapipe", "fallback", or "auto"
            enable_gpu: Whether to use GPU acceleration
            model_quality: Quality setting ("low", "medium", "high")

        Returns:
            Initialized segmentation model
        """

        if preferred_model == "auto":
            # Clean migration: MatAnyone primary, RVM fallback
            models_to_try = ["matanyone", "rvm", "fallback"]
        else:
            models_to_try = [preferred_model, "fallback"]  # Always have fallback

        for model_type in models_to_try:
            try:
                if model_type == "matanyone":
                    try:
                        segmenter = MatAnyoneSegmenter(enable_gpu=enable_gpu, model_quality=model_quality)
                        if segmenter.initialize():
                            log_info("🚀 Using MatAnyone segmentation (CVPR 2025)", "SegmentationFactory")
                            return segmenter
                    except Exception as e:
                        log_warning(f"MatAnyone not available, falling back: {e}", "SegmentationFactory")
                        continue

                elif model_type == "rvm" and TORCH_AVAILABLE:
                    segmenter = RVMSegmenter(enable_gpu=enable_gpu, model_quality=model_quality)
                    if segmenter.initialize():
                        log_info("Using RobustVideoMatting segmentation", "SegmentationFactory")
                        return segmenter

                elif model_type == "mediapipe":
                    segmenter = MediaPipeSegmenter(enable_gpu=enable_gpu, model_quality=model_quality)
                    if segmenter.initialize():
                        log_info("Using MediaPipe segmentation", "SegmentationFactory")
                        return segmenter

                elif model_type == "fallback":
                    segmenter = FallbackSegmenter(enable_gpu=enable_gpu, model_quality=model_quality)
                    if segmenter.initialize():
                        log_info("Using OpenCV fallback segmentation", "SegmentationFactory")
                        return segmenter

            except Exception as e:
                log_warning(f"Failed to initialize {model_type} segmentation: {e}", "SegmentationFactory")
                continue

        # If we get here, no models worked
        raise RuntimeError("No segmentation models could be initialized")

# Convenience function for easy model creation
def create_segmentation_model(model_type: str = "auto", enable_gpu: bool = True,
                             quality: str = "medium") -> SegmentationModel:
    """
    Convenience function to create segmentation model

    Args:
        model_type: "matanyone", "rvm", "mediapipe", "fallback", or "auto"
        enable_gpu: Whether to use GPU acceleration
        quality: Quality setting ("low", "medium", "high")

    Returns:
        Initialized segmentation model
    """
    return SegmentationModelFactory.create_segmenter(
        preferred_model=model_type,
        enable_gpu=enable_gpu,
        model_quality=quality
    )

class MatAnyoneSegmenter(SegmentationModel):
    """
    MatAnyone-based segmentation model for superior hair, glasses, and background handling
    Replaces RVM with state-of-the-art video matting technology
    """

    def __init__(self, model_name: str = "PeiqingYang/MatAnyone", enable_gpu: bool = True,
                 model_quality: str = "medium"):
        """
        Initialize MatAnyone segmenter

        Args:
            model_name: MatAnyone model identifier
            enable_gpu: Whether to use GPU acceleration
            model_quality: Quality setting affecting processing parameters
        """
        super().__init__(enable_gpu, model_quality)
        self.model_name = model_name
        self.processor = None
        
        # Quality-based parameters
        if model_quality == "low":
            self.max_size = 720
            self.confidence_threshold = 0.3
        elif model_quality == "medium":
            self.max_size = 1080
            self.confidence_threshold = 0.25
        else:  # high
            self.max_size = 1440
            self.confidence_threshold = 0.2
        
        # MatAnyone-specific settings
        self.temp_dir = None
        self.last_mask_path = None
        self.frame_counter = 0

    def initialize(self) -> bool:
        """
        Initialize MatAnyone processor

        Returns:
            True if successful, False otherwise
        """
        try:
            log_info("🚀 Initializing MatAnyone segmenter...", "MatAnyoneSegmenter")
            
            # Import MatAnyone processor (safe import)
            try:
                from app.video_enhancer.matanyone_processor import MatAnyoneProcessor
                self.processor = MatAnyoneProcessor(self.model_name)
            except ImportError as e:
                log_error(f"MatAnyone processor not available: {e}", "MatAnyoneSegmenter")
                return False
            
            # Create temporary directory for processing
            from pathlib import Path
            self.temp_dir = Path("temp_matanyone_segmentation")
            self.temp_dir.mkdir(exist_ok=True)
            
            log_info("✅ MatAnyone segmenter initialized successfully", "MatAnyoneSegmenter")
            return True
            
        except Exception as e:
            log_error(f"❌ Failed to initialize MatAnyone segmenter: {e}", "MatAnyoneSegmenter")
            return False

    @torch.no_grad()
    def segment_frame(self, frame: np.ndarray, downsample_ratio: float = None) -> np.ndarray:
        """
        Segment frame using MatAnyone for superior hair, glasses, and background handling
        
        Args:
            frame: Input frame (BGR format)
            downsample_ratio: Scaling factor (ignored for MatAnyone, uses max_size instead)
            
        Returns:
            Alpha matte as numpy array (0.0 to 1.0)
        """
        if not self.processor:
            log_error("MatAnyone processor not initialized", "MatAnyoneSegmenter")
            return self._create_fallback_mask(frame)
        
        try:
            self.frame_counter += 1
            log_info(f"🎬 Processing frame {self.frame_counter} with MatAnyone...", "MatAnyoneSegmenter")
            
            # Create temporary video file for this frame
            temp_video_path = self.temp_dir / f"frame_{self.frame_counter}.mp4"
            
            # Save frame as single-frame video
            h, w = frame.shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(str(temp_video_path), fourcc, 1.0, (w, h))
            out.write(frame)
            out.release()
            
            # Create or reuse mask for first frame
            if self.last_mask_path is None or self.frame_counter == 1:
                log_info("🎭 Creating first-frame mask for MatAnyone...", "MatAnyoneSegmenter")
                self.last_mask_path = self.processor.create_simple_first_frame_mask(
                    str(temp_video_path), 
                    str(self.temp_dir / "first_frame_mask.png")
                )
            
            # Process with MatAnyone
            start_time = time.time()
            
            foreground_path, alpha_path = self.processor.processor.process_video(
                input_path=str(temp_video_path),
                mask_path=self.last_mask_path,
                output_path=str(self.temp_dir / f"output_{self.frame_counter}"),
                max_size=self.max_size,
                save_frames=False
            )
            
            processing_time = time.time() - start_time
            
            # Read alpha matte result
            alpha_video = cv2.VideoCapture(alpha_path)
            ret, alpha_frame = alpha_video.read()
            alpha_video.release()
            
            if not ret:
                raise ValueError("Failed to read MatAnyone alpha result")
            
            # Convert to grayscale alpha matte
            if len(alpha_frame.shape) == 3:
                alpha_matte = cv2.cvtColor(alpha_frame, cv2.COLOR_BGR2GRAY)
            else:
                alpha_matte = alpha_frame
            
            # Normalize to 0-1 range
            alpha_matte = alpha_matte.astype(np.float32) / 255.0
            
            # Resize back to original frame size if needed
            if alpha_matte.shape != (h, w):
                alpha_matte = cv2.resize(alpha_matte, (w, h), interpolation=cv2.INTER_LINEAR)
            
            # Clean up temporary files
            try:
                temp_video_path.unlink()
                Path(foreground_path).unlink()
                Path(alpha_path).unlink()
            except:
                pass  # Ignore cleanup errors
            
            # 🔍 DEBUG: Log MatAnyone results
            log_info(f"🔍 MATANYONE SEGMENTATION DEBUG:", "MatAnyoneSegmenter")
            log_info(f"   - Processing time: {processing_time:.3f}s", "MatAnyoneSegmenter")
            log_info(f"   - Alpha shape: {alpha_matte.shape}", "MatAnyoneSegmenter")
            log_info(f"   - Alpha range: {alpha_matte.min():.3f} to {alpha_matte.max():.3f}", "MatAnyoneSegmenter")
            log_info(f"   - Alpha mean: {alpha_matte.mean():.3f}", "MatAnyoneSegmenter")
            log_info(f"   - Subject pixels: {(alpha_matte > 0.5).sum()}/{alpha_matte.size} ({(alpha_matte > 0.5).sum()/alpha_matte.size*100:.1f}%)", "MatAnyoneSegmenter")
            
            log_info(f"✅ MatAnyone segmentation complete for frame {self.frame_counter}", "MatAnyoneSegmenter")
            
            return alpha_matte
            
        except Exception as e:
            log_error(f"❌ MatAnyone segmentation failed for frame {self.frame_counter}: {e}", "MatAnyoneSegmenter")
            return self._create_fallback_mask(frame)
    
    def _create_fallback_mask(self, frame: np.ndarray) -> np.ndarray:
        """
        Create a simple fallback mask when MatAnyone fails
        """
        h, w = frame.shape[:2]
        fallback_mask = np.zeros((h, w), dtype=np.float32)
        
        # Create center rectangle mask
        margin_x, margin_y = int(w * 0.2), int(h * 0.15)
        fallback_mask[margin_y:h-margin_y, margin_x:w-margin_x] = 1.0
        
        log_warning("⚠️ Using fallback mask due to MatAnyone error", "MatAnyoneSegmenter")
        return fallback_mask
    
    def cleanup(self):
        """
        Clean up temporary files and resources
        """
        try:
            if self.temp_dir and self.temp_dir.exists():
                import shutil
                shutil.rmtree(self.temp_dir)
                log_info("🧹 MatAnyone temporary files cleaned up", "MatAnyoneSegmenter")
        except Exception as e:
            log_warning(f"⚠️ Failed to clean up MatAnyone temp files: {e}", "MatAnyoneSegmenter")
    
    def __del__(self):
        """Cleanup on destruction"""
        self.cleanup()
