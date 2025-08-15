"""
Advanced Segmentation Models for MyAvatar Background Processing
Ported from Videotix with MyAvatar architecture integration
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
        """Cleanup model resources"""
        if hasattr(self, 'model') and self.model is not None:
            del self.model
            self.model = None
        
        if TORCH_AVAILABLE and torch.cuda.is_available():
            torch.cuda.empty_cache()

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
        
        # Quality-based parameters
        if model_quality == "low":
            self.downsample_ratio = 0.25
            self.batch_size = 1
        elif model_quality == "medium":
            self.downsample_ratio = 0.5
            self.batch_size = 1
        else:  # high
            self.downsample_ratio = 0.8
            self.batch_size = 1
    
    def initialize(self) -> bool:
        """
        Initialize RobustVideoMatting model
        
        Returns:
            True if successful, False otherwise
        """
        if not TORCH_AVAILABLE:
            log_error("PyTorch not available for RVM segmentation", "RVMSegmenter")
            return False
        
        start_time = time.time()
        
        try:
            log_info(f"Initializing RVM model: {self.model_name}", "RVMSegmenter")
            
            # Determine device
            if self.enable_gpu and torch.cuda.is_available():
                self.device = torch.device('cuda')
                gpu_name = torch.cuda.get_device_name(0)
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
                log_info(f"Using GPU: {gpu_name} ({gpu_memory:.1f} GB)", "RVMSegmenter")
            else:
                self.device = torch.device('cpu')
                log_info("Using CPU for RVM processing", "RVMSegmenter")
            
            # Load model from torch hub with error handling
            try:
                self.model = torch.hub.load("PeterL1n/RobustVideoMatting", self.model_name, trust_repo=True)
            except Exception as hub_error:
                log_error(f"Failed to load from torch hub: {hub_error}", "RVMSegmenter")
                # Try alternative loading method
                try:
                    log_info("Attempting local RVM model loading...", "RVMSegmenter")
                    # This would require pre-downloaded models
                    # For now, just raise the original error
                    raise hub_error
                except Exception:
                    return False
            
            # Move model to device and set to eval mode
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
            dummy_input = torch.randn(1, 3, 256, 256).to(self.device)
            with torch.no_grad():
                self.model(dummy_input, *self.rec, downsample_ratio=self.downsample_ratio)
            log_info("Model warmup completed", "RVMSegmenter")
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
                raise RuntimeError("RVM model not initialized")
        
        start_time = time.time()
        
        try:
            # Use instance downsample ratio if not overridden
            if downsample_ratio is None:
                downsample_ratio = self.downsample_ratio
            
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Convert to tensor and normalize
            src = torch.from_numpy(frame_rgb).float() / 255.0
            src = src.permute(2, 0, 1).unsqueeze(0)  # (1, 3, H, W)
            
            # Move to device
            src = src.to(self.device)
            
            # Forward pass with recurrent states for temporal consistency
            fgr, pha, *self.rec = self.model(src, *self.rec, downsample_ratio=downsample_ratio)
            
            # Convert alpha matte to numpy
            mask = pha[0].cpu().numpy()  # (H, W)
            mask = (mask * 255).astype(np.uint8)
            
            # Resize mask to original frame size if needed
            if mask.shape != frame.shape[:2]:
                mask = cv2.resize(mask, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_LINEAR)
            
            # Update performance tracking
            self.frame_count += 1
            self.total_time += time.time() - start_time
            
            return mask
            
        except Exception as e:
            log_error(f"Error in RVM segmentation: {e}", "RVMSegmenter", e)
            # Return empty mask on error
            return np.zeros(frame.shape[:2], dtype=np.uint8)

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
            self.model_selection = 1  # More accurate model
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
                raise RuntimeError("MediaPipe segmentation not initialized")
        
        start_time = time.time()
        
        try:
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Process frame
            results = self.selfie_segmentation.process(frame_rgb)
            
            # Convert segmentation mask
            if results.segmentation_mask is not None:
                mask = (results.segmentation_mask * 255).astype(np.uint8)
            else:
                mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            
            # Update performance tracking
            self.frame_count += 1
            self.total_time += time.time() - start_time
            
            return mask
            
        except Exception as e:
            log_error(f"Error in MediaPipe segmentation: {e}", "MediaPipeSegmenter", e)
            return np.zeros(frame.shape[:2], dtype=np.uint8)

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
        """Initialize fallback segmenter (always succeeds)"""
        start_time = time.time()
        log_info("Initializing OpenCV fallback segmentation", "FallbackSegmenter")
        
        self.is_initialized = True
        self.initialization_time = time.time() - start_time
        
        log_info(f"Fallback segmentation initialized in {self.initialization_time:.2f}s", "FallbackSegmenter")
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
            
            # Use adaptive thresholding
            thresh = cv2.adaptiveThreshold(
                blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY_INV, 11, 2
            )
            
            # Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Create mask from largest contours
            mask = np.zeros_like(gray)
            
            if contours:
                # Sort contours by area and take the largest ones
                contours = sorted(contours, key=cv2.contourArea, reverse=True)
                for i in range(min(self.contour_count, len(contours))):
                    if cv2.contourArea(contours[i]) > 1000:  # Minimum area threshold
                        cv2.drawContours(mask, [contours[i]], -1, 255, -1)
            
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
            # Try models in order of quality
            models_to_try = ["rvm", "mediapipe", "fallback"]
        else:
            models_to_try = [preferred_model, "fallback"]  # Always have fallback
        
        for model_type in models_to_try:
            try:
                if model_type == "rvm" and TORCH_AVAILABLE:
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
        model_type: "rvm", "mediapipe", "fallback", or "auto"
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
